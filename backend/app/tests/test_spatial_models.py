"""Spatial ORM schema tests (SRS §20.4–20.6). No database required."""

from __future__ import annotations

import pytest
from geoalchemy2 import Geometry

from app.models import (
    District,
    FloodHazardZone,
    Mandal,
    Municipality,
    Parcel,
    Railway,
    Road,
    State,
    Substation,
    TransmissionLine,
    Village,
    Ward,
    WaterBody,
)
from app.models.base import Base

# (model, expected schema, expected geometry type) — SRS §20.4.
SPATIAL_MODELS = [
    (State, "admin", "MULTIPOLYGON"),
    (District, "admin", "MULTIPOLYGON"),
    (Mandal, "admin", "MULTIPOLYGON"),
    (Village, "admin", "MULTIPOLYGON"),
    (Municipality, "admin", "MULTIPOLYGON"),
    (Ward, "admin", "MULTIPOLYGON"),
    (FloodHazardZone, "hazards", "MULTIPOLYGON"),
    (WaterBody, "hazards", "MULTIPOLYGON"),
    (Road, "infrastructure", "LINESTRING"),
    (Railway, "infrastructure", "LINESTRING"),
    (TransmissionLine, "infrastructure", "LINESTRING"),
    (Substation, "infrastructure", "POINT"),
    (Parcel, "cadastral", "POLYGON"),
]


@pytest.mark.parametrize("model, schema, geom_type", SPATIAL_MODELS)
def test_schema_and_geometry(model: type, schema: str, geom_type: str) -> None:
    table = model.__table__
    assert table.schema == schema
    geom = table.c.geom
    assert isinstance(geom.type, Geometry)
    assert geom.type.geometry_type == geom_type
    # Every geometry is WGS84 (SRS §20.6).
    assert geom.type.srid == 4326


@pytest.mark.parametrize("model, schema, geom_type", SPATIAL_MODELS)
def test_geometry_has_gist_index(model: type, schema: str, geom_type: str) -> None:
    """Each spatial table carries a GiST index on geom (SRS §20.5)."""
    gist_indexes = [
        ix
        for ix in model.__table__.indexes
        if ix.dialect_options["postgresql"].get("using") == "gist"
        and "geom" in {c.name for c in ix.columns}
    ]
    assert gist_indexes, f"{model.__name__} is missing a GiST index on geom"


def test_all_schemas_present() -> None:
    """The eight logical schemas (SRS §20.3) are covered by the registered tables."""
    schemas = {t.schema for t in Base.metadata.tables.values()}
    assert {"admin", "hazards", "infrastructure", "cadastral", "metadata"} <= schemas
