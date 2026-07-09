"""Phase 11 — hot-path resilience (audit 11-A/11-B/11-C/11-E).

Proves the SRS §23 fetch-result cache (read-through, TTL-honoring, fail-open),
the bounded-concurrency GEE offload, the per-connector fetch deadline, the
end-to-end /ask deadline, and catalog routing completeness — all with fakes,
no live Redis, PostGIS, Earth Engine, or LLM.
"""

from __future__ import annotations

import asyncio
import json
import threading
import time

import pytest

from app.connectors import build_default_connectors, get_default_connector_registry
from app.connectors._concurrency import run_blocking
from app.connectors.base import NullReason
from app.connectors.registry import ConnectorRegistry
from app.core.config import Settings
from app.core.errors import DeadlineExceededError
from app.datasets.registry import get_dataset_registry
from app.fetchers.cache import FetchResultCache, parse_ttl
from app.metadata.catalog import get_catalog
from app.synthesizers import SynthesisResult
from app.tests._ask_fakes import build_fake_pipeline
from app.tests._fetch_fakes import (
    FailingTerrainSource,
    FakeTerrainSource,
    build_orchestrator,
)

_POINT = {"lat": 17.385, "lng": 78.486}


# --------------------------------------------------------------------------- #
# Test doubles                                                                #
# --------------------------------------------------------------------------- #
class FakeRedis:
    """A dict-backed Redis double recording the TTL of every write."""

    def __init__(self) -> None:
        self.store: dict[str, str] = {}
        self.ttls: dict[str, int] = {}

    async def mget(self, keys: list[str]) -> list[str | None]:
        return [self.store.get(key) for key in keys]

    async def set(self, key: str, value: str, ex: int | None = None) -> None:
        self.store[key] = value
        if ex is not None:
            self.ttls[key] = ex


class BrokenRedis:
    """A Redis double that is down: every operation raises."""

    async def mget(self, keys: list[str]) -> list[str | None]:
        raise ConnectionError("redis unreachable")

    async def set(self, key: str, value: str, ex: int | None = None) -> None:
        raise ConnectionError("redis unreachable")


class CountingTerrainSource(FakeTerrainSource):
    """A terrain source counting upstream round trips (the 'GEE calls' proxy)."""

    def __init__(self) -> None:
        super().__init__()
        self.calls = 0

    def sample(self, lat: float, lng: float):  # noqa: ANN201 - protocol match
        self.calls += 1
        return super().sample(lat, lng)


class SlowTerrainSource(FakeTerrainSource):
    """A terrain source stuck on a slow upstream (blocking, like the GEE SDK)."""

    def sample(self, lat: float, lng: float):  # noqa: ANN201 - protocol match
        time.sleep(0.5)
        return super().sample(lat, lng)


class SlowSynthesizer:
    """A synthesizer standing in for a stalled LLM provider."""

    async def synthesize(self, *, question, plan, fetch) -> SynthesisResult:  # noqa: ANN001
        await asyncio.sleep(0.5)
        return SynthesisResult(answer="too late")


def _cache(redis: object) -> FetchResultCache:
    return FetchResultCache(catalog=get_catalog(), datasets=get_dataset_registry(), redis=redis)


# --------------------------------------------------------------------------- #
# 11-A · TTL descriptor parsing                                               #
# --------------------------------------------------------------------------- #
def test_parse_ttl_units() -> None:
    assert parse_ttl("30d") == 30 * 86_400
    assert parse_ttl("7D") == 7 * 86_400
    assert parse_ttl("12h") == 12 * 3600
    assert parse_ttl("45m") == 45 * 60
    assert parse_ttl("90s") == 90
    assert parse_ttl("2w") == 2 * 604_800


def test_parse_ttl_rejects_missing_or_malformed() -> None:
    assert parse_ttl(None) is None
    assert parse_ttl("") is None
    assert parse_ttl("soon") is None
    assert parse_ttl("30") is None  # unitless is ambiguous — never guess


