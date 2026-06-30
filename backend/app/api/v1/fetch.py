"""Deterministic Fetch API (SRS §13.9–13.12).

``POST /api/v1/fetch`` retrieves raw geospatial field values for a coordinate
with full provenance (SRS §17) and citations (SRS §16). No AI runs here — the
endpoint is a thin adapter over the deterministic Fetch Orchestrator (SRS §15).

Error semantics:

- Out-of-range coordinates or an empty/ambiguous selector → ``422`` (SRS §15.6).
- An unknown or ``planned`` field → ``422`` (SRS §11.6, §38.4).
- An unknown preset → ``404`` (SRS §15.8).
- A connector failing at runtime never aborts the request: the other fields are
  returned and the failure appears under ``partial_failures`` with ``200``
  (SRS §15.16, §13.12).
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session
from app.fetchers import FetchOrchestrator, build_fetch_orchestrator
from app.schemas.fetch import FetchRequest, FetchResponse

router = APIRouter(tags=["fetch"])


async def get_fetch_orchestrator(
    session: Annotated[AsyncSession, Depends(get_session)],
) -> FetchOrchestrator:
    """Provide a request-scoped Fetch Orchestrator (overridable in tests)."""
    return build_fetch_orchestrator(session)


@router.post(
    "/fetch",
    response_model=FetchResponse,
    summary="Deterministic field retrieval (SRS §13.9)",
    response_model_exclude_none=False,
)
async def fetch(
    payload: FetchRequest,
    request: Request,
    orchestrator: Annotated[FetchOrchestrator, Depends(get_fetch_orchestrator)],
) -> FetchResponse:
    """Retrieve fields (or an expanded preset) at a coordinate (SRS §13.9)."""
    correlation_id = getattr(request.state, "correlation_id", "")
    return await orchestrator.fetch(
        lat=payload.lat,
        lng=payload.lng,
        fields=payload.fields,
        preset=payload.preset,
        request_id=correlation_id,
    )
