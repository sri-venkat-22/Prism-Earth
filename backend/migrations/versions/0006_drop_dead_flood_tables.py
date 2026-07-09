"""Drop the dead CWC/NRSC placeholder flood tables (Phase 10-C).

``hazards.flood_hazard_zone`` and ``hazards.historical_flood`` held hand-drawn
placeholder rectangles labelled "CWC" that no connector ever read: no open bulk
CWC/NRSC flood-hazard GIS layer exists for Telangana, and the flood fields
(``flood_hazard_class``, ``within_flood_hazard_polygon``) are served live from
JRC GloFAS via Earth Engine (``app/connectors/natural_hazard.py``). Removing
the tables keeps the schema aligned with the sources the runtime actually
queries (SRS §16.4). ``hazards.water_body`` (OpenStreetMap-seeded) remains.

Revision ID: 0006_drop_dead_flood_tables
Revises: 0005_auth
Create Date: 2026-07-08
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from geoalchemy2 import Geometry

revision = "0006_drop_dead_flood_tables"
down_revision = "0005_auth"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_index("ix_hazards_historical_flood_geom", "historical_flood", schema="hazards")
    op.drop_table("historical_flood", schema="hazards")
    op.drop_index("ix_hazards_flood_hazard_zone_geom", "flood_hazard_zone", schema="hazards")
    op.drop_table("flood_hazard_zone", schema="hazards")


def downgrade() -> None:
    # Recreates the (empty) tables exactly as migration 0004 defined them; the
    # placeholder fixture data is intentionally not restorable.
    op.create_table(
        "flood_hazard_zone",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("hazard_class", sa.String(32), nullable=False),
        sa.Column("name", sa.String(128)),
        sa.Column(
            "geom",
            Geometry(geometry_type="MULTIPOLYGON", srid=4326, spatial_index=False),
            nullable=False,
        ),
        schema="hazards",
    )
    op.create_index(
        "ix_hazards_flood_hazard_zone_geom",
        "flood_hazard_zone",
        ["geom"],
        schema="hazards",
        postgresql_using="gist",
    )
    op.create_table(
        "historical_flood",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("event_name", sa.String(128)),
        sa.Column("year", sa.Integer()),
        sa.Column(
            "geom",
            Geometry(geometry_type="MULTIPOLYGON", srid=4326, spatial_index=False),
            nullable=False,
        ),
        schema="hazards",
    )
    op.create_index(
        "ix_hazards_historical_flood_geom",
        "historical_flood",
        ["geom"],
        schema="hazards",
        postgresql_using="gist",
    )
