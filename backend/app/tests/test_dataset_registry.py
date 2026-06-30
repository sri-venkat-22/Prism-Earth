"""Dataset Registry tests (SRS §16.10, §16.15)."""

from __future__ import annotations

import pytest

from app.core.errors import InternalError
from app.datasets.registry import DatasetRegistry, build_dataset_registry, get_dataset_registry


def test_registry_merges_yaml_and_gee_sources() -> None:
    registry = build_dataset_registry()
    # From configs/datasets.yaml (the §16.10 registry).
    assert registry.has("Survey of India Administrative Boundaries")
    assert registry.has("ISRO CartoDEM")
    # From the Earth Engine registry (so GEE-sourced provenance resolves).
    assert registry.has("Copernicus DEM GLO-30")


def test_registry_resolves_authoritative_metadata() -> None:
    registry = get_dataset_registry()
    soi = registry.require("Survey of India Administrative Boundaries")
    assert soi.provider == "Survey of India"
    assert soi.source_url and soi.crs == "EPSG:4326"


def test_require_unregistered_dataset_is_a_system_error() -> None:
    """An unregistered dataset must raise, never yield a fabricated citation."""
    registry = get_dataset_registry()
    with pytest.raises(InternalError):
        registry.require("Made Up Dataset")


def test_yaml_wins_on_name_collision() -> None:
    # Both sources may know a dataset; the declarative registry entry wins.
    registry = DatasetRegistry(
        [
            # YAML-style entry first.
            _meta("Shared", provider="YAML"),
            _meta("Shared", provider="GEE"),
        ]
    )
    assert registry.require("Shared").provider == "YAML"


def _meta(name: str, **kwargs: object):
    from app.datasets.registry import DatasetMeta

    return DatasetMeta(name=name, **kwargs)  # type: ignore[arg-type]
