"""Cadastral Connector (SRS §18.9, §24.3 — region-gated).

Parcel-level land records for the pilot region from Telangana Bhu Bharati
parcels seeded into PostGIS (SRS §20.4): ``parcel_id``, ``survey_number``,
``parcel_area``, ``parcel_geometry``, ``zoning``, and ``ownership_category``,
resolved by point-in-polygon over the containing parcel (SRS §15.7).

Bhu Bharati (bhubharati.telangana.gov.in) is the Telangana land-records system
that replaced Dharani in 2025; like its predecessor it offers only a manual,
single-parcel citizen lookup — no bulk export or API — so there is no path to
real bulk cadastral data without a government data-sharing agreement. This
connector therefore serves a small, manually curated dev fixture; production
deployments require that agreement.

Every cadastral field is ``REGION_GATED`` (SRS §24.3): outside Telangana the
Fetch Orchestrator returns them as ``unsupported_state`` nulls *before* routing,
so this connector only runs inside the enabling state. Inside the state a point
that falls in no mapped parcel returns a typed null (SRS §15.17). The connector
depends on a :class:`CadastralSource` protocol and is unit-testable with a fake.
"""

from __future__ import annotations

from typing import Protocol

from pydantic import BaseModel, ConfigDict

from app.connectors._spatial import PostgisQueryRunner, containing_geojson
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
from app.models.spatial import Parcel

logger = get_logger(__name__)

_BHU_BHARATI = "Telangana Bhu Bharati"
_SERVABLE: frozenset[str] = frozenset(
    {
        "parcel_id",
        "survey_number",
        "parcel_area",
        "parcel_geometry",
        "zoning",
        "ownership_category",
    }
)


class ParcelRecord(BaseModel):
    """The parcel containing a point, or empty when none is mapped there."""

    model_config = ConfigDict(frozen=True)

    parcel_id: str | None = None
    survey_number: str | None = None
    parcel_area: float | None = None
    parcel_geometry: str | None = None  # GeoJSON
    zoning: str | None = None
    ownership_category: str | None = None


class CadastralSource(Protocol):
    """A point source of the containing parcel (implemented by PostGIS)."""

    async def parcel_at(self, lat: float, lng: float) -> ParcelRecord: ...


class PostgisCadastralSource(PostgisQueryRunner):
    """PostGIS-backed :class:`CadastralSource` (SRS §20.4, §18.9)."""

    async def parcel_at(self, lat: float, lng: float) -> ParcelRecord:
        async with self._session() as session:
            found = await containing_geojson(session, Parcel, lat, lng)
        if found is None:
            return ParcelRecord()
        parcel, geojson = found
        return ParcelRecord(
            parcel_id=parcel.parcel_id,
            survey_number=parcel.survey_number,
            parcel_area=parcel.area_sqm,
            parcel_geometry=geojson,
            zoning=parcel.zoning,
            ownership_category=parcel.ownership_category,
        )


class CadastralConnector(BaseConnector):
    """Parcel-level land records from PostGIS (SRS §18.9, region-gated §24.3)."""

    name = "cadastral_connector"
    layer = Layer.CADASTRAL

    def __init__(self, source: CadastralSource) -> None:
        self._source = source

    def servable_fields(self) -> frozenset[str]:
        return _SERVABLE

    async def fetch(self, fields: list[str], context: FetchContext) -> list[FieldResult]:
        await self.validate(fields)
        record = await self._source.parcel_at(context.lat, context.lng)
        values = record.model_dump()

        results: list[FieldResult] = []
        for field in fields:
            value = values[field]
            results.append(
                FieldResult(
                    field=field,
                    value=value,
                    dataset=_BHU_BHARATI,
                    confidence=Confidence.HIGH,
                    null_reason=None if value is not None else NullReason.DATA_UNAVAILABLE,
                )
            )
        return results

    async def metadata(self) -> ConnectorMetadata:
        return ConnectorMetadata(
            name=self.name,
            layer=self.layer,
            datasets=(_BHU_BHARATI,),
            servable_fields=tuple(sorted(_SERVABLE)),
        )
