"""POST /api/v1/fetch API tests (SRS §13.9–13.12).

Exercises the HTTP surface with the Fetch Orchestrator dependency overridden by
a fake-backed orchestrator, so no live PostGIS / Earth Engine is required.
"""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from app.api.v1.fetch import get_fetch_orchestrator
from app.main import app
from app.tests._fetch_fakes import (
    FailingTerrainSource,
    FakeTerrainSource,
    build_orchestrator,
    make_context,
)

_POINT = {"lat": 17.385, "lng": 78.486}


def _override(orchestrator) -> Iterator[TestClient]:
    app.dependency_overrides[get_fetch_orchestrator] = lambda: orchestrator
    try:
        with TestClient(app) as client:
            yield client
    finally:
        app.dependency_overrides.pop(get_fetch_orchestrator, None)


@pytest.fixture()
def healthy_client() -> Iterator[TestClient]:
    orch = build_orchestrator(
        context=make_context(state="Telangana", district="Hyderabad"),
        terrain_source=FakeTerrainSource(elevation=542.16, slope=3.4),
    )
    yield from _override(orch)


@pytest.fixture()
def failing_terrain_client() -> Iterator[TestClient]:
    orch = build_orchestrator(
        context=make_context(state="Telangana", district="Hyderabad"),
        terrain_source=FailingTerrainSource(),
    )
    yield from _override(orch)


def test_fetch_fields_end_to_end(healthy_client: TestClient) -> None:
    resp = healthy_client.post(
        "/api/v1/fetch", json={**_POINT, "fields": ["elevation", "slope", "district_name"]}
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["fields"]["elevation"]["value"] == pytest.approx(542.16)
    assert body["fields"]["district_name"]["value"] == "Hyderabad"
    assert body["provenance"]["elevation"]["source_url"]
    assert {c["dataset"] for c in body["citations"]} == {
        "Copernicus DEM GLO-30",
        "Survey of India Administrative Boundaries",
    }
    assert body["partial_failures"] == []


def test_fetch_preset_expands(healthy_client: TestClient) -> None:
    resp = healthy_client.post("/api/v1/fetch", json={**_POINT, "preset": "terrain"})
    assert resp.status_code == 200
    fields = resp.json()["fields"]
    assert {"elevation", "slope", "aspect", "terrain_roughness", "soil_drainage_class"} == set(
        fields
    )


def test_fetch_partial_failure_still_200(failing_terrain_client: TestClient) -> None:
    resp = failing_terrain_client.post(
        "/api/v1/fetch", json={**_POINT, "fields": ["elevation", "district_name"]}
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["fields"]["district_name"]["value"] == "Hyderabad"
    assert body["fields"]["elevation"]["value"] is None
    assert len(body["partial_failures"]) == 1
    assert body["partial_failures"][0]["connector"] == "terrain_connector"


def test_fetch_planned_field_rejected(healthy_client: TestClient) -> None:
    resp = healthy_client.post(
        "/api/v1/fetch", json={**_POINT, "fields": ["elevation", "seismic_zone"]}
    )
    assert resp.status_code == 422
    assert resp.json()["error"]["code"] == "VALIDATION_ERROR"


def test_fetch_requires_exactly_one_selector(healthy_client: TestClient) -> None:
    # Neither fields nor preset.
    resp = healthy_client.post("/api/v1/fetch", json={**_POINT})
    assert resp.status_code == 422
    # Both at once.
    resp = healthy_client.post(
        "/api/v1/fetch", json={**_POINT, "fields": ["elevation"], "preset": "terrain"}
    )
    assert resp.status_code == 422


def test_fetch_unknown_preset_404(healthy_client: TestClient) -> None:
    resp = healthy_client.post("/api/v1/fetch", json={**_POINT, "preset": "does_not_exist"})
    assert resp.status_code == 404
