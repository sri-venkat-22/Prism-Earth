"""Health, readiness, and liveness endpoints (SRS §13.16).

- ``GET /api/v1/health``  — overall status + dependency report; always ``200``
  while the process is serving (liveness + informational, per DoD).
- ``GET /api/v1/ready``   — readiness probe; ``200`` only when the database and
  Redis are reachable, otherwise ``503``.
- ``GET /api/v1/live``    — pure process liveness; always ``200``.

Each endpoint reports API, database, Redis, Google Earth Engine, and connector
status (SRS §13.16). In Phase 0, GEE and connectors are not yet implemented and
are reported as ``not_configured`` / ``not_applicable``.
"""

from __future__ import annotations

from fastapi import APIRouter, Response, status

from app.core.config import get_settings
from app.core.database import ping_database
from app.core.redis import ping_redis
from app.schemas.common import (
    ComponentStatus,
    HealthResponse,
    LivenessResponse,
    ReadinessResponse,
)
from app.utils.time import utcnow_iso

router = APIRouter(tags=["health"])

# Placeholder statuses for subsystems introduced in later phases.
_GEE_PHASE0 = ComponentStatus(status="not_configured", detail="Implemented in Phase 2 (SRS §19)")
_CONNECTORS_PHASE0 = ComponentStatus(
    status="not_applicable", detail="No connectors registered until Phase 3 (SRS §18)"
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
            "earth_engine": _GEE_PHASE0,
            "connectors": _CONNECTORS_PHASE0,
        },
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
