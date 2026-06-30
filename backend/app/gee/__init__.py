"""Google Earth Engine integration (SRS §19).

Service-account authentication (§19.3), the supported-dataset registry (§19.4),
and a thin point-sampling client (§19.6). Import the public surface from here:

    from app.gee import EarthEngineClient, initialize_earth_engine, DATASETS
"""

from __future__ import annotations

from app.gee.auth import initialize_earth_engine
from app.gee.client import EarthEngineClient
from app.gee.datasets import DATASETS, ELEVATION_DATASET_KEY, GEEDataset, get_dataset

__all__ = [
    "EarthEngineClient",
    "initialize_earth_engine",
    "DATASETS",
    "ELEVATION_DATASET_KEY",
    "GEEDataset",
    "get_dataset",
]
