"""Phase 4 connector unit tests — Climate (§18.4), Land Cover (§18.5), Natural
Hazard (§18.6), Infrastructure & Utilities (§18.7), Cadastral (§18.9), and Built
Environment. Each connector is exercised with a fake source (no live PostGIS or
Earth Engine), proving the sample → standardized FieldResult mapping."""

from __future__ import annotations

import pytest

from app.connectors.base import Confidence, FetchContext, NullReason
from app.connectors.built_environment import BuildingSample, BuiltEnvironmentConnector
from app.connectors.cadastral import CadastralConnector, ParcelRecord
from app.connectors.climate import ClimateConnector, ClimateSample
from app.connectors.infrastructure import InfrastructureConnector, InfrastructureSample
from app.connectors.land_cover import LandCoverConnector, LandCoverSample
from app.connectors.natural_hazard import (
    HazardRasterSample,
    HazardVectorSample,
    NaturalHazardConnector,
)
from app.connectors.utilities import UtilitiesConnector, UtilitiesSample
from app.tests._fetch_fakes import (
    FakeBuildingsSource,
    FakeCadastralSource,
    FakeClimateSource,
    FakeHazardRasterSource,
    FakeHazardVectorSource,
    FakeInfrastructureSource,
    FakeLandCoverSource,
    FakeUtilitiesSource,
    make_context,
)


def _ctx(**kwargs: object) -> FetchContext:
    context = make_context(**kwargs)  # type: ignore[arg-type]
    return FetchContext(lat=context.lat, lng=context.lng, spatial=context)


# --------------------------------------------------------------------------- #
# Climate (§18.4)                                                             #
# --------------------------------------------------------------------------- #
async def test_climate_returns_values_and_correct_datasets() -> None:
    connector = ClimateConnector(FakeClimateSource())
    fields = ["annual_rainfall_mm", "annual_temperature_c", "aridity_index", "wind_speed"]
    results = {r.field: r for r in await connector.fetch(fields, _ctx())}

    assert results["annual_rainfall_mm"].value == pytest.approx(812.5)
    assert results["annual_rainfall_mm"].dataset == "TerraClimate"
    assert results["annual_rainfall_mm"].confidence is Confidence.HIGH
    # wind_speed cites ERA5, the exact producing dataset (SRS §16.4).
    assert results["wind_speed"].dataset == "ERA5"
    assert results["wind_speed"].null_reason is None


async def test_climate_nulls_when_no_coverage() -> None:
    connector = ClimateConnector(FakeClimateSource(ClimateSample()))
    (result,) = await connector.fetch(["annual_rainfall_mm"], _ctx())
    assert result.value is None
    assert result.null_reason is NullReason.OUTSIDE_COVERAGE


async def test_climate_rejects_unservable_field() -> None:
    connector = ClimateConnector(FakeClimateSource())
    with pytest.raises(ValueError):
        await connector.validate(["max_temperature_c"])


# --------------------------------------------------------------------------- #
# Land Cover (§18.5)                                                          #
# --------------------------------------------------------------------------- #
async def test_land_cover_returns_values() -> None:
    connector = LandCoverConnector(FakeLandCoverSource())
    fields = ["ndvi_current", "dominant_land_cover", "wetland_presence"]
    results = {r.field: r for r in await connector.fetch(fields, _ctx())}

    assert results["ndvi_current"].value == pytest.approx(0.62)
    assert results["ndvi_current"].dataset == "Copernicus Sentinel-2"
    assert results["dominant_land_cover"].value == "cropland"
    assert results["dominant_land_cover"].dataset == "ESA WorldCover"
    assert results["wetland_presence"].value is False


async def test_land_cover_null_when_no_coverage() -> None:
    connector = LandCoverConnector(FakeLandCoverSource(LandCoverSample()))
    (result,) = await connector.fetch(["dominant_land_cover"], _ctx())
    assert result.value is None
    assert result.null_reason is NullReason.OUTSIDE_COVERAGE


# --------------------------------------------------------------------------- #
# Natural Hazard (§18.6) — hybrid vector + raster                             #
# --------------------------------------------------------------------------- #
async def test_natural_hazard_mixes_vector_and_raster() -> None:
    connector = NaturalHazardConnector(
        vector=FakeHazardVectorSource(), raster=FakeHazardRasterSource()
    )
    fields = [
        "flood_hazard_class",
        "within_flood_hazard_polygon",
        "nearest_waterbody_distance_m",
        "surface_water_permanence_pct",
        "active_fire_count_10km_24h",
    ]
    results = {r.field: r for r in await connector.fetch(fields, _ctx())}

    assert results["flood_hazard_class"].value == "moderate"
    assert results["flood_hazard_class"].dataset == "JRC Global River Flood Hazard Maps"
    assert results["within_flood_hazard_polygon"].value is True
    assert results["nearest_waterbody_distance_m"].dataset == "OpenStreetMap"
    assert results["surface_water_permanence_pct"].dataset == "JRC Global Surface Water"
    assert results["active_fire_count_10km_24h"].value == 0
    assert results["active_fire_count_10km_24h"].dataset == "VIIRS Active Fires (VNP14A1)"


