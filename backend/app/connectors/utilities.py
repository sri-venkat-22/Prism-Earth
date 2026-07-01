"""Utilities Connector (SRS §18.7 — power/grid/telecom).

Nearest-neighbour distances to grid infrastructure over the OpenStreetMap
extract seeded into PostGIS (SRS §20.4): ``nearest_substation_distance`` and
``nearest_powerline_distance``, both via the ``<->`` KNN query (SRS §18.7).

``telecom_coverage`` (TRAI) and the region-gated ``electricity_distribution_company``
/ ``industrial_tariff`` are owned by this layer but not yet servable — no TRAI /
DISCOM / TSERC source is wired — so the orchestrator returns them as typed nulls
(SRS §15.17). The connector depends on a :class:`UtilitiesSource` protocol so it
is unit-testable with a fake source.
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
from app.models.spatial import Substation, TransmissionLine

logger = get_logger(__name__)

_OSM = "OpenStreetMap"
_SERVABLE: frozenset[str] = frozenset({"nearest_substation_distance", "nearest_powerline_distance"})


class UtilitiesSample(BaseModel):
    """Distances (metres) to the nearest grid infrastructure."""

    model_config = ConfigDict(frozen=True)

    nearest_substation_distance: float | None = None
    nearest_powerline_distance: float | None = None


class UtilitiesSource(Protocol):
    """A point source of utility distances (implemented by PostGIS)."""

    async def sample(self, lat: float, lng: float) -> UtilitiesSample: ...


class PostgisUtilitiesSource(PostgisQueryRunner):
    """PostGIS-backed :class:`UtilitiesSource` (SRS §20.4, §18.7)."""

    async def sample(self, lat: float, lng: float) -> UtilitiesSample:
        async with self._session() as session:
            substation = await nearest(session, Substation, lat, lng)
            powerline = await nearest(session, TransmissionLine, lat, lng)
        return UtilitiesSample(
            nearest_substation_distance=substation.distance_m if substation is not None else None,
            nearest_powerline_distance=powerline.distance_m if powerline is not None else None,
        )


class UtilitiesConnector(BaseConnector):
    """Grid-infrastructure distances from PostGIS (SRS §18.7)."""

    name = "utilities_connector"
    layer = Layer.UTILITIES

    def __init__(self, source: UtilitiesSource) -> None:
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
