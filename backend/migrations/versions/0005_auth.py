"""Authentication tables (SRS §13.20).

Adds ``metadata.api_token`` (hashed bearer tokens) and ``metadata.oauth_client``
(dynamically registered OAuth clients). Short-lived auth/device/refresh codes and
rate-limit counters are not persisted here — they live in the ephemeral store.

Revision ID: 0005_auth
Revises: 0004_spatial_layers
Create Date: 2026-07-02
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0005_auth"
down_revision = "0004_spatial_layers"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "api_token",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("token_hash", sa.String(64), nullable=False, unique=True),
        sa.Column("prefix", sa.String(16), nullable=False),
        sa.Column("name", sa.String(128), nullable=False),
        sa.Column("subject", sa.String(128), nullable=False),
        sa.Column("scopes", sa.Text(), nullable=False, server_default=""),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True)),
        sa.Column("last_used_at", sa.DateTime(timezone=True)),
        sa.Column("revoked", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("rate_limit_per_minute", sa.Integer()),
        schema="metadata",
    )
    op.create_index(
        "ix_metadata_api_token_subject",
        "api_token",
        ["subject"],
        schema="metadata",
    )
    op.create_table(
        "oauth_client",
        sa.Column("client_id", sa.String(64), primary_key=True),
        sa.Column("client_secret_hash", sa.String(64)),
        sa.Column("name", sa.String(128), nullable=False),
        sa.Column("redirect_uris", sa.Text(), nullable=False, server_default=""),
        sa.Column("grant_types", sa.Text(), nullable=False, server_default=""),
        sa.Column("scopes", sa.Text(), nullable=False, server_default=""),
        sa.Column(
            "token_endpoint_auth_method",
            sa.String(32),
            nullable=False,
            server_default="none",
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        schema="metadata",
    )


def downgrade() -> None:
    op.drop_table("oauth_client", schema="metadata")
    op.drop_index("ix_metadata_api_token_subject", table_name="api_token", schema="metadata")
    op.drop_table("api_token", schema="metadata")
