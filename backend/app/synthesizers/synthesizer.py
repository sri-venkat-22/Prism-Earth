"""The Synthesizer — fetched values → cited, human-readable answer (SRS §6.5).

The Synthesizer is the final AI stage of ``/api/v1/ask``. It receives ONLY the
values the Fetch Engine actually retrieved and turns them into a structured,
human-readable answer with inline citations (SRS §6.5, §16.8). It never invents
missing data: fields the fetch could not resolve are marked explicitly as
unavailable, never given a fabricated value (SRS §6.5, §38.8).

Two implementations share one interface:

- :class:`TemplateSynthesizer` — deterministic, LLM-free. Zero hallucination by
  construction: it can only emit values present in the fetch result. Used as the
  default fallback and to prove the anti-fabrication invariant.
- :class:`LLMSynthesizer` — fluent prose from a configurable model, constrained
  to the same fetched-only inputs, with a guard that (a) falls back to the
  template on an empty response and (b) always marks unavailable fields
  explicitly even if the model omits them.

The set of unavailable fields is computed deterministically from the fetch
nulls, independent of the model — so a null is always surfaced, never hidden.
"""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable

from pydantic import BaseModel, ConfigDict

from app.connectors.base import NullReason
from app.core.logging import get_logger
from app.llm import LLMClient
from app.planners.schema import ExecutionPlan
from app.schemas.fetch import FetchResponse

logger = get_logger(__name__)


class SynthesisResult(BaseModel):
    """The synthesized answer plus synthesizer telemetry (SRS §13.14)."""

    model_config = ConfigDict(frozen=True)

    answer: str
    model: str | None = None
    unavailable_fields: list[str] = []
    citations_used: list[str] = []
    prompt_tokens: int | None = None
    completion_tokens: int | None = None


@runtime_checkable
class Synthesizer(Protocol):
    """Turns fetched values into a cited answer (SRS §6.5)."""

    async def synthesize(
        self, *, question: str, plan: ExecutionPlan, fetch: FetchResponse
    ) -> SynthesisResult: ...


# --------------------------------------------------------------------------- #
# Shared views over the fetch result                                          #
# --------------------------------------------------------------------------- #
class _Resolved(BaseModel):
    name: str
    value: Any
    unit: str | None
    dataset: str
    citation_id: str | None
    confidence: str


class _Unavailable(BaseModel):
    name: str
    reason: str


_REASON_TEXT: dict[str, str] = {
    NullReason.DATA_UNAVAILABLE.value: "not available at this location",
    NullReason.OUTSIDE_COVERAGE.value: "outside the data source's coverage",
    NullReason.UNSUPPORTED_STATE.value: "not available outside the supported pilot region",
    NullReason.NOT_APPLICABLE.value: "not applicable at this location",
    NullReason.CONNECTOR_TIMEOUT.value: "temporarily unavailable (the data source did not respond)",
    NullReason.DATASET_UNAVAILABLE.value: "temporarily unavailable (data source offline)",
}


def _partition(fetch: FetchResponse) -> tuple[list[_Resolved], list[_Unavailable]]:
    """Split the fetch result into resolved values and unavailable fields."""
    field_to_citation: dict[str, str] = {}
    for citation in fetch.citations:
        for field_name in citation.field_names:
            field_to_citation.setdefault(field_name, citation.citation_id)

    resolved: list[_Resolved] = []
    unavailable: list[_Unavailable] = []
    for name, obj in fetch.fields.items():
        if obj.value is not None:
            resolved.append(
                _Resolved(
                    name=name,
                    value=obj.value,
                    unit=obj.unit,
                    dataset=obj.dataset,
                    citation_id=field_to_citation.get(name),
                    confidence=obj.confidence.value,
                )
            )
        else:
            unavailable.append(_Unavailable(name=name, reason=_reason_for(name, fetch)))
    return resolved, unavailable


def _reason_for(name: str, fetch: FetchResponse) -> str:
    """A human-readable reason a field is unavailable (SRS §17.6)."""
    field = fetch.fields[name]
    if field.null_meaning:
        return field.null_meaning
    prov = fetch.provenance.get(name)
    if prov is not None and prov.reason:
        return _REASON_TEXT.get(prov.reason, "not available at this location")
    return "not available at this location"


def _humanize(name: str) -> str:
    return name.replace("_", " ")


def _format_value(value: Any) -> str:
    if isinstance(value, bool):
        return "yes" if value else "no"
    if isinstance(value, float):
        return f"{round(value, 2):g}"
    return str(value)


def _place(fetch: FetchResponse) -> str:
    loc = fetch.location
    parts = [p for p in (loc.taluk, loc.district, loc.state) if p]
    return ", ".join(parts) if parts else "this location"


# --------------------------------------------------------------------------- #
# Deterministic template synthesizer                                          #
# --------------------------------------------------------------------------- #
class TemplateSynthesizer:
    """LLM-free, deterministic synthesizer (SRS §6.5, §38.8).

    Emits only values present in the fetch result and lists every unavailable
    field explicitly. Hallucination is impossible by construction, so this is the
    safe default and the reference for the anti-fabrication guarantee.
    """

    async def synthesize(
        self, *, question: str, plan: ExecutionPlan, fetch: FetchResponse
    ) -> SynthesisResult:
        resolved, unavailable = _partition(fetch)
        answer = _template_answer(resolved, unavailable, fetch)
        return SynthesisResult(
            answer=answer,
            model=None,
            unavailable_fields=[u.name for u in unavailable],
            citations_used=_unique(r.citation_id for r in resolved if r.citation_id),
        )


