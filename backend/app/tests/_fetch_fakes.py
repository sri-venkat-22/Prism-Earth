"""Shared fakes for Phase 3 fetch tests (no live PostGIS or Earth Engine).

Mirrors the project's established injection style (see ``test_state_detection`` and
``test_gee_client``): connectors and state detection take collaborators that are
trivially faked, so the deterministic fetch spine is proven end-to-end without
external services.
"""

from __future__ import annotations

from app.citations.engine import CitationEngine
from app.connectors.administrative import AdministrativeConnector
from app.connectors.base import BaseConnector
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
from app.connectors.registry import ConnectorRegistry
from app.connectors.terrain import TerrainConnector, TerrainSample
from app.connectors.utilities import UtilitiesConnector, UtilitiesSample
from app.datasets.registry import get_dataset_registry
from app.fetchers.orchestrator import FetchOrchestrator
from app.metadata.catalog import get_catalog
from app.metadata.state_registry import get_state_registry
from app.provenance.generator import ProvenanceGenerator
from app.schemas.spatial import AdminUnit, SpatialContext

DEM_DATASET = "Copernicus DEM GLO-30"


def make_context(
    *,
    in_pilot_region: bool = True,
    state: str | None = "Telangana",
    district: str | None = "Hyderabad",
    mandal: str | None = None,
    village: str | None = None,
    municipality: str | None = None,
    ward: str | None = None,
    lat: float = 17.385,
    lng: float = 78.486,
) -> SpatialContext:
    """Build a resolved spatial context for a coordinate."""

    def _unit(name: str | None, id_: int) -> AdminUnit | None:
        return AdminUnit(id=id_, name=name) if name is not None else None

    return SpatialContext(
        lat=lat,
        lng=lng,
        in_pilot_region=in_pilot_region,
        state=_unit(state, 1),
        district=_unit(district, 2),
        mandal=_unit(mandal, 3),
        village=_unit(village, 4),
        municipality=_unit(municipality, 5),
        ward=_unit(ward, 6),
    )


class FakeStateDetection:
    """Returns a fixed spatial context (stands in for the PostGIS service)."""

    def __init__(self, context: SpatialContext) -> None:
        self._context = context

    async def resolve(self, lat: float, lng: float) -> SpatialContext:
        return self._context


class FakeTerrainSource:
    """A terrain source returning fixed values (stands in for Earth Engine)."""

    def __init__(
        self,
        *,
        elevation: float | None = 542.16,
        slope: float | None = 3.4,
        aspect: float | None = 180.0,
        dataset_name: str = DEM_DATASET,
    ) -> None:
        self._sample = TerrainSample(elevation=elevation, slope=slope, aspect=aspect)
        self._dataset_name = dataset_name

    @property
    def dataset_name(self) -> str:
        return self._dataset_name

    def sample(self, lat: float, lng: float) -> TerrainSample:
        return self._sample


class FailingTerrainSource:
    """A terrain source that fails at fetch time (SRS §15.16 partial failure)."""

    dataset_name = DEM_DATASET

    def sample(self, lat: float, lng: float) -> TerrainSample:
        raise RuntimeError("Earth Engine request timed out")


def build_orchestrator(
    *,
    context: SpatialContext | None = None,
    terrain_source: object | None = None,
    connectors: list[BaseConnector] | None = None,
) -> FetchOrchestrator:
    """Assemble a FetchOrchestrator from real catalog/registries + fake sources."""
    catalog = get_catalog()
    dataset_registry = get_dataset_registry()
    if connectors is None:
        source = terrain_source if terrain_source is not None else FakeTerrainSource()
        connectors = [TerrainConnector(source), AdministrativeConnector()]  # type: ignore[arg-type]
    return FetchOrchestrator(
        catalog=catalog,
        connectors=ConnectorRegistry(catalog, connectors),
        state_detection=FakeStateDetection(context or make_context()),
        state_registry=get_state_registry(),
        provenance=ProvenanceGenerator(catalog, dataset_registry),
        citations=CitationEngine(dataset_registry),
    )


