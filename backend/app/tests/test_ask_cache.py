"""Ask-result cache tests (SRS §23, §38.8).

/ask has no auth wall and its LLM can carry a small provider quota (e.g.
Gemini's free-tier daily request cap), so a repeat identical question must not
spend a second Planner + Synthesizer round trip. Verifies the cache itself
(roundtrip, normalization, fail-open) and that a pipeline with caching enabled
actually skips the LLM on a repeat call.
"""

from __future__ import annotations

import json

from app.ask.cache import AskResultCache
from app.ask.pipeline import AskPipeline
from app.metadata.catalog import get_catalog
from app.planners import Planner
from app.synthesizers import LLMSynthesizer
from app.tests._ask_fakes import FakeLLM, build_fake_pipeline
from app.tests._fetch_fakes import build_full_orchestrator, make_context

_POINT = {"lat": 17.385, "lng": 78.486}
_PLAN_JSON = json.dumps(
    {
        "intent": "Terrain",
        "presets": ["terrain"],
        "planning_reason": "Terrain question needs the terrain preset.",
    }
)


class FakeRedis:
    """A dict-backed Redis double (mirrors the pattern in test_phase11_resilience)."""

    def __init__(self) -> None:
        self.store: dict[str, str] = {}

    async def get(self, key: str) -> str | None:
        return self.store.get(key)

    async def set(self, key: str, value: str, ex: int | None = None) -> None:
        self.store[key] = value


class BrokenRedis:
    """A Redis double that is down: every operation raises."""

    async def get(self, key: str) -> str | None:
        raise ConnectionError("redis unreachable")

    async def set(self, key: str, value: str, ex: int | None = None) -> None:
        raise ConnectionError("redis unreachable")


async def _sample_response():
    pipeline, _ = build_fake_pipeline(planner_json=_PLAN_JSON)
    return await pipeline.ask(**_POINT, question="Describe the terrain.")


# --------------------------------------------------------------------------- #
# AskResultCache unit tests                                                    #
# --------------------------------------------------------------------------- #
async def test_cache_roundtrip() -> None:
    response = await _sample_response()
    cache = AskResultCache(redis=FakeRedis())
    await cache.put(response, question="Describe the terrain.", **_POINT)
    hit = await cache.get(question="Describe the terrain.", **_POINT)
    assert hit is not None
    assert hit.answer == response.answer


async def test_cache_normalizes_question_text() -> None:
    # Retyping with different case/whitespace still hits the same entry.
    response = await _sample_response()
    cache = AskResultCache(redis=FakeRedis())
    await cache.put(response, question="Describe the terrain.", **_POINT)
    hit = await cache.get(question="  DESCRIBE   the terrain.  ", **_POINT)
    assert hit is not None


async def test_cache_miss_on_different_question() -> None:
    response = await _sample_response()
    cache = AskResultCache(redis=FakeRedis())
    await cache.put(response, question="Describe the terrain.", **_POINT)
    assert await cache.get(question="What is the elevation?", **_POINT) is None


async def test_cache_fails_open_when_redis_is_down() -> None:
    response = await _sample_response()
    cache = AskResultCache(redis=BrokenRedis())
    await cache.put(response, question="Describe the terrain.", **_POINT)  # must not raise
    assert await cache.get(question="Describe the terrain.", **_POINT) is None


# --------------------------------------------------------------------------- #
# Pipeline-level: a repeat identical question skips the LLM entirely           #
# --------------------------------------------------------------------------- #
async def test_repeat_question_skips_planner_and_synthesizer() -> None:
    catalog = get_catalog()
    client = FakeLLM(planner_json=_PLAN_JSON)
    pipeline = AskPipeline(
        planner=Planner(llm=client, catalog=catalog),
        orchestrator=build_full_orchestrator(make_context()),
        synthesizer=LLMSynthesizer(llm=client),
        catalog=catalog,
        cache=AskResultCache(redis=FakeRedis()),
    )

    first = await pipeline.ask(**_POINT, question="Describe the terrain.")
    calls_after_first = len(client.calls)
    assert calls_after_first == 2  # one Planner call, one Synthesizer call

    second = await pipeline.ask(**_POINT, question="Describe the terrain.")
    assert len(client.calls) == calls_after_first  # no new LLM calls
    assert second.answer == first.answer
