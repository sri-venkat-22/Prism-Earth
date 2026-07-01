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

    @property
    def ee(self) -> Any:
        """The bound Earth Engine module (connectors build queries against it)."""
        return self._ee

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

    # --- Terrain derivatives (SRS §18.3 slope/aspect from a DEM) ----------- #
    def reduce_point(
        self, image: Any, band: str, lat: float, lng: float, *, scale: float
    ) -> float | None:
        """Mean-reduce one band of an arbitrary image at a point (SRS §19.6).

        Public so the Phase 4 connectors (Climate/Land-Cover/Hazard) can sample
        images they build themselves — e.g. a temporally reduced collection or a
        derived index — against :attr:`ee`, mirroring the Terrain connector.
        """
        point = self._ee.Geometry.Point([lng, lat])  # WGS84 (lng, lat)
        reduced = image.reduceRegion(
            reducer=self._ee.Reducer.mean(),
            geometry=point,
            scale=scale,
            maxPixels=1_000_000_000,
        )
        value = reduced.get(band).getInfo()
        return None if value is None else float(value)

    # Backwards-compatible internal alias (kept for the terrain sampler below).
    _reduce_image = reduce_point

    def collection_mean(
        self, dataset: GEEDataset, band: str, lat: float, lng: float, *, scale: float | None = None
    ) -> float | None:
        """Temporally mean-reduce a collection band, then sample at the point.

        Unlike :meth:`point_value` (which mosaics — the *latest* pixel), this
        averages every image in the collection first, giving the long-term
        climatological mean the Climate/Land-Cover connectors need (SRS §18.4).
        """
        image = self._ee.ImageCollection(dataset.ee_id).select(band).mean()
        return self.reduce_point(image, band, lat, lng, scale=scale or 30)

    def collection_mean_multi(
        self,
        dataset: GEEDataset,
        bands: list[str],
        lat: float,
        lng: float,
        *,
        scale: float | None = None,
    ) -> dict[str, float | None]:
        """Temporally mean-reduce *every* band in one round trip (SRS §19.9).

        Earth Engine calls are network round trips; a connector needing several
        bands from the same collection (e.g. Climate's rainfall/temperature/
        evapotranspiration) should ask for them together here rather than call
        :meth:`collection_mean` once per band, which multiplies request count for
        no benefit — the server already computes a multi-band ``reduceRegion`` in
        a single pass.
        """
        image = self._ee.ImageCollection(dataset.ee_id).select(bands).mean()
        point = self._ee.Geometry.Point([lng, lat])  # WGS84 (lng, lat)
        reduced = image.reduceRegion(
            reducer=self._ee.Reducer.mean(),
            geometry=point,
            scale=scale or 30,
            maxPixels=1_000_000_000,
        ).getInfo()
        return {
            band: (None if reduced.get(band) is None else float(reduced[band])) for band in bands
        }

    def sample_terrain(
        self, dataset: GEEDataset, lat: float, lng: float, *, scale: float = 30
    ) -> dict[str, float | None]:
        """Sample elevation and its slope/aspect derivatives from a DEM.

        Slope and aspect are computed on-the-fly with ``ee.Terrain`` (SRS §18.3),
        so all three terrain values come from the same elevation source. Each
        value is ``None`` where the DEM has no coverage (SRS §15.17).
        """
        dem = self._image(dataset, dataset.bands[0])
        elevation = self._reduce_image(dem, dataset.bands[0], lat, lng, scale=scale)
        slope = self._reduce_image(self._ee.Terrain.slope(dem), "slope", lat, lng, scale=scale)
        aspect = self._reduce_image(self._ee.Terrain.aspect(dem), "aspect", lat, lng, scale=scale)
        logger.info(
            "gee.sample_terrain",
            lat=lat,
            lng=lng,
            dataset=dataset.key,
            elevation=elevation,
            slope=slope,
            aspect=aspect,
        )
        return {"elevation": elevation, "slope": slope, "aspect": aspect}
