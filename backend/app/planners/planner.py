"""The Planner — NL question → catalog-constrained execution plan (SRS §14).

The Planner is the first AI stage of ``/api/v1/ask``. It reads the metadata
catalog (its only domain knowledge, SRS §14.4), asks a configurable model to
propose an intent, presets, and fields (SRS §14.6, §14.14), then constructs the
final :class:`ExecutionPlan` **deterministically** from that proposal:

- explicit fields are filtered through :meth:`Catalog.is_selectable`, so unknown
  or ``planned`` fields are dropped, never selected (SRS §11.6, §14.15, §38.3);
- selected presets are validated and expanded via the catalog (SRS §14.9);
- the union is canonicalized to catalog order and de-duplicated, so the same
  proposal always yields the same field list (deterministic planning, SRS §14.13);
- layers and connectors are *derived* from the fields via the catalog, so the
  model can never invent a connector (SRS §14.15).

The Planner never fetches data, computes values, or writes an answer
(SRS §14.12). It only plans.
"""

from __future__ import annotations

import json
import time

from app.core.logging import get_logger
from app.llm import LLMClient
from app.metadata.catalog import Catalog, get_catalog
from app.planners.prompts import build_planner_system_prompt, build_planner_user_prompt
from app.planners.schema import ExecutionPlan, LLMPlanProposal

logger = get_logger(__name__)


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
    """Turns a natural-language question into an execution plan (SRS §14)."""

    def __init__(self, *, llm: LLMClient, catalog: Catalog | None = None) -> None:
        self._llm = llm
        self._catalog = catalog or get_catalog()
        # Built once from the catalog; cache-friendly and version-controlled (§14.14, §14.16).
        self._system_prompt = build_planner_system_prompt(self._catalog)
        # Catalog order for canonicalization — a pure function of the catalog.
        self._field_order = [f.name for f in self._catalog.fields()]

    async def plan(
        self, question: str, *, lat: float, lng: float, request_id: str = ""
    ) -> PlanResult:
        """Plan retrieval for ``question`` at a coordinate (SRS §14.6)."""
        started = time.perf_counter()
        user_prompt = build_planner_user_prompt(question, lat=lat, lng=lng)
        result = await self._llm.complete(
            system=self._system_prompt, user=user_prompt, json_object=True
        )
        proposal = self._parse(result.text)
        plan = self._constrain(proposal)
        duration_ms = (time.perf_counter() - started) * 1000.0

        logger.info(
            "planner.planned",
            request_id=request_id,
            intent=plan.intent,
            presets=plan.presets,
            field_count=len(plan.fields),
            dropped=len(plan.warnings),
            duration_ms=round(duration_ms, 1),
        )
        return PlanResult(
            plan=plan,
            duration_ms=duration_ms,
            model=result.model,
            prompt_tokens=result.prompt_tokens,
            completion_tokens=result.completion_tokens,
        )

    # ------------------------------------------------------------------ #
    # Parsing                                                            #
    # ------------------------------------------------------------------ #
    def _parse(self, text: str) -> LLMPlanProposal:
        """Extract the JSON proposal from the model output (SRS §14.13).

        Tolerates code fences and surrounding prose. An unparseable response is
        treated as an empty proposal — the catalog constraint then yields an
        unfulfillable plan rather than a fabricated one (SRS §14.15).
        """
        raw = _extract_json_object(text)
        if raw is None:
            logger.warning("planner.unparseable_response", preview=text[:200])
            return LLMPlanProposal()
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            logger.warning("planner.invalid_json", preview=raw[:200])
            return LLMPlanProposal()
        if not isinstance(data, dict):
            return LLMPlanProposal()
        return LLMPlanProposal.model_validate(data)

    # ------------------------------------------------------------------ #
    # Catalog constraint (the anti-hallucination core, SRS §14.15)       #
    # ------------------------------------------------------------------ #
    def _constrain(self, proposal: LLMPlanProposal) -> ExecutionPlan:
        """Build a deterministic, catalog-valid plan from a raw proposal."""
        warnings: list[str] = []

        # Validate presets: keep only registered ones (SRS §14.9).
        presets: list[str] = []
        for preset_id in _unique(proposal.presets):
            if self._catalog.has_preset(preset_id):
                presets.append(preset_id)
            else:
                warnings.append(f"Ignored unknown preset: {preset_id!r}")

        # Collect candidate fields from expanded presets + explicit fields.
        candidates: list[str] = []
        for preset_id in presets:
            candidates.extend(self._catalog.expand_preset(preset_id))
        candidates.extend(proposal.fields)

        # Filter to selectable catalog fields — this is where planned and
        # undocumented fields are provably dropped (SRS §11.6, §14.15, §38.3).
        selected: set[str] = set()
        for name in candidates:
            if self._catalog.is_selectable(name):
                selected.add(name)
            elif not self._catalog.has_field(name):
                warnings.append(f"Dropped undocumented field not in catalog: {name!r}")
            else:  # exists but is planned/unavailable
                warnings.append(f"Dropped non-selectable (planned) field: {name!r}")

        # Canonicalize to catalog order so the plan is order-stable (SRS §14.13).
        fields = [name for name in self._field_order if name in selected]

        # Derive layers and connectors from the fields — never from the model.
        layers = _unique(self._catalog.field(f).layer.value for f in fields)
        connectors = _unique(self._catalog.connector_for_field(f) for f in fields)

        # Belt-and-suspenders: the invariant the whole method exists to enforce.
        self._catalog.assert_selectable(fields)

        reason = proposal.planning_reason.strip()
        if not fields and not reason:
            reason = "No registered field matches this question; it cannot be fulfilled."

        return ExecutionPlan(
            intent=proposal.intent.strip() or "General Inquiry",
            presets=presets,
            fields=fields,
            layers=layers,
            connectors=connectors,
            planning_reason=reason,
            warnings=warnings,
        )


def _extract_json_object(text: str) -> str | None:
    """Return the first balanced ``{...}`` block in ``text``, or None."""
    start = text.find("{")
    if start == -1:
        return None
    depth = 0
    in_string = False
    escaped = False
    for index in range(start, len(text)):
        char = text[index]
        if in_string:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                in_string = False
            continue
        if char == '"':
            in_string = True
        elif char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return text[start : index + 1]
    return None


def _unique(values) -> list[str]:  # type: ignore[no-untyped-def]
    """De-duplicate while preserving first-seen order."""
    seen: set[str] = set()
    ordered: list[str] = []
    for value in values:
        if value not in seen:
            seen.add(value)
            ordered.append(value)
    return ordered
