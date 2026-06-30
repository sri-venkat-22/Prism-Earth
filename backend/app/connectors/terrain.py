"""Terrain Connector (SRS §18.3).

Provides terrain and elevation information sampled from a Digital Elevation
Model via Google Earth Engine (SRS §18.3, §19.6). Version 1 serves
``elevation``, ``slope``, and ``aspect`` — elevation is sampled directly and
slope/aspect are derived with ``ee.Terrain`` from the same DEM, so all three
share one provenance source (SRS §16.4 Accuracy).

The connector depends on a :class:`TerrainSource` protocol rather than the Earth
Engine client directly, so it is unit-testable with a fake source (no live
credentials), mirroring the GEE client's injectable design.
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
from app.gee import DATASETS, TERRAIN_DEM_KEY, EarthEngineClient, GEEDataset
from app.metadata.enums import Layer

logger = get_logger(__name__)

# Fields the connector can retrieve today (a subset of the §18.3 terrain set).
_SERVABLE: frozenset[str] = frozenset({"elevation", "slope", "aspect"})

# Confidence by field: a direct DEM sample is high; geometric derivatives medium.
_CONFIDENCE: dict[str, Confidence] = {
    "elevation": Confidence.HIGH,
    "slope": Confidence.MEDIUM,
    "aspect": Confidence.MEDIUM,
}


class TerrainSample(BaseModel):
    """Elevation and its derivatives at a point (metres / degrees)."""

    model_config = ConfigDict(frozen=True)

    elevation: float | None = None
    slope: float | None = None
    aspect: float | None = None


class TerrainSource(Protocol):
    """A point source of terrain values (implemented by GEE; faked in tests)."""

    def sample(self, lat: float, lng: float) -> TerrainSample: ...

    @property
    def dataset_name(self) -> str: ...


class GeeTerrainSource:
    """Earth Engine-backed :class:`TerrainSource` sampling a DEM (SRS §18.3)."""

    def __init__(
        self, *, client: EarthEngineClient | None = None, dataset: GEEDataset | None = None
    ) -> None:
        self._dataset = dataset or DATASETS[TERRAIN_DEM_KEY]
        # The client is created lazily so missing GEE credentials surface as a
        # connector failure at fetch time (a partial failure) rather than an
        # import/construction crash (SRS §15.16, §19.10).
        self._client = client

    @property
    def dataset_name(self) -> str:
        return self._dataset.name

    def _ensure_client(self) -> EarthEngineClient:
        if self._client is None:
            self._client = EarthEngineClient()
        return self._client

    def sample(self, lat: float, lng: float) -> TerrainSample:
        values = self._ensure_client().sample_terrain(self._dataset, lat, lng)
        return TerrainSample(**values)


class TerrainConnector(BaseConnector):
    """Elevation/slope/aspect from a DEM via Earth Engine (SRS §18.3)."""

    name = "terrain_connector"
    layer = Layer.TERRAIN

    def __init__(self, source: TerrainSource) -> None:
        self._source = source

    def servable_fields(self) -> frozenset[str]:
        return _SERVABLE

    async def fetch(self, fields: list[str], context: FetchContext) -> list[FieldResult]:
        await self.validate(fields)
        # GEE calls are blocking; run them off the event loop so connectors fan
        # out concurrently (SRS §15.12). A failure here propagates to the
        # orchestrator as a partial failure (SRS §18.13).
        sample = await asyncio.to_thread(self._source.sample, context.lat, context.lng)
        dataset = self._source.dataset_name
        values = {"elevation": sample.elevation, "slope": sample.slope, "aspect": sample.aspect}

        results: list[FieldResult] = []
        for field in fields:
            value = values[field]
            results.append(
                FieldResult(
                    field=field,
                    value=value,
                    dataset=dataset,
                    confidence=_CONFIDENCE[field],
                    null_reason=None if value is not None else NullReason.OUTSIDE_COVERAGE,
                )
            )
        return results

    async def metadata(self) -> ConnectorMetadata:
        return ConnectorMetadata(
            name=self.name,
            layer=self.layer,
            datasets=(self._source.dataset_name,),
            servable_fields=tuple(sorted(_SERVABLE)),
        )
