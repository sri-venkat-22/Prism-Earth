"""Google Earth Engine integration (SRS §19).

Service-account authentication (§19.3), the supported-dataset registry (§19.4),
and a thin point-sampling client (§19.6). Import the public surface from here:

    from app.gee import EarthEngineClient, initialize_earth_engine, DATASETS
"""

from __future__ import annotations

from app.gee.auth import initialize_earth_engine
from app.gee.client import EarthEngineClient
from app.gee.datasets import (
    DATASETS,
    ELEVATION_DATASET_KEY,
    ERA5_KEY,
    JRC_GLOFAS_FLOOD_HAZARD_KEY,
    JRC_SURFACE_WATER_KEY,
    MODIS_NDVI_KEY,
    OPEN_BUILDINGS_ASSET,
    OPEN_BUILDINGS_DATASET,
    SENTINEL2_KEY,
    TERRACLIMATE_KEY,
    TERRAIN_DEM_KEY,
    VIIRS_FIRE_KEY,
    WORLDCOVER_KEY,
    GEEDataset,
    get_dataset,
)

__all__ = [
    "EarthEngineClient",
    "initialize_earth_engine",
    "DATASETS",
    "ELEVATION_DATASET_KEY",
    "TERRAIN_DEM_KEY",
    "TERRACLIMATE_KEY",
    "ERA5_KEY",
    "SENTINEL2_KEY",
    "MODIS_NDVI_KEY",
    "WORLDCOVER_KEY",
    "JRC_SURFACE_WATER_KEY",
    "JRC_GLOFAS_FLOOD_HAZARD_KEY",
    "VIIRS_FIRE_KEY",
    "OPEN_BUILDINGS_ASSET",
    "OPEN_BUILDINGS_DATASET",
    "GEEDataset",
    "get_dataset",
]
