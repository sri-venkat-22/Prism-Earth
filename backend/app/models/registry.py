"""Metadata-registry ORM entities (SRS §22.3 Primary Entities).

These tables live in the ``metadata`` schema (SRS §20.3) and persist the core
catalog entities — ``Dataset, Field, Layer, Preset, State, Connector`` — plus
the runtime ``Provenance``, ``Citation``, and ``RequestLog`` records.

The Python Metadata Catalog (``app.metadata``) remains the single source of
truth (SRS §11.4); the catalog/registry tables here are a *mirror* populated by
the seed (``scripts/seed_telangana.py``) so downstream SQL joins and the
Provenance/Citation systems (SRS §16, §17) have normalized, referentially
consistent rows to work with. ``Provenance``, ``Citation``, and ``RequestLog``
are written at request time (SRS §15.15, §13.16).
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    Uuid,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base

_SCHEMA = {"schema": "metadata"}


class LayerRow(Base):
    """A domain layer (SRS §11.5, §22.3 Layer)."""

    __tablename__ = "layer"
    __table_args__ = _SCHEMA

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    purpose: Mapped[str] = mapped_column(Text, nullable=False)
    connector: Mapped[str] = mapped_column(String(64), nullable=False)


class ConnectorRow(Base):
    """A dataset connector (SRS §15.9–15.11, §22.3 Connector)."""

    __tablename__ = "connector"
    __table_args__ = _SCHEMA

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    layer_id: Mapped[str | None] = mapped_column(ForeignKey("metadata.layer.id"))
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)


class DatasetRow(Base):
    """A registered dataset (SRS §19.4, §19.11, §20.8, §22.3 Dataset)."""

    __tablename__ = "dataset"
    __table_args__ = _SCHEMA

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    name: Mapped[str] = mapped_column(String(128), nullable=False, unique=True)
    provider: Mapped[str | None] = mapped_column(String(128))
    version: Mapped[str | None] = mapped_column(String(64))
    source_url: Mapped[str | None] = mapped_column(Text)
    purpose: Mapped[str | None] = mapped_column(Text)
    crs: Mapped[str] = mapped_column(String(32), nullable=False, default="EPSG:4326")
    ttl: Mapped[str | None] = mapped_column(String(32))
    spatial_resolution: Mapped[str | None] = mapped_column(String(64))
    temporal_resolution: Mapped[str | None] = mapped_column(String(64))
    update_frequency: Mapped[str | None] = mapped_column(String(64))
    license: Mapped[str | None] = mapped_column(String(128))


class FieldRow(Base):
    """A catalog field (SRS §11.4, §22.3 Field). ``id`` mirrors ``name``."""

    __tablename__ = "field"
    __table_args__ = _SCHEMA

    id: Mapped[str] = mapped_column(String(128), primary_key=True)
    name: Mapped[str] = mapped_column(String(128), nullable=False, unique=True)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    layer_id: Mapped[str] = mapped_column(ForeignKey("metadata.layer.id"), nullable=False)
    lifecycle: Mapped[str] = mapped_column(String(16), nullable=False)
    availability: Mapped[str] = mapped_column(String(16), nullable=False)
    nullable: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    null_meaning: Mapped[str | None] = mapped_column(Text)
    source: Mapped[str] = mapped_column(String(128), nullable=False)
    source_url: Mapped[str | None] = mapped_column(Text)
    dataset_ttl: Mapped[str | None] = mapped_column(String(32))
    unit: Mapped[str | None] = mapped_column(String(32))
    datatype: Mapped[str] = mapped_column(String(16), nullable=False)
    interpretation_hint: Mapped[str] = mapped_column(Text, nullable=False, default="")


class PresetRow(Base):
    """A preset bundle (SRS §11.7, §22.3 Preset)."""

    __tablename__ = "preset"
    __table_args__ = _SCHEMA

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)


class PresetField(Base):
    """Ordered preset → field membership (SRS §11.7)."""

    __tablename__ = "preset_field"
    __table_args__ = _SCHEMA

    preset_id: Mapped[str] = mapped_column(ForeignKey("metadata.preset.id"), primary_key=True)
    field_id: Mapped[str] = mapped_column(ForeignKey("metadata.field.id"), primary_key=True)
    position: Mapped[int] = mapped_column(Integer, nullable=False, default=0)


class StateRow(Base):
    """A registered region (SRS §21.1, §22.3 State).

    The registry row (slug, code, lifecycle, bbox envelope). The precise
    administrative polygon lives in :class:`app.models.spatial.State`.
    """

    __tablename__ = "state"
    __table_args__ = _SCHEMA

    id: Mapped[str] = mapped_column(String(64), primary_key=True)  # slug
    code: Mapped[str] = mapped_column(String(8), nullable=False)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    registered: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    lifecycle: Mapped[str] = mapped_column(String(16), nullable=False, default="stable")
    min_lat: Mapped[float | None] = mapped_column(Float)
    max_lat: Mapped[float | None] = mapped_column(Float)
    min_lng: Mapped[float | None] = mapped_column(Float)
    max_lng: Mapped[float | None] = mapped_column(Float)


class Provenance(Base):
    """Per-field provenance record (SRS §15.15, §19.12, §22.3 Provenance)."""

    __tablename__ = "provenance"
    __table_args__ = _SCHEMA

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    dataset_name: Mapped[str] = mapped_column(String(128), nullable=False)
    dataset_version: Mapped[str | None] = mapped_column(String(64))
    field_name: Mapped[str | None] = mapped_column(String(128))
    source_url: Mapped[str | None] = mapped_column(Text)
    retrieved_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    processing_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    spatial_resolution: Mapped[str | None] = mapped_column(String(64))
    confidence: Mapped[str | None] = mapped_column(String(16))
    ttl: Mapped[str | None] = mapped_column(String(32))
    null_meaning: Mapped[str | None] = mapped_column(Text)
    correlation_id: Mapped[str | None] = mapped_column(String(64), index=True)


class Citation(Base):
    """A user-visible citation derived from provenance (SRS §16, §22.3 Citation)."""

    __tablename__ = "citation"
    __table_args__ = _SCHEMA

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    provenance_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("metadata.provenance.id", ondelete="CASCADE")
    )
    text: Mapped[str] = mapped_column(Text, nullable=False)
    dataset_name: Mapped[str] = mapped_column(String(128), nullable=False)
    source_url: Mapped[str | None] = mapped_column(Text)
    accessed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class RequestLog(Base):
    """Structured request audit trail (SRS §13.16, §15.19, §22.3 Request Log)."""

    __tablename__ = "request_log"
    __table_args__ = _SCHEMA

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    correlation_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    method: Mapped[str] = mapped_column(String(8), nullable=False)
    path: Mapped[str] = mapped_column(Text, nullable=False)
    lat: Mapped[float | None] = mapped_column(Float)
    lng: Mapped[float | None] = mapped_column(Float)
    status_code: Mapped[int | None] = mapped_column(Integer)
    duration_ms: Mapped[float | None] = mapped_column(Float)
    field_count: Mapped[int | None] = mapped_column(Integer)
    cache_hit: Mapped[bool | None] = mapped_column(Boolean)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), index=True
    )
