"""Shared fakes for the Phase 5 AI-pipeline tests (no live model or PostGIS).

Mirrors the project's injection style (see ``_fetch_fakes``): the Planner and
Synthesizer take an :class:`~app.llm.LLMClient`, so a scripted :class:`FakeLLM`
drives the whole ``/ask`` pipeline deterministically without any provider key.
The Fetch Engine is the real orchestrator wired with the Phase 3/4 fake
connectors (:func:`build_full_orchestrator`), so ``/ask`` is proven end-to-end.
"""

from __future__ import annotations

from app.ask.pipeline import AskPipeline
from app.llm import LLMResult
from app.metadata.catalog import get_catalog
from app.planners import Planner
from app.schemas.spatial import SpatialContext
from app.synthesizers import LLMSynthesizer, Synthesizer
from app.tests._fetch_fakes import build_full_orchestrator, make_context


class FakeLLM:
    """A scripted LLM: planner JSON on ``json_object`` calls, prose otherwise.

    ``json_object=True`` is the Planner's structured call; ``False`` is the
    Synthesizer's prose call, so one fake serves both stages with distinct,
    fixed outputs — making the whole pipeline deterministic.
    """

    def __init__(
        self,
        *,
        planner_json: str = "{}",
        synthesizer_text: str = "Synthesized answer.",
        model: str = "fake-model",
    ) -> None:
        self._planner_json = planner_json
        self._synthesizer_text = synthesizer_text
        self._model = model
        self.calls: list[dict[str, object]] = []

    @property
    def model(self) -> str:
        return self._model

    async def complete(self, *, system: str, user: str, json_object: bool = False) -> LLMResult:
        self.calls.append({"system": system, "user": user, "json_object": json_object})
        text = self._planner_json if json_object else self._synthesizer_text
        return LLMResult(text=text, model=self._model, prompt_tokens=42, completion_tokens=7)


def build_fake_pipeline(
    *,
    planner_json: str,
    synthesizer_text: str = "Based on the retrieved data, here is the assessment.",
    context: SpatialContext | None = None,
    synthesizer: Synthesizer | None = None,
    llm: FakeLLM | None = None,
) -> tuple[AskPipeline, FakeLLM]:
    """Assemble an :class:`AskPipeline` from a scripted LLM + fake connectors."""
    catalog = get_catalog()
    client = llm or FakeLLM(planner_json=planner_json, synthesizer_text=synthesizer_text)
    planner = Planner(llm=client, catalog=catalog)
    orchestrator = build_full_orchestrator(context or make_context())
    synth = synthesizer or LLMSynthesizer(llm=client)
    pipeline = AskPipeline(
        planner=planner, orchestrator=orchestrator, synthesizer=synth, catalog=catalog
    )
    return pipeline, client
