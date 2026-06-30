"""The Dataset Registry (SRS §16.10, §13.15).

The registry is the single source of truth for citation and provenance metadata
(SRS §16.10): for every dataset that can produce a field value it holds the
dataset name, provider, version, official source URL, license, CRS, resolution,
and cache TTL. The deterministic Citation Engine (SRS §16) and the Provenance
System (SRS §17) resolve a returned field's dataset against this registry — they
never invent metadata from model memory (SRS §16.4 Independence, §38.2).

Two sources feed the registry, deduplicated by dataset name:

1. ``configs/datasets.yaml`` — the declarative dataset registry (SRS §16.10),
   covering the government / open-data sources the connectors cite.
2. ``app.gee.datasets.DATASETS`` — the Earth Engine assets the raster connectors
   actually sample (SRS §19.4), so provenance can name the *exact* dataset that
   produced a value (SRS §16.4 Accuracy) even when it is accessed via GEE.

The YAML entries win on a name collision. A connector that returns a dataset
name absent from the registry is a build/config defect, not a fabricated
citation: :meth:`DatasetRegistry.require` raises a system error (SRS §16.15).
"""

from __future__ import annotations

from functools import lru_cache

from pydantic import BaseModel, ConfigDict, Field

from app.config.loader import load_datasets_config
from app.core.errors import InternalError
from app.core.logging import get_logger
from app.gee.datasets import DATASETS as GEE_DATASETS

logger = get_logger(__name__)

_DEFAULT_CRS = "EPSG:4326"


class DatasetMeta(BaseModel):
    """Authoritative metadata for one dataset (SRS §16.10, §13.15)."""

    model_config = ConfigDict(frozen=True)

    name: str = Field(..., description="Canonical dataset name (the citation key)")
    provider: str | None = Field(None, description="Data provider / publisher")
    version: str | None = Field(None, description="Dataset release / version (SRS §16.7)")
    source_url: str | None = Field(None, description="Official dataset URL (SRS §16.7)")
    purpose: str | None = Field(None, description="What the dataset is used for")
    license: str | None = Field(None, description="Usage license (SRS §16.7)")
    crs: str = Field(_DEFAULT_CRS, description="Coordinate reference system (SRS §17.2)")
    spatial_resolution: str | None = Field(None, description="Native pixel size (SRS §17.2)")
    temporal_resolution: str | None = Field(None, description="Observation cadence")
    update_frequency: str | None = Field(None, description="How often the source refreshes")
    ttl: str | None = Field(None, description="Cache validity, e.g. '30d' (SRS §16.7)")
    layers: tuple[str, ...] = Field((), description="Domain layers served (SRS §11.5)")


class DatasetRegistry:
    """Name-keyed lookup over registered datasets (SRS §16.10)."""

    def __init__(self, datasets: list[DatasetMeta]) -> None:
        self._by_name: dict[str, DatasetMeta] = {}
        for dataset in datasets:
            # First writer wins; the YAML registry is loaded before GEE assets.
            self._by_name.setdefault(dataset.name, dataset)

    def names(self) -> list[str]:
        return sorted(self._by_name)

    def all(self) -> list[DatasetMeta]:
        return list(self._by_name.values())

    def has(self, name: str) -> bool:
        return name in self._by_name

    def get(self, name: str) -> DatasetMeta | None:
        return self._by_name.get(name)

    def require(self, name: str) -> DatasetMeta:
        """Resolve a dataset by name or raise a system error (SRS §16.15).

        An unregistered dataset name means a connector emitted provenance the
        registry cannot vouch for. Per SRS §16.14/§16.15 the platform raises
        rather than return an incomplete or fabricated citation.
        """
        dataset = self._by_name.get(name)
        if dataset is None:
            raise InternalError(
                "Unregistered dataset cannot be cited.",
                details=(
                    f"Dataset {name!r} is not in the Dataset Registry "
                    "(configs/datasets.yaml or the Earth Engine registry, SRS §16.10)."
                ),
            )
        return dataset


def _from_yaml(entries: dict[str, dict[str, object]]) -> list[DatasetMeta]:
    """Build dataset metadata from ``configs/datasets.yaml`` (SRS §16.10)."""
    datasets: list[DatasetMeta] = []
    for entry in entries.values():
        name = entry.get("name")
        if not isinstance(name, str):  # pragma: no cover - guarded by config shape
            continue
        datasets.append(
            DatasetMeta(
                name=name,
                provider=_opt_str(entry.get("provider")),
                version=_opt_str(entry.get("version")),
                source_url=_opt_str(entry.get("source_url")),
                purpose=_opt_str(entry.get("purpose")),
                license=_opt_str(entry.get("license")),
                crs=_opt_str(entry.get("crs")) or _DEFAULT_CRS,
                spatial_resolution=_opt_str(entry.get("spatial_resolution")),
                temporal_resolution=_opt_str(entry.get("temporal_resolution")),
                update_frequency=_opt_str(entry.get("update_frequency")),
                ttl=_opt_str(entry.get("ttl")),
                layers=tuple(entry.get("layers", []) or []),  # type: ignore[arg-type]
            )
        )
    return datasets


def _from_gee() -> list[DatasetMeta]:
    """Build dataset metadata from the Earth Engine registry (SRS §19.4)."""
    return [
        DatasetMeta(
            name=ds.name,
            provider=ds.provider,
            source_url=ds.source_url,
            purpose=ds.purpose,
            crs=_DEFAULT_CRS,  # GEE point sampling is performed in WGS84 (SRS §19.7)
            spatial_resolution=ds.spatial_resolution,
            temporal_resolution=ds.temporal_resolution,
            ttl=ds.ttl,
            layers=ds.layers,
        )
        for ds in GEE_DATASETS.values()
    ]


def _opt_str(value: object) -> str | None:
    return str(value) if value is not None else None


def build_dataset_registry() -> DatasetRegistry:
    """Construct the registry from ``datasets.yaml`` + the Earth Engine registry."""
    yaml_entries = load_datasets_config().get("datasets", {}) or {}
    datasets = _from_yaml(yaml_entries) + _from_gee()
    registry = DatasetRegistry(datasets)
    logger.info("dataset_registry.loaded", count=len(registry.names()))
    return registry


@lru_cache(maxsize=1)
def get_dataset_registry() -> DatasetRegistry:
    """Return the process-wide Dataset Registry (SRS §16.10)."""
    return build_dataset_registry()
