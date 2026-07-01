"""Climate Connector (SRS §18.4).

Long-term climate indicators sampled from Earth Engine (SRS §18.4, §19.6):
``annual_rainfall_mm``, ``annual_temperature_c``, ``aridity_index``, and
``evapotranspiration`` from TerraClimate, and ``wind_speed`` from ERA5. Like the
Terrain connector, it depends on a :class:`ClimateSource` protocol rather than
the Earth Engine client directly, so it is unit-testable with a fake source (no
live credentials), and each field cites the exact dataset that produced it
(SRS §16.4).
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
from app.gee import DATASETS, ERA5_KEY, TERRACLIMATE_KEY, EarthEngineClient
from app.metadata.enums import Layer

logger = get_logger(__name__)

_TERRACLIMATE = "TerraClimate"
_ERA5 = "ERA5"

# Field → (citation dataset, confidence). Rainfall/temperature are near-direct
# observations (high); the ratio and modelled-flux fields are medium.
_SPEC: dict[str, tuple[str, Confidence]] = {
    "annual_rainfall_mm": (_TERRACLIMATE, Confidence.HIGH),
    "annual_temperature_c": (_TERRACLIMATE, Confidence.HIGH),
    "aridity_index": (_TERRACLIMATE, Confidence.MEDIUM),
    "evapotranspiration": (_TERRACLIMATE, Confidence.MEDIUM),
    "wind_speed": (_ERA5, Confidence.MEDIUM),
}
_SERVABLE: frozenset[str] = frozenset(_SPEC)

# Native pixel sizes used as the reduction scale (metres).
_TERRACLIMATE_SCALE = 4638.0
_ERA5_SCALE = 11132.0


class ClimateSample(BaseModel):
    """Climate indicators at a point (annualized, SI units)."""

    model_config = ConfigDict(frozen=True)

    annual_rainfall_mm: float | None = None
    annual_temperature_c: float | None = None
    aridity_index: float | None = None
    evapotranspiration: float | None = None
    wind_speed: float | None = None


class ClimateSource(Protocol):
    """A point source of climate values (implemented by GEE; faked in tests)."""

    def sample(self, lat: float, lng: float) -> ClimateSample: ...


class GeeClimateSource:
    """Earth Engine-backed :class:`ClimateSource` (SRS §18.4, §19.6).

    TerraClimate stores monthly climatologies; annual totals are the monthly
    mean ×12, temperature bands are stored in units of 0.1 °C, and the aridity
    index is the UNEP ratio ``P / PET``. Wind speed is the magnitude of the ERA5
    10 m u/v components. Each raw sample is ``None`` where the dataset has no
    coverage (SRS §15.17), which the connector maps to a typed null.
    """

    def __init__(self, *, client: EarthEngineClient | None = None) -> None:
        # Lazily created so missing credentials surface as a fetch-time partial
        # failure, not an import/construction crash (SRS §15.16, §19.10).
        self._client = client

    def _ensure_client(self) -> EarthEngineClient:
        if self._client is None:
            self._client = EarthEngineClient()
        return self._client

    def sample(self, lat: float, lng: float) -> ClimateSample:
        client = self._ensure_client()

        # Two GEE round trips total (one per source collection), not one per
        # band: each collection's needed bands are fetched together via
        # `collection_mean_multi`, which issues a single multi-band
        # `reduceRegion` rather than a separate request per band.
        tc = DATASETS[TERRACLIMATE_KEY]
        tc_bands = client.collection_mean_multi(
            tc, ["pr", "tmmx", "tmmn", "aet", "pet"], lat, lng, scale=_TERRACLIMATE_SCALE
        )
        ppt = tc_bands["pr"]  # mm/month (band is named "pr", precipitation)
        tmmx = tc_bands["tmmx"]  # 0.1 °C
        tmmn = tc_bands["tmmn"]  # 0.1 °C
        aet = tc_bands["aet"]  # 0.1 mm/month
        pet = tc_bands["pet"]  # 0.1 mm/month

        annual_rainfall = None if ppt is None else ppt * 12.0
        annual_temp = None if tmmx is None or tmmn is None else (tmmx + tmmn) / 2.0 * 0.1
        evapotranspiration = None if aet is None else aet * 0.1 * 12.0
        annual_pet = None if pet is None else pet * 0.1 * 12.0
        aridity = (
            None if annual_rainfall is None or not annual_pet else annual_rainfall / annual_pet
        )

        era5 = DATASETS[ERA5_KEY]
        era5_bands = client.collection_mean_multi(
            era5,
            ["u_component_of_wind_10m", "v_component_of_wind_10m"],
            lat,
            lng,
            scale=_ERA5_SCALE,
        )
        u = era5_bands["u_component_of_wind_10m"]
        v = era5_bands["v_component_of_wind_10m"]
        wind_speed = None if u is None or v is None else math.hypot(u, v)

        return ClimateSample(
            annual_rainfall_mm=annual_rainfall,
            annual_temperature_c=annual_temp,
            aridity_index=aridity,
            evapotranspiration=evapotranspiration,
            wind_speed=wind_speed,
        )


class ClimateConnector(BaseConnector):
    """Climate indicators from TerraClimate + ERA5 via Earth Engine (SRS §18.4)."""

    name = "climate_connector"
    layer = Layer.CLIMATE

    def __init__(self, source: ClimateSource) -> None:
        self._source = source

    def servable_fields(self) -> frozenset[str]:
        return _SERVABLE

    async def fetch(self, fields: list[str], context: FetchContext) -> list[FieldResult]:
        await self.validate(fields)
        # GEE calls are blocking; run them off the event loop (SRS §15.12).
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
            datasets=(_TERRACLIMATE, _ERA5),
            servable_fields=tuple(sorted(_SERVABLE)),
        )
