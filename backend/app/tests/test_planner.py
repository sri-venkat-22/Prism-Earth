"""Planner tests (SRS §14, revised — deterministic broad planning).

The plan is a pure function of the catalog: every selectable field, in catalog
order, layers/connectors derived — no LLM involved, so /ask spends exactly one
model call (the Synthesizer's) and can never plan an unregistered field.
"""

from __future__ import annotations

from app.metadata.catalog import get_catalog
from app.planners import PLANNER_MODEL, Planner

_CATALOG = get_catalog()


async def _plan():
    planner = Planner(catalog=_CATALOG)
    return await planner.plan("test question", lat=17.385, lng=78.486)


async def test_plan_is_every_selectable_field_in_catalog_order() -> None:
    plan = (await _plan()).plan
    expected = [f.name for f in _CATALOG.fields() if f.selectable]
    assert plan.fields == expected
    assert plan.is_fulfillable


async def test_plan_never_contains_planned_or_undocumented_fields() -> None:
    plan = (await _plan()).plan
    for name in plan.fields:
        assert _CATALOG.is_selectable(name)
    # seismic_zone is registered but planned (not selectable) — provably absent.
    assert "seismic_zone" not in plan.fields


async def test_layers_and_connectors_are_derived_from_the_catalog() -> None:
    plan = (await _plan()).plan
    assert plan.layers
    assert plan.connectors
    for name in plan.fields:
        assert _CATALOG.connector_for_field(name) in plan.connectors
        assert _CATALOG.field(name).layer.value in plan.layers


async def test_planner_is_deterministic_and_free() -> None:
    first = await _plan()
    second = await _plan()
    assert first.plan == second.plan
    # No model, no tokens — planning costs nothing (the quota belongs to synthesis).
    assert first.model == PLANNER_MODEL
    assert first.prompt_tokens is None
    assert first.completion_tokens is None
