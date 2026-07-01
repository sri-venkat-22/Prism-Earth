"""Planner tests (SRS §14).

Proves the anti-hallucination and determinism guarantees that Phase 5's DoD
depends on: the Planner selects only registered, selectable fields; it can never
pick a planned or undocumented field; and the same model output always yields
the same plan.
"""

from __future__ import annotations

import json

from app.metadata.catalog import get_catalog
from app.planners import Planner
from app.tests._ask_fakes import FakeLLM

_CATALOG = get_catalog()


async def _plan(planner_json: str):
    planner = Planner(llm=FakeLLM(planner_json=planner_json), catalog=_CATALOG)
    result = await planner.plan("test question", lat=17.385, lng=78.486)
    return result.plan


async def test_planner_expands_preset_in_catalog_order() -> None:
    plan = await _plan(
        json.dumps({"intent": "Renewable Energy Site Selection", "presets": ["solar_siting"]})
    )
    expected = _CATALOG.expand_preset("solar_siting")
    # Same set, canonicalized to catalog order.
    assert set(plan.fields) == set(expected)
    catalog_order = [f.name for f in _CATALOG.fields()]
    assert plan.fields == [f for f in catalog_order if f in set(expected)]
    assert plan.presets == ["solar_siting"]
    # Layers/connectors are derived, not model-chosen.
    assert plan.layers
    assert plan.connectors
    for name in plan.fields:
        assert _CATALOG.connector_for_field(name) in plan.connectors


async def test_planner_cannot_select_planned_or_undocumented_fields() -> None:
    # The model tries to select a planned field (seismic_zone) and an invented one.
    proposal = {
        "intent": "Terrain Analysis",
        "fields": ["elevation", "seismic_zone", "totally_made_up_field", "slope"],
    }
    plan = await _plan(json.dumps(proposal))

    assert plan.fields == ["elevation", "slope"]
    assert "seismic_zone" not in plan.fields
    assert "totally_made_up_field" not in plan.fields
    # Every selected field is provably selectable in the catalog.
    for name in plan.fields:
        assert _CATALOG.is_selectable(name)
    # The rejections are recorded for explainability (SRS §14.15, §14.17).
    joined = " ".join(plan.warnings)
    assert "seismic_zone" in joined
    assert "totally_made_up_field" in joined


async def test_planner_is_deterministic() -> None:
    proposal = json.dumps(
        {"intent": "Terrain Analysis", "fields": ["slope", "elevation", "aspect"]}
    )
    planner = Planner(llm=FakeLLM(planner_json=proposal), catalog=_CATALOG)
    first = (await planner.plan("q", lat=17.385, lng=78.486)).plan
    second = (await planner.plan("q", lat=17.385, lng=78.486)).plan
    assert first == second
    assert first.fields == second.fields


async def test_planner_field_order_is_canonical_not_proposal_order() -> None:
    # Two proposals with the same field set in different orders yield one plan.
    plan_a = await _plan(json.dumps({"fields": ["slope", "elevation"]}))
    plan_b = await _plan(json.dumps({"fields": ["elevation", "slope"]}))
    assert plan_a.fields == plan_b.fields


async def test_planner_drops_unknown_preset() -> None:
    plan = await _plan(json.dumps({"presets": ["does_not_exist", "terrain"]}))
    assert plan.presets == ["terrain"]
    assert set(plan.fields) == set(_CATALOG.expand_preset("terrain"))
    assert any("does_not_exist" in w for w in plan.warnings)


async def test_planner_unfulfillable_when_nothing_matches() -> None:
    plan = await _plan(json.dumps({"intent": "Unknown", "fields": ["no_such_field"]}))
    assert plan.fields == []
    assert plan.is_fulfillable is False
    assert "cannot be fulfilled" in plan.planning_reason.lower()


async def test_planner_tolerates_unparseable_model_output() -> None:
    plan = await _plan("I'm sorry, I cannot help with that.")
    assert plan.fields == []
    assert plan.is_fulfillable is False


async def test_planner_extracts_json_from_code_fence() -> None:
    fenced = '```json\n{"fields": ["elevation"]}\n```'
    plan = await _plan(fenced)
    assert plan.fields == ["elevation"]
