"""SQLAlchemy declarative base (SRS §22).

Phase 0 defines no entities. The shared :class:`Base` and naming convention are
provided so Alembic autogeneration (Phase 2, SRS §22.3) produces consistent,
predictable constraint names.
"""

from __future__ import annotations

from sqlalchemy import MetaData
from sqlalchemy.orm import DeclarativeBase

# Deterministic constraint naming for clean Alembic migrations.
NAMING_CONVENTION = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    """Declarative base for all ORM models."""

    metadata = MetaData(naming_convention=NAMING_CONVENTION)
