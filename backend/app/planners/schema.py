"""The Planner's structured execution plan (SRS §14.13).

:class:`ExecutionPlan` is the contract the Planner emits and the Fetch Engine
consumes unchanged (SRS §14.2, §14.13). It carries the detected intent, the
optimized presets, the catalog-validated field selection, and the *derived*
layers and connectors (derived from the fields via the catalog, never chosen
by the model — SRS §14.15). ``planning_reason`` and ``warnings`` make every
decision explainable (SRS §14.17).

The model never populates this object directly. The Planner parses the model's
proposal, constrains it to registered, selectable fields, and constructs the
plan deterministically — so a plan can never name a planned or undocumented
field, and the same proposal always yields the same plan (SRS §14.13, §38.3).
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class ExecutionPlan(BaseModel):
    """A deterministic execution plan handed to the Fetch Engine (SRS §14.13)."""

    model_config = ConfigDict(frozen=True)

    intent: str = Field(..., description="Detected geospatial intent (SRS §14.7)")
    presets: list[str] = Field(
        default_factory=list, description="Catalog presets selected (SRS §14.9)"
    )
    fields: list[str] = Field(
        default_factory=list,
        description="Selectable catalog fields, in catalog order (SRS §14.8, §14.13)",
    )
    layers: list[str] = Field(
        default_factory=list, description="Layers spanned by the fields (derived, SRS §14.5)"
    )
    connectors: list[str] = Field(
        default_factory=list, description="Connectors the fields require (derived, SRS §14.13)"
    )
    planning_reason: str = Field("", description="Why these fields were selected (SRS §14.17)")
    warnings: list[str] = Field(
        default_factory=list,
        description="Planning notes — e.g. proposed fields dropped as planned/undocumented "
        "(SRS §14.15, §14.11)",
    )

    @property
    def is_fulfillable(self) -> bool:
        """Whether the plan selected any retrievable field (SRS §14.15)."""
        return bool(self.fields)


class LLMPlanProposal(BaseModel):
    """The raw, untrusted proposal parsed from the model (SRS §14.13, §14.15).

    Only ``presets`` and ``fields`` influence retrieval, and both are validated
    against the catalog before use. ``layers``/``connectors`` from the model are
    ignored — the Planner derives them — so the model cannot invent a connector.
    """

    model_config = ConfigDict(extra="ignore")

    intent: str = ""
    presets: list[str] = Field(default_factory=list)
    fields: list[str] = Field(default_factory=list)
    planning_reason: str = ""
