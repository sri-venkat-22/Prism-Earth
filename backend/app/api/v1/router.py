"""Aggregate router for API v1 (SRS §13.2).

Mounts the health endpoints (Phase 0) and the metadata / State Registry
endpoints (Phase 1). Fetch, ask, and dataset routers are added in later phases.
"""

from __future__ import annotations

from fastapi import APIRouter

from app.api.v1 import health, meta

api_v1_router = APIRouter()
api_v1_router.include_router(health.router)
api_v1_router.include_router(meta.router)
