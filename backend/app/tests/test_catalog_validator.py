"""Tests for the catalog validator (SRS §11.9, Phase 1 DoD).

The real catalog must validate clean; deliberately bad field/preset references
must fail the validator.
"""

from __future__ import annotations

from app.metadata.catalog import (
    EXPECTED_LAYER_COUNT,
    EXPECTED_PRESET_COUNT,
    Catalog,
    build_catalog,
)
from app.metadata.enums import Layer
from app.metadata.models import PresetDefinition
from app.metadata.seed_fields import FIELDS
from app.metadata.seed_layers import LAYERS
from app.metadata.seed_presets import PRESETS
from app.metadata.state_registry import build_state_registry
from app.metadata.validator import CatalogValidationError, validate_catalog


def test_real_catalog_validates_clean() -> None:
    """DoD: the catalog validator passes for the shipped catalog."""
    report = validate_catalog(build_catalog(), build_state_registry())
    assert report.ok, report.errors
    assert report.stats.layers == EXPECTED_LAYER_COUNT
    assert report.stats.presets == EXPECTED_PRESET_COUNT
    assert report.stats.planned > 0
    report.raise_for_status()  # must not raise


def test_preset_referencing_undocumented_field_fails() -> None:
    """DoD: a deliberately bad preset → field reference fails the validator."""
    bad_preset = PresetDefinition(
        id="broken_preset",
        name="Broken",
        description="References a field that does not exist.",
        fields=("elevation", "field_that_does_not_exist"),
    )
    catalog = Catalog(LAYERS, FIELDS, (*PRESETS, bad_preset))
    report = validate_catalog(catalog, build_state_registry())
    assert not report.ok
    assert any("undocumented field" in e for e in report.errors)


def test_preset_referencing_planned_field_fails() -> None:
    catalog = build_catalog()
    planned_name = catalog.planned_fields()[0].name
    bad_preset = PresetDefinition(
        id="planned_preset",
        name="Planned",
        description="References a planned field.",
        fields=("elevation", planned_name),
    )
    catalog = Catalog(LAYERS, FIELDS, (*PRESETS, bad_preset))
    report = validate_catalog(catalog, build_state_registry())
    assert not report.ok
    assert any("planned field" in e for e in report.errors)


def test_field_referencing_unregistered_layer_fails() -> None:
    """A field whose layer is not registered (no connector) fails validation."""
    layers_without_cadastral = tuple(layer for layer in LAYERS if layer.id is not Layer.CADASTRAL)
    catalog = Catalog(layers_without_cadastral, FIELDS, PRESETS)
    report = validate_catalog(catalog, build_state_registry())
    assert not report.ok
    assert any("unregistered layer" in e for e in report.errors)


def test_raise_for_status_raises_on_failure() -> None:
    bad_preset = PresetDefinition(
        id="broken",
        name="Broken",
        description="bad",
        fields=("nope_not_real",),
    )
    catalog = Catalog(LAYERS, FIELDS, (*PRESETS, bad_preset))
    report = validate_catalog(catalog, build_state_registry())
    try:
        report.raise_for_status()
    except CatalogValidationError:
        pass
    else:  # pragma: no cover
        raise AssertionError("expected CatalogValidationError")
