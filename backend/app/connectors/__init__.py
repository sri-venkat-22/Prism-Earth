"""Dataset Connector Layer (SRS §18).

Independent adapters between the platform and individual data sources, all
implementing the standard connector interface (SRS §18.2) and returning the
standardized Field Object (SRS §18.11). Phase 3 wires two connectors to prove
both data paths — Terrain (GEE, SRS §18.3) and Administrative (PostGIS,
SRS §18.8) — routed by the catalog-driven Connector Registry (SRS §18.10).
"""

from __future__ import annotations

from app.connectors.administrative import AdministrativeConnector
from app.connectors.base import (
    BaseConnector,
    Confidence,
    ConnectorHealth,
    ConnectorMetadata,
    FetchContext,
    FieldResult,
    NullReason,
)
from app.connectors.registry import ConnectorRegistry
from app.connectors.terrain import (
    GeeTerrainSource,
    TerrainConnector,
    TerrainSample,
    TerrainSource,
)
from app.metadata.catalog import Catalog


def build_default_connectors() -> list[BaseConnector]:
    """The Version-1 connectors wired in Phase 3 (SRS §18.3, §18.8).

    Both are constructed with their real data sources; the Terrain connector's
    Earth Engine client is created lazily, so missing GEE credentials surface as
    a partial failure at fetch time rather than at construction (SRS §15.16).
    """
    return [
        TerrainConnector(GeeTerrainSource()),
        AdministrativeConnector(),
    ]


def build_connector_registry(
    catalog: Catalog, connectors: list[BaseConnector] | None = None
) -> ConnectorRegistry:
    """Build the catalog-driven Connector Registry (SRS §18.10)."""
    chosen = connectors if connectors is not None else build_default_connectors()
    return ConnectorRegistry(catalog, chosen)


__all__ = [
    "BaseConnector",
    "Confidence",
    "ConnectorHealth",
    "ConnectorMetadata",
    "FetchContext",
    "FieldResult",
    "NullReason",
    "ConnectorRegistry",
    "TerrainConnector",
    "TerrainSource",
    "TerrainSample",
    "GeeTerrainSource",
    "AdministrativeConnector",
    "build_default_connectors",
    "build_connector_registry",
]
