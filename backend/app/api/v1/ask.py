"""Natural-language geospatial intelligence API (SRS §13.13).

``POST /api/v1/ask`` runs the AI pipeline — Planner (SRS §14) → Fetch Engine
(SRS §15) → Synthesizer (SRS §6.5) — and returns a cited answer plus a full
execution trace (SRS §13.14). The endpoint is a thin adapter over
:class:`AskPipeline`; all planning, fetching, and synthesis happen there.

Error semantics:

- Out-of-range coordinates → ``422`` (validated by the Fetch Engine, SRS §15.6).
- An empty ``question`` → ``422`` (request validation).
- The language model being unavailable/misconfigured → ``503`` (SRS §38.8): the
  platform reports the limitation rather than fabricating a plan or answer.
- A connector failing at runtime never aborts the request — the answer is
  synthesized from the fields that resolved, and the failure appears under
  ``trace.fetch.partial_failures`` (SRS §15.16).
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.ask import AskPipeline, build_ask_pipeline
from app.core.database import get_session
from app.schemas.ask import AskRequest, AskResponse

router = APIRouter(tags=["ask"])


async def get_ask_pipeline(
    session: Annotated[AsyncSession, Depends(get_session)],
) -> AskPipeline:
    """Provide a request-scoped Ask pipeline (overridable in tests)."""
    return build_ask_pipeline(session)


@router.post(
    "/ask",
    response_model=AskResponse,
    summary="Natural-language geospatial intelligence (SRS §13.13)",
    response_model_exclude_none=False,
)
async def ask(
    payload: AskRequest,
    request: Request,
    pipeline: Annotated[AskPipeline, Depends(get_ask_pipeline)],
) -> AskResponse:
    """Plan → fetch → synthesize a cited answer for a question (SRS §13.13)."""
    correlation_id = getattr(request.state, "correlation_id", "")
    return await pipeline.ask(
        lat=payload.lat,
        lng=payload.lng,
        question=payload.question,
        request_id=correlation_id,
    )
