"""Land Cover Connector (SRS §18.5).

Vegetation and land-use signals sampled from Earth Engine (SRS §18.5, §19.6):
``ndvi_current`` from a recent Sentinel-2 composite, ``ndvi_historical`` from
MODIS, and ``dominant_land_cover`` / ``tree_canopy_pct`` / ``wetland_presence``
from the ESA WorldCover classification. Mirrors the Terrain connector: it depends
on a :class:`LandCoverSource` protocol, so it is unit-testable with a fake source
and each field cites the dataset that produced it (SRS §16.4).

``cropland_class`` (and the region-gated ``dominant_crop_class``) are owned by
this layer but not yet servable — no crop-classification source is wired — so the
orchestrator returns them as typed nulls (SRS §15.17).
"""

from __future__ import annotations

import asyncio
from typing import Protocol

from pydantic import BaseModel, ConfigDict

from app.connectors.base import (
    BaseConnector,
    Confidence,
    ConnectorMetadata,
    FetchContext,
    FieldResult,
    NullReason,
)
from app.core.logging import get_logger
from app.gee import (
    DATASETS,
    MODIS_NDVI_KEY,
    SENTINEL2_KEY,
    WORLDCOVER_KEY,
    EarthEngineClient,
)
from app.metadata.enums import Layer

logger = get_logger(__name__)

_SENTINEL2 = "Copernicus Sentinel-2"
_MODIS = "MODIS Vegetation Indices (MOD13Q1)"
_WORLDCOVER = "ESA WorldCover"

_SPEC: dict[str, tuple[str, Confidence]] = {
    "ndvi_current": (_SENTINEL2, Confidence.HIGH),
    "ndvi_historical": (_MODIS, Confidence.MEDIUM),
    "dominant_land_cover": (_WORLDCOVER, Confidence.HIGH),
    "tree_canopy_pct": (_WORLDCOVER, Confidence.MEDIUM),
    "wetland_presence": (_WORLDCOVER, Confidence.MEDIUM),
}
_SERVABLE: frozenset[str] = frozenset(_SPEC)

# ESA WorldCover v200 class codes → catalog land-cover names.
_WORLDCOVER_CLASSES: dict[int, str] = {
    10: "tree_cover",
    20: "shrubland",
    30: "grassland",
    40: "cropland",
    50: "built_up",
    60: "bare",
    70: "snow_and_ice",
    80: "water",
    90: "herbaceous_wetland",
    95: "mangroves",
    100: "moss_and_lichen",
}
_TREE_CLASS = 10
_WETLAND_CLASSES = frozenset({90, 95})


class LandCoverSample(BaseModel):
    """Land-cover signals at a point."""

    model_config = ConfigDict(frozen=True)

    ndvi_current: float | None = None
    ndvi_historical: float | None = None
    dominant_land_cover: str | None = None
    tree_canopy_pct: float | None = None
    wetland_presence: bool | None = None


class LandCoverSource(Protocol):
    """A point source of land-cover values (implemented by GEE; faked in tests)."""

    def sample(self, lat: float, lng: float) -> LandCoverSample: ...


