"""Aggregate router for API v1 (SRS §13.2).

Phase 0 mounts only the health endpoints. Metadata, fetch, ask, and dataset
routers are added in later phases.
"""

from __future__ import annotations

from fastapi import APIRouter

from app.api.v1 import health

api_v1_router = APIRouter()
api_v1_router.include_router(health.router)
