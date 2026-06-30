"""Spatial ORM entities (SRS §20.4 Spatial Layers, §24.4 Spatial Data Seed).

Administrative boundaries (``admin``), natural-hazard layers (``hazards``),
infrastructure (``infrastructure``), and cadastral parcels (``cadastral``) — the
vector datasets PostGIS serves to the Fetch Engine (SRS §20.1).

Every geometry column is stored in **EPSG:4326 / WGS84** (SRS §20.6) and carries
an explicit **GiST** index (SRS §20.5) for point-in-polygon, nearest-neighbour,
and bounding-box queries. ``spatial_index=False`` is set on each column so the
index is created once — by name — in the migrations, never duplicated by
GeoAlchemy2's automatic index event.
"""

from __future__ import annotations

from geoalchemy2 import Geometry, WKBElement
from sqlalchemy import Float, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base

SRID = 4326


def _geom(kind: str) -> Mapped[WKBElement]:
    """A non-nullable WGS84 geometry column (index created in the migration)."""
    return mapped_column(
        Geometry(geometry_type=kind, srid=SRID, spatial_index=False),
        nullable=False,
    )


def _gist(table: str, schema: str) -> Index:
    """Explicit GiST index on the ``geom`` column (SRS §20.5)."""
    return Index(f"ix_{schema}_{table}_geom", "geom", postgresql_using="gist")


# --------------------------------------------------------------------------- #
# admin — administrative boundaries (SRS §20.4 Administrative)                 #
# --------------------------------------------------------------------------- #
class State(Base):
    """State boundary polygon (SRS §20.4, §24.4). Telangana in Version 1."""

    __tablename__ = "state"
    __table_args__ = (_gist("state", "admin"), {"schema": "admin"})

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    code: Mapped[str] = mapped_column(String(8), nullable=False)
    name: Mapped[str] = mapped_column(String(128), nullable=False, unique=True)
    geom: Mapped[WKBElement] = _geom("MULTIPOLYGON")


class District(Base):
    """District boundary polygon (SRS §20.4, §24.4)."""

    __tablename__ = "district"
    __table_args__ = (_gist("district", "admin"), {"schema": "admin"})

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    code: Mapped[str | None] = mapped_column(String(16))
    state_id: Mapped[int] = mapped_column(
        ForeignKey("admin.state.id", ondelete="CASCADE"), nullable=False, index=True
    )
    geom: Mapped[WKBElement] = _geom("MULTIPOLYGON")


class Mandal(Base):
    """Mandal / taluk boundary polygon (SRS §20.4, §24.4)."""

    __tablename__ = "mandal"
    __table_args__ = (_gist("mandal", "admin"), {"schema": "admin"})

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    code: Mapped[str | None] = mapped_column(String(16))
    district_id: Mapped[int] = mapped_column(
        ForeignKey("admin.district.id", ondelete="CASCADE"), nullable=False, index=True
    )
    geom: Mapped[WKBElement] = _geom("MULTIPOLYGON")


class Village(Base):
    """Village boundary polygon (SRS §20.4, §24.4)."""

    __tablename__ = "village"
    __table_args__ = (_gist("village", "admin"), {"schema": "admin"})

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    code: Mapped[str | None] = mapped_column(String(16))
    mandal_id: Mapped[int] = mapped_column(
        ForeignKey("admin.mandal.id", ondelete="CASCADE"), nullable=False, index=True
    )
    geom: Mapped[WKBElement] = _geom("MULTIPOLYGON")


class Municipality(Base):
    """Municipal / urban-local-body boundary (SRS §20.4, §24.3 region-gated)."""

    __tablename__ = "municipality"
    __table_args__ = (_gist("municipality", "admin"), {"schema": "admin"})

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    district_id: Mapped[int] = mapped_column(
        ForeignKey("admin.district.id", ondelete="CASCADE"), nullable=False, index=True
    )
    geom: Mapped[WKBElement] = _geom("MULTIPOLYGON")