async def test_natural_hazard_null_outside_flood_zone() -> None:
    connector = NaturalHazardConnector(
        vector=FakeHazardVectorSource(HazardVectorSample()),
        raster=FakeHazardRasterSource(HazardRasterSample()),
    )
    results = {
        r.field: r
        for r in await connector.fetch(
            ["flood_hazard_class", "within_flood_hazard_polygon"], _ctx()
        )
    }
    # No GloFAS inundation at any return period → class is a typed null, but
    # membership is a definite False (not null) — both raster-sourced now.
    assert results["flood_hazard_class"].value is None
    assert results["flood_hazard_class"].null_reason is NullReason.OUTSIDE_COVERAGE
    assert results["within_flood_hazard_polygon"].value is False


# --------------------------------------------------------------------------- #
# Infrastructure & Utilities (§18.7)                                          #
# --------------------------------------------------------------------------- #
async def test_infrastructure_distances() -> None:
    connector = InfrastructureConnector(FakeInfrastructureSource())
    results = {
        r.field: r
        for r in await connector.fetch(
            ["nearest_highway_distance", "nearest_railway_distance"], _ctx()
        )
    }
    assert results["nearest_highway_distance"].value == pytest.approx(1500.0)
    assert results["nearest_highway_distance"].dataset == "OpenStreetMap"
    assert results["nearest_railway_distance"].confidence is Confidence.HIGH


async def test_infrastructure_null_when_absent() -> None:
    connector = InfrastructureConnector(FakeInfrastructureSource(InfrastructureSample()))
    (result,) = await connector.fetch(["nearest_highway_distance"], _ctx())
    assert result.value is None
    assert result.null_reason is NullReason.DATA_UNAVAILABLE


async def test_utilities_distances() -> None:
    connector = UtilitiesConnector(FakeUtilitiesSource())
    results = {
        r.field: r
        for r in await connector.fetch(
            ["nearest_substation_distance", "nearest_powerline_distance"], _ctx()
        )
    }
    assert results["nearest_substation_distance"].value == pytest.approx(800.0)
    assert results["nearest_powerline_distance"].dataset == "OpenStreetMap"


async def test_utilities_cannot_serve_telecom() -> None:
    """telecom_coverage is owned by the layer but not wired — a validation guard."""
    connector = UtilitiesConnector(FakeUtilitiesSource(UtilitiesSample()))
    with pytest.raises(ValueError):
        await connector.validate(["telecom_coverage"])


# --------------------------------------------------------------------------- #
# Cadastral (§18.9, region-gated §24.3)                                       #
# --------------------------------------------------------------------------- #
async def test_cadastral_returns_parcel() -> None:
    connector = CadastralConnector(FakeCadastralSource())
    fields = ["parcel_id", "survey_number", "parcel_area", "zoning", "parcel_geometry"]
    results = {r.field: r for r in await connector.fetch(fields, _ctx())}

    assert results["parcel_id"].value == "HYD-KHB-001"
    assert results["parcel_id"].dataset == "Telangana Bhu Bharati"
    assert results["parcel_area"].value == pytest.approx(4500.0)
    assert results["parcel_geometry"].value.startswith("{")


async def test_cadastral_null_when_no_parcel() -> None:
    connector = CadastralConnector(FakeCadastralSource(ParcelRecord()))
    (result,) = await connector.fetch(["parcel_id"], _ctx())
    assert result.value is None
    assert result.null_reason is NullReason.DATA_UNAVAILABLE


# --------------------------------------------------------------------------- #
# Built Environment                                                           #
# --------------------------------------------------------------------------- #
async def test_built_environment_returns_stats() -> None:
    connector = BuiltEnvironmentConnector(FakeBuildingsSource())
    fields = ["building_present", "building_count_250m", "nearest_building_distance_m"]
    results = {r.field: r for r in await connector.fetch(fields, _ctx())}

    assert results["building_present"].value is True
    assert results["building_present"].dataset == "Google Open Buildings"
    assert results["building_count_250m"].value == 42
    assert results["nearest_building_distance_m"].value == pytest.approx(0.0)


async def test_built_environment_undeveloped_point() -> None:
    connector = BuiltEnvironmentConnector(
        FakeBuildingsSource(
            BuildingSample(building_present=False, building_count_250m=0, built_up_area_pct_1km=0.0)
        )
    )
    results = {
        r.field: r
        for r in await connector.fetch(["building_present", "building_footprint_area_m2"], _ctx())
    }
    assert results["building_present"].value is False
    # No containing footprint → area is a typed null.
    assert results["building_footprint_area_m2"].value is None
    assert results["building_footprint_area_m2"].null_reason is NullReason.OUTSIDE_COVERAGE
