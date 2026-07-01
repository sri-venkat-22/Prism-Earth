"""Request/response schemas for ``POST /api/v1/ask`` (SRS §13.13, §13.14).

Unlike ``/fetch``, this endpoint runs the AI pipeline: Planner (SRS §14) →
Fetch Engine (SRS §15, reused unchanged) → Synthesizer (SRS §6.5). The response
mirrors the SRS §13.13 shape — ``{answer, citations, trace, provenance}`` — and
attaches a full execution :class:`Trace` (SRS §13.14) so the UI can visualize
the planner reasoning and the fetch execution.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.schemas.fetch import Citation, FetchLocation, PartialFailure, ProvenanceObject


# --------------------------------------------------------------------------- #
# Request — SRS §13.13                                                         #
# --------------------------------------------------------------------------- #
class AskRequest(BaseModel):
    """A natural-language geospatial query (SRS §13.13)."""

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "lat": 17.385,
                    "lng": 78.486,
                    "question": "Is this area suitable for solar farm development?",
                }
            ]
        }
    )

    lat: float = Field(..., description="Latitude (WGS84)")
    lng: float = Field(..., description="Longitude (WGS84)")
    question: str = Field(..., description="Natural-language question about the location")

    @field_validator("question")
    @classmethod
    def _non_empty(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("'question' must not be empty.")
        return value


# --------------------------------------------------------------------------- #
# Trace — SRS §13.14                                                           #
# --------------------------------------------------------------------------- #
class PlannerTrace(BaseModel):
    """The Planner's output and telemetry (SRS §13.14, §14.17)."""

    intent: str
    presets: list[str]
    fields: list[str]
    layers: list[str]
    connectors: list[str]
    planning_reason: str
    warnings: list[str] = []
    model: str
    duration_ms: float
    prompt_tokens: int | None = None
    completion_tokens: int | None = None


class ConnectorExecution(BaseModel):
    """One connector's participation in the fetch (SRS §13.14 connector execution)."""

    connector: str
    fields: list[str]
    status: str = Field(..., description="ok | failed")
    reason: str | None = None


class FetchTrace(BaseModel):
    """The Fetch Engine's execution summary (SRS §13.14, §15.13)."""

    requested_fields: list[str]
    resolved_fields: list[str]
    null_fields: list[str]
    datasets_used: list[str]
    connectors: list[ConnectorExecution]
    partial_failures: list[PartialFailure]
    duration_ms: float


class SynthesizerTrace(BaseModel):
    """The Synthesizer's metadata (SRS §13.14, §6.5)."""

    model: str | None
    unavailable_fields: list[str]
    citations_used: list[str]
    duration_ms: float
    prompt_tokens: int | None = None
    completion_tokens: int | None = None


class Trace(BaseModel):
    """The full execution trace exposed to the UI (SRS §13.14)."""

    planner: PlannerTrace
    fetch: FetchTrace
    synthesizer: SynthesizerTrace
    total_duration_ms: float


# --------------------------------------------------------------------------- #
# Response — SRS §13.13                                                        #
# --------------------------------------------------------------------------- #
class AskResponse(BaseModel):
    """The full ``POST /api/v1/ask`` response (SRS §13.13)."""

    request_id: str
    timestamp: str
    location: FetchLocation
    answer: str
    citations: list[Citation]
    trace: Trace
    provenance: dict[str, ProvenanceObject]
