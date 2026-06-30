"""Metadata registry entities (SRS §22.3 Primary Entities).

Creates the core catalog/registry tables in the ``metadata`` schema:
Dataset, Field, Layer, Preset (+ preset_field), State, Connector, plus the
runtime Provenance, Citation, and RequestLog tables.

Revision ID: 0002_metadata_registry
Revises: 0001_ext_schemas
Create Date: 2026-06-29
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0002_metadata_registry"
down_revision = "0001_ext_schemas"
branch_labels = None
depends_on = None

_NOW = sa.text("now()")


def upgrade() -> None:
    op.create_table(
        "layer",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("name", sa.String(128), nullable=False),
        sa.Column("purpose", sa.Text(), nullable=False),
        sa.Column("connector", sa.String(64), nullable=False),
        schema="metadata",
    )
    op.create_table(
        "connector",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("name", sa.String(128), nullable=False),
        sa.Column("layer_id", sa.String(64), sa.ForeignKey("metadata.layer.id")),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        schema="metadata",
    )
    op.create_table(
        "dataset",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("name", sa.String(128), nullable=False, unique=True),
        sa.Column("provider", sa.String(128)),
        sa.Column("version", sa.String(64)),
        sa.Column("source_url", sa.Text()),
        sa.Column("purpose", sa.Text()),
        sa.Column("crs", sa.String(32), nullable=False, server_default="EPSG:4326"),
        sa.Column("ttl", sa.String(32)),
        sa.Column("spatial_resolution", sa.String(64)),
        sa.Column("temporal_resolution", sa.String(64)),
        sa.Column("update_frequency", sa.String(64)),
        sa.Column("license", sa.String(128)),
        schema="metadata",
    )
    op.create_table(
        "field",
        sa.Column("id", sa.String(128), primary_key=True),
        sa.Column("name", sa.String(128), nullable=False, unique=True),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("layer_id", sa.String(64), sa.ForeignKey("metadata.layer.id"), nullable=False),
        sa.Column("lifecycle", sa.String(16), nullable=False),
        sa.Column("availability", sa.String(16), nullable=False),
        sa.Column("nullable", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("null_meaning", sa.Text()),
        sa.Column("source", sa.String(128), nullable=False),
        sa.Column("source_url", sa.Text()),
        sa.Column("dataset_ttl", sa.String(32)),
        sa.Column("unit", sa.String(32)),
        sa.Column("datatype", sa.String(16), nullable=False),
        sa.Column("interpretation_hint", sa.Text(), nullable=False, server_default=""),
        schema="metadata",
    )
    op.create_table(
        "preset",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("name", sa.String(128), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        schema="metadata",
    )
    op.create_table(
        "preset_field",
        sa.Column("preset_id", sa.String(64), sa.ForeignKey("metadata.preset.id"), primary_key=True),
        sa.Column("field_id", sa.String(128), sa.ForeignKey("metadata.field.id"), primary_key=True),
        sa.Column("position", sa.Integer(), nullable=False, server_default="0"),
        schema="metadata",
    )
    op.create_table(
        "state",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("code", sa.String(8), nullable=False),
        sa.Column("name", sa.String(128), nullable=False),
        sa.Column("registered", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("lifecycle", sa.String(16), nullable=False, server_default="stable"),
        sa.Column("min_lat", sa.Float()),
        sa.Column("max_lat", sa.Float()),
        sa.Column("min_lng", sa.Float()),
        sa.Column("max_lng", sa.Float()),
        schema="metadata",
    )
    op.create_table(
        "provenance",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("dataset_name", sa.String(128), nullable=False),
        sa.Column("dataset_version", sa.String(64)),
        sa.Column("field_name", sa.String(128)),
        sa.Column("source_url", sa.Text()),
        sa.Column("retrieved_at", sa.DateTime(timezone=True), nullable=False, server_default=_NOW),
        sa.Column("processing_date", sa.DateTime(timezone=True)),
        sa.Column("spatial_resolution", sa.String(64)),
        sa.Column("confidence", sa.String(16)),
        sa.Column("ttl", sa.String(32)),
        sa.Column("null_meaning", sa.Text()),
        sa.Column("correlation_id", sa.String(64)),
        schema="metadata",
    )
    op.create_index(
        "ix_metadata_provenance_correlation_id",
        "provenance",
        ["correlation_id"],
        schema="metadata",
    )
    op.create_table(
        "citation",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "provenance_id",
            sa.Uuid(),
            sa.ForeignKey("metadata.provenance.id", ondelete="CASCADE"),
        ),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("dataset_name", sa.String(128), nullable=False),
        sa.Column("source_url", sa.Text()),
        sa.Column("accessed_at", sa.DateTime(timezone=True), nullable=False, server_default=_NOW),
        schema="metadata",
    )
    op.create_table(
        "request_log",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("correlation_id", sa.String(64), nullable=False),
        sa.Column("method", sa.String(8), nullable=False),
        sa.Column("path", sa.Text(), nullable=False),
        sa.Column("lat", sa.Float()),
        sa.Column("lng", sa.Float()),
        sa.Column("status_code", sa.Integer()),
        sa.Column("duration_ms", sa.Float()),
        sa.Column("field_count", sa.Integer()),
        sa.Column("cache_hit", sa.Boolean()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=_NOW),
        schema="metadata",
    )
    op.create_index(
        "ix_metadata_request_log_correlation_id",
        "request_log",
        ["correlation_id"],
        schema="metadata",
    )
    op.create_index(
        "ix_metadata_request_log_created_at",
        "request_log",
        ["created_at"],
        schema="metadata",
    )


def downgrade() -> None:
    op.drop_table("request_log", schema="metadata")
    op.drop_table("citation", schema="metadata")
    op.drop_table("provenance", schema="metadata")
    op.drop_table("state", schema="metadata")
    op.drop_table("preset_field", schema="metadata")
    op.drop_table("preset", schema="metadata")
    op.drop_table("field", schema="metadata")
    op.drop_table("dataset", schema="metadata")
    op.drop_table("connector", schema="metadata")
    op.drop_table("layer", schema="metadata")
