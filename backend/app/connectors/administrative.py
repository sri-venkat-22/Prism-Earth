"""Administrative Connector (SRS §18.8).

Returns the administrative hierarchy containing a coordinate — state, district,
taluk/mandal, village, and (region-gated) municipality and ward. The underlying
data path is PostGIS: the Fetch Orchestrator runs the point-in-polygon State
Detection query once (SRS §15.7) against the Survey of India boundaries and
shares the result on the :class:`FetchContext`. This connector maps that
resolved hierarchy onto catalog fields, so it holds no database session of its
own and is trivially testable.

Cited dataset: ``Survey of India Administrative Boundaries`` (Dataset Registry).
"""

from __future__ import annotations

from collections.abc import Callable

from app.connectors.base import (
    BaseConnector,
    Confidence,
    ConnectorMetadata,
    FetchContext,
    FieldResult,
    NullReason,
)
from app.metadata.enums import Layer
from app.schemas.spatial import AdminUnit, SpatialContext

# The administrative hierarchy is sourced from more than one authoritative
# boundary set, so each field cites the dataset that actually produced it
# (SRS §16.4 Accuracy): the rural hierarchy from Survey of India, urban local
# bodies from the SBM/MoHUA + GHMC ULB layer, and wards from GHMC.
_SOI = "Survey of India Administrative Boundaries"
_ULB = "Urban Local Body Boundaries (SBM-MoHUA / GHMC)"
_WARD = "GHMC Ward Boundaries"

# Field → (accessor on the spatial context, confidence, source dataset). State
# and district come straight from authoritative boundaries (high); finer units
# are coarser-sourced (medium).
_FIELDS: dict[str, tuple[Callable[[SpatialContext], AdminUnit | None], Confidence, str]] = {
    "state_name": (lambda c: c.state, Confidence.HIGH, _SOI),
    "district_name": (lambda c: c.district, Confidence.HIGH, _SOI),
    "taluk_name": (lambda c: c.mandal, Confidence.MEDIUM, _SOI),
    "village_name": (lambda c: c.village, Confidence.MEDIUM, _SOI),
    "municipality_name": (lambda c: c.municipality, Confidence.MEDIUM, _ULB),
    "ward_name": (lambda c: c.ward, Confidence.MEDIUM, _WARD),
}

_SERVABLE: frozenset[str] = frozenset(_FIELDS)
_DATASETS: tuple[str, ...] = (_SOI, _ULB, _WARD)


class AdministrativeConnector(BaseConnector):
    """Administrative hierarchy from PostGIS-resolved boundaries (SRS §18.8)."""

    name = "administrative_connector"
    layer = Layer.ADMINISTRATIVE

    def servable_fields(self) -> frozenset[str]:
        return _SERVABLE

    async def fetch(self, fields: list[str], context: FetchContext) -> list[FieldResult]:
        await self.validate(fields)
        results: list[FieldResult] = []
        for field in fields:
            accessor, confidence, dataset = _FIELDS[field]
            unit = accessor(context.spatial)
            value = unit.name if unit is not None else None
            results.append(
                FieldResult(
                    field=field,
                    value=value,
                    dataset=dataset,
                    confidence=confidence,
                    null_reason=None if value is not None else _null_reason(context.spatial),
                )
            )
        return results

    async def metadata(self) -> ConnectorMetadata:
        return ConnectorMetadata(
            name=self.name,
            layer=self.layer,
            datasets=_DATASETS,
            servable_fields=tuple(sorted(_SERVABLE)),
        )


def _null_reason(spatial: SpatialContext) -> NullReason:
    """A missing unit outside any seeded region is out-of-coverage; inside a
    resolved state it is simply unmapped at this point (SRS §15.17)."""
    return NullReason.OUTSIDE_COVERAGE if spatial.state is None else NullReason.DATA_UNAVAILABLE
