"""Aggregate router for API v1 (SRS §13.2).

Mounts the health endpoints (Phase 0), the metadata / State Registry endpoints
(Phase 1), the deterministic Fetch API (Phase 3), and the natural-language Ask
API (Phase 5). The dataset router is added in a later phase.
"""

from __future__ import annotations

from fastapi import APIRouter

from app.api.v1 import ask, fetch, health, meta

api_v1_router = APIRouter()
api_v1_router.include_router(health.router)
api_v1_router.include_router(meta.router)
api_v1_router.include_router(fetch.router)
api_v1_router.include_router(ask.router)
