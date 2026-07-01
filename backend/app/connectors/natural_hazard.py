"""Natural Hazard Connector (SRS §18.6).

Combines the two Prism Earth data paths in one connector (SRS §18.1):

- **Earth Engine raster** (SRS §19.6): ``flood_hazard_class`` and
  ``within_flood_hazard_polygon`` derived from JRC's Global River Flood Hazard
  Maps (Copernicus GloFAS v2.1); ``surface_water_permanence_pct`` from the JRC
  Global Surface Water occurrence band; and ``active_fire_count_10km_24h`` from
  VIIRS active fires in the last 24 hours within 10 km.
- **PostGIS vector** (SRS §20.4): ``nearest_waterbody_distance_m`` /
  ``nearest_waterbody_name`` by nearest-neighbour over OpenStreetMap waterbodies.

No open bulk CWC/NRSC flood-hazard GIS layer exists for Telangana (confirmed by
research 2026-07-01: NRSC's Flood Hazard Zonation Atlas covers Bihar only;
Bhuvan/NDEM's flood layers are login/VPN-gated viewers, not downloadable data).
GloFAS ships a categorical ``depth_category`` band per return period, but its
2–4 value legend is not documented anywhere in JRC's public metadata, so rather
than guess at undocumented codes, this connector derives its own
``flood_hazard_class`` from the fully-documented *depth* bands (metres): the
shortest return period at which the point is modelled as inundated sets the
class (see :data:`_FLOOD_RETURN_PERIODS`) — an explicit, stated Prism Earth
convention, not one attributed to JRC (SRS §16.4 Independence).

Both data paths are injected as protocols so the connector is unit-testable with
fakes (no live PostGIS or Earth Engine). ``wildfire_risk`` is owned by this layer
but not yet servable (no derived model wired) and returns a typed null.
"""

from __future__ import annotations

import asyncio
import datetime as dt
from typing import Protocol

from pydantic import BaseModel, ConfigDict

from app.connectors._spatial import PostgisQueryRunner, nearest
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
    JRC_GLOFAS_FLOOD_HAZARD_KEY,
    JRC_SURFACE_WATER_KEY,
    VIIRS_FIRE_KEY,
    EarthEngineClient,
)
from app.metadata.enums import Layer
from app.models.spatial import WaterBody

logger = get_logger(__name__)

_OSM = "OpenStreetMap"
_GLOFAS = "JRC Global River Flood Hazard Maps"  # must match the registry name exactly
_JRC = "JRC Global Surface Water"
_VIIRS = "VIIRS Active Fires (VNP14A1)"

# Field → (citation dataset, confidence).
_SPEC: dict[str, tuple[str, Confidence]] = {
    "flood_hazard_class": (_GLOFAS, Confidence.MEDIUM),
    "within_flood_hazard_polygon": (_GLOFAS, Confidence.MEDIUM),
    "nearest_waterbody_distance_m": (_OSM, Confidence.HIGH),
    "nearest_waterbody_name": (_OSM, Confidence.MEDIUM),
    "surface_water_permanence_pct": (_JRC, Confidence.HIGH),
    "active_fire_count_10km_24h": (_VIIRS, Confidence.HIGH),
}
_VECTOR_FIELDS = frozenset({"nearest_waterbody_distance_m", "nearest_waterbody_name"})
_RASTER_FIELDS = frozenset(
    {
        "flood_hazard_class",
        "within_flood_hazard_polygon",
        "surface_water_permanence_pct",
        "active_fire_count_10km_24h",
    }
)
_SERVABLE: frozenset[str] = _VECTOR_FIELDS | _RASTER_FIELDS

_FIRE_CONFIDENCE = 7  # VIIRS FireMask ≥ 7 is nominal-or-higher confidence fire.
_FIRE_RADIUS_M = 10_000

# GloFAS return-period depth bands, most-frequent (most hazardous trigger) to
# rarest, paired with the class Prism Earth assigns when that band is the
# *shortest* return period at which the point is modelled as inundated (see the
# module docstring for why this is our own derivation, not a JRC-native code).
_FLOOD_RETURN_PERIODS: tuple[tuple[str, str], ...] = (
    ("RP10_depth", "very_high"),
    ("RP20_depth", "very_high"),
    ("RP50_depth", "high"),
    ("RP75_depth", "high"),
    ("RP100_depth", "moderate"),
    ("RP200_depth", "moderate"),
    ("RP500_depth", "low"),
)


class HazardVectorSample(BaseModel):
    """Waterbody signals from PostGIS."""

    model_config = ConfigDict(frozen=True)

    nearest_waterbody_distance_m: float | None = None
    nearest_waterbody_name: str | None = None


class HazardRasterSample(BaseModel):
    """Flood-hazard, surface-water, and active-fire signals from Earth Engine."""

    model_config = ConfigDict(frozen=True)

    flood_hazard_class: str | None = None
    within_flood_hazard_polygon: bool = False
    surface_water_permanence_pct: float | None = None
    active_fire_count_10km_24h: int = 0


class HazardVectorSource(Protocol):
    """PostGIS point source of waterbody signals (faked in tests)."""

    async def sample(self, lat: float, lng: float) -> HazardVectorSample: ...


class HazardRasterSource(Protocol):
    """Earth Engine point source of flood/surface-water/fire signals (faked in tests)."""

    def sample(self, lat: float, lng: float) -> HazardRasterSample: ...