# --------------------------------------------------------------------------- #
# 11-A · Read-through caching (SRS §23)                                       #
# --------------------------------------------------------------------------- #
async def test_repeated_fetch_is_served_from_cache_without_second_round_trip() -> None:
    """DoD: a repeated /fetch at the same coordinate never re-hits the source."""
    source = CountingTerrainSource()
    orchestrator = build_orchestrator(terrain_source=source, cache=_cache(FakeRedis()))

    first = await orchestrator.fetch(**_POINT, fields=["elevation", "slope"])
    second = await orchestrator.fetch(**_POINT, fields=["elevation", "slope"])

    assert source.calls == 1  # second fetch = cache hit, zero upstream calls
    assert second.fields["elevation"].value == first.fields["elevation"].value == 542.16
    # The cached response keeps full provenance + citations (SRS §17, §16).
    assert second.provenance["elevation"].dataset == first.provenance["elevation"].dataset
    assert second.citations


async def test_cache_entry_ttl_matches_published_provenance_ttl() -> None:
    """Entries expire on the dataset's declared TTL — never an invented one."""
    redis = FakeRedis()
    cache = _cache(redis)
    orchestrator = build_orchestrator(cache=cache)

    response = await orchestrator.fetch(**_POINT, fields=["elevation"])

    key = cache.key("elevation", **_POINT)
    assert key in redis.store
    published = response.provenance["elevation"].ttl  # e.g. "365d" (SRS §15.18)
    assert redis.ttls[key] == parse_ttl(published)
    # The stored payload round-trips to the exact field result.
    assert json.loads(redis.store[key])["value"] == 542.16


async def test_cache_hit_reports_original_retrieval_time_in_provenance() -> None:
    """A cache-served value never claims a fresh retrieval (SRS §17.3)."""
    from app.connectors.base import Confidence, FieldResult
    from app.tests._fetch_fakes import DEM_DATASET

    cache = _cache(FakeRedis())
    stamp = "2026-01-01T00:00:00Z"
    await cache.put_many(
        [
            FieldResult(
                field="elevation",
                value=500.0,
                dataset=DEM_DATASET,
                confidence=Confidence.HIGH,
                retrieved_at=stamp,
            )
        ],
        **_POINT,
    )

    orchestrator = build_orchestrator(cache=cache)
    response = await orchestrator.fetch(**_POINT, fields=["elevation"])

    assert response.fields["elevation"].value == 500.0
    assert response.provenance["elevation"].retrieved_at == stamp
    assert response.timestamp != stamp  # the response itself is current


async def test_nearby_coordinates_share_a_cache_entry() -> None:
    """Coordinates are rounded (4 dp ≈ 11 m) so GPS jitter still hits."""
    source = CountingTerrainSource()
    orchestrator = build_orchestrator(terrain_source=source, cache=_cache(FakeRedis()))

    await orchestrator.fetch(lat=17.38501, lng=78.48602, fields=["elevation"])
    await orchestrator.fetch(lat=17.38503, lng=78.48598, fields=["elevation"])

    assert source.calls == 1


async def test_cache_is_fail_open_when_redis_is_down() -> None:
    """Redis being unreachable degrades to misses; the fetch still resolves."""
    source = CountingTerrainSource()
    orchestrator = build_orchestrator(terrain_source=source, cache=_cache(BrokenRedis()))

    response = await orchestrator.fetch(**_POINT, fields=["elevation"])

    assert response.fields["elevation"].value == 542.16
    assert not response.partial_failures  # a cache outage is never a data failure
    assert source.calls == 1


async def test_connector_failure_nulls_are_never_cached() -> None:
    """A transient outage must not be pinned into Redis for a dataset's TTL."""
    redis = FakeRedis()
    orchestrator = build_orchestrator(terrain_source=FailingTerrainSource(), cache=_cache(redis))

    response = await orchestrator.fetch(**_POINT, fields=["elevation"])

    assert response.fields["elevation"].value is None
    assert response.provenance["elevation"].reason == NullReason.CONNECTOR_TIMEOUT.value
    assert not redis.store  # nothing cached from the failed connector