class Ward(Base):
    """Municipal ward boundary (SRS §20.4, §24.3 region-gated)."""

    __tablename__ = "ward"
    __table_args__ = (_gist("ward", "admin"), {"schema": "admin"})

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    municipality_id: Mapped[int] = mapped_column(
        ForeignKey("admin.municipality.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    geom: Mapped[WKBElement] = _geom("MULTIPOLYGON")


# --------------------------------------------------------------------------- #
# hazards — flood & water layers (SRS §20.4 Natural Hazards, §24.4)            #
# --------------------------------------------------------------------------- #
class FloodHazardZone(Base):
    """Flood hazard zone polygon (SRS §20.4, §24.4)."""

    __tablename__ = "flood_hazard_zone"
    __table_args__ = (_gist("flood_hazard_zone", "hazards"), {"schema": "hazards"})

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    hazard_class: Mapped[str] = mapped_column(String(32), nullable=False)
    name: Mapped[str | None] = mapped_column(String(128))
    geom: Mapped[WKBElement] = _geom("MULTIPOLYGON")


class WaterBody(Base):
    """Water body polygon (SRS §20.4, §24.2 NRSC Waterbody Database)."""

    __tablename__ = "water_body"
    __table_args__ = (_gist("water_body", "hazards"), {"schema": "hazards"})

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str | None] = mapped_column(String(128))
    kind: Mapped[str | None] = mapped_column(String(32))
    geom: Mapped[WKBElement] = _geom("MULTIPOLYGON")


class HistoricalFlood(Base):
    """Historical flood extent polygon (SRS §20.4, §24.2 CWC Flood Data)."""

    __tablename__ = "historical_flood"
    __table_args__ = (_gist("historical_flood", "hazards"), {"schema": "hazards"})

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    event_name: Mapped[str | None] = mapped_column(String(128))
    year: Mapped[int | None] = mapped_column(Integer)
    geom: Mapped[WKBElement] = _geom("MULTIPOLYGON")


# --------------------------------------------------------------------------- #
# infrastructure — roads, rail, power (SRS §20.4 Infrastructure)              #
# --------------------------------------------------------------------------- #
class Road(Base):
    """Road centreline (SRS §20.4)."""

    __tablename__ = "road"
    __table_args__ = (_gist("road", "infrastructure"), {"schema": "infrastructure"})

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str | None] = mapped_column(String(128))
    road_class: Mapped[str | None] = mapped_column(String(32))
    geom: Mapped[WKBElement] = _geom("LINESTRING")


class Railway(Base):
    """Railway centreline (SRS §20.4)."""

    __tablename__ = "railway"
    __table_args__ = (_gist("railway", "infrastructure"), {"schema": "infrastructure"})

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str | None] = mapped_column(String(128))
    geom: Mapped[WKBElement] = _geom("LINESTRING")


class TransmissionLine(Base):
    """Power transmission line (SRS §20.4)."""

    __tablename__ = "transmission_line"
    __table_args__ = (
        _gist("transmission_line", "infrastructure"),
        {"schema": "infrastructure"},
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str | None] = mapped_column(String(128))
    voltage_kv: Mapped[int | None] = mapped_column(Integer)
    geom: Mapped[WKBElement] = _geom("LINESTRING")


class Substation(Base):
    """Electrical substation point (SRS §20.4)."""

    __tablename__ = "substation"
    __table_args__ = (
        _gist("substation", "infrastructure"),
        {"schema": "infrastructure"},
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str | None] = mapped_column(String(128))
    geom: Mapped[WKBElement] = _geom("POINT")


# --------------------------------------------------------------------------- #
# cadastral — survey parcels (SRS §20.4 Cadastral, §24.3/§24.4 pilot-only)     #
# --------------------------------------------------------------------------- #
class Parcel(Base):
    """Survey parcel polygon — available only in the pilot region (SRS §24.3)."""

    __tablename__ = "parcel"
    __table_args__ = (_gist("parcel", "cadastral"), {"schema": "cadastral"})

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    parcel_id: Mapped[str] = mapped_column(String(64), nullable=False)
    survey_number: Mapped[str | None] = mapped_column(String(64))
    zoning: Mapped[str | None] = mapped_column(String(64))
    ownership_category: Mapped[str | None] = mapped_column(String(64))
    area_sqm: Mapped[float | None] = mapped_column(Float)
    notes: Mapped[str | None] = mapped_column(Text)
    geom: Mapped[WKBElement] = _geom("POLYGON")
