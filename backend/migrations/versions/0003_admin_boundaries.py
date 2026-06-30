"""Administrative boundary layers (SRS §20.4, §20.5, §24.4).

State → District → Mandal → Village plus Municipality → Ward, each with a
``MultiPolygon`` geometry in EPSG:4326 (SRS §20.6) and a GiST index (SRS §20.5)
for point-in-polygon state detection (SRS §15.7).

Revision ID: 0003_admin_boundaries
Revises: 0002_metadata_registry
Create Date: 2026-06-29
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from geoalchemy2 import Geometry

revision = "0003_admin_boundaries"
down_revision = "0002_metadata_registry"
branch_labels = None
depends_on = None

_SCHEMA = "admin"


def _geom() -> sa.Column:
    # spatial_index=False: the GiST index is created explicitly below so its
    # name is deterministic and not duplicated by GeoAlchemy2 (SRS §20.5).
    return sa.Column(
        "geom",
        Geometry(geometry_type="MULTIPOLYGON", srid=4326, spatial_index=False),
        nullable=False,
    )


def _gist(table: str) -> None:
    op.create_index(
        f"ix_{_SCHEMA}_{table}_geom",
        table,
        ["geom"],
        schema=_SCHEMA,
        postgresql_using="gist",
    )


def upgrade() -> None:
    op.create_table(
        "state",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("code", sa.String(8), nullable=False),
        sa.Column("name", sa.String(128), nullable=False, unique=True),
        _geom(),
        schema=_SCHEMA,
    )
    _gist("state")

    op.create_table(
        "district",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("name", sa.String(128), nullable=False),
        sa.Column("code", sa.String(16)),
        sa.Column(
            "state_id",
            sa.Integer(),
            sa.ForeignKey("admin.state.id", ondelete="CASCADE"),
            nullable=False,
        ),
        _geom(),
        schema=_SCHEMA,
    )
    op.create_index("ix_admin_district_state_id", "district", ["state_id"], schema=_SCHEMA)
    _gist("district")

    op.create_table(
        "mandal",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("name", sa.String(128), nullable=False),
        sa.Column("code", sa.String(16)),
        sa.Column(
            "district_id",
            sa.Integer(),
            sa.ForeignKey("admin.district.id", ondelete="CASCADE"),
            nullable=False,
        ),
        _geom(),
        schema=_SCHEMA,
    )
    op.create_index("ix_admin_mandal_district_id", "mandal", ["district_id"], schema=_SCHEMA)
    _gist("mandal")

    op.create_table(
        "village",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("name", sa.String(128), nullable=False),
        sa.Column("code", sa.String(16)),
        sa.Column(
            "mandal_id",
            sa.Integer(),
            sa.ForeignKey("admin.mandal.id", ondelete="CASCADE"),
            nullable=False,
        ),
        _geom(),
        schema=_SCHEMA,
    )
    op.create_index("ix_admin_village_mandal_id", "village", ["mandal_id"], schema=_SCHEMA)
    _gist("village")

    op.create_table(
        "municipality",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("name", sa.String(128), nullable=False),
        sa.Column(
            "district_id",
            sa.Integer(),
            sa.ForeignKey("admin.district.id", ondelete="CASCADE"),
            nullable=False,
        ),
        _geom(),
        schema=_SCHEMA,
    )
    op.create_index(
        "ix_admin_municipality_district_id", "municipality", ["district_id"], schema=_SCHEMA
    )
    _gist("municipality")

    op.create_table(
        "ward",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("name", sa.String(128), nullable=False),
        sa.Column(
            "municipality_id",
            sa.Integer(),
            sa.ForeignKey("admin.municipality.id", ondelete="CASCADE"),
            nullable=False,
        ),
        _geom(),
        schema=_SCHEMA,
    )
    op.create_index("ix_admin_ward_municipality_id", "ward", ["municipality_id"], schema=_SCHEMA)
    _gist("ward")


def downgrade() -> None:
    op.drop_table("ward", schema=_SCHEMA)
    op.drop_table("municipality", schema=_SCHEMA)
    op.drop_table("village", schema=_SCHEMA)
    op.drop_table("mandal", schema=_SCHEMA)
    op.drop_table("district", schema=_SCHEMA)
    op.drop_table("state", schema=_SCHEMA)
