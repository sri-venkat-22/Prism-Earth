"""The Planner — deterministic broad execution plan (SRS §14, revised).

Planning used to be an LLM call that narrowed the question down to a minimal
field selection. That narrowing contradicted the product rule that ``/ask``
fetches broadly — the Synthesizer focuses the *answer*, never the *fetch* —
and it spent half of the per-ask LLM budget: two model calls per question
against a small provider quota (e.g. Gemini's free-tier daily request cap).

The plan is now a pure function of the Metadata Catalog: every selectable
field, in catalog order, with layers and connectors derived via the catalog.
``/ask``'s single LLM call belongs to the Synthesizer (SRS §6.5).

The anti-hallucination guarantees (SRS §14.15, §38.3) now hold by
construction: no model proposes fields, so an unregistered or ``planned``
field can never enter a plan.
"""

from __future__ import annotations

import time

from app.core.logging import get_logger
from app.metadata.catalog import Catalog, get_catalog
from app.planners.schema import ExecutionPlan

logger = get_logger(__name__)

# PlannerTrace.model value — planning involves no language model.
PLANNER_MODEL = "deterministic-catalog"

_PLANNING_REASON = (
    "Broad-fetch policy: every selectable catalog field is retrieved for the "
    "location; the Synthesizer focuses the answer on the question."
)


class PlanResult:
    """A completed plan plus planning telemetry (SRS §14.17, §14.18)."""

    __slots__ = ("plan", "duration_ms", "model", "prompt_tokens", "completion_tokens")

    def __init__(
        self,
        *,
        plan: ExecutionPlan,
        duration_ms: float,
        model: str,
        prompt_tokens: int | None,
        completion_tokens: int | None,
    ) -> None:
        self.plan = plan
        self.duration_ms = duration_ms
        self.model = model
        self.prompt_tokens = prompt_tokens
        self.completion_tokens = completion_tokens


class Planner:
    """Builds the broad, catalog-derived execution plan (SRS §14)."""

    def __init__(self, *, catalog: Catalog | None = None) -> None:
        self._catalog = catalog or get_catalog()
        # The plan is a pure function of the catalog, so build it once.
        fields = [f.name for f in self._catalog.fields() if f.selectable]
        layers = _unique(self._catalog.field(name).layer.value for name in fields)
        connectors = _unique(self._catalog.connector_for_field(name) for name in fields)
        self._catalog.assert_selectable(fields)
        self._plan = ExecutionPlan(
            intent="Location Intelligence",
            presets=[],
            fields=fields,
            layers=layers,
            connectors=connectors,
            planning_reason=_PLANNING_REASON,
            warnings=[],
        )

    async def plan(
        self, question: str, *, lat: float, lng: float, request_id: str = ""
    ) -> PlanResult:
        """Plan retrieval for ``question`` at a coordinate (SRS §14.6).

        The question does not influence the plan — the fetch is always broad —
        but the signature is kept so the pipeline treats planning as a stage.
        """
        started = time.perf_counter()
        duration_ms = (time.perf_counter() - started) * 1000.0
        logger.info(
            "planner.planned",
            request_id=request_id,
            intent=self._plan.intent,
            field_count=len(self._plan.fields),
            duration_ms=round(duration_ms, 1),
        )
        return PlanResult(
            plan=self._plan,
            duration_ms=duration_ms,
            model=PLANNER_MODEL,
            prompt_tokens=None,
            completion_tokens=None,
        )


def _unique(values) -> list[str]:  # type: ignore[no-untyped-def]
    """De-duplicate while preserving first-seen order."""
    seen: set[str] = set()
    ordered: list[str] = []
    for value in values:
        if value not in seen:
            seen.add(value)
            ordered.append(value)
    return ordered
