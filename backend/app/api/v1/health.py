"""Health, readiness, and liveness endpoints (SRS §13.16).

- ``GET /api/v1/health``  — overall status + dependency report; always ``200``
  while the process is serving (liveness + informational, per DoD).
- ``GET /api/v1/ready``   — readiness probe; ``200`` only when the database and
  Redis are reachable, otherwise ``503``.
- ``GET /api/v1/live``    — pure process liveness; always ``200``.

Each endpoint reports API, database, Redis, Google Earth Engine, and connector
status (SRS §13.16). Earth Engine (Phase 2, SRS §19) reports whether the service
account is configured; connectors remain ``not_applicable`` until Phase 3.
"""

from __future__ import annotations

from fastapi import APIRouter, Response, status

from app.connectors import build_connector_registry
from app.core.config import Settings, get_settings
from app.core.database import ping_database
from app.core.redis import ping_redis
from app.metadata.catalog import get_catalog
from app.schemas.common import (
    ComponentStatus,
    ConnectorHealthObject,
    ConnectorsHealthResponse,
    HealthResponse,
    LivenessResponse,
    ReadinessResponse,
)
from app.utils.time import utcnow_iso

router = APIRouter(tags=["health"])


def _connectors_status() -> ComponentStatus:
    """Summarize registered-connector status for the top-level health payload."""
    registry = build_connector_registry(get_catalog())
    count = len(registry.connectors())
    return ComponentStatus(status="ok", detail=f"{count} connectors registered (SRS §18.10)")


def _earth_engine_status(settings: Settings) -> ComponentStatus:
    """Report Earth Engine service-account configuration (SRS §19.3)."""
    if settings.earth_engine_configured:
        return ComponentStatus(status="ok", detail="Service account configured")
    return ComponentStatus(
        status="not_configured",
        detail="Set PRISM_EARTH_ENGINE_SERVICE_ACCOUNT and PRISM_EARTH_ENGINE_KEY_FILE (SRS §19.3)",
    )


@router.get("/health", response_model=HealthResponse, summary="Service health")
async def health() -> HealthResponse:
    """Report overall service health. Returns ``200`` whenever the API is up."""
    settings = get_settings()
    db_ok = await ping_database()
    redis_ok = await ping_redis()

    return HealthResponse(
        status="ok",
        service=settings.app_name,
        version=settings.app_version,
        environment=settings.app_env,
        timestamp=utcnow_iso(),
        components={
            "api": ComponentStatus(status="ok"),
            "database": ComponentStatus(status="ok" if db_ok else "down"),
            "redis": ComponentStatus(status="ok" if redis_ok else "down"),
            "earth_engine": _earth_engine_status(settings),
            "connectors": _connectors_status(),
        },
    )


@router.get(
    "/health/connectors",
    response_model=ConnectorsHealthResponse,
    summary="Per-connector health (SRS §18.12)",
)
async def connectors_health() -> ConnectorsHealthResponse:
    """Report each registered connector's operational status (SRS §18.12).

    Catalog-driven: every domain layer's connector is listed with the number of
    fields it can serve. Always ``200`` — a degraded connector is reported, not
    raised, so callers can see the whole fleet's state at a glance.
    """
    registry = build_connector_registry(get_catalog())
    connectors: list[ConnectorHealthObject] = []
    for connector in registry.connectors():
        health_report = await connector.health()
        connectors.append(
            ConnectorHealthObject(
                name=connector.name,
                layer=connector.layer.value,
                status=health_report.status,
                servable_fields=len(connector.servable_fields()),
                detail=health_report.detail,
            )
        )
    overall = "ok" if all(c.status == "ok" for c in connectors) else "degraded"
    return ConnectorsHealthResponse(
        status=overall,
        timestamp=utcnow_iso(),
        count=len(connectors),
        connectors=connectors,
    )


@router.get("/ready", response_model=ReadinessResponse, summary="Readiness probe")
async def ready(response: Response) -> ReadinessResponse:
    """Return ``200`` only when all critical dependencies are reachable."""
    db_ok = await ping_database()
    redis_ok = await ping_redis()
    is_ready = db_ok and redis_ok

    if not is_ready:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE

    return ReadinessResponse(
        status="ready" if is_ready else "not_ready",
        timestamp=utcnow_iso(),
        checks={
            "database": ComponentStatus(status="ok" if db_ok else "down"),
            "redis": ComponentStatus(status="ok" if redis_ok else "down"),
        },
    )


@router.get("/live", response_model=LivenessResponse, summary="Liveness probe")
async def live() -> LivenessResponse:
    """Pure process liveness — always ``200`` while the app is serving."""
    return LivenessResponse(status="alive", timestamp=utcnow_iso())
