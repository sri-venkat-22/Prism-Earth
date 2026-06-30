"""PostGIS extensions and logical schemas (SRS §20.3, §20.6).

Creates the PostGIS extensions and the eight logical schemas that partition the
spatial database (SRS §20.3). This is the root migration for Phase 2.

Revision ID: 0001_ext_schemas
Revises:
Create Date: 2026-06-29
"""

from __future__ import annotations

from alembic import op

revision = "0001_ext_schemas"
down_revision = None
branch_labels = None
depends_on = None

# Logical schemas (SRS §20.3 Database Structure).
SCHEMAS = (
    "admin",
    "terrain",
    "climate",
    "land_cover",
    "hazards",
    "infrastructure",
    "cadastral",
    "metadata",
)


def upgrade() -> None:
    # PostGIS + supporting extensions (SRS §20). Mirrors docker initdb so a
    # plain `alembic upgrade head` provisions a fresh database end-to-end.
    op.execute("CREATE EXTENSION IF NOT EXISTS postgis")
    op.execute("CREATE EXTENSION IF NOT EXISTS postgis_topology")
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")
    for schema in SCHEMAS:
        op.execute(f'CREATE SCHEMA IF NOT EXISTS "{schema}"')


def downgrade() -> None:
    for schema in reversed(SCHEMAS):
        op.execute(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE')
    # Drop topology before postgis (topology depends on postgis).
    op.execute("DROP EXTENSION IF EXISTS pg_trgm")
    op.execute("DROP EXTENSION IF EXISTS postgis_topology")
    op.execute("DROP EXTENSION IF EXISTS postgis")
