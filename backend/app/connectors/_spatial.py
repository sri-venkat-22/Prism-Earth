"""Shared PostGIS spatial queries for the ingest-backed connectors (SRS §20, §18).

The Infrastructure (§18.7), Utilities (§18.7), Natural-Hazard vector (§18.6),
and Cadastral (§18.9) connectors resolve values from the PostGIS spatial layers
seeded in Phase 2 (SRS §20.4). They share two query shapes — nearest-neighbour
distance (the SRS §18.7 ``<->`` KNN pattern) and point-in-polygon containment
(SRS §15.7) — centralized here so each connector's source stays declarative.

Distances are returned in **metres** (via a geography cast) and every geometry
is EPSG:4326 / WGS84 (SRS §20.6).

Concurrency: the Fetch Orchestrator fans connectors out with ``asyncio.gather``
(SRS §15.12), and a single :class:`AsyncSession` is not safe for concurrent use.
Each source therefore opens its **own** short-lived session per fetch from the
shared sessionmaker (:class:`PostgisQueryRunner`) rather than sharing the
request-scoped session used by State Detection.
"""

from __future__ import annotations

from typing import Any, NamedTuple

from sqlalchemy import ColumnElement, func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.database import get_sessionmaker

WGS84 = 4326


def wgs84_point(lat: float, lng: float) -> ColumnElement[Any]:
    """A WGS84 point expression (``ST_MakePoint`` takes x=lng, y=lat)."""
    return func.ST_SetSRID(func.ST_MakePoint(lng, lat), WGS84)


class Nearest(NamedTuple):
    """The nearest row and its geodesic distance to the query point (metres)."""

    distance_m: float
    row: Any


async def nearest(
    session: AsyncSession,
    model: type[Any],
    lat: float,
    lng: float,
    *,
    where: ColumnElement[bool] | None = None,
) -> Nearest | None:
    """Return the nearest ``model`` row to the point with its distance in metres.

    Ordering uses the index-assisted ``<->`` KNN operator (SRS §18.7); the
    distance is the accurate geography (metre) distance, not the planar proxy.
    ``None`` when the (optionally filtered) table has no rows.
    """
    point = wgs84_point(lat, lng)
    distance_m = func.ST_Distance(func.geography(model.geom), func.geography(point))
    stmt = select(model, distance_m.label("distance_m"))
    if where is not None:
        stmt = stmt.where(where)
    stmt = stmt.order_by(model.geom.op("<->")(point)).limit(1)
    row = (await session.execute(stmt)).first()
    if row is None:
        return None
    return Nearest(distance_m=float(row[1]), row=row[0])


async def containing_geojson(
    session: AsyncSession,
    model: type[Any],
    lat: float,
    lng: float,
) -> tuple[Any, str] | None:
    """Containing polygon plus its geometry serialized as GeoJSON (SRS §18.9)."""
    point = wgs84_point(lat, lng)
    stmt = (
        select(model, func.ST_AsGeoJSON(model.geom))
        .where(func.ST_Contains(model.geom, point))
        .limit(1)
    )
    row = (await session.execute(stmt)).first()
    if row is None:
        return None
    return row[0], row[1]


class PostgisQueryRunner:
    """Runs spatial queries in their own short-lived session (concurrency-safe).

    Subclasses (the connector data sources) call :meth:`_session` to obtain a
    fresh session per fetch. The sessionmaker is resolved lazily so constructing
    a source never touches the database — missing infrastructure surfaces as a
    connector-level partial failure at fetch time (SRS §15.16), exactly like the
    Terrain connector's lazily-created Earth Engine client.
    """

    def __init__(self, sessionmaker: async_sessionmaker[AsyncSession] | None = None) -> None:
        self._sessionmaker = sessionmaker

    def _factory(self) -> async_sessionmaker[AsyncSession]:
        if self._sessionmaker is None:
            self._sessionmaker = get_sessionmaker()
        return self._sessionmaker

    def _session(self) -> AsyncSession:
        """A new session; use as ``async with self._session() as session:``."""
        return self._factory()()
