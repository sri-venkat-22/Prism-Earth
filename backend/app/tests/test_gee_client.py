"""Earth Engine client + auth tests (SRS §19.3, §19.4, §19.6).

Uses an injected fake ``ee`` module so the wrapper is exercised without live
credentials or network access.
"""

from __future__ import annotations

import pytest

from app.core.config import Settings
from app.core.errors import AuthenticationError
from app.gee import DATASETS, EarthEngineClient
from app.gee.auth import initialize_earth_engine, reset_initialized


# --------------------------------------------------------------------------- #
# Fake ee module                                                              #
# --------------------------------------------------------------------------- #
class _FakeNumber:
    def __init__(self, value: float | None) -> None:
        self._value = value

    def getInfo(self) -> float | None:  # noqa: N802 (mirrors ee API)
        return self._value


class _FakeReduced:
    def __init__(self, value: float | None) -> None:
        self._value = value

    def get(self, band: str) -> _FakeNumber:
        return _FakeNumber(self._value)


class _FakeImage:
    def __init__(self, value: float | None) -> None:
        self._value = value

    def select(self, band: str) -> _FakeImage:
        return self

    def mosaic(self) -> _FakeImage:
        return self

    def reduceRegion(self, **kwargs: object) -> _FakeReduced:  # noqa: N802
        return _FakeReduced(self._value)


class _FakeGeometry:
    @staticmethod
    def Point(coords: list[float]) -> tuple[str, tuple[float, ...]]:  # noqa: N802
        return ("Point", tuple(coords))


class _FakeReducer:
    @staticmethod
    def mean() -> str:
        return "mean"


class FakeEE:
    Geometry = _FakeGeometry
    Reducer = _FakeReducer

    def __init__(self, value: float | None = 542.16) -> None:
        self._value = value
        self.initialized = False
        self.init_kwargs: dict[str, object] | None = None
        self.credentials: tuple[object, ...] | None = None

    def Image(self, asset_id: str) -> _FakeImage:  # noqa: N802
        return _FakeImage(self._value)

    def ImageCollection(self, asset_id: str) -> _FakeImage:  # noqa: N802
        return _FakeImage(self._value)

    def ServiceAccountCredentials(self, account: str, key_file: str):  # noqa: N802
        self.credentials = (account, key_file)
        return self.credentials

    def Initialize(self, credentials: object, **kwargs: object) -> None:  # noqa: N802
        self.initialized = True
        self.init_kwargs = kwargs


@pytest.fixture(autouse=True)
def _reset_auth() -> None:
    reset_initialized()


# --------------------------------------------------------------------------- #
# Dataset registry (SRS §19.4)                                                #
# --------------------------------------------------------------------------- #
def test_supported_datasets_registered() -> None:
    required = {
        "sentinel2",
        "terraclimate",
        "jrc_surface_water",
        "copernicus_dem",
        "modis_vegetation",
        "viirs_fire",
        "srtm",
    }
    assert required <= set(DATASETS)
    for dataset in DATASETS.values():
        assert dataset.ee_id
        assert dataset.bands  # at least one band for sampling
        assert dataset.source_url


# --------------------------------------------------------------------------- #
# Authentication (SRS §19.3)                                                   #
# --------------------------------------------------------------------------- #
def test_initialize_requires_configuration() -> None:
    settings = Settings(earth_engine_service_account=None, earth_engine_key_file=None)
    with pytest.raises(AuthenticationError):
        initialize_earth_engine(settings, ee_module=FakeEE())


def test_initialize_uses_service_account_and_is_idempotent() -> None:
    settings = Settings(
        earth_engine_service_account="prism@example.iam.gserviceaccount.com",
        earth_engine_key_file="/tmp/key.json",
        earth_engine_project="prism-earth",
    )
    fake = FakeEE()
    initialize_earth_engine(settings, ee_module=fake)
    assert fake.initialized is True
    assert fake.credentials == (
        "prism@example.iam.gserviceaccount.com",
        "/tmp/key.json",
    )
    assert fake.init_kwargs == {"project": "prism-earth"}

    # Second call is a no-op (idempotent) — re-init would flip this fake.
    second = FakeEE()
    initialize_earth_engine(settings, ee_module=second)
    assert second.initialized is False


# --------------------------------------------------------------------------- #
# Point sampling (SRS §19.6)                                                   #
# --------------------------------------------------------------------------- #
def test_sample_elevation_returns_value() -> None:
    client = EarthEngineClient(ee_module=FakeEE(542.16), auto_initialize=False)
    assert client.sample_elevation(17.385, 78.486) == pytest.approx(542.16)


def test_point_value_handles_no_coverage() -> None:
    client = EarthEngineClient(ee_module=FakeEE(None), auto_initialize=False)
    assert client.sample_elevation(17.385, 78.486) is None


def test_point_value_on_collection_dataset() -> None:
    client = EarthEngineClient(ee_module=FakeEE(0.42), auto_initialize=False)
    ndvi = DATASETS["sentinel2"]
    assert client.point_value(ndvi, ndvi.bands[0], 17.385, 78.486) == pytest.approx(0.42)
