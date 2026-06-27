"""FastAPI application factory (SRS §11.3 Layer 1, §13).

Wires together configuration, structured logging, middleware, the standard
error handlers (SRS §28), and the versioned API router. No business logic is
implemented in Phase 0.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.router import api_v1_router
from app.config.loader import ConfigError, load_all_configs
from app.core.config import Settings, get_settings
from app.core.database import dispose_engine, init_engine
from app.core.errors import register_exception_handlers
from app.core.logging import configure_logging, get_logger
from app.core.redis import close_redis, init_redis
from app.middleware.correlation import CorrelationIdMiddleware

logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Initialize and tear down shared resources."""
    settings: Settings = app.state.settings
    init_engine(settings)
    init_redis(settings)
    try:
        load_all_configs()
    except ConfigError as exc:
        # Stub configs are expected in Phase 0; log but don't crash startup.
        logger.warning("config.load_failed", error=str(exc))
    logger.info("app.startup.complete", env=settings.app_env, version=settings.app_version)
    try:
        yield
    finally:
        await dispose_engine()
        await close_redis()
        logger.info("app.shutdown.complete")


def create_app(settings: Settings | None = None) -> FastAPI:
    """Build and configure the FastAPI application."""
    settings = settings or get_settings()
    configure_logging(settings)

    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        description=(
            "Prism Earth — deterministic, citation-backed geospatial intelligence. "
            "Phase 0 scaffold (no business logic)."
        ),
        openapi_url=f"{settings.api_v1_prefix}/openapi.json",
        docs_url="/docs",
        redoc_url="/redoc",
        lifespan=lifespan,
    )
    app.state.settings = settings

    # Middleware (outermost first).
    app.add_middleware(CorrelationIdMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    register_exception_handlers(app)
    app.include_router(api_v1_router, prefix=settings.api_v1_prefix)

    @app.get("/", tags=["meta"], summary="Service banner")
    async def root() -> dict[str, str]:
        return {
            "service": settings.app_name,
            "version": settings.app_version,
            "docs": "/docs",
            "health": f"{settings.api_v1_prefix}/health",
        }

    return app


app = create_app()
