"""Catalog validator (SRS §11.4, §11.6, §11.9).

Verifies the integrity of the Metadata Catalog and its links to the State
Registry. It rejects undocumented fields, validates every preset → field
reference, and checks that each field maps to a registered layer (and therefore
a connector). It runs at startup (fail fast) and in the test suite.

The checks intentionally re-assert some per-entry invariants already enforced by
the Pydantic models, so the catalog stays valid even if those models are later
relaxed.
"""

from __future__ import annotations

from collections import Counter

from pydantic import BaseModel

from app.metadata.catalog import EXPECTED_LAYER_COUNT, EXPECTED_PRESET_COUNT, Catalog
from app.metadata.enums import Availability, Lifecycle
from app.metadata.seed_fields import FIELDS
from app.metadata.seed_presets import PRESETS
from app.metadata.state_registry import StateRegistry


class CatalogValidationError(RuntimeError):
    """Raised when the catalog fails validation (a build/config defect)."""


class CatalogStats(BaseModel):
    """Summary counts for the active catalog (SRS §11.4)."""

    fields: int
    stable: int
    beta: int
    planned: int
    region_gated: int
    layers: int
    presets: int


class ValidationReport(BaseModel):
    """Result of validating the catalog."""

    ok: bool
    errors: list[str]
    warnings: list[str]
    stats: CatalogStats

    def raise_for_status(self) -> None:
        if not self.ok:
            raise CatalogValidationError(
                "Metadata catalog validation failed:\n  - " + "\n  - ".join(self.errors)
            )


def _stats(catalog: Catalog) -> CatalogStats:
    by_lifecycle = Counter(f.lifecycle for f in catalog.fields())
    return CatalogStats(
        fields=len(catalog.fields()),
        stable=by_lifecycle[Lifecycle.STABLE],
        beta=by_lifecycle[Lifecycle.BETA],
        planned=by_lifecycle[Lifecycle.PLANNED],
        region_gated=len(catalog.region_gated_fields()),
        layers=len(catalog.layers()),
        presets=len(catalog.presets()),
    )


def validate_catalog(
    catalog: Catalog,
    registry: StateRegistry,
) -> ValidationReport:
    """Validate catalog integrity and its links to the State Registry."""
    errors: list[str] = []
    warnings: list[str] = []

    # 1. Canonical counts (SRS §11.4): exactly 7 layers and 14 presets.
    if len(catalog.layers()) != EXPECTED_LAYER_COUNT:
        errors.append(
            f"Expected {EXPECTED_LAYER_COUNT} layers, found {len(catalog.layers())} (SRS §11.4)."
        )
    if len(catalog.presets()) != EXPECTED_PRESET_COUNT:
        errors.append(
            f"Expected {EXPECTED_PRESET_COUNT} presets, found {len(catalog.presets())} "
            "(SRS §11.4)."
        )

    # 2. Duplicate identifiers in the seed (the catalog dict would mask these).
    for name, count in Counter(f.name for f in FIELDS).items():
        if count > 1:
            errors.append(f"Duplicate field name in seed: {name!r} ({count}×).")
    for pid, count in Counter(p.id for p in PRESETS).items():
        if count > 1:
            errors.append(f"Duplicate preset id in seed: {pid!r} ({count}×).")

    # 3. Every field maps to a registered layer with a connector (SRS §11.5).
    for field in catalog.fields():
        if not catalog.has_layer(field.layer):
            errors.append(f"Field {field.name!r} references unregistered layer {field.layer!r}.")
            continue
        if not catalog.connector_for_layer(field.layer):
            errors.append(f"Layer {field.layer!r} (field {field.name!r}) has no connector.")

    # Every layer must own a non-empty connector (SRS §11.5, §18.10).
    for layer in catalog.layers():
        if not layer.connector:
            errors.append(f"Layer {layer.id!r} has no connector.")

    # 4. Per-field invariants re-asserted (SRS §11.4, §11.6).
    for field in catalog.fields():
        if field.nullable and not field.null_meaning:
            errors.append(f"Nullable field {field.name!r} is missing null_meaning.")
        if field.availability is Availability.REGION_GATED and not field.nullable:
            errors.append(
                f"Region-gated field {field.name!r} must be nullable (null outside its region)."
            )
        planned = field.lifecycle is Lifecycle.PLANNED
        if planned != (field.availability is Availability.PLANNED):
            errors.append(f"Field {field.name!r}: planned lifecycle and availability must agree.")

    # 5. Preset → field references (SRS §11.7, §13.8). Presets must reference
    #    documented, selectable fields — never undocumented or planned ones.
    for preset in catalog.presets():
        for field_name in preset.fields:
            if not catalog.has_field(field_name):
                errors.append(f"Preset {preset.id!r} references undocumented field {field_name!r}.")
            elif not catalog.field(field_name).selectable:
                errors.append(
                    f"Preset {preset.id!r} references planned field {field_name!r} "
                    "(planned fields cannot be fetched, SRS §11.6)."
                )

    # 6. State Registry ↔ catalog consistency (SRS §11.8, §24.3). Every
    #    region-gated field a state enables must exist and be REGION_GATED.
    enabled_anywhere: set[str] = set()
    for state in registry.states():
        for field_name in state.enabled_fields:
            enabled_anywhere.add(field_name)
            if not catalog.has_field(field_name):
                errors.append(f"State {state.slug!r} enables undocumented field {field_name!r}.")
            elif catalog.field(field_name).availability is not Availability.REGION_GATED:
                errors.append(
                    f"State {state.slug!r} enables field {field_name!r}, "
                    "but it is not REGION_GATED in the catalog."
                )

    # A region-gated field that no registered state enables is unreachable.
    for field in catalog.region_gated_fields():
        if field.name not in enabled_anywhere:
            warnings.append(
                f"Region-gated field {field.name!r} is not enabled by any registered state."
            )

    return ValidationReport(ok=not errors, errors=errors, warnings=warnings, stats=_stats(catalog))
