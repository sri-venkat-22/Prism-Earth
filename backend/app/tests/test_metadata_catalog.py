"""Tests for the Metadata Catalog, presets, and lifecycle enforcement.

Covers SRS §11.4–11.7 and the Phase 1 Definition of Done for the catalog and
preset endpoints.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.core.errors import ValidationAppError
from app.metadata.catalog import (
    EXPECTED_LAYER_COUNT,
    EXPECTED_PRESET_COUNT,
    build_catalog,
)
from app.metadata.enums import Availability, Lifecycle


def test_catalog_has_seven_layers() -> None:
    catalog = build_catalog()
    assert len(catalog.layers()) == EXPECTED_LAYER_COUNT
    # Each layer owns a connector (SRS §11.5).
    assert all(layer.connector for layer in catalog.layers())


def test_catalog_has_fourteen_presets() -> None:
    assert len(build_catalog().presets()) == EXPECTED_PRESET_COUNT


def test_every_field_maps_to_a_layer_and_connector() -> None:
    catalog = build_catalog()
    for field in catalog.fields():
        assert catalog.has_layer(field.layer)
        assert catalog.connector_for_field(field.name)


def test_get_meta_fields_returns_catalog_with_flags(client: TestClient) -> None:
    """DoD: GET /meta/fields returns the catalog with lifecycle/availability."""
    resp = client.get("/api/v1/meta/fields")
    assert resp.status_code == 200
    body = resp.json()
    assert body["count"] == len(body["fields"]) > 0

    field = next(f for f in body["fields"] if f["name"] == "elevation")
    # SRS §13.6 field-object keys are present.
    for key in (
        "id",
        "name",
        "description",
        "layer",
        "lifecycle",
        "available",
        "nullable",
        "null_meaning",
        "source",
        "source_url",
        "unit",
        "datatype",
        "ttl",
        "interpretation_hint",
        "presets",
    ):
        assert key in field
    assert field["available"] is True
    assert field["lifecycle"] == "stable"
    assert field["connector"] == "terrain_connector"


def test_get_meta_layers_returns_seven(client: TestClient) -> None:
    resp = client.get("/api/v1/meta/layers")
    assert resp.status_code == 200
    body = resp.json()
    assert body["count"] == EXPECTED_LAYER_COUNT
    ids = [layer["id"] for layer in body["layers"]]
    assert ids == [
        "terrain",
        "climate",
        "land_cover",
        "natural_hazard",
        "infrastructure",
        "administrative",
        "cadastral",
    ]


def test_get_meta_presets_expand_to_valid_fields(client: TestClient) -> None:
    """DoD: GET /meta/presets returns 14 presets expanding to valid fields."""
    catalog = build_catalog()
    resp = client.get("/api/v1/meta/presets")
    assert resp.status_code == 200
    body = resp.json()
    assert body["count"] == EXPECTED_PRESET_COUNT

    for preset in body["presets"]:
        assert preset["fields"], f"preset {preset['id']} has no fields"
        for field_name in preset["fields"]:
            assert catalog.has_field(field_name)
            # Presets never expand to planned fields (SRS §11.6).
            assert catalog.field(field_name).selectable


def test_named_presets_from_srs_present(client: TestClient) -> None:
    body = client.get("/api/v1/meta/presets").json()
    ids = {p["id"] for p in body["presets"]}
    # The three presets named verbatim in SRS §11.7.
    assert {"terrain", "flood_risk", "wildfire_underwrite"} <= ids


def test_region_gated_preset_supported_only_in_telangana(client: TestClient) -> None:
    body = client.get("/api/v1/meta/presets").json()
    presets = {p["id"]: p for p in body["presets"]}
    assert presets["cadastral_profile"]["supported_states"] == ["telangana"]
    # A fully-nationwide preset is supported everywhere.
    assert presets["climate_profile"]["supported_states"] == ["*"]


def test_planned_fields_are_not_selectable() -> None:
    """SRS §11.6: planned fields are defined but never selectable."""
    catalog = build_catalog()
    planned = catalog.planned_fields()
    assert planned, "expected some planned fields in the catalog"
    for field in planned:
        assert field.lifecycle is Lifecycle.PLANNED
        assert field.availability is Availability.PLANNED
        assert field.available is False
        assert catalog.is_selectable(field.name) is False


def test_assert_selectable_rejects_planned_and_unknown() -> None:
    catalog = build_catalog()
    planned_name = catalog.planned_fields()[0].name

    # Stable/beta fields are accepted.
    catalog.assert_selectable(["elevation", "ndvi_current"])

    with pytest.raises(ValidationAppError):
        catalog.assert_selectable(["elevation", planned_name])
    with pytest.raises(ValidationAppError):
        catalog.assert_selectable(["definitely_not_a_field"])


def test_field_presets_are_back_populated() -> None:
    catalog = build_catalog()
    elevation = catalog.field("elevation")
    assert "terrain" in elevation.presets
    # The back-populated mapping is consistent with the preset definitions.
    for preset in catalog.presets():
        for field_name in preset.fields:
            assert preset.id in catalog.field(field_name).presets


def test_fields_can_be_filtered_by_layer_and_lifecycle(client: TestClient) -> None:
    planned = client.get("/api/v1/meta/fields", params={"lifecycle": "planned"}).json()
    assert planned["count"] > 0
    assert all(f["lifecycle"] == "planned" for f in planned["fields"])

    cadastral = client.get("/api/v1/meta/fields", params={"layer": "cadastral"}).json()
    assert cadastral["count"] > 0
    assert all(f["layer"] == "cadastral" for f in cadastral["fields"])

    available = client.get("/api/v1/meta/fields", params={"available": "true"}).json()
    assert all(f["available"] is True for f in available["fields"])
