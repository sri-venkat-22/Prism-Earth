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
from app.connectors.registry import ConnectorRegistry
from app.connectors.terrain import TerrainConnector, TerrainSample
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