# --------------------------------------------------------------------------- #
# Phase 4 fake sources — one per connector, returning fixed sample values so    #
# the whole nine-connector fleet is proven end-to-end without live services.    #
# --------------------------------------------------------------------------- #
class FakeClimateSource:
    def __init__(self, sample: ClimateSample | None = None) -> None:
        self._sample = sample or ClimateSample(
            annual_rainfall_mm=812.5,
            annual_temperature_c=27.3,
            aridity_index=0.42,
            evapotranspiration=640.0,
            wind_speed=3.1,
        )

    def sample(self, lat: float, lng: float) -> ClimateSample:
        return self._sample


class FakeLandCoverSource:
    def __init__(self, sample: LandCoverSample | None = None) -> None:
        self._sample = sample or LandCoverSample(
            ndvi_current=0.62,
            ndvi_historical=0.55,
            dominant_land_cover="cropland",
            tree_canopy_pct=12.5,
            wetland_presence=False,
        )

    def sample(self, lat: float, lng: float) -> LandCoverSample:
        return self._sample


class FakeHazardVectorSource:
    def __init__(self, sample: HazardVectorSample | None = None) -> None:
        self._sample = sample or HazardVectorSample(
            nearest_waterbody_distance_m=320.0,
            nearest_waterbody_name="Hussain Sagar",
        )

    async def sample(self, lat: float, lng: float) -> HazardVectorSample:
        return self._sample


class FakeHazardRasterSource:
    def __init__(self, sample: HazardRasterSample | None = None) -> None:
        self._sample = sample or HazardRasterSample(
            flood_hazard_class="moderate",
            within_flood_hazard_polygon=True,
            surface_water_permanence_pct=8.0,
            active_fire_count_10km_24h=0,
        )

    def sample(self, lat: float, lng: float) -> HazardRasterSample:
        return self._sample


class FakeInfrastructureSource:
    def __init__(self, sample: InfrastructureSample | None = None) -> None:
        self._sample = sample or InfrastructureSample(
            nearest_highway_distance=1500.0,
            nearest_railway_distance=2300.0,
        )

    async def sample(self, lat: float, lng: float) -> InfrastructureSample:
        return self._sample


class FakeUtilitiesSource:
    def __init__(self, sample: UtilitiesSample | None = None) -> None:
        self._sample = sample or UtilitiesSample(
            nearest_substation_distance=800.0,
            nearest_powerline_distance=1200.0,
        )

    async def sample(self, lat: float, lng: float) -> UtilitiesSample:
        return self._sample


class FakeCadastralSource:
    def __init__(self, record: ParcelRecord | None = None) -> None:
        self._record = record or ParcelRecord(
            parcel_id="HYD-KHB-001",
            survey_number="123/A",
            parcel_area=4500.0,
            parcel_geometry='{"type": "Polygon", "coordinates": []}',
            zoning="residential",
            ownership_category="private",
        )

    async def parcel_at(self, lat: float, lng: float) -> ParcelRecord:
        return self._record


class FakeBuildingsSource:
    def __init__(self, sample: BuildingSample | None = None) -> None:
        self._sample = sample or BuildingSample(
            building_present=True,
            building_footprint_area_m2=250.0,
            building_count_250m=42,
            nearest_building_distance_m=0.0,
            built_up_area_pct_1km=18.5,
        )

    def sample(self, lat: float, lng: float) -> BuildingSample:
        return self._sample


def build_all_fake_connectors() -> list[BaseConnector]:
    """The full Version-1 fleet (nine connectors) backed by fake sources."""
    return [
        TerrainConnector(FakeTerrainSource()),
        ClimateConnector(FakeClimateSource()),
        LandCoverConnector(FakeLandCoverSource()),
        NaturalHazardConnector(vector=FakeHazardVectorSource(), raster=FakeHazardRasterSource()),
        InfrastructureConnector(FakeInfrastructureSource()),
        UtilitiesConnector(FakeUtilitiesSource()),
        AdministrativeConnector(),
        CadastralConnector(FakeCadastralSource()),
        BuiltEnvironmentConnector(FakeBuildingsSource()),
    ]


def build_full_orchestrator(context: SpatialContext | None = None) -> FetchOrchestrator:
    """A FetchOrchestrator wired with all nine connectors (fake-backed)."""
    return build_orchestrator(context=context, connectors=build_all_fake_connectors())
