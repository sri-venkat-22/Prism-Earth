"""Record each OAuth client's registration trust level (Phase 12-B).

Adds ``metadata.oauth_client.self_registered``: True for clients created via
open (unauthenticated) RFC 7591 dynamic registration — the low-trust MCP
surface, whose tokens carry the reduced self-registered rate budget — and
False for admin-registered, operator-vetted clients (SRS §13.20 trust model).

Existing rows default to True: every client registered before this migration
came through the open endpoint.

Revision ID: 0007_oauth_client_trust
Revises: 0006_drop_dead_flood_tables
Create Date: 2026-07-08
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0007_oauth_client_trust"
down_revision = "0006_drop_dead_flood_tables"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "oauth_client",
        sa.Column("self_registered", sa.Boolean(), nullable=False, server_default=sa.true()),
        schema="metadata",
    )


def downgrade() -> None:
    op.drop_column("oauth_client", "self_registered", schema="metadata")
