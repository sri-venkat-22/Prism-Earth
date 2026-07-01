"""Synthesizer tests (SRS §6.5, §16.8, §38.8).

Proves the anti-fabrication guarantee: unavailable fields are marked explicitly
and never given a value, resolved values carry inline citations, and the LLM
synthesizer both guards against dropping unavailable fields and falls back to
the deterministic template on an empty model response.
"""

from __future__ import annotations

import pytest

from app.planners import ExecutionPlan
from app.synthesizers import LLMSynthesizer, TemplateSynthesizer
from app.tests._ask_fakes import FakeLLM
from app.tests._fetch_fakes import build_full_orchestrator, make_context

_POINT = {"lat": 17.385, "lng": 78.486}
# elevation/slope resolve via the fake terrain source; soil_drainage_class is
# owned by the terrain connector but not wired, so it comes back null.
_FIELDS = ["elevation", "slope", "soil_drainage_class"]
_PLAN = ExecutionPlan(intent="Terrain Analysis", fields=_FIELDS)


async def _fetch():
    orchestrator = build_full_orchestrator(make_context(state="Telangana", district="Hyderabad"))
    return await orchestrator.fetch(fields=_FIELDS, **_POINT)


async def test_template_marks_unavailable_and_cites_resolved() -> None:
    fetch = await _fetch()
    result = await TemplateSynthesizer().synthesize(
        question="Describe terrain", plan=_PLAN, fetch=fetch
    )

    # Unavailable field is surfaced explicitly, never fabricated.
    assert result.unavailable_fields == ["soil_drainage_class"]
    assert "soil drainage class" in result.answer.lower()
    assert "unavailable" in result.answer.lower()

    # Resolved values are cited inline (SRS §16.8).
    assert "Copernicus DEM GLO-30" in result.answer
    assert "[CIT-" in result.answer
    assert result.citations_used
    # Deterministic synthesizer names no model.
    assert result.model is None


async def test_template_does_not_invent_a_value_for_unavailable_field() -> None:
    fetch = await _fetch()
    result = await TemplateSynthesizer().synthesize(question="q", plan=_PLAN, fetch=fetch)
    # The unavailable field appears only in the "unavailable" clause — never with
    # a number or citation attached to it.
    for line in result.answer.splitlines():
        if "soil drainage" in line.lower():
            assert "[CIT-" not in line
            assert not any(ch.isdigit() for ch in line)


async def test_llm_synthesizer_guard_marks_unavailable_when_model_omits_it() -> None:
    fetch = await _fetch()
    # Model answer talks only about resolved data, ignoring the null field.
    llm = FakeLLM(
        synthesizer_text="The terrain elevation is 542.16 m [CIT-001], with gentle slope."
    )
    result = await LLMSynthesizer(llm=llm).synthesize(question="q", plan=_PLAN, fetch=fetch)

    assert result.unavailable_fields == ["soil_drainage_class"]
    # The guard appended an explicit unavailable note (SRS §38.8).
    assert "soil drainage class" in result.answer.lower()
    assert result.model == "fake-model"


async def test_llm_synthesizer_falls_back_to_template_on_empty_response() -> None:
    fetch = await _fetch()
    result = await LLMSynthesizer(llm=FakeLLM(synthesizer_text="   ")).synthesize(
        question="q", plan=_PLAN, fetch=fetch
    )
    assert result.answer.strip()
    assert "soil drainage class" in result.answer.lower()
    # Fallback is the deterministic template, which names no model.
    assert result.model is None


async def test_llm_synthesizer_only_reports_valid_citation_ids() -> None:
    fetch = await _fetch()
    result = await LLMSynthesizer(llm=FakeLLM(synthesizer_text="answer")).synthesize(
        question="q", plan=_PLAN, fetch=fetch
    )
    valid = {c.citation_id for c in fetch.citations}
    assert set(result.citations_used).issubset(valid)


@pytest.mark.parametrize("synth", [TemplateSynthesizer(), LLMSynthesizer(llm=FakeLLM())])
async def test_no_synthesizer_fabricates_a_null(synth) -> None:
    fetch = await _fetch()
    result = await synth.synthesize(question="q", plan=_PLAN, fetch=fetch)
    assert "soil_drainage_class" in result.unavailable_fields
