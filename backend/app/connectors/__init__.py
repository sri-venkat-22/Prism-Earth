"""Dataset Connector Layer (SRS §18).

Independent adapters between the platform and individual data sources, all
implementing the standard connector interface (SRS §18.2) and returning the
standardized Field Object (SRS §18.11). The catalog-driven Connector Registry
(SRS §18.10) routes each field to its owning connector via its layer, so adding
a connector never touches the orchestrator (SRS §18.14).

Version-1 wiring (nine layers, nine connectors):

- **GEE point-sampling** (SRS §19.6): Terrain (§18.3), Climate (§18.4),
  Land Cover (§18.5), and Built Environment.
- **PostGIS spatial** (SRS §20.4): Administrative (§18.8), Infrastructure and
  Utilities (§18.7), and Cadastral (§18.9, region-gated §24.3).
- **Hybrid**: Natural Hazard (§18.6) combines JRC/VIIRS raster sampling with
  CWC/NRSC vector queries.

Each connector depends on an injected *source* protocol, so the whole layer is
unit-testable with fakes (no live PostGIS or Earth Engine); the real sources are
created lazily, so missing credentials/database surface as partial failures at
fetch time rather than at construction (SRS §15.16).
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
from app.connectors.built_environment import (
    BuildingSample,
    BuildingsSource,
    BuiltEnvironmentConnector,
    GeeBuildingsSource,
)
from app.connectors.cadastral import (
    CadastralConnector,
    CadastralSource,
    ParcelRecord,
    PostgisCadastralSource,
)
from app.connectors.climate import ClimateConnector, ClimateSample, ClimateSource, GeeClimateSource
from app.connectors.infrastructure import (
    InfrastructureConnector,
    InfrastructureSample,
    InfrastructureSource,
    PostgisInfrastructureSource,
)
from app.connectors.land_cover import (
    GeeLandCoverSource,
    LandCoverConnector,
    LandCoverSample,
    LandCoverSource,
)
from app.connectors.natural_hazard import (
    GeeHazardSource,
    HazardRasterSample,
    HazardRasterSource,
    HazardVectorSample,
    HazardVectorSource,
    NaturalHazardConnector,
    PostgisHazardSource,
)
from app.connectors.registry import ConnectorRegistry
from app.connectors.terrain import (
    GeeTerrainSource,
    TerrainConnector,
    TerrainSample,
    TerrainSource,
)
from app.connectors.utilities import (
    PostgisUtilitiesSource,
    UtilitiesConnector,
    UtilitiesSample,
    UtilitiesSource,
)
from app.metadata.catalog import Catalog


def build_default_connectors() -> list[BaseConnector]:
    """The Version-1 connectors — one per domain layer (SRS §18, §11.5).

    Every connector is constructed with its real data source. GEE clients and
    PostGIS sessionmakers are resolved lazily, so missing credentials or database
    connectivity surface as partial failures at fetch time (SRS §15.16), never as
    an import/construction crash.
    """
    return [
        TerrainConnector(GeeTerrainSource()),
        ClimateConnector(GeeClimateSource()),
        LandCoverConnector(GeeLandCoverSource()),
        NaturalHazardConnector(vector=PostgisHazardSource(), raster=GeeHazardSource()),
        InfrastructureConnector(PostgisInfrastructureSource()),
        UtilitiesConnector(PostgisUtilitiesSource()),
        AdministrativeConnector(),
        CadastralConnector(PostgisCadastralSource()),
        BuiltEnvironmentConnector(GeeBuildingsSource()),
    ]


def build_connector_registry(
    catalog: Catalog, connectors: list[BaseConnector] | None = None
) -> ConnectorRegistry:
    """Build the catalog-driven Connector Registry (SRS §18.10)."""
    chosen = connectors if connectors is not None else build_default_connectors()
    return ConnectorRegistry(catalog, chosen)


__all__ = [
    # Interface + shared types (SRS §18.2, §18.11)
    "BaseConnector",
    "Confidence",
    "ConnectorHealth",
    "ConnectorMetadata",
    "FetchContext",
    "FieldResult",
    "NullReason",
    "ConnectorRegistry",
    # Terrain (§18.3)
    "TerrainConnector",
    "TerrainSource",
    "TerrainSample",
    "GeeTerrainSource",
    # Climate (§18.4)
    "ClimateConnector",
    "ClimateSource",
    "ClimateSample",
    "GeeClimateSource",
    # Land Cover (§18.5)
    "LandCoverConnector",
    "LandCoverSource",
    "LandCoverSample",
    "GeeLandCoverSource",
    # Natural Hazard (§18.6)
    "NaturalHazardConnector",
    "HazardVectorSource",
    "HazardVectorSample",
    "HazardRasterSource",
    "HazardRasterSample",
    "PostgisHazardSource",
    "GeeHazardSource",
    # Infrastructure (§18.7)
    "InfrastructureConnector",
    "InfrastructureSource",
    "InfrastructureSample",
    "PostgisInfrastructureSource",
    # Utilities (§18.7)
    "UtilitiesConnector",
    "UtilitiesSource",
    "UtilitiesSample",
    "PostgisUtilitiesSource",
    # Administrative (§18.8)
    "AdministrativeConnector",
    # Cadastral (§18.9, region-gated §24.3)
    "CadastralConnector",
    "CadastralSource",
    "ParcelRecord",
    "PostgisCadastralSource",
    # Built Environment
    "BuiltEnvironmentConnector",
    "BuildingsSource",
    "BuildingSample",
    "GeeBuildingsSource",
    # Builders
    "build_default_connectors",
    "build_connector_registry",
]
