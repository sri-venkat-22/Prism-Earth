"""Ask-pipeline result caching (SRS §23, §38.8).

A read-through Redis cache over whole ``/ask`` answers, keyed by the exact
question text and a rounded coordinate. ``/ask`` has no auth wall (it's the
public demo surface) and the LLM behind it can carry a small provider quota
(e.g. Gemini's free-tier daily request cap), so a repeat identical question —
the example prompts on the Ask page chief among them — must not re-spend that
budget on a second Planner + Synthesizer round trip.

Failure policy: fail-open, mirroring :class:`app.fetchers.cache.FetchResultCache`
— Redis being unreachable turns every read into a miss and every write into a
no-op; the ask path never depends on the cache.
"""

from __future__ import annotations

import hashlib
import re

from app.core.logging import get_logger
from app.core.redis import get_redis
from app.schemas.ask import AskResponse

logger = get_logger(__name__)

_KEY_PREFIX = "terra:askcache"
_WHITESPACE = re.compile(r"\s+")


def _normalize(question: str) -> str:
    """Trim/lowercase/collapse whitespace so trivial retyping still hits (§23.2)."""
    return _WHITESPACE.sub(" ", question.strip().lower())


class AskResultCache:
    """Read-through Redis cache over :class:`AskResponse` (SRS §23)."""

    def __init__(
        self,
        *,
        redis: object | None = None,
        ttl_seconds: int = 3600,
        precision: int = 4,
    ) -> None:
        # Injectable for tests; resolved lazily so constructing the cache never
        # requires a live Redis (mirrors FetchResultCache).
        self._redis = redis
        self._ttl_seconds = ttl_seconds
        self._precision = precision

    def _client(self) -> object:
        if self._redis is None:
            self._redis = get_redis()
        return self._redis

    def key(self, *, question: str, lat: float, lng: float) -> str:
        p = self._precision
        digest = hashlib.sha256(_normalize(question).encode()).hexdigest()[:16]
        return f"{_KEY_PREFIX}:{lat:.{p}f},{lng:.{p}f}:{digest}"

    async def get(self, *, question: str, lat: float, lng: float) -> AskResponse | None:
        """Return the cached answer, or ``None`` on a miss (fail-open on error)."""
        key = self.key(question=question, lat=lat, lng=lng)
        try:
            payload = await self._client().get(key)  # type: ignore[attr-defined]
        except Exception as exc:  # fail-open: Redis down → a miss (§23.5)
            logger.warning("ask_cache.read_failed", error=str(exc))
            return None
        if payload is None:
            return None
        try:
            response = AskResponse.model_validate_json(payload)
        except Exception:  # corrupted entry → treat as a miss
            logger.warning("ask_cache.decode_failed")
            return None
        logger.info("ask_cache.hit", lat=lat, lng=lng)
        return response

    async def put(self, response: AskResponse, *, question: str, lat: float, lng: float) -> None:
        """Store ``response`` under its TTL (fail-open on error)."""
        if self._ttl_seconds <= 0:
            return
        key = self.key(question=question, lat=lat, lng=lng)
        try:
            await self._client().set(  # type: ignore[attr-defined]
                key, response.model_dump_json(), ex=self._ttl_seconds
            )
        except Exception as exc:  # fail-open: a write failure is only a lost hit
            logger.warning("ask_cache.write_failed", error=str(exc))
