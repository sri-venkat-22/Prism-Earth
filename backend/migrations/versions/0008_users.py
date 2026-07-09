"""End-user accounts (SRS §13.20).

Adds ``metadata.user`` — email/password (or Google) accounts. A user's session
and issued API tokens reuse ``metadata.api_token`` with ``subject == user.id``,
so no session table is needed.

Revision ID: 0008_users
Revises: 0007_oauth_client_trust
Create Date: 2026-07-09
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0008_users"
down_revision = "0007_oauth_client_trust"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "user",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("email", sa.String(320), nullable=False, unique=True),
        sa.Column("password_hash", sa.String(255)),
        sa.Column("organization", sa.String(128)),
        sa.Column("google_sub", sa.String(64), unique=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        schema="metadata",
    )


def downgrade() -> None:
    op.drop_table("user", schema="metadata")
