"""Infrastructure Connector (SRS §18.7 — transport & access).

Nearest-neighbour distances to transport infrastructure over the OpenStreetMap
extract seeded into PostGIS (SRS §20.4): ``nearest_highway_distance`` (nearest
national/state highway) and ``nearest_railway_distance``. Both use the
index-assisted ``<->`` KNN query (SRS §18.7) via the shared spatial helpers.

The connector depends on an :class:`InfrastructureSource` protocol, so it is
unit-testable with a fake source (no live PostGIS), mirroring the Terrain
connector's injectable design.
"""

from __future__ import annotations

from typing import Protocol

from pydantic import BaseModel, ConfigDict

from app.connectors._spatial import PostgisQueryRunner, nearest
from app.connectors.base import (
    BaseConnector,
    Confidence,
    ConnectorMetadata,
    FetchContext,
    FieldResult,
    NullReason,
)
from app.core.logging import get_logger
from app.metadata.enums import Layer
from app.models.spatial import Railway, Road

logger = get_logger(__name__)

_OSM = "OpenStreetMap"
_SERVABLE: frozenset[str] = frozenset({"nearest_highway_distance", "nearest_railway_distance"})

# OSM road classes that count as a highway for nearest_highway_distance.
_HIGHWAY_CLASSES = ("national_highway", "state_highway")


class InfrastructureSample(BaseModel):
    """Distances (metres) to the nearest transport infrastructure."""

    model_config = ConfigDict(frozen=True)

    nearest_highway_distance: float | None = None
    nearest_railway_distance: float | None = None


class InfrastructureSource(Protocol):
    """A point source of infrastructure distances (implemented by PostGIS)."""

    async def sample(self, lat: float, lng: float) -> InfrastructureSample: ...


class PostgisInfrastructureSource(PostgisQueryRunner):
    """PostGIS-backed :class:`InfrastructureSource` (SRS §20.4, §18.7)."""

    async def sample(self, lat: float, lng: float) -> InfrastructureSample:
        async with self._session() as session:
            highway = await nearest(
                session, Road, lat, lng, where=Road.road_class.in_(_HIGHWAY_CLASSES)
            )
            railway = await nearest(session, Railway, lat, lng)
        return InfrastructureSample(
            nearest_highway_distance=highway.distance_m if highway is not None else None,
            nearest_railway_distance=railway.distance_m if railway is not None else None,
        )


class InfrastructureConnector(BaseConnector):
    """Transport-infrastructure distances from PostGIS (SRS §18.7)."""

    name = "infrastructure_connector"
    layer = Layer.INFRASTRUCTURE

    def __init__(self, source: InfrastructureSource) -> None:
        self._source = source

    def servable_fields(self) -> frozenset[str]:
        return _SERVABLE

    async def fetch(self, fields: list[str], context: FetchContext) -> list[FieldResult]:
        await self.validate(fields)
        sample = await self._source.sample(context.lat, context.lng)
        values = sample.model_dump()

        results: list[FieldResult] = []
        for field in fields:
            value = values[field]
            results.append(
                FieldResult(
                    field=field,
                    value=value,
                    dataset=_OSM,
                    confidence=Confidence.HIGH,
                    null_reason=None if value is not None else NullReason.DATA_UNAVAILABLE,
                )
            )
        return results

    async def metadata(self) -> ConnectorMetadata:
        return ConnectorMetadata(
            name=self.name,
            layer=self.layer,
            datasets=(_OSM,),
            servable_fields=tuple(sorted(_SERVABLE)),
        )
