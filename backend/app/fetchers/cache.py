"""Fetch-result caching (SRS §23).

A keyed read-through cache over connector field results, backed by the shared
Redis client (SRS §23.2). Without it every ``/fetch`` and ``/ask`` re-hits
Google Earth Engine — several blocking round trips per request — so GEE latency
and cost scale linearly with traffic (§23.1).

Key shape: ``terra:fetchcache:{connector}:{field}:{lat},{lng}`` with the
coordinate rounded to a configurable number of decimals (4 ≈ 11 m — inside the
resolution of every sampled raster, so nearby repeat lookups share an entry).

Each entry's TTL honors the field's catalog TTL, falling back to the dataset's
registry TTL — the same precedence the Provenance Generator publishes (§15.18),
so a cached value never outlives the freshness the platform claims for it.

Failure policy: **fail-open**. Redis being unreachable turns every read into a
miss and every write into a no-op; the fetch path never depends on the cache.
Only results a connector actually produced are written — the orchestrator's
synthesized failure nulls (``connector_timeout`` / ``dataset_unavailable``)
never enter the cache, so a transient outage is never pinned for a dataset's
multi-day TTL.
"""

from __future__ import annotations

import asyncio
import re

from app.connectors.base import FieldResult, NullReason
from app.core.logging import get_logger
from app.core.redis import get_redis
from app.datasets.registry import DatasetRegistry
from app.metadata.catalog import Catalog
from app.observability.metrics import record_cache_event
from app.utils.time import utcnow_iso

logger = get_logger(__name__)

_KEY_PREFIX = "terra:fetchcache"

#: Failure nulls must never be cached — they describe a moment, not the data.
_UNCACHEABLE_REASONS = frozenset({NullReason.CONNECTOR_TIMEOUT, NullReason.DATASET_UNAVAILABLE})

_TTL_PATTERN = re.compile(r"^\s*(\d+)\s*([smhdw])\s*$", re.IGNORECASE)
_UNIT_SECONDS = {"s": 1, "m": 60, "h": 3600, "d": 86_400, "w": 604_800}


def parse_ttl(ttl: str | None) -> int | None:
    """Parse a registry TTL descriptor (e.g. ``'30d'``, SRS §16.7) into seconds.

    Returns ``None`` for a missing or unparseable descriptor — the caller then
    skips caching rather than guessing a lifetime.
    """
    if ttl is None:
        return None
    match = _TTL_PATTERN.match(ttl)
    if match is None:
        logger.warning("fetch_cache.ttl_unparseable", ttl=ttl)
        return None
    return int(match.group(1)) * _UNIT_SECONDS[match.group(2).lower()]


class FetchResultCache:
    """Read-through Redis cache for connector :class:`FieldResult`s (SRS §23)."""

    def __init__(
        self,
        *,
        catalog: Catalog,
        datasets: DatasetRegistry,
        redis: object | None = None,
        precision: int = 4,
    ) -> None:
        self._catalog = catalog
        self._datasets = datasets
        # Injectable for tests; resolved lazily so constructing the cache never
        # requires a live Redis (mirrors the connectors' lazy clients).
        self._redis = redis
        self._precision = precision

    def _client(self) -> object:
        if self._redis is None:
            self._redis = get_redis()
        return self._redis

    def key(self, field_name: str, *, lat: float, lng: float) -> str:
        """The cache key for one field at a rounded coordinate (§23.2)."""
        connector = self._catalog.connector_for_field(field_name)
        p = self._precision
        return f"{_KEY_PREFIX}:{connector}:{field_name}:{lat:.{p}f},{lng:.{p}f}"

    def ttl_seconds(self, result: FieldResult) -> int | None:
        """The entry lifetime: catalog field TTL, else the dataset's (§15.18)."""
        field = self._catalog.field(result.field)
        meta = self._datasets.get(result.dataset)
        return parse_ttl(field.dataset_ttl or (meta.ttl if meta else None))

    async def get_many(
        self, fields: list[str], *, lat: float, lng: float
    ) -> dict[str, FieldResult]:
        """Look up ``fields`` at a coordinate; return only the hits (fail-open)."""
        if not fields:
            return {}
        keys = [self.key(name, lat=lat, lng=lng) for name in fields]
        try:
            payloads = await self._client().mget(keys)  # type: ignore[attr-defined]
        except Exception as exc:  # fail-open: Redis down → all misses (§23.5)
            logger.warning("fetch_cache.read_failed", error=str(exc))
            return {}

        hits: dict[str, FieldResult] = {}
        for name, payload in zip(fields, payloads, strict=True):
            if payload is not None:
                try:
                    hits[name] = FieldResult.model_validate_json(payload)
                except Exception:  # corrupted entry → treat as a miss
                    logger.warning("fetch_cache.decode_failed", field=name)
            record_cache_event("fetch_result", hit=name in hits)
        if hits:
            logger.info("fetch_cache.hit", fields=sorted(hits), lat=lat, lng=lng)
        return hits

    async def put_many(self, results: list[FieldResult], *, lat: float, lng: float) -> None:
        """Store connector-produced results under their dataset TTLs (fail-open)."""
        retrieved_at = utcnow_iso()
        writes: list[tuple[str, str, int]] = []
        for result in results:
            if result.null_reason in _UNCACHEABLE_REASONS:
                continue
            ttl = self.ttl_seconds(result)
            if ttl is None or ttl <= 0:
                continue  # no declared freshness window → never cache (§23)
            # Stamp the true retrieval time so a later cache hit reports it in
            # provenance instead of claiming a fresh retrieval (SRS §17.3).
            stamped = result.model_copy(
                update={"retrieved_at": result.retrieved_at or retrieved_at}
            )
            writes.append(
                (self.key(result.field, lat=lat, lng=lng), stamped.model_dump_json(), ttl)
            )
        if not writes:
            return
        try:
            client = self._client()
            await asyncio.gather(
                *(client.set(key, payload, ex=ttl) for key, payload, ttl in writes)  # type: ignore[attr-defined]
            )
        except Exception as exc:  # fail-open: a write failure is only a lost hit
            logger.warning("fetch_cache.write_failed", error=str(exc))