class GeeLandCoverSource:
    """Earth Engine-backed :class:`LandCoverSource` (SRS §18.5, §19.6)."""

    def __init__(self, *, client: EarthEngineClient | None = None) -> None:
        self._client = client

    def _ensure_client(self) -> EarthEngineClient:
        if self._client is None:
            self._client = EarthEngineClient()
        return self._client

    def sample(self, lat: float, lng: float) -> LandCoverSample:
        """One Earth Engine round trip for all four signals.

        Sentinel-2 NDVI, MODIS NDVI, and the two WorldCover reductions (point
        class + 500 m tree-fraction) are independent computed expressions over
        different images and geometries — Earth Engine can't merge them into one
        ``reduceRegion`` (that takes a single geometry), but it *can* evaluate
        several independent expressions together: bundle each into one
        ``ee.Dictionary`` and call ``getInfo()`` once, which is a single request
        regardless of how many sub-expressions it contains (SRS §19.9).
        """
        client = self._ensure_client()
        ee = client.ee
        point = ee.Geometry.Point([lng, lat])

        s2 = DATASETS[SENTINEL2_KEY]
        composite = (
            ee.ImageCollection(s2.ee_id)
            .filter(ee.Filter.lt("CLOUDY_PIXEL_PERCENTAGE", 30))
            .median()
        )
        ndvi_current_img = composite.normalizedDifference(["B8", "B4"]).rename("ndvi")

        modis = DATASETS[MODIS_NDVI_KEY]
        ndvi_historical_img = ee.ImageCollection(modis.ee_id).select("NDVI").mean()

        wc = DATASETS[WORLDCOVER_KEY]
        wc_image = ee.ImageCollection(wc.ee_id).select("Map").mosaic()
        is_tree = wc_image.eq(_TREE_CLASS)
        tree_region = point.buffer(500)

        combined = ee.Dictionary(
            {
                "ndvi_current": ndvi_current_img.reduceRegion(
                    reducer=ee.Reducer.mean(), geometry=point, scale=10, maxPixels=1_000_000_000
                ).get("ndvi"),
                "ndvi_historical": ndvi_historical_img.reduceRegion(
                    reducer=ee.Reducer.mean(), geometry=point, scale=250, maxPixels=1_000_000_000
                ).get("NDVI"),
                "worldcover_class": wc_image.reduceRegion(
                    reducer=ee.Reducer.mean(), geometry=point, scale=10, maxPixels=1_000_000_000
                ).get("Map"),
                "tree_fraction": is_tree.reduceRegion(
                    reducer=ee.Reducer.mean(),
                    geometry=tree_region,
                    scale=10,
                    maxPixels=1_000_000_000,
                ).get("Map"),
            }
        ).getInfo()

        ndvi_current = combined.get("ndvi_current")
        ndvi_historical_raw = combined.get("ndvi_historical")
        # MODIS NDVI is scaled ×10⁴.
        ndvi_historical = None if ndvi_historical_raw is None else ndvi_historical_raw * 0.0001
        land_class_raw = combined.get("worldcover_class")
        land_class = None if land_class_raw is None else int(round(land_class_raw))
        tree_fraction = combined.get("tree_fraction")

        return LandCoverSample(
            ndvi_current=None if ndvi_current is None else float(ndvi_current),
            ndvi_historical=ndvi_historical,
            dominant_land_cover=_WORLDCOVER_CLASSES.get(land_class) if land_class else None,
            tree_canopy_pct=None if tree_fraction is None else float(tree_fraction) * 100.0,
            wetland_presence=None if land_class is None else land_class in _WETLAND_CLASSES,
        )


class LandCoverConnector(BaseConnector):
    """Vegetation and land-use signals via Earth Engine (SRS §18.5)."""

    name = "land_cover_connector"
    layer = Layer.LAND_COVER

    def __init__(self, source: LandCoverSource) -> None:
        self._source = source

    def servable_fields(self) -> frozenset[str]:
        return _SERVABLE

    async def fetch(self, fields: list[str], context: FetchContext) -> list[FieldResult]:
        await self.validate(fields)
        sample = await asyncio.to_thread(self._source.sample, context.lat, context.lng)
        values = sample.model_dump()

        results: list[FieldResult] = []
        for field in fields:
            dataset, confidence = _SPEC[field]
            value = values[field]
            results.append(
                FieldResult(
                    field=field,
                    value=value,
                    dataset=dataset,
                    confidence=confidence,
                    null_reason=None if value is not None else NullReason.OUTSIDE_COVERAGE,
                )
            )
        return results

    async def metadata(self) -> ConnectorMetadata:
        return ConnectorMetadata(
            name=self.name,
            layer=self.layer,
            datasets=(_SENTINEL2, _MODIS, _WORLDCOVER),
            servable_fields=tuple(sorted(_SERVABLE)),
        )
