"""Catalog entry schemas (SRS §11.4 Metadata Catalog, §11.5, §11.7, §22.3).

These Pydantic models define the *shape* of every catalog entry — a field, a
layer, or a preset. They carry every attribute required by SRS §11.4 so the
catalog is structurally complete even for ``planned`` entries.

The models enforce per-entry invariants (naming, null-meaning consistency). The
cross-entry rules (preset → field references, field → layer/connector mapping,
canonical counts) live in :mod:`app.metadata.validator`.
"""

from __future__ import annotations

import re

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.metadata.enums import Availability, DataType, Layer, Lifecycle

# Field and preset identifiers are lowercase snake_case (e.g. ``ndvi_current``).
_IDENTIFIER = re.compile(r"^[a-z][a-z0-9_]*$")


class CatalogField(BaseModel):
    """A single field in the Metadata Catalog (every attribute of SRS §11.4).

    ``name`` doubles as the stable identifier (SRS §13.6 exposes both ``id`` and
    ``name``; here they are the same value). ``presets`` is left empty in the
    seed and back-populated by the catalog from the preset definitions, keeping
    a single source of truth for the field ↔ preset mapping.
    """

    model_config = ConfigDict(frozen=True)

    name: str = Field(..., description="Unique field identifier / name (SRS §11.4)")
    description: str = Field(..., description="Human-readable description")
    layer: Layer = Field(..., description="Owning domain layer (SRS §11.5)")
    lifecycle: Lifecycle = Field(..., description="stable | beta | planned (SRS §11.6)")
    availability: Availability = Field(..., description="Geographic availability (SRS §11.4)")
    nullable: bool = Field(False, description="Whether the value may be null")
    null_meaning: str | None = Field(None, description="What a null value means (SRS §11.4)")
    source: str = Field(..., description="Dataset / source name")
    source_url: str | None = Field(None, description="Official dataset URL")
    dataset_ttl: str | None = Field(None, description="Cache duration, e.g. '30d' (SRS §11.4)")
    interpretation_hint: str = Field("", description="Guidance for interpreting the field")
    unit: str | None = Field(None, description="Measurement unit (None for categorical)")
    datatype: DataType = Field(..., description="Output data type")

    presets: tuple[str, ...] = Field(
        default=(),
        description="Presets that include this field (back-populated by the catalog)",
    )

    @property
    def id(self) -> str:
        """Stable identifier exposed by the Metadata API (SRS §13.6)."""
        return self.name

    @property
    def available(self) -> bool:
        """Whether the field is retrievable at all (``planned`` fields are not)."""
        return self.lifecycle is not Lifecycle.PLANNED

    @property
    def selectable(self) -> bool:
        """Whether the Planner/Fetch Engine may select this field (SRS §11.6)."""
        return self.lifecycle is not Lifecycle.PLANNED

    @model_validator(mode="after")
    def _check_invariants(self) -> CatalogField:
        if not _IDENTIFIER.match(self.name):
            raise ValueError(f"Field name must be lowercase snake_case: {self.name!r}")

        # null_meaning must be present iff the field is nullable (SRS §11.4).
        if self.nullable and not self.null_meaning:
            raise ValueError(f"Nullable field {self.name!r} must define null_meaning")
        if not self.nullable and self.null_meaning:
            raise ValueError(f"Non-nullable field {self.name!r} must not set null_meaning")

        # Lifecycle/availability must agree on the ``planned`` state (SRS §11.6).
        planned = self.lifecycle is Lifecycle.PLANNED
        gated = self.availability is Availability.PLANNED
        if planned != gated:
            raise ValueError(
                f"Field {self.name!r}: PLANNED lifecycle and availability must be set together"
            )
        return self


class LayerDefinition(BaseModel):
    """One of the seven domain layers (SRS §11.5). Each layer owns a connector."""

    model_config = ConfigDict(frozen=True)

    id: Layer = Field(..., description="Layer identifier (SRS §11.5)")
    name: str = Field(..., description="Display name")
    purpose: str = Field(..., description="What the layer covers (SRS §11.5)")
    connector: str = Field(..., description="Connector that owns this layer (SRS §11.5, §18)")


class PresetDefinition(BaseModel):
    """A predefined field bundle expanded before connector execution (SRS §11.7).

    ``layers`` and ``supported_states`` are derived by the catalog/registry from
    the member fields, so a preset only declares its name, description, and
    fields. Presets never include ``planned`` fields (enforced by the validator).
    """

    model_config = ConfigDict(frozen=True)

    id: str = Field(..., description="Unique preset identifier")
    name: str = Field(..., description="Display name (SRS §13.8)")
    description: str = Field(..., description="What the preset is for")
    fields: tuple[str, ...] = Field(..., description="Catalog field names included (SRS §13.8)")

    @model_validator(mode="after")
    def _check_invariants(self) -> PresetDefinition:
        if not _IDENTIFIER.match(self.id):
            raise ValueError(f"Preset id must be lowercase snake_case: {self.id!r}")
        if not self.fields:
            raise ValueError(f"Preset {self.id!r} must include at least one field")
        if len(set(self.fields)) != len(self.fields):
            raise ValueError(f"Preset {self.id!r} has duplicate fields")
        return self