def _template_answer(
    resolved: list[_Resolved], unavailable: list[_Unavailable], fetch: FetchResponse
) -> str:
    lines: list[str] = []
    place = _place(fetch)
    if resolved:
        lines.append(f"Here is what the retrieved data shows for {place}:")
        for r in resolved:
            unit = f" {r.unit}" if r.unit else ""
            cite = f" ({r.dataset}"
            cite += f" [{r.citation_id}])" if r.citation_id else ")"
            lines.append(
                f"- {_humanize(r.name).capitalize()}: {_format_value(r.value)}{unit}{cite}."
            )
    else:
        lines.append(f"No requested data could be retrieved for {place}.")

    if unavailable:
        lines.append("")
        lines.append(
            "The following requested information is unavailable and has not been estimated:"
        )
        for u in unavailable:
            lines.append(f"- {_humanize(u.name).capitalize()}: {u.reason}.")
    return "\n".join(lines)


# --------------------------------------------------------------------------- #
# LLM synthesizer                                                             #
# --------------------------------------------------------------------------- #
_SYNTH_SYSTEM = (
    "You are the Synthesizer for Prism Earth, a deterministic geospatial "
    "intelligence platform. You write a clear, concise answer to the user's "
    "question using ONLY the retrieved data provided to you.\n"
    "STRICT RULES:\n"
    "1. Use only the values given. Never invent, estimate, infer, or round to a "
    "different number. If a value is not provided, you do not know it.\n"
    "2. Cite every factual value inline using its citation marker exactly as "
    "given, e.g. 'the elevation is 502 m [CIT-002]'.\n"
    "3. For any field listed as unavailable, state explicitly that it is "
    "unavailable — never guess a value for it.\n"
    "4. You may summarize and interpret the provided values in plain language, "
    "but every specific number or category you state must come from the data and "
    "carry its citation.\n"
    "5. Write prose for a person. Do not output JSON or a bare bullet dump of raw "
    "field names."
)


class LLMSynthesizer:
    """Fluent, model-generated answer constrained to fetched values (SRS §6.5)."""

    def __init__(self, *, llm: LLMClient) -> None:
        self._llm = llm
        self._fallback = TemplateSynthesizer()

    async def synthesize(
        self, *, question: str, plan: ExecutionPlan, fetch: FetchResponse
    ) -> SynthesisResult:
        resolved, unavailable = _partition(fetch)
        unavailable_names = [u.name for u in unavailable]

        user_prompt = _build_synth_user_prompt(question, plan, resolved, unavailable)
        result = await self._llm.complete(system=_SYNTH_SYSTEM, user=user_prompt, json_object=False)
        answer = result.text.strip()

        if not answer:
            # Empty model output — fall back to the deterministic answer rather
            # than return nothing (SRS §6.5).
            logger.warning("synthesizer.empty_response", model=result.model)
            return await self._fallback.synthesize(question=question, plan=plan, fetch=fetch)

        # Guard: guarantee unavailable fields are marked even if the model omitted
        # them, so a null is never silently dropped (SRS §38.8).
        answer = _ensure_unavailable_noted(answer, unavailable)

        valid_ids = {c.citation_id for c in fetch.citations}
        citations_used = [
            cid
            for cid in _unique(r.citation_id for r in resolved if r.citation_id)
            if cid in valid_ids
        ]

        return SynthesisResult(
            answer=answer,
            model=result.model,
            unavailable_fields=unavailable_names,
            citations_used=citations_used,
            prompt_tokens=result.prompt_tokens,
            completion_tokens=result.completion_tokens,
        )


def _build_synth_user_prompt(
    question: str,
    plan: ExecutionPlan,
    resolved: list[_Resolved],
    unavailable: list[_Unavailable],
) -> str:
    lines = [f"User question: {question}", f"Detected intent: {plan.intent}", ""]
    if resolved:
        lines.append("Retrieved data (use these values, cite each):")
        for r in resolved:
            unit = f" {r.unit}" if r.unit else ""
            cite = f" [{r.citation_id}]" if r.citation_id else " [uncited]"
            lines.append(
                f"- {r.name} = {_format_value(r.value)}{unit} — source: {r.dataset}{cite} "
                f"(confidence: {r.confidence})"
            )
    else:
        lines.append("Retrieved data: none of the requested fields returned a value.")
    if unavailable:
        lines.append("")
        lines.append("Unavailable fields (state each as unavailable, do NOT invent a value):")
        for u in unavailable:
            lines.append(f"- {u.name}: {u.reason}")
    lines.append("")
    lines.append("Write the answer now.")
    return "\n".join(lines)


def _ensure_unavailable_noted(answer: str, unavailable: list[_Unavailable]) -> str:
    """Append an explicit unavailable-fields note if the model omitted them."""
    if not unavailable:
        return answer
    lowered = answer.lower()
    if any(u.name in lowered or _humanize(u.name) in lowered for u in unavailable):
        return answer
    note_items = "; ".join(f"{_humanize(u.name)} ({u.reason})" for u in unavailable)
    return f"{answer}\n\nNot available at this location (not estimated): {note_items}."


def _unique(values) -> list[str]:  # type: ignore[no-untyped-def]
    seen: set[str] = set()
    ordered: list[str] = []
    for value in values:
        if value is not None and value not in seen:
            seen.add(value)
            ordered.append(value)
    return ordered
