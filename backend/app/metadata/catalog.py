"""The Metadata Catalog — the platform's single source of truth (SRS §11.4).

Every downstream subsystem (Planner, Fetch Engine, Citation Engine, frontend,
Metadata APIs) reads field, layer, and preset definitions from this catalog. No
field name is hardcoded outside the seed modules.

The :class:`Catalog` indexes the seed data, back-populates each field's
``presets`` from the preset definitions (single source of truth for the
field ↔ preset mapping), resolves each field's connector via its layer, and
exposes the lifecycle-enforcement helpers required by SRS §11.6 — ``planned``
fields are never selectable or fetchable.

Canonical Version-1 counts (SRS §11.4): 7 layers and 14 presets. The active
field catalog grows toward the 157-field target; implemented fields are stable
or beta and the remainder are ``planned``.
"""

from __future__ import annotations

from functools import lru_cache

from app.core.errors import NotFoundError, ValidationAppError
from app.metadata.enums import Availability, Layer, Lifecycle
from app.metadata.models import CatalogField, LayerDefinition, PresetDefinition
from app.metadata.seed_fields import FIELDS
from app.metadata.seed_layers import LAYERS
from app.metadata.seed_presets import PRESETS

# Canonical counts asserted by the validator (SRS §11.4).
EXPECTED_LAYER_COUNT = 7
EXPECTED_PRESET_COUNT = 14


class Catalog:
    """An indexed, immutable view over the layers, fields, and presets."""

    def __init__(
        self,
        layers: tuple[LayerDefinition, ...],
        fields: tuple[CatalogField, ...],
        presets: tuple[PresetDefinition, ...],
    ) -> None:
        self._layers: dict[Layer, LayerDefinition] = {layer.id: layer for layer in layers}
        self._presets: dict[str, PresetDefinition] = {preset.id: preset for preset in presets}

        # Back-populate each field's ``presets`` from the preset definitions so
        # the mapping is derived, never duplicated. A field referenced by a
        # preset that does not exist is left untouched here and flagged by the
        # validator instead.
        field_to_presets: dict[str, list[str]] = {field.name: [] for field in fields}
        for preset in presets:
            for field_name in preset.fields:
                field_to_presets.setdefault(field_name, []).append(preset.id)

        self._fields: dict[str, CatalogField] = {}
        self._field_order: list[str] = []
        for field in fields:
            enriched = field.model_copy(
                update={"presets": tuple(field_to_presets.get(field.name, []))}
            )
            self._fields[field.name] = enriched
            self._field_order.append(field.name)

    # --- Layers (SRS §11.5) ------------------------------------------------ #
    def layers(self) -> list[LayerDefinition]:
        return list(self._layers.values())

    def layer(self, layer_id: Layer | str) -> LayerDefinition:
        key = Layer(layer_id)
        try:
            return self._layers[key]
        except KeyError as exc:  # pragma: no cover - guarded by validator
            raise NotFoundError(f"Unknown layer: {layer_id!r}") from exc

    def has_layer(self, layer_id: Layer | str) -> bool:
        try:
            return Layer(layer_id) in self._layers
        except ValueError:
            return False

    def connector_for_layer(self, layer_id: Layer | str) -> str:
        return self.layer(layer_id).connector

    def connector_for_field(self, field_name: str) -> str:
        """Resolve the connector that owns a field, via its layer (SRS §11.5)."""
        return self.connector_for_layer(self.field(field_name).layer)

    # --- Fields (SRS §11.4) ------------------------------------------------ #
    def fields(self) -> list[CatalogField]:
        """All fields in catalog order, with ``presets`` back-populated."""
        return [self._fields[name] for name in self._field_order]

    def field(self, name: str) -> CatalogField:
        try:
            return self._fields[name]
        except KeyError as exc:
            raise NotFoundError(f"Unknown field: {name!r}") from exc

    def has_field(self, name: str) -> bool:
        return name in self._fields

    def field_names(self) -> set[str]:
        return set(self._fields)

    # --- Presets (SRS §11.7) ----------------------------------------------- #
    def presets(self) -> list[PresetDefinition]:
        return list(self._presets.values())

    def preset(self, preset_id: str) -> PresetDefinition:
        try:
            return self._presets[preset_id]
        except KeyError as exc:
            raise NotFoundError(f"Unknown preset: {preset_id!r}") from exc

    def has_preset(self, preset_id: str) -> bool:
        return preset_id in self._presets

    def preset_layers(self, preset: PresetDefinition) -> list[Layer]:
        """Distinct layers spanned by a preset's fields, in catalog order."""
        seen: list[Layer] = []
        for field_name in preset.fields:
            layer = self.field(field_name).layer
            if layer not in seen:
                seen.append(layer)
        return seen

    def expand_preset(self, preset_id: str) -> list[str]:
        """Expand a preset to its member field names (SRS §11.7)."""
        return list(self.preset(preset_id).fields)

    # --- Lifecycle enforcement (SRS §11.6) --------------------------------- #
    def is_selectable(self, name: str) -> bool:
        """Whether the Planner/Fetch Engine may select this field.

        Returns ``False`` for unknown fields and for ``planned`` fields, which
        are defined in the catalog but never retrievable (SRS §11.6).
        """
        return self.has_field(name) and self.field(name).selectable

    def planned_fields(self) -> list[CatalogField]:
        return [f for f in self.fields() if f.lifecycle is Lifecycle.PLANNED]

    def selectable_fields(self) -> list[CatalogField]:
        return [f for f in self.fields() if f.selectable]

    def region_gated_fields(self) -> list[CatalogField]:
        return [f for f in self.fields() if f.availability is Availability.REGION_GATED]

    def assert_selectable(self, names: list[str]) -> None:
        """Reject any unknown or ``planned`` field before connector execution.

        Raises :class:`ValidationAppError` (SRS §11.9) listing every offending
        field. Used by the Fetch Engine and Planner so that ``planned`` fields
        can never be requested directly (SRS §11.6).
        """
        unknown = sorted(n for n in names if not self.has_field(n))
        planned = sorted(n for n in names if self.has_field(n) and not self.field(n).selectable)
        problems: list[str] = []
        if unknown:
            problems.append(f"unknown fields: {', '.join(unknown)}")
        if planned:
            problems.append(f"planned fields cannot be selected: {', '.join(planned)}")
        if problems:
            raise ValidationAppError(
                "Field selection rejected — " + "; ".join(problems),
                details="; ".join(problems),
            )


def build_catalog() -> Catalog:
    """Construct a catalog from the seed modules."""
    return Catalog(LAYERS, FIELDS, PRESETS)


@lru_cache(maxsize=1)
def get_catalog() -> Catalog:
    """Return the process-wide catalog (the metadata cache, SRS §23.1)."""
    return build_catalog()
