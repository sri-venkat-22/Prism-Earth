"""The standard connector interface and shared connector types (SRS §18.1, §18.2).

Every dataset connector is an independent adapter between the platform and a
single logical data source (SRS §18). Connectors share one interface so the
Fetch Engine treats them uniformly (SRS §18.2) and converts dataset-specific
formats into the standardized Prism Earth Field Object (SRS §18.11).

This module defines:

- :class:`Confidence` — the data-quality indicator (SRS §17.2/§17.4).
- :class:`NullReason` — why a value is null or a fetch failed (SRS §15.17, §17.6).
- :class:`FieldResult` — a connector's standardized per-field output. It carries
  the value, the *exact* dataset that produced it (SRS §16.4), the confidence,
  and — for a missing value — the reason. Downstream the Provenance System and
  Citation Engine enrich it from the catalog and Dataset Registry.
- :class:`FetchContext` — the resolved request context handed to every connector.
- :class:`BaseConnector` — the ``initialize / validate / fetch / metadata /
  health / shutdown`` interface (SRS §18.2).
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.metadata.enums import Layer
from app.schemas.spatial import SpatialContext


class Confidence(StrEnum):
    """Per-field data-quality indicator (SRS §17.2 Confidence, §17.4)."""

    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class NullReason(StrEnum):
    """Why a field has no value, or why a connector failed (SRS §15.17, §17.6).

    The Fetch Engine distinguishes a legitimately absent value from a runtime
    failure; both are recorded in provenance so a null is never ambiguous.
    """

    DATA_UNAVAILABLE = "data_unavailable"  # source not integrated / no datum here
    OUTSIDE_COVERAGE = "outside_coverage"  # point is outside the dataset's extent
    UNSUPPORTED_STATE = "unsupported_state"  # region-gated field, state not enabled
    NOT_APPLICABLE = "not_applicable"  # field does not apply at this location
    CONNECTOR_TIMEOUT = "connector_timeout"  # connector failed at runtime (retryable)
    DATASET_UNAVAILABLE = "dataset_unavailable"  # upstream dataset temporarily down


class FieldResult(BaseModel):
    """A connector's standardized output for one field (SRS §18.11).

    ``dataset`` names the exact dataset that produced ``value`` and MUST be
    registered in the Dataset Registry (SRS §16.10) so provenance and citations
    resolve to authoritative metadata. When ``value`` is ``None``, ``null_reason``
    explains why (SRS §15.17); ``null_meaning`` is filled from the catalog later.
    """

    model_config = ConfigDict(frozen=True)

    field: str = Field(..., description="Catalog field name")
    value: Any | None = Field(None, description="Retrieved value, or None")
    dataset: str = Field(..., description="Exact source dataset (Dataset Registry key)")
    confidence: Confidence = Field(Confidence.HIGH, description="Data-quality indicator")
    null_reason: NullReason | None = Field(
        None, description="Why the value is null (required when value is None)"
    )

    @property
    def is_null(self) -> bool:
        return self.value is None


class FetchContext(BaseModel):
    """The resolved request context passed to every connector (SRS §15.4).

    State detection (SRS §15.7) runs once in the orchestrator and its result is
    shared with all connectors, so the Administrative connector reads the
    PostGIS-resolved hierarchy here rather than re-querying.
    """

    model_config = ConfigDict(frozen=True)

    lat: float
    lng: float
    spatial: SpatialContext


class ConnectorMetadata(BaseModel):
    """Static description of a connector (SRS §18.2 metadata())."""

    model_config = ConfigDict(frozen=True)

    name: str
    layer: Layer
    datasets: tuple[str, ...] = ()
    servable_fields: tuple[str, ...] = ()


class ConnectorHealth(BaseModel):
    """Operational status of a connector (SRS §18.12)."""

    model_config = ConfigDict(frozen=True)

    name: str
    status: str = Field(..., description="ok | degraded | down | not_configured")
    detail: str | None = None


class BaseConnector(ABC):
    """The standard connector interface (SRS §18.2).

    Subclasses adapt one logical data source. The lifecycle is
    ``initialize → (validate, fetch)* → shutdown``; ``metadata`` and ``health``
    may be called at any time. ``fetch`` raises on a connector-level failure
    (e.g. the upstream dataset is unreachable); the Fetch Orchestrator isolates
    that into a partial failure without aborting the request (SRS §18.13, §15.16).
    A field that simply has no value at the point is returned as a null
    :class:`FieldResult`, not an exception (SRS §15.17).
    """

    #: Registry key — must equal the owning layer's connector (SRS §11.5, §18.10).
    name: str
    #: The single domain layer this connector serves (SRS §11.5).
    layer: Layer

    def servable_fields(self) -> frozenset[str]:
        """Catalog fields this connector can actually retrieve today.

        A subset of the layer's fields: the orchestrator returns owned-but-not-yet
        -servable fields as null (``DATA_UNAVAILABLE``) without calling ``fetch``.
        """
        return frozenset()

    async def initialize(self) -> None:  # noqa: B027 - optional lifecycle hook, no-op by default
        """Prepare resources (auth, pools). Idempotent; default is a no-op."""

    async def validate(self, fields: list[str]) -> None:
        """Validate that this connector can serve ``fields`` (SRS §18.2).

        Raises :class:`ValueError` for a field outside :meth:`servable_fields`.
        The orchestrator only routes servable fields here, so this is a guard.
        """
        unservable = sorted(f for f in fields if f not in self.servable_fields())
        if unservable:
            raise ValueError(f"{self.name} cannot serve fields: {', '.join(unservable)}")

    @abstractmethod
    async def fetch(self, fields: list[str], context: FetchContext) -> list[FieldResult]:
        """Retrieve ``fields`` at ``context`` as standardized results (SRS §18.11)."""

    @abstractmethod
    async def metadata(self) -> ConnectorMetadata:
        """Return this connector's static descriptor (SRS §18.2)."""

    async def health(self) -> ConnectorHealth:
        """Report operational status (SRS §18.12). Default: ``ok``."""
        return ConnectorHealth(name=self.name, status="ok")

    async def shutdown(self) -> None:  # noqa: B027 - optional lifecycle hook, no-op by default
        """Release resources. Default is a no-op."""