# --------------------------------------------------------------------------- #
# 11-B · Per-fetch deadline + bounded GEE concurrency                          #
# --------------------------------------------------------------------------- #
async def test_slow_connector_becomes_timeout_null_not_a_hung_request() -> None:
    """DoD: a slow connector yields CONNECTOR_TIMEOUT nulls; the rest resolve."""
    orchestrator = build_orchestrator(terrain_source=SlowTerrainSource(), deadline_seconds=0.05)

    started = time.perf_counter()
    response = await orchestrator.fetch(
        **_POINT, fields=["elevation", "state_name", "district_name"]
    )
    elapsed = time.perf_counter() - started

    assert elapsed < 0.45  # did not wait out the 0.5 s upstream stall
    assert response.fields["elevation"].value is None
    assert response.provenance["elevation"].reason == NullReason.CONNECTOR_TIMEOUT.value
    # The failure is isolated: administrative fields still resolve (SRS §15.16).
    assert response.fields["state_name"].value == "Telangana"
    [failure] = response.partial_failures
    assert failure.connector == "terrain_connector"
    assert failure.retryable is True
    assert "deadline" in failure.reason


async def test_run_blocking_bounds_concurrent_blocking_calls(monkeypatch) -> None:  # noqa: ANN001
    """At most ``gee_max_concurrency`` blocking calls run at once per loop."""
    from app.connectors import _concurrency

    monkeypatch.setattr(_concurrency, "get_settings", lambda: Settings(gee_max_concurrency=2))

    lock = threading.Lock()
    active = 0
    peak = 0

    def blocking_call() -> None:
        nonlocal active, peak
        with lock:
            active += 1
            peak = max(peak, active)
        time.sleep(0.05)
        with lock:
            active -= 1

    await asyncio.gather(*(run_blocking(blocking_call) for _ in range(8)))
    assert peak <= 2


# --------------------------------------------------------------------------- #
# 11-C · End-to-end /ask deadline                                             #
# --------------------------------------------------------------------------- #
_PLAN = json.dumps(
    {
        "intent": "Renewable Energy Site Selection",
        "presets": ["solar_siting"],
        "planning_reason": "Deadline test plan.",
    }
)


async def test_ask_deadline_fails_fast_with_504_semantics() -> None:
    """A stalled stage trips the overall deadline instead of hanging /ask."""
    pipeline, _ = build_fake_pipeline(
        planner_json=_PLAN, synthesizer=SlowSynthesizer(), deadline_seconds=0.05
    )
    started = time.perf_counter()
    with pytest.raises(DeadlineExceededError) as excinfo:
        await pipeline.ask(**_POINT, question="Is this suitable for solar?")
    assert time.perf_counter() - started < 0.45
    assert excinfo.value.status_code == 504
    assert excinfo.value.code == "DEADLINE_EXCEEDED"


async def test_ask_completes_within_deadline_unaffected() -> None:
    """A healthy pipeline under the same deadline answers normally."""
    pipeline, _ = build_fake_pipeline(planner_json=_PLAN, deadline_seconds=5.0)
    response = await pipeline.ask(**_POINT, question="Is this suitable for solar?")
    assert response.answer.strip()


# --------------------------------------------------------------------------- #
# 11-E · Catalog routing completeness (SRS §18.10, §11.5)                     #
# --------------------------------------------------------------------------- #
def test_every_active_field_routes_to_a_registered_connector() -> None:
    """No selectable field may be silently unroutable in the default fleet."""
    catalog = get_catalog()
    registry = ConnectorRegistry(catalog, build_default_connectors())

    selectable = [field.name for field in catalog.selectable_fields()]
    grouped, unrouted = registry.route(selectable)

    assert unrouted == {}, f"fields with no deployed connector: {sorted(unrouted)}"
    routed = {name for names in grouped.values() for name in names}
    assert routed == set(selectable)


def test_every_layer_connector_key_is_registered() -> None:
    """Each catalog layer's connector key resolves to a deployed connector."""
    catalog = get_catalog()
    registry = ConnectorRegistry(catalog, build_default_connectors())
    for layer in catalog.layers():
        assert registry.has(layer.connector), f"layer {layer.id} → {layer.connector} unregistered"


def test_default_connector_registry_is_memoized() -> None:
    """Health/fetch share one process-wide registry (audit 11-D)."""
    assert get_default_connector_registry() is get_default_connector_registry()
