"""Built Environment Connector (SRS §18, Built Environment layer).

Building-footprint signals from the Google Open Buildings v3 vector dataset via
Earth Engine: ``building_present``, ``building_footprint_area_m2``,
``building_count_250m``, ``nearest_building_distance_m``, and
``built_up_area_pct_1km``. Open Buildings covers all of India, so these are
nationwide.

Open Buildings is a vector ``FeatureCollection`` (not a raster band), so the
connector queries the asset directly through :class:`GeeBuildingsSource` and
cites the ``Google Open Buildings`` registry entry. As with every connector it
depends on a :class:`BuildingsSource` protocol and is unit-testable with a fake.
"""

from __future__ import annotations

import asyncio
import math
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
from app.gee import EarthEngineClient
from app.gee.datasets import OPEN_BUILDINGS_ASSET, OPEN_BUILDINGS_DATASET
from app.metadata.enums import Layer

logger = get_logger(__name__)

_OPEN_BUILDINGS = OPEN_BUILDINGS_DATASET

_SPEC: dict[str, Confidence] = {
    "building_present": Confidence.HIGH,
    "building_footprint_area_m2": Confidence.MEDIUM,
    "building_count_250m": Confidence.HIGH,
    "nearest_building_distance_m": Confidence.MEDIUM,
    "built_up_area_pct_1km": Confidence.MEDIUM,
}
_SERVABLE: frozenset[str] = frozenset(_SPEC)

_COUNT_RADIUS_M = 250
_SEARCH_RADIUS_M = 2000
_BUILTUP_RADIUS_M = 1000
_AREA_PROPERTY = "area_in_meters"


class BuildingSample(BaseModel):
    """Building-footprint signals at a point."""

    model_config = ConfigDict(frozen=True)

    building_present: bool = False
    building_footprint_area_m2: float | None = None
    building_count_250m: int = 0
    nearest_building_distance_m: float | None = None
    built_up_area_pct_1km: float = 0.0


class BuildingsSource(Protocol):
    """A point source of building-footprint stats (implemented by GEE)."""

    def sample(self, lat: float, lng: float) -> BuildingSample: ...


class GeeBuildingsSource:
    """Earth Engine-backed :class:`BuildingsSource` over Open Buildings v3."""

    def __init__(self, *, client: EarthEngineClient | None = None) -> None:
        self._client = client

    def _ensure_client(self) -> EarthEngineClient:
        if self._client is None:
            self._client = EarthEngineClient()
        return self._client

    def sample(self, lat: float, lng: float) -> BuildingSample:
        """One Earth Engine round trip for all five signals.

        The original implementation issued up to six sequential ``getInfo()``
        calls (present, footprint, count, a conditional nearby-check, nearest,
        built-up sum). Every one of those is an independent aggregate over a
        ``FeatureCollection`` filter, so they bundle into a single
        ``ee.Dictionary`` evaluated with one ``getInfo()`` (SRS §19.9) — and
        computing ``nearest`` from the *same* 2 km-buffered collection
        unconditionally also removes the need for the old present-implies-zero
        special case: a building containing the point has distance 0 to it by
        definition, so the aggregate already yields 0.0 in that case.
        """
        ee = self._ensure_client().ee
        buildings = ee.FeatureCollection(OPEN_BUILDINGS_ASSET)
        point = ee.Geometry.Point([lng, lat])

        containing = buildings.filterBounds(point)
        count_area = buildings.filterBounds(point.buffer(_COUNT_RADIUS_M))
        builtup_area = buildings.filterBounds(point.buffer(_BUILTUP_RADIUS_M))
        nearby = buildings.filterBounds(point.buffer(_SEARCH_RADIUS_M))
        nearby_with_dist = nearby.map(
            lambda f: ee.Feature(None, {"dist": f.geometry().distance(point)})
        )

        combined = ee.Dictionary(
            {
                "present_count": containing.size(),
                "footprint_sum": containing.aggregate_sum(_AREA_PROPERTY),
                "count_250m": count_area.size(),
                "builtup_footprint_sum": builtup_area.aggregate_sum(_AREA_PROPERTY),
                "nearest_dist": nearby_with_dist.aggregate_min("dist"),
            }
        ).getInfo()

        present = bool(combined["present_count"])
        buffer_area_m2 = math.pi * _BUILTUP_RADIUS_M**2
        builtup_sum = combined.get("builtup_footprint_sum") or 0.0
        nearest_dist = combined.get("nearest_dist")

        return BuildingSample(
            building_present=present,
            building_footprint_area_m2=(float(combined["footprint_sum"]) if present else None),
            building_count_250m=int(combined["count_250m"]),
            nearest_building_distance_m=(None if nearest_dist is None else float(nearest_dist)),
            built_up_area_pct_1km=float(builtup_sum) / buffer_area_m2 * 100.0,
        )


class BuiltEnvironmentConnector(BaseConnector):
    """Building-footprint signals from Google Open Buildings (SRS §18)."""

    name = "built_environment_connector"
    layer = Layer.BUILT_ENVIRONMENT

    def __init__(self, source: BuildingsSource) -> None:
        self._source = source

    def servable_fields(self) -> frozenset[str]:
        return _SERVABLE

    async def fetch(self, fields: list[str], context: FetchContext) -> list[FieldResult]:
        await self.validate(fields)
        sample = await asyncio.to_thread(self._source.sample, context.lat, context.lng)
        values = sample.model_dump()

        results: list[FieldResult] = []
        for field in fields:
            value = values[field]
            results.append(
                FieldResult(
                    field=field,
                    value=value,
                    dataset=_OPEN_BUILDINGS,
                    confidence=_SPEC[field],
                    null_reason=None if value is not None else NullReason.OUTSIDE_COVERAGE,
                )
            )
        return results

    async def metadata(self) -> ConnectorMetadata:
        return ConnectorMetadata(
            name=self.name,
            layer=self.layer,
            datasets=(_OPEN_BUILDINGS,),
            servable_fields=tuple(sorted(_SERVABLE)),
        )
