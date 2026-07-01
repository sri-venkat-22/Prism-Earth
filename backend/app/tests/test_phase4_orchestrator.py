"""Phase 4 Definition of Done — the full connector fleet, end to end.

Proves, with fake-backed connectors (no live PostGIS or Earth Engine):

1. Every preset in the catalog resolves for a Telangana point — servable fields
   carry real values, the rest are typed nulls, and no request aborts.
2. Region-gated cadastral fields null out cleanly outside Telangana (SRS §24.3).
3. Nationwide connectors still resolve outside the pilot region.
4. Catalog ↔ connector consistency: no field lacks an owning connector, and no
   connector serves fields outside its layer (SRS §11.5, §18.10).
"""

from __future__ import annotations

import pytest

from app.connectors import build_default_connectors
from app.metadata.catalog import get_catalog
from app.metadata.enums import Availability
from app.tests._fetch_fakes import (
    build_all_fake_connectors,
    build_full_orchestrator,
    make_context,
)

_TELANGANA_POINT = {"lat": 17.385, "lng": 78.486}
_OUTSIDE_POINT = {"lat": 19.07, "lng": 72.87}  # Mumbai — outside Telangana


def _full_telangana_context():
    """A fully-resolved Telangana hierarchy so administrative fields all populate."""
    return make_context(
        state="Telangana",
        district="Hyderabad",
        mandal="Khairatabad",
        village="Somajiguda",
        municipality="GHMC",
        ward="Ward 1",
    )


def _served_fields() -> set[str]:
    served: set[str] = set()
    for connector in build_all_fake_connectors():
        served |= connector.servable_fields()
    return served


# --------------------------------------------------------------------------- #
# DoD #1 — every preset resolves for a Telangana point                        #
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("preset_id", [p.id for p in get_catalog().presets()])
async def test_every_preset_resolves_for_telangana(preset_id: str) -> None:
    orch = build_full_orchestrator(context=_full_telangana_context())
    served = _served_fields()

    resp = await orch.fetch(**_TELANGANA_POINT, preset=preset_id)

    fields = get_catalog().expand_preset(preset_id)
    assert set(resp.fields) == set(fields)
    # Every servable field carries a value; every other resolves to a typed null
    # (owned-but-unwired) — nothing errors, in the pilot region every gated field
    # in these presets is enabled by Telangana.
    for name in fields:
        obj = resp.fields[name]
        if name in served:
            assert obj.value is not None, f"{preset_id}: expected value for {name}"
        else:
            assert obj.value is None, f"{preset_id}: expected null for {name}"
            assert resp.provenance[name].reason is not None
    # Every connector is deployed, so nothing is unrouted (SRS §15.16).
    assert resp.partial_failures == []
    # Resolved fields produced deterministic, registry-backed citations (SRS §16).
    assert resp.summary.resolved == sum(1 for f in fields if f in served)


async def test_solar_siting_returns_real_values() -> None:
    """A representative commercial preset: every field resolves with a value."""
    orch = build_full_orchestrator(context=_full_telangana_context())
    resp = await orch.fetch(**_TELANGANA_POINT, preset="solar_siting")

    assert resp.fields["elevation"].value is not None
    assert resp.fields["annual_temperature_c"].value is not None
    assert resp.fields["nearest_substation_distance"].value is not None
    assert resp.summary.null == 0
    assert {c.dataset for c in resp.citations} >= {"TerraClimate", "OpenStreetMap"}


# --------------------------------------------------------------------------- #
# DoD #2 — region-gated cadastral fields null out outside Telangana           #
# --------------------------------------------------------------------------- #
async def test_cadastral_nulls_outside_telangana() -> None:
    orch = build_full_orchestrator(
        context=make_context(in_pilot_region=False, state=None, district=None)
    )
    resp = await orch.fetch(**_OUTSIDE_POINT, preset="cadastral_profile")

    for name in ("parcel_id", "survey_number", "zoning"):
        assert resp.fields[name].value is None
        assert resp.provenance[name].reason == "unsupported_state"
        assert resp.provenance[name].null_meaning is not None
    # Gating happens before routing, so no connector ran and nothing failed.
    assert resp.partial_failures == []


async def test_cadastral_resolves_inside_telangana() -> None:
    orch = build_full_orchestrator(context=_full_telangana_context())
    resp = await orch.fetch(**_TELANGANA_POINT, preset="cadastral_profile")
    assert resp.fields["parcel_id"].value == "HYD-KHB-001"
    assert resp.fields["zoning"].value == "residential"
    assert {c.dataset for c in resp.citations} == {"Telangana Bhu Bharati"}


# --------------------------------------------------------------------------- #
# DoD #3 — nationwide connectors resolve anywhere                             #
# --------------------------------------------------------------------------- #
async def test_nationwide_fields_resolve_outside_telangana() -> None:
    orch = build_full_orchestrator(
        context=make_context(in_pilot_region=False, state=None, district=None)
    )
    resp = await orch.fetch(
        **_OUTSIDE_POINT,
        fields=["elevation", "annual_rainfall_mm", "ndvi_current", "building_present"],
    )
    assert resp.fields["annual_rainfall_mm"].value is not None
    assert resp.fields["ndvi_current"].value is not None
    assert resp.fields["building_present"].value is not None
    assert resp.partial_failures == []


# --------------------------------------------------------------------------- #
# DoD #4 — catalog ↔ connector consistency                                    #
# --------------------------------------------------------------------------- #
def test_every_field_has_a_registered_connector() -> None:
    catalog = get_catalog()
    connectors = {c.name for c in build_default_connectors()}
    for field in catalog.fields():
        assert catalog.connector_for_field(field.name) in connectors


def test_every_connector_serves_only_its_layer_fields() -> None:
    catalog = get_catalog()
    for connector in build_default_connectors():
        layer_fields = {f.name for f in catalog.fields() if f.layer is connector.layer}
        assert connector.servable_fields() <= layer_fields
        # The connector's registry key equals its layer's connector (SRS §11.5).
        assert catalog.connector_for_layer(connector.layer) == connector.name


def test_no_connector_without_owned_fields() -> None:
    """Every registered connector owns at least one catalog field (no orphans)."""
    catalog = get_catalog()
    for connector in build_default_connectors():
        layer_fields = [f for f in catalog.fields() if f.layer is connector.layer]
        assert layer_fields, f"{connector.name} owns no catalog fields"


def test_region_gated_cadastral_fields_are_gated() -> None:
    """Cadastral fields are REGION_GATED so the orchestrator nulls them outside TG."""
    catalog = get_catalog()
    cadastral = [f for f in catalog.fields() if f.layer.value == "cadastral" and f.selectable]
    assert cadastral
    assert all(f.availability is Availability.REGION_GATED for f in cadastral)
