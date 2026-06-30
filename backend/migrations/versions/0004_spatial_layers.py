"""Hazard, infrastructure, and cadastral spatial layers (SRS §20.4, §24.4).

Natural-hazard polygons (flood zones, water bodies, historical floods),
infrastructure lines/points (roads, railways, transmission lines, substations),
and cadastral survey parcels. All geometries are EPSG:4326 (SRS §20.6) with a
GiST index (SRS §20.5).

Revision ID: 0004_spatial_layers
Revises: 0003_admin_boundaries
Create Date: 2026-06-29
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from geoalchemy2 import Geometry

revision = "0004_spatial_layers"
down_revision = "0003_admin_boundaries"
branch_labels = None
depends_on = None


def _geom(kind: str) -> sa.Column:
    return sa.Column(
        "geom",
        Geometry(geometry_type=kind, srid=4326, spatial_index=False),
        nullable=False,
    )


def _gist(table: str, schema: str) -> None:
    op.create_index(
        f"ix_{schema}_{table}_geom",
        table,
        ["geom"],
        schema=schema,
        postgresql_using="gist",
    )


def upgrade() -> None:
    # --- hazards (SRS §20.4 Natural Hazards) ------------------------------- #
    op.create_table(
        "flood_hazard_zone",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("hazard_class", sa.String(32), nullable=False),
        sa.Column("name", sa.String(128)),
        _geom("MULTIPOLYGON"),
        schema="hazards",
    )
    _gist("flood_hazard_zone", "hazards")

    op.create_table(
        "water_body",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("name", sa.String(128)),
        sa.Column("kind", sa.String(32)),
        _geom("MULTIPOLYGON"),
        schema="hazards",
    )
    _gist("water_body", "hazards")

    op.create_table(
        "historical_flood",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("event_name", sa.String(128)),
        sa.Column("year", sa.Integer()),
        _geom("MULTIPOLYGON"),
        schema="hazards",
    )
    _gist("historical_flood", "hazards")

    # --- infrastructure (SRS §20.4 Infrastructure) ------------------------- #
    op.create_table(
        "road",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("name", sa.String(128)),
        sa.Column("road_class", sa.String(32)),
        _geom("LINESTRING"),
        schema="infrastructure",
    )
    _gist("road", "infrastructure")

    op.create_table(
        "railway",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("name", sa.String(128)),
        _geom("LINESTRING"),
        schema="infrastructure",
    )
    _gist("railway", "infrastructure")

    op.create_table(
        "transmission_line",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("name", sa.String(128)),
        sa.Column("voltage_kv", sa.Integer()),
        _geom("LINESTRING"),
        schema="infrastructure",
    )
    _gist("transmission_line", "infrastructure")

    op.create_table(
        "substation",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("name", sa.String(128)),
        _geom("POINT"),
        schema="infrastructure",
    )
    _gist("substation", "infrastructure")

    # --- cadastral (SRS §20.4 Cadastral, pilot-region only §24.3) ---------- #
    op.create_table(
        "parcel",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("parcel_id", sa.String(64), nullable=False),
        sa.Column("survey_number", sa.String(64)),
        sa.Column("zoning", sa.String(64)),
        sa.Column("ownership_category", sa.String(64)),
        sa.Column("area_sqm", sa.Float()),
        sa.Column("notes", sa.Text()),
        _geom("POLYGON"),
        schema="cadastral",
    )
    _gist("parcel", "cadastral")


def downgrade() -> None:
    op.drop_table("parcel", schema="cadastral")
    op.drop_table("substation", schema="infrastructure")
    op.drop_table("transmission_line", schema="infrastructure")
    op.drop_table("railway", schema="infrastructure")
    op.drop_table("road", schema="infrastructure")
    op.drop_table("historical_flood", schema="hazards")
    op.drop_table("water_body", schema="hazards")
    op.drop_table("flood_hazard_zone", schema="hazards")
