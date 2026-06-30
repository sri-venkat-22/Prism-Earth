"""Thin Earth Engine client wrapper (SRS §19.1, §19.6, §19.7).

A minimal abstraction over the Earth Engine API for point queries — the
foundation the Terrain/Climate/Land-Cover/Hazard connectors build on in Phase 3.
Version 1 implements the §19.6 workflow for point sampling:

    coordinates → dataset selection → spatial filter → value extraction.

All spatial operations use WGS84 / EPSG:4326 (SRS §19.7). The wrapper is
constructed with an injectable ``ee`` module so it can be unit-tested without
live credentials.
"""

from __future__ import annotations

from typing import Any

from app.core.config import Settings, get_settings
from app.core.logging import get_logger
from app.gee.auth import _import_ee, initialize_earth_engine
from app.gee.datasets import DATASETS, ELEVATION_DATASET_KEY, GEEDataset

logger = get_logger(__name__)


class EarthEngineClient:
    """Point-sampling wrapper over the Earth Engine API (SRS §19.6)."""

    def __init__(
        self,
        *,
        ee_module: Any | None = None,
        settings: Settings | None = None,
        auto_initialize: bool = True,
    ) -> None:
        self._settings = settings or get_settings()
        self._ee = ee_module if ee_module is not None else _import_ee()
        if auto_initialize:
            initialize_earth_engine(self._settings, ee_module=self._ee)

    # --- Image selection (SRS §19.6 dataset selection) --------------------- #
    def _image(self, dataset: GEEDataset, band: str) -> Any:
        """Resolve a dataset + band to a single Earth Engine image."""
        if dataset.is_collection:
            return self._ee.ImageCollection(dataset.ee_id).select(band).mosaic()
        return self._ee.Image(dataset.ee_id).select(band)

    # --- Point sampling (SRS §19.6 value extraction) ----------------------- #
    def point_value(
        self,
        dataset: GEEDataset,
        band: str,
        lat: float,
        lng: float,
        *,
        scale: float | None = None,
    ) -> float | None:
        """Sample one band of a dataset at a coordinate (SRS §19.6, §19.7).

        Returns the reduced (mean) pixel value, or ``None`` where the dataset
        has no coverage at the point (SRS §15.17 null handling).
        """
        point = self._ee.Geometry.Point([lng, lat])  # WGS84 (lng, lat)
        image = self._image(dataset, band)
        reduced = image.reduceRegion(
            reducer=self._ee.Reducer.mean(),
            geometry=point,
            scale=scale or 30,
            maxPixels=1_000_000_000,
        )
        value = reduced.get(band).getInfo()
        return None if value is None else float(value)

    def sample_elevation(self, lat: float, lng: float) -> float | None:
        """Smoke-test: sample elevation at a coordinate (SRS §19, DoD #3)."""
        dataset = DATASETS[ELEVATION_DATASET_KEY]
        value = self.point_value(dataset, dataset.bands[0], lat, lng, scale=30)
        logger.info("gee.sample_elevation", lat=lat, lng=lng, value=value)
        return value
