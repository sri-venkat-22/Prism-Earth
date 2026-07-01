"""The Ask pipeline — plan → fetch → synthesize (SRS §13.13, §6.5, §14, §15).

``AskPipeline`` orchestrates the three stages of ``/api/v1/ask``:

1. **Planner** (SRS §14): the natural-language question becomes a
   catalog-constrained :class:`ExecutionPlan`.
2. **Fetch Engine** (SRS §15): the plan's fields feed the *existing*
   deterministic :class:`FetchOrchestrator` unchanged — no new data logic here.
3. **Synthesizer** (SRS §6.5): the fetched values become a cited answer.

The pipeline itself contains no data logic and no AI — it wires the stages,
times each one, and assembles the response and the execution :class:`Trace`
(SRS §13.14). The planner's ``fields`` are authoritative: presets were already
expanded to fields during planning, so the pipeline always fetches explicit
fields, preserving the plan exactly.
"""

from __future__ import annotations

import time

from app.core.logging import get_logger
from app.fetchers import FetchOrchestrator
from app.metadata.catalog import Catalog, get_catalog
from app.planners import Planner
from app.planners.planner import PlanResult
from app.schemas.ask import (
    AskResponse,
    ConnectorExecution,
    FetchTrace,
    PlannerTrace,
    SynthesizerTrace,
    Trace,
)
from app.schemas.fetch import FetchResponse
from app.synthesizers import SynthesisResult, Synthesizer

logger = get_logger(__name__)


class AskPipeline:
    """Runs the Planner → Fetch → Synthesizer pipeline (SRS §13.13)."""

    def __init__(
        self,
        *,
        planner: Planner,
        orchestrator: FetchOrchestrator,
        synthesizer: Synthesizer,
        catalog: Catalog | None = None,
    ) -> None:
        self._planner = planner
        self._orchestrator = orchestrator
        self._synthesizer = synthesizer
        self._catalog = catalog or get_catalog()

    async def ask(
        self, *, lat: float, lng: float, question: str, request_id: str = ""
    ) -> AskResponse:
        """Answer a natural-language question about a coordinate (SRS §13.13)."""
        started = time.perf_counter()

        # 1. Plan (SRS §14). The planner never fetches or answers.
        plan_result = await self._planner.plan(question, lat=lat, lng=lng, request_id=request_id)
        plan = plan_result.plan

        # 2. Fetch (SRS §15) — the plan's fields drive the existing orchestrator.
        fetch_started = time.perf_counter()
        fetch = await self._orchestrator.fetch(
            lat=lat, lng=lng, fields=plan.fields, request_id=request_id
        )
        fetch_ms = (time.perf_counter() - fetch_started) * 1000.0

        # 3. Synthesize (SRS §6.5) — only fetched values are seen here.
        synth_started = time.perf_counter()
        synthesis = await self._synthesizer.synthesize(question=question, plan=plan, fetch=fetch)
        synth_ms = (time.perf_counter() - synth_started) * 1000.0

        total_ms = (time.perf_counter() - started) * 1000.0
        trace = self._build_trace(
            plan_result=plan_result,
            fetch=fetch,
            fetch_ms=fetch_ms,
            synthesis=synthesis,
            synth_ms=synth_ms,
            total_ms=total_ms,
        )

        logger.info(
            "ask.completed",
            request_id=request_id,
            intent=plan.intent,
            requested=len(plan.fields),
            resolved=len(trace.fetch.resolved_fields),
            total_ms=round(total_ms, 1),
        )

        return AskResponse(
            request_id=fetch.request_id or request_id,
            timestamp=fetch.timestamp,
            location=fetch.location,
            answer=synthesis.answer,
            citations=fetch.citations,
            trace=trace,
            provenance=fetch.provenance,
        )

    # ------------------------------------------------------------------ #
    # Trace assembly (SRS §13.14)                                        #
    # ------------------------------------------------------------------ #
    def _build_trace(
        self,
        *,
        plan_result: PlanResult,
        fetch: FetchResponse,
        fetch_ms: float,
        synthesis: SynthesisResult,
        synth_ms: float,
        total_ms: float,
    ) -> Trace:
        plan = plan_result.plan
        planner_trace = PlannerTrace(
            intent=plan.intent,
            presets=plan.presets,
            fields=plan.fields,
            layers=plan.layers,
            connectors=plan.connectors,
            planning_reason=plan.planning_reason,
            warnings=plan.warnings,
            model=plan_result.model,
            duration_ms=round(plan_result.duration_ms, 2),
            prompt_tokens=plan_result.prompt_tokens,
            completion_tokens=plan_result.completion_tokens,
        )

        resolved = [name for name, obj in fetch.fields.items() if obj.value is not None]
        null_fields = [name for name, obj in fetch.fields.items() if obj.value is None]
        fetch_trace = FetchTrace(
            requested_fields=list(fetch.fields),
            resolved_fields=resolved,
            null_fields=null_fields,
            datasets_used=fetch.summary.datasets_used,
            connectors=self._connector_executions(fetch),
            partial_failures=fetch.partial_failures,
            duration_ms=round(fetch_ms, 2),
        )

        synth_trace = SynthesizerTrace(
            model=synthesis.model,
            unavailable_fields=synthesis.unavailable_fields,
            citations_used=synthesis.citations_used,
            duration_ms=round(synth_ms, 2),
            prompt_tokens=synthesis.prompt_tokens,
            completion_tokens=synthesis.completion_tokens,
        )

        return Trace(
            planner=planner_trace,
            fetch=fetch_trace,
            synthesizer=synth_trace,
            total_duration_ms=round(total_ms, 2),
        )

    def _connector_executions(self, fetch: FetchResponse) -> list[ConnectorExecution]:
        """Group requested fields by owning connector and mark failures (§13.14)."""
        groups: dict[str, list[str]] = {}
        for name in fetch.fields:
            key = self._catalog.connector_for_field(name)
            groups.setdefault(key, []).append(name)

        failures = {pf.connector: pf for pf in fetch.partial_failures if pf.connector}
        executions: list[ConnectorExecution] = []
        for connector, fields in groups.items():
            failure = failures.get(connector)
            executions.append(
                ConnectorExecution(
                    connector=connector,
                    fields=fields,
                    status="failed" if failure is not None else "ok",
                    reason=failure.reason if failure is not None else None,
                )
            )
        return executions
