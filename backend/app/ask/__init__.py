"""The Ask pipeline (SRS §13.13).

Wires the Planner (SRS §14), the existing Fetch Engine (SRS §15), and the
Synthesizer (SRS §6.5) into the ``/api/v1/ask`` flow. Import the public surface:

    from app.ask import AskPipeline, build_ask_pipeline
"""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.ask.pipeline import AskPipeline
from app.fetchers import FetchOrchestrator, build_fetch_orchestrator
from app.llm import LLMClient, build_llm_client
from app.metadata.catalog import get_catalog
from app.planners import Planner
from app.synthesizers import LLMSynthesizer, Synthesizer


def build_ask_pipeline(
    session: AsyncSession,
    *,
    llm: LLMClient | None = None,
    planner: Planner | None = None,
    orchestrator: FetchOrchestrator | None = None,
    synthesizer: Synthesizer | None = None,
) -> AskPipeline:
    """Wire an :class:`AskPipeline` with production dependencies (SRS §13.13).

    The Fetch Engine needs a database session for state detection (SRS §15.7).
    ``llm``, ``planner``, ``orchestrator``, and ``synthesizer`` are injectable so
    tests can drive the whole pipeline with fakes (no live model or PostGIS).
    """
    catalog = get_catalog()
    client = llm or build_llm_client()
    return AskPipeline(
        planner=planner or Planner(llm=client, catalog=catalog),
        orchestrator=orchestrator or build_fetch_orchestrator(session),
        synthesizer=synthesizer or LLMSynthesizer(llm=client),
        catalog=catalog,
    )


__all__ = [
    "AskPipeline",
    "build_ask_pipeline",
]
