"""State Detection Service (SRS §15.7).

Resolves a coordinate to its administrative hierarchy
(India boundary → state → district → mandal/taluk → village, plus
municipality → ward) via PostGIS point-in-polygon queries against the seeded
``admin`` boundaries. This is the spatial backbone the Fetch Engine calls
(SRS §15.7) before routing connectors.

The precise PostGIS resolution here is authoritative; the Phase-1
:meth:`app.metadata.state_registry.StateRegistry.state_for_coordinate` bbox
check remains a cheap pre-filter for callers without a database session.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import ColumnElement, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import ValidationAppError
from app.core.logging import get_logger
from app.models.spatial import (
    District,
    Mandal,
    Municipality,
    State,
    Village,
    Ward,
)
from app.schemas.spatial import AdminUnit, SpatialContext

logger = get_logger(__name__)


def _unit(row: Any | None) -> AdminUnit | None:
    if row is None:
        return None
    return AdminUnit(id=row.id, name=row.name, code=getattr(row, "code", None))


class StateDetectionService:
    """Point-in-polygon administrative resolution against PostGIS (SRS §15.7)."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def resolve(self, lat: float, lng: float) -> SpatialContext:
        """Resolve ``(lat, lng)`` to its administrative hierarchy.

        Coordinates outside every seeded boundary return
        ``in_pilot_region=False`` with empty units (SRS §24.1) — not an error.
        Out-of-range coordinates raise a structured validation error (SRS §15.6).
        """
        _validate_coordinate(lat, lng)

        # WGS84 point (SRS §20.6); ST_MakePoint takes (x=lng, y=lat).
        point = func.ST_SetSRID(func.ST_MakePoint(lng, lat), 4326)

        state = await self._containing(State, point)
        if state is None:
            logger.info("state_detection.outside_region", lat=lat, lng=lng)
            return SpatialContext(lat=lat, lng=lng, in_pilot_region=False)

        district = await self._containing(District, point, District.state_id == state.id)
        mandal = village = None
        municipality = ward = None
        if district is not None:
            mandal = await self._containing(Mandal, point, Mandal.district_id == district.id)
            if mandal is not None:
                village = await self._containing(Village, point, Village.mandal_id == mandal.id)
            municipality = await self._containing(
                Municipality, point, Municipality.district_id == district.id
            )
            if municipality is not None:
                ward = await self._containing(Ward, point, Ward.municipality_id == municipality.id)

        context = SpatialContext(
            lat=lat,
            lng=lng,
            in_pilot_region=True,
            state=_unit(state),
            district=_unit(district),
            mandal=_unit(mandal),
            village=_unit(village),
            municipality=_unit(municipality),
            ward=_unit(ward),
        )
        logger.info(
            "state_detection.resolved",
            lat=lat,
            lng=lng,
            state=context.state.name if context.state else None,
            district=context.district.name if context.district else None,
            mandal=context.mandal.name if context.mandal else None,
            village=context.village.name if context.village else None,
        )
        return context

    async def _containing(
        self,
        model: type[Any],
        point: ColumnElement[Any],
        parent: ColumnElement[bool] | None = None,
    ) -> Any | None:
        """Return the first row whose geometry contains ``point`` (SRS §15.7)."""
        stmt = select(model).where(func.ST_Contains(model.geom, point))
        if parent is not None:
            stmt = stmt.where(parent)
        stmt = stmt.limit(1)
        result = await self._session.execute(stmt)
        return result.scalars().first()


def validate_coordinate(lat: float, lng: float) -> None:
    """Validate WGS84 latitude/longitude ranges (SRS §15.6, §13.18).

    Public so the Fetch Orchestrator can run coordinate validation as its first
    workflow step (SRS §15.4) independently of state detection.
    """
    if not (-90.0 <= lat <= 90.0):
        raise ValidationAppError(
            f"Latitude out of range: {lat}",
            details="Latitude must be within [-90, 90].",
        )
    if not (-180.0 <= lng <= 180.0):
        raise ValidationAppError(
            f"Longitude out of range: {lng}",
            details="Longitude must be within [-180, 180].",
        )


# Backwards-compatible internal alias.
_validate_coordinate = validate_coordinate


async def get_state_detection_service(session: AsyncSession) -> StateDetectionService:
    """FastAPI-style provider for the State Detection Service.

    Wire with ``Depends(get_session)`` in routers; kept dependency-light so the
    Fetch Engine (Phase 3) can construct it directly with any session.
    """
    return StateDetectionService(session)