class PostgisHazardSource(PostgisQueryRunner):
    """PostGIS-backed :class:`HazardVectorSource` (SRS §20.4)."""

    async def sample(self, lat: float, lng: float) -> HazardVectorSample:
        async with self._session() as session:
            water = await nearest(session, WaterBody, lat, lng)
        return HazardVectorSample(
            nearest_waterbody_distance_m=water.distance_m if water is not None else None,
            nearest_waterbody_name=water.row.name if water is not None else None,
        )


class GeeHazardSource:
    """Earth Engine-backed :class:`HazardRasterSource` (SRS §18.6, §19.6)."""

    def __init__(self, *, client: EarthEngineClient | None = None) -> None:
        self._client = client

    def _ensure_client(self) -> EarthEngineClient:
        if self._client is None:
            self._client = EarthEngineClient()
        return self._client

    def sample(self, lat: float, lng: float) -> HazardRasterSample:
        client = self._ensure_client()
        jrc = DATASETS[JRC_SURFACE_WATER_KEY]
        occurrence = client.point_value(jrc, "occurrence", lat, lng, scale=30)
        hazard_class, within_polygon = self._flood_hazard(client, lat, lng)
        return HazardRasterSample(
            flood_hazard_class=hazard_class,
            within_flood_hazard_polygon=within_polygon,
            surface_water_permanence_pct=occurrence,
            active_fire_count_10km_24h=self._active_fire_count(client, lat, lng),
        )

    def _flood_hazard(
        self, client: EarthEngineClient, lat: float, lng: float
    ) -> tuple[str | None, bool]:
        """Sample every GloFAS return-period depth band in a single round trip.

        All 7 bands are fetched with one ``reduceRegion`` + ``getInfo`` call (not
        one per band) to keep Earth Engine usage minimal. ``None``/non-positive
        depth means GloFAS does not model this point as inundated at that return
        period (SRS §15.17); no positive depth at any return period (including
        the rare 500-year event) means the point is outside the flood model's
        hazard extent entirely.
        """
        ee = client.ee
        glofas = DATASETS[JRC_GLOFAS_FLOOD_HAZARD_KEY]
        bands = [band for band, _ in _FLOOD_RETURN_PERIODS]
        image = ee.ImageCollection(glofas.ee_id).select(bands).mosaic()
        point = ee.Geometry.Point([lng, lat])
        depths = image.reduceRegion(
            reducer=ee.Reducer.mean(), geometry=point, scale=90, maxPixels=1_000_000_000
        ).getInfo()
        for band, hazard_class in _FLOOD_RETURN_PERIODS:
            depth = depths.get(band)
            if depth is not None and depth > 0:
                return hazard_class, True
        return None, False

    def _active_fire_count(self, client: EarthEngineClient, lat: float, lng: float) -> int:
        ee = client.ee
        viirs = DATASETS[VIIRS_FIRE_KEY]
        end = ee.Date(dt.datetime.now(dt.UTC))
        start = end.advance(-1, "day")
        fires = ee.ImageCollection(viirs.ee_id).filterDate(start, end).select("FireMask")
        # VIIRS active-fire has real processing latency, so the exact last 24h
        # window can have zero images; `.max()` on an empty collection yields a
        # zero-band image that `.gte()` rejects. Branch server-side (one round
        # trip, not a client-side pre-check) so an empty window resolves to "no
        # fire detected" rather than erroring (SRS §15.17).
        no_fire = ee.Image(0).rename("FireMask")
        mask = ee.Image(
            ee.Algorithms.If(fires.size().gt(0), fires.max().gte(_FIRE_CONFIDENCE), no_fire)
        )
        region = ee.Geometry.Point([lng, lat]).buffer(_FIRE_RADIUS_M)
        reduced = mask.reduceRegion(
            reducer=ee.Reducer.sum(), geometry=region, scale=500, maxPixels=1_000_000_000
        )
        count = reduced.get("FireMask").getInfo()
        return 0 if count is None else int(count)


class NaturalHazardConnector(BaseConnector):
    """Flood, surface-water, and fire hazard signals (SRS §18.6)."""

    name = "natural_hazard_connector"
    layer = Layer.NATURAL_HAZARD

    def __init__(self, *, vector: HazardVectorSource, raster: HazardRasterSource) -> None:
        self._vector = vector
        self._raster = raster

    def servable_fields(self) -> frozenset[str]:
        return _SERVABLE

    async def fetch(self, fields: list[str], context: FetchContext) -> list[FieldResult]:
        await self.validate(fields)
        need_vector = any(f in _VECTOR_FIELDS for f in fields)
        need_raster = any(f in _RASTER_FIELDS for f in fields)

        vector = (
            await self._vector.sample(context.lat, context.lng)
            if need_vector
            else HazardVectorSample()
        )
        raster = (
            await asyncio.to_thread(self._raster.sample, context.lat, context.lng)
            if need_raster
            else HazardRasterSample()
        )
        values = {**vector.model_dump(), **raster.model_dump()}

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
                    null_reason=None if value is not None else _null_reason(field),
                )
            )
        return results

    async def metadata(self) -> ConnectorMetadata:
        return ConnectorMetadata(
            name=self.name,
            layer=self.layer,
            datasets=(_OSM, _GLOFAS, _JRC, _VIIRS),
            servable_fields=tuple(sorted(_SERVABLE)),
        )


def _null_reason(field: str) -> NullReason:
    """A raster miss is out-of-coverage; a vector miss is feature-absent (SRS §15.17)."""
    return NullReason.OUTSIDE_COVERAGE if field in _RASTER_FIELDS else NullReason.DATA_UNAVAILABLE
