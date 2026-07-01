"""Earth Engine dataset registry (SRS §19.4, §19.11).

The supported Earth Engine datasets, each carrying the metadata the Provenance
System (SRS §19.12) and Citation Engine need: name, provider, purpose, the
Earth Engine asset id, bands, resolution, source URL, and TTL. Registering them
here keeps the Planner and Fetch Engine metadata-driven (SRS §19.11).

No raster is fetched at import time — these are pure descriptors.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class GEEDataset(BaseModel):
    """Descriptor for one Earth Engine dataset (SRS §19.4)."""

    model_config = ConfigDict(frozen=True)

    key: str = Field(..., description="Short registry key")
    name: str = Field(..., description="Human-readable dataset name (SRS §19.11)")
    provider: str = Field(..., description="Dataset provider")
    purpose: str = Field(..., description="What it is used for (SRS §19.4)")
    ee_id: str = Field(..., description="Earth Engine asset id")
    is_collection: bool = Field(False, description="True for ImageCollection assets")
    bands: tuple[str, ...] = Field((), description="Relevant band names")
    spatial_resolution: str | None = Field(None, description="Native pixel size, e.g. '30m'")
    temporal_resolution: str | None = Field(None, description="Cadence, e.g. 'monthly'")
    source_url: str | None = Field(None, description="Catalog/source URL (SRS §19.12)")
    ttl: str | None = Field(None, description="Cache duration, e.g. '30d' (SRS §19.9)")
    layers: tuple[str, ...] = Field((), description="Domain layers served (SRS §11.5)")


# The §19.4 supported datasets. `srtm` is the guaranteed-available elevation
# source used by the smoke test; Copernicus DEM is the §19.4 production fallback.
DATASETS: dict[str, GEEDataset] = {
    "sentinel2": GEEDataset(
        key="sentinel2",
        name="Copernicus Sentinel-2",
        provider="ESA / Copernicus",
        purpose="Land Cover & NDVI",
        ee_id="COPERNICUS/S2_SR_HARMONIZED",
        is_collection=True,
        bands=("B4", "B8"),
        spatial_resolution="10m",
        temporal_resolution="5-day",
        source_url="https://developers.google.com/earth-engine/datasets/catalog/COPERNICUS_S2_SR_HARMONIZED",
        ttl="7d",
        layers=("land_cover",),
    ),
    "terraclimate": GEEDataset(
        key="terraclimate",
        name="TerraClimate",
        provider="University of Idaho",
        purpose="Climate Indicators",
        ee_id="IDAHO_EPSCOR/TERRACLIMATE",
        is_collection=True,
        bands=("pr", "tmmx", "tmmn", "aet", "pet", "pdsi"),
        spatial_resolution="4638m",
        temporal_resolution="monthly",
        source_url="https://developers.google.com/earth-engine/datasets/catalog/IDAHO_EPSCOR_TERRACLIMATE",
        ttl="30d",
        layers=("climate",),
    ),
    "era5": GEEDataset(
        key="era5",
        name="ERA5",
        provider="ECMWF / Copernicus C3S",
        purpose="Wind speed (climate)",
        ee_id="ECMWF/ERA5_LAND/MONTHLY_AGGR",
        is_collection=True,
        bands=("u_component_of_wind_10m", "v_component_of_wind_10m"),
        spatial_resolution="11132m",
        temporal_resolution="monthly",
        source_url="https://developers.google.com/earth-engine/datasets/catalog/ECMWF_ERA5_LAND_MONTHLY_AGGR",
        ttl="30d",
        layers=("climate",),
    ),
    "esa_worldcover": GEEDataset(
        key="esa_worldcover",
        name="ESA WorldCover",
        provider="ESA",
        purpose="Land-cover classification, tree canopy, wetlands",
        ee_id="ESA/WorldCover/v200",
        is_collection=True,
        bands=("Map",),
        spatial_resolution="10m",
        temporal_resolution="2021",
        source_url="https://developers.google.com/earth-engine/datasets/catalog/ESA_WorldCover_v200",
        ttl="365d",
        layers=("land_cover",),
    ),
    "jrc_surface_water": GEEDataset(
        key="jrc_surface_water",
        name="JRC Global Surface Water",
        provider="EC JRC / Google",
        purpose="Historical Water Presence",
        ee_id="JRC/GSW1_4/GlobalSurfaceWater",
        is_collection=False,
        bands=("occurrence",),
        spatial_resolution="30m",
        temporal_resolution="1984-2021",
        source_url="https://developers.google.com/earth-engine/datasets/catalog/JRC_GSW1_4_GlobalSurfaceWater",
        ttl="90d",
        layers=("natural_hazard",),
    ),
    "jrc_glofas_flood_hazard": GEEDataset(
        key="jrc_glofas_flood_hazard",
        name="JRC Global River Flood Hazard Maps",
        provider="EC JRC / Copernicus Emergency Management Service (GloFAS)",
        purpose="River flood hazard by return period (natural hazard)",
        ee_id="JRC/CEMS_GLOFAS/FloodHazard/v2_1",
        is_collection=True,
        bands=(
            "RP10_depth",
            "RP20_depth",
            "RP50_depth",
            "RP75_depth",
            "RP100_depth",
            "RP200_depth",
            "RP500_depth",
        ),
        spatial_resolution="90m",
        temporal_resolution="static (2024 release)",
        source_url="https://developers.google.com/earth-engine/datasets/catalog/JRC_CEMS_GLOFAS_FloodHazard_v2_1",
        ttl="365d",
        layers=("natural_hazard",),
    ),
    "copernicus_dem": GEEDataset(
        key="copernicus_dem",
        name="Copernicus DEM GLO-30",
        provider="ESA / Copernicus",
        purpose="Elevation (Fallback)",
        ee_id="COPERNICUS/DEM/GLO30",
        is_collection=True,
        bands=("DEM",),
        spatial_resolution="30m",
        temporal_resolution="static",
        source_url="https://developers.google.com/earth-engine/datasets/catalog/COPERNICUS_DEM_GLO30",
        ttl="365d",
        layers=("terrain",),
    ),
    "modis_vegetation": GEEDataset(
        key="modis_vegetation",
        name="MODIS Vegetation Indices (MOD13Q1)",
        provider="NASA LP DAAC",
        purpose="Vegetation Analysis",
        ee_id="MODIS/061/MOD13Q1",
        is_collection=True,
        bands=("NDVI", "EVI"),
        spatial_resolution="250m",
        temporal_resolution="16-day",
        source_url="https://developers.google.com/earth-engine/datasets/catalog/MODIS_061_MOD13Q1",
        ttl="16d",
        layers=("land_cover",),
    ),
    "viirs_fire": GEEDataset(
        key="viirs_fire",
        name="VIIRS Active Fires (VNP14A1)",
        provider="NASA LP DAAC",
        purpose="Active Fire Detection",
        ee_id="NOAA/VIIRS/001/VNP14A1",
        is_collection=True,
        bands=("FireMask",),
        spatial_resolution="500m",
        temporal_resolution="daily",
        source_url="https://developers.google.com/earth-engine/datasets/catalog/NOAA_VIIRS_001_VNP14A1",
        ttl="1d",
        layers=("natural_hazard",),
    ),
    "srtm": GEEDataset(
        key="srtm",
        name="USGS SRTM GL1 v3",
        provider="NASA / USGS",
        purpose="Elevation (smoke-test source)",
        ee_id="USGS/SRTMGL1_003",
        is_collection=False,
        bands=("elevation",),
        spatial_resolution="30m",
        temporal_resolution="static",
        source_url="https://developers.google.com/earth-engine/datasets/catalog/USGS_SRTMGL1_003",
        ttl="365d",
        layers=("terrain",),
    ),
}

# The dataset the elevation smoke test samples (SRS §19, DoD #3).
ELEVATION_DATASET_KEY = "srtm"

# The DEM the Terrain connector samples for elevation/slope/aspect (SRS §18.3).
# SRS §18.3 designates ISRO CartoDEM as the primary terrain source, but CartoDEM
# is not in the public Earth Engine catalog; Copernicus DEM GLO-30 is the
# §19.4-registered production DEM (and the catalog's documented elevation
# fallback), so terrain provenance honestly cites Copernicus DEM (SRS §16.4).
TERRAIN_DEM_KEY = "copernicus_dem"

# Dataset keys the Phase 4 GEE connectors sample (SRS §18.4–18.6).
TERRACLIMATE_KEY = "terraclimate"
ERA5_KEY = "era5"
SENTINEL2_KEY = "sentinel2"
MODIS_NDVI_KEY = "modis_vegetation"
WORLDCOVER_KEY = "esa_worldcover"
JRC_SURFACE_WATER_KEY = "jrc_surface_water"
JRC_GLOFAS_FLOOD_HAZARD_KEY = "jrc_glofas_flood_hazard"
VIIRS_FIRE_KEY = "viirs_fire"

# Google Open Buildings is a vector FeatureCollection (no raster bands), so it is
# not a raster :class:`GEEDataset`; the Built-Environment connector queries this
# asset directly and cites the ``configs/datasets.yaml`` registry entry.
OPEN_BUILDINGS_ASSET = "GOOGLE/Research/open-buildings/v3/polygons"
OPEN_BUILDINGS_DATASET = "Google Open Buildings"


def get_dataset(key: str) -> GEEDataset:
    """Return a registered dataset descriptor by key."""
    try:
        return DATASETS[key]
    except KeyError as exc:  # pragma: no cover - defensive
        raise KeyError(f"Unknown Earth Engine dataset: {key!r}") from exc
