"""Fetch Orchestrator tests — the Phase 3 Definition of Done (SRS §15, §16, §17).

These prove the whole deterministic spine end-to-end with injected fakes (no live
PostGIS or Earth Engine), exactly as the DoD specifies.
"""

from __future__ import annotations

import pytest

from app.core.errors import ValidationAppError
from app.tests._fetch_fakes import (
    DEM_DATASET,
    FailingTerrainSource,
    FakeTerrainSource,
    build_orchestrator,
    make_context,
)

_SOI = "Survey of India Administrative Boundaries"
_TELANGANA_POINT = {"lat": 17.385, "lng": 78.486}


# --------------------------------------------------------------------------- #
# DoD #1 — elevation + slope + district_name with full provenance + citations #
# --------------------------------------------------------------------------- #
async def test_fetch_returns_values_provenance_and_citations() -> None:
    orch = build_orchestrator(
        context=make_context(state="Telangana", district="Hyderabad"),
        terrain_source=FakeTerrainSource(elevation=542.16, slope=3.4),
    )
    resp = await orch.fetch(
        **_TELANGANA_POINT, fields=["elevation", "slope", "district_name"], request_id="REQ-1"
    )

    # Real values.
    assert resp.fields["elevation"].value == pytest.approx(542.16)
    assert resp.fields["slope"].value == pytest.approx(3.4)
    assert resp.fields["district_name"].value == "Hyderabad"

    # Complete provenance per field (SRS §13.11, §17.3).
    for name in ("elevation", "slope", "district_name"):
        prov = resp.provenance[name]
        assert prov.dataset and prov.source_url and prov.retrieved_at
        assert prov.confidence is not None
        assert resp.fields[name].retrieved_at == resp.timestamp

    # Field object carries unit/datatype/dataset (SRS §13.10).
    assert resp.fields["elevation"].unit == "m"
    assert resp.fields["elevation"].dataset == DEM_DATASET

    # Deduplicated citations: DEM (elevation, slope) + SoI (district_name).
    datasets = {c.dataset: c for c in resp.citations}
    assert set(datasets) == {DEM_DATASET, _SOI}
    assert datasets[DEM_DATASET].field_names == ["elevation", "slope"]
    assert resp.partial_failures == []
    assert resp.summary.resolved == 3 and resp.summary.null == 0
    assert resp.location.state == "Telangana" and resp.location.district == "Hyderabad"


# --------------------------------------------------------------------------- #
# DoD #2 — preset expansion                                                   #
# --------------------------------------------------------------------------- #
async def test_preset_expands_and_returns_all_member_fields() -> None:
    orch = build_orchestrator(terrain_source=FakeTerrainSource())
    resp = await orch.fetch(**_TELANGANA_POINT, preset="terrain")

    # The terrain preset's five fields all appear in the response.
    expected = {"elevation", "slope", "aspect", "terrain_roughness", "soil_drainage_class"}
    assert set(resp.fields) == expected

    # The DEM-backed fields have real values; sources not yet wired return a
    # typed null with a recorded reason rather than failing the request.
    assert resp.fields["elevation"].value is not None
    assert resp.fields["slope"].value is not None
    assert resp.fields["soil_drainage_class"].value is None
    assert resp.provenance["soil_drainage_class"].reason == "data_unavailable"
    assert resp.partial_failures == []


# --------------------------------------------------------------------------- #
# DoD #3 — a failing connector never aborts the request (still 200)           #
# --------------------------------------------------------------------------- #
async def test_partial_failure_does_not_abort_request() -> None:
    orch = build_orchestrator(terrain_source=FailingTerrainSource())
    resp = await orch.fetch(**_TELANGANA_POINT, fields=["elevation", "slope", "district_name"])

    # The healthy connector still returns its value.
    assert resp.fields["district_name"].value == "Hyderabad"
    # The failed connector's fields are null with a runtime reason.
    assert resp.fields["elevation"].value is None
    assert resp.provenance["elevation"].reason == "connector_timeout"

    # One partial-failure entry for the terrain connector (SRS §13.12, §15.16).
    assert len(resp.partial_failures) == 1
    failure = resp.partial_failures[0]
    assert failure.connector == "terrain_connector"
    assert failure.layer == "terrain"
    assert failure.retryable is True
    # No citation is fabricated for the failed dataset.
    assert all(c.dataset == _SOI for c in resp.citations)


# --------------------------------------------------------------------------- #
# DoD #4 — planned / unknown fields are rejected (SRS §11.6, §38.4)           #
# --------------------------------------------------------------------------- #
async def test_planned_field_is_rejected() -> None:
    orch = build_orchestrator()
    with pytest.raises(ValidationAppError):
        # 'seismic_zone' is a planned field in the catalog.
        await orch.fetch(**_TELANGANA_POINT, fields=["elevation", "seismic_zone"])


async def test_unknown_field_is_rejected() -> None:
    orch = build_orchestrator()
    with pytest.raises(ValidationAppError):
        await orch.fetch(**_TELANGANA_POINT, fields=["not_a_real_field"])


# --------------------------------------------------------------------------- #
# Supporting behaviour                                                        #
# --------------------------------------------------------------------------- #
async def test_out_of_range_coordinate_rejected() -> None:
    orch = build_orchestrator()
    with pytest.raises(ValidationAppError):
        await orch.fetch(lat=99.0, lng=78.0, fields=["elevation"])


async def test_unrouted_field_becomes_partial_failure() -> None:
    """A valid field whose connector is not deployed returns null + a failure."""
    orch = build_orchestrator()
    resp = await orch.fetch(**_TELANGANA_POINT, fields=["elevation", "annual_rainfall_mm"])

    assert resp.fields["elevation"].value is not None
    assert resp.fields["annual_rainfall_mm"].value is None
    failures = {f.connector for f in resp.partial_failures}
    assert "climate_connector" in failures
    assert any(not f.retryable for f in resp.partial_failures)


async def test_region_gated_field_nulls_outside_enabling_state() -> None:
    """municipality_name is region-gated; outside Telangana it nulls cleanly."""
    orch = build_orchestrator(
        context=make_context(in_pilot_region=False, state=None, district=None)
    )
    resp = await orch.fetch(lat=19.07, lng=72.87, fields=["state_name", "municipality_name"])

    assert resp.fields["municipality_name"].value is None
    assert resp.provenance["municipality_name"].reason == "unsupported_state"
    assert resp.provenance["municipality_name"].null_meaning is not None
    # No connector ran for the gated field, so no partial failure.
    assert resp.partial_failures == []


async def test_region_gated_field_resolves_inside_enabling_state() -> None:
    orch = build_orchestrator(
        context=make_context(
            state="Telangana", district="Hyderabad", municipality="GHMC", ward="Ward 1"
        )
    )
    resp = await orch.fetch(**_TELANGANA_POINT, fields=["municipality_name", "ward_name"])
    assert resp.fields["municipality_name"].value == "GHMC"
    assert resp.fields["ward_name"].value == "Ward 1"


async def test_determinism_same_request_same_result() -> None:
    orch = build_orchestrator(terrain_source=FakeTerrainSource())
    fields = ["elevation", "slope", "district_name"]
    first = await orch.fetch(**_TELANGANA_POINT, fields=fields)
    second = await orch.fetch(**_TELANGANA_POINT, fields=fields)
    # Field values, provenance datasets, and citation ids are stable.
    assert [c.dataset for c in first.citations] == [c.dataset for c in second.citations]
    assert {n: f.value for n, f in first.fields.items()} == {
        n: f.value for n, f in second.fields.items()
    }
