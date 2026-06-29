"""Metadata Catalog & State Registry (SRS §11.4–11.8).

The single source of truth for fields, layers, and presets, plus the
configuration-driven State Registry. Import the cached accessors from here:

    from app.metadata import get_catalog, get_state_registry, validate_catalog
"""

from __future__ import annotations

from app.metadata.catalog import Catalog, build_catalog, get_catalog
from app.metadata.state_registry import (
    RegionResolution,
    RegisteredState,
    StateRegistry,
    build_state_registry,
    get_state_registry,
)
from app.metadata.validator import (
    CatalogValidationError,
    ValidationReport,
    validate_catalog,
)

__all__ = [
    "Catalog",
    "build_catalog",
    "get_catalog",
    "RegisteredState",
    "RegionResolution",
    "StateRegistry",
    "build_state_registry",
    "get_state_registry",
    "CatalogValidationError",
    "ValidationReport",
    "validate_catalog",
]
