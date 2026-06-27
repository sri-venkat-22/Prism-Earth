"""Async SQLAlchemy engine and session management (SRS §9, §22).

The engine and sessionmaker are created lazily during application startup
(:func:`app.main.create_app` lifespan). No ORM models are defined in Phase 0 —
see :mod:`app.models.base` for the declarative base that future migrations and
entities (SRS §22.3) will build on.
"""

from __future__ import annotations

from collections.abc import AsyncIterator

from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.core.config import Settings, get_settings
from app.core.logging import get_logger

logger = get_logger(__name__)

_engine: AsyncEngine | None = None
_sessionmaker: async_sessionmaker[AsyncSession] | None = None


def init_engine(settings: Settings | None = None) -> AsyncEngine:
    """Create the global async engine and sessionmaker (idempotent)."""
    global _engine, _sessionmaker
    if _engine is None:
        settings = settings or get_settings()
        _engine = create_async_engine(
            settings.database_url,
            echo=settings.debug,
            pool_pre_ping=True,
            future=True,
        )
        _sessionmaker = async_sessionmaker(
            bind=_engine, expire_on_commit=False, autoflush=False
        )
        logger.info("database.engine.initialized", host=settings.postgres_host)
    return _engine


def get_engine() -> AsyncEngine:
    """Return the initialized engine, creating it on demand."""
    return _engine or init_engine()


def get_sessionmaker() -> async_sessionmaker[AsyncSession]:
    if _sessionmaker is None:
        init_engine()
    assert _sessionmaker is not None  # set by init_engine above
    return _sessionmaker


async def get_session() -> AsyncIterator[AsyncSession]:
    """FastAPI dependency yielding a transactional async session."""
    factory = get_sessionmaker()
    async with factory() as session:
        yield session


async def ping_database() -> bool:
    """Return ``True`` if a trivial query succeeds (readiness check, SRS §13.16)."""
    try:
        engine = get_engine()
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        return True
    except Exception as exc:  # report, never raise (health/readiness checks)
        logger.warning("database.ping.failed", error=str(exc))
        return False


async def dispose_engine() -> None:
    """Dispose the engine on application shutdown."""
    global _engine, _sessionmaker
    if _engine is not None:
        await _engine.dispose()
        _engine = None
        _sessionmaker = None
        logger.info("database.engine.disposed")
