"""Dataset Registry — the single source of truth for citation/provenance metadata.

The Citation Engine (SRS §16.10) and Provenance System (SRS §17.5) resolve every
returned field's dataset to authoritative metadata (provider, version, source URL,
license, TTL) through this registry. Import the cached accessor from here:

    from app.datasets import DatasetMeta, DatasetRegistry, get_dataset_registry
"""

from __future__ import annotations

from app.datasets.registry import (
    DatasetMeta,
    DatasetRegistry,
    build_dataset_registry,
    get_dataset_registry,
)

__all__ = [
    "DatasetMeta",
    "DatasetRegistry",
    "build_dataset_registry",
    "get_dataset_registry",
]
