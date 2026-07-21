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
from app.api.well_known import router as well_known_router
from app.auth.stores import InMemoryEphemeralStore, RedisEphemeralStore
from app.config.loader import ConfigError, load_all_configs
from app.core.config import Settings, get_settings
from app.core.database import dispose_engine, init_engine
from app.core.errors import register_exception_handlers
from app.core.logging import configure_logging, get_logger
from app.core.redis import close_redis, get_redis, init_redis
from app.metadata import get_catalog, get_state_registry, validate_catalog
from app.middleware.correlation import CorrelationIdMiddleware
from app.middleware.request_log import RequestLogMiddleware, RequestLogWriter
from app.middleware.security import SecurityHeadersMiddleware
from app.observability import MetricsMiddleware, configure_tracing, metrics_router

logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Initialize and tear down shared resources."""
    settings: Settings = app.state.settings

    # Fail fast on fatal misconfiguration — an open production API, a wildcard
    # CORS origin, or an invalid credentials pairing — before allocating any
    # resources or serving a single request (SRS §29, §13.20). The readiness
    # probe reports the same problems as defense in depth (§13.16).
    problems = settings.validate_runtime()
    if problems:
        for problem in problems:
            logger.error("config.invalid", detail=problem)
        raise RuntimeError("Refusing to start — fatal configuration errors: " + " ".join(problems))

    init_engine(settings)
    init_redis(settings)
    try:
        load_all_configs()
    except ConfigError as exc:
        # Stub configs are expected in Phase 0; log but don't crash startup.
        logger.warning("config.load_failed", error=str(exc))

    # Build and validate the Metadata Catalog + State Registry (SRS §11.4–11.9).
    # The catalog is the single source of truth; a misbuilt catalog must not
    # serve traffic, so validation failures fail startup fast.
    catalog = get_catalog()
    registry = get_state_registry()
    report = validate_catalog(catalog, registry)
    for warning in report.warnings:
        logger.warning("catalog.validation.warning", detail=warning)
    report.raise_for_status()
    logger.info(
        "catalog.validated",
        fields=report.stats.fields,
        layers=report.stats.layers,
        presets=report.stats.presets,
        states=registry.slugs(),
    )
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
            "Deterministic, citation-backed geospatial intelligence for India "
            "(SRS §1, §13). Public metadata discovery via `/meta/*`; deterministic "
            "retrieval via `POST /fetch`; natural-language cited answers via "
            "`POST /ask`. Every field carries provenance; every answer cites its "
            "sources."
        ),
        openapi_tags=[
            {"name": "meta", "description": "Public metadata catalog & State Registry (§13.5)."},
            {"name": "fetch", "description": "Deterministic field retrieval (§13.9)."},
            {"name": "ask", "description": "Natural-language geospatial intelligence (§13.13)."},
            {"name": "auth", "description": "Token, device-flow, and OAuth endpoints (§13.20)."},
            {"name": "health", "description": "Health, readiness, and liveness probes (§13.16)."},
        ],
        openapi_url=f"{settings.api_v1_prefix}/openapi.json",
        docs_url="/docs",
        redoc_url="/redoc",
        lifespan=lifespan,
    )
    app.state.settings = settings

    # Ephemeral auth state (auth/device codes, rate-limit counters, SRS §13.19/§23).
    # Redis is the multi-instance backend; the in-process store is correct for
    # single-instance dev and hermetic tests. Built here so it is shared across
    # requests within this app instance.
    if settings.auth_use_redis:
        app.state.ephemeral_store = RedisEphemeralStore(get_redis())
    else:
        app.state.ephemeral_store = InMemoryEphemeralStore()

    # The request-log writer follows the ephemeral_store pattern: it lives on
    # app.state so tests can swap in a recorder or None (SRS §22.3).
    app.state.request_log_writer = RequestLogWriter() if settings.request_log_enabled else None

    # Middleware. add_middleware installs outermost-last, so the request path is
    # CORS -> Security -> Correlation -> Metrics -> RequestLog -> app.
    # RequestLog is innermost so it sees the handler's request.state.audit and
    # the still-bound correlation id; Metrics' access log runs one layer out
    # (SRS §27.1); Correlation binds the id outside both (SRS §28.2).
    app.add_middleware(RequestLogMiddleware)
    if settings.metrics_enabled:
        app.add_middleware(MetricsMiddleware)
    app.add_middleware(CorrelationIdMiddleware)
    app.add_middleware(SecurityHeadersMiddleware, hsts=settings.is_production)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=settings.cors_allow_credentials,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    register_exception_handlers(app)
    app.include_router(api_v1_router, prefix=settings.api_v1_prefix)
    # OAuth discovery documents live at the origin root (SRS §13.20, §34).
    app.include_router(well_known_router)
    # Prometheus scrape endpoint at the origin root (SRS §27.2/§27.3).
    if settings.metrics_enabled:
        app.include_router(metrics_router)

    # Opt-in OpenTelemetry tracing (no-op unless an OTLP endpoint is configured).
    configure_tracing(app, settings)

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
