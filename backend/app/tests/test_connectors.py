"""Connector tests — Terrain (§18.3) and Administrative (§18.8), plus the
catalog-driven Connector Registry (§18.10)."""

from __future__ import annotations

import pytest

from app.connectors.administrative import AdministrativeConnector
from app.connectors.base import Confidence, FetchContext, NullReason
from app.connectors.registry import ConnectorRegistry
from app.connectors.terrain import TerrainConnector
from app.metadata.catalog import get_catalog
from app.metadata.enums import Layer
from app.tests._fetch_fakes import DEM_DATASET, FakeTerrainSource, make_context


def _ctx(**kwargs: object) -> FetchContext:
    context = make_context(**kwargs)  # type: ignore[arg-type]
    return FetchContext(lat=context.lat, lng=context.lng, spatial=context)


# --------------------------------------------------------------------------- #
# Terrain connector (SRS §18.3)                                               #
# --------------------------------------------------------------------------- #
async def test_terrain_returns_standardized_results() -> None:
    connector = TerrainConnector(FakeTerrainSource(elevation=542.16, slope=3.4))
    results = {r.field: r for r in await connector.fetch(["elevation", "slope"], _ctx())}

    assert results["elevation"].value == pytest.approx(542.16)
    assert results["elevation"].dataset == DEM_DATASET
    assert results["elevation"].confidence is Confidence.HIGH
    assert results["slope"].confidence is Confidence.MEDIUM  # derived
    assert results["slope"].null_reason is None


async def test_terrain_null_when_no_coverage() -> None:
    connector = TerrainConnector(FakeTerrainSource(elevation=None))
    (result,) = await connector.fetch(["elevation"], _ctx())
    assert result.value is None
    assert result.null_reason is NullReason.OUTSIDE_COVERAGE


async def test_terrain_failure_propagates() -> None:
    class _Boom:
        dataset_name = DEM_DATASET

        def sample(self, lat: float, lng: float):  # noqa: ANN201
            raise RuntimeError("ee down")

    connector = TerrainConnector(_Boom())
    with pytest.raises(RuntimeError):
        await connector.fetch(["elevation"], _ctx())


async def test_terrain_rejects_unservable_field() -> None:
    connector = TerrainConnector(FakeTerrainSource())
    with pytest.raises(ValueError):
        await connector.validate(["groundwater_depth_m"])


# --------------------------------------------------------------------------- #
# Administrative connector (SRS §18.8)                                        #
# --------------------------------------------------------------------------- #
async def test_administrative_maps_hierarchy() -> None:
    connector = AdministrativeConnector()
    ctx = _ctx(state="Telangana", district="Hyderabad", mandal="Khairatabad")
    results = {
        r.field: r
        for r in await connector.fetch(["state_name", "district_name", "taluk_name"], ctx)
    }
    assert results["state_name"].value == "Telangana"
    assert results["district_name"].value == "Hyderabad"
    assert results["taluk_name"].value == "Khairatabad"
    assert results["state_name"].dataset == "Survey of India Administrative Boundaries"


async def test_administrative_null_outside_region() -> None:
    connector = AdministrativeConnector()
    ctx = _ctx(in_pilot_region=False, state=None, district=None)
    (result,) = await connector.fetch(["district_name"], ctx)
    assert result.value is None
    assert result.null_reason is NullReason.OUTSIDE_COVERAGE


# --------------------------------------------------------------------------- #
# Connector Registry (SRS §18.10)                                            #
# --------------------------------------------------------------------------- #
def _registry() -> ConnectorRegistry:
    catalog = get_catalog()
    return ConnectorRegistry(
        catalog, [TerrainConnector(FakeTerrainSource()), AdministrativeConnector()]
    )


def test_registry_routes_by_catalog() -> None:
    registry = _registry()
    grouped, unrouted = registry.route(["elevation", "slope", "district_name"])
    routed = {c.name: fields for c, fields in grouped.items()}
    assert routed["terrain_connector"] == ["elevation", "slope"]
    assert routed["administrative_connector"] == ["district_name"]
    assert unrouted == {}


def test_registry_reports_unrouted_fields() -> None:
    """A field whose connector is not deployed is reported, not crashed."""
    registry = _registry()
    grouped, unrouted = registry.route(["elevation", "annual_rainfall_mm"])
    assert unrouted == {"annual_rainfall_mm": "climate_connector"}
    assert list(grouped.values()) == [["elevation"]]


def test_registry_connector_for_field() -> None:
    registry = _registry()
    connector = registry.connector_for_field("elevation")
    assert connector is not None and connector.layer is Layer.TERRAIN
