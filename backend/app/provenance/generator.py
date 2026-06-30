"""Provenance generation (SRS §17, §15.15).

The Provenance Generator turns each connector :class:`FieldResult` into a
complete :class:`FieldProvenance` record by enriching it with authoritative
metadata from the Metadata Catalog (units, datatype, null semantics, per-field
TTL — SRS §17.5) and the Dataset Registry (dataset version, source URL, license
— SRS §16.10). It normalizes provenance across all connectors (SRS §15.15) so
downstream components are dataset-independent.

Every returned field gets a record, including nulls and failures: provenance
records *why* a value is missing (SRS §17.6), so a null is never ambiguous. The
generator never fabricates metadata — it only reflects the catalog, the
registry, and what the connector reported (SRS §16.4 Independence).
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict

from app.connectors.base import Confidence, FieldResult, NullReason
from app.datasets.registry import DatasetRegistry
from app.metadata.catalog import Catalog
from app.metadata.enums import DataType, Layer


class FieldProvenance(BaseModel):
    """The full lineage of one returned field (SRS §17.2, §17.3).

    Carries everything needed to build both the API Field Object (SRS §13.10)
    and the Provenance Object (SRS §13.11): the value and its catalog typing,
    the exact dataset and its registry metadata, the confidence, and — for a
    missing value — the reason and the catalog's ``null_meaning`` (SRS §17.6).
    """

    model_config = ConfigDict(frozen=True)

    field: str
    layer: Layer
    value: Any | None
    unit: str | None
    datatype: DataType
    confidence: Confidence
    dataset: str
    dataset_version: str | None
    source_url: str | None
    license: str | None
    retrieved_at: str
    ttl: str | None
    null_meaning: str | None = None
    reason: NullReason | None = None

    @property
    def succeeded(self) -> bool:
        """Whether the field carries a value (drives citation eligibility, §16.14)."""
        return self.value is not None


class ProvenanceSummary(BaseModel):
    """Response-level provenance roll-up (SRS §17.4 Response Level)."""

    model_config = ConfigDict(frozen=True)

    datasets: tuple[str, ...]
    field_count: int
    resolved_count: int
    null_count: int


class ProvenanceGenerator:
    """Builds normalized provenance from connector results (SRS §15.15, §17)."""

    def __init__(self, catalog: Catalog, dataset_registry: DatasetRegistry) -> None:
        self._catalog = catalog
        self._datasets = dataset_registry

    def generate(self, result: FieldResult, *, retrieved_at: str) -> FieldProvenance:
        """Enrich one connector result into a full provenance record (SRS §17.3)."""
        field = self._catalog.field(result.field)
        # Dataset metadata is best-effort here: successful values are validated
        # by the Citation Engine (SRS §16.15); a null may name a not-yet-registered
        # source, which must not break provenance.
        meta = self._datasets.get(result.dataset)
        null_meaning = field.null_meaning if result.is_null else None

        return FieldProvenance(
            field=result.field,
            layer=field.layer,
            value=result.value,
            unit=field.unit,
            datatype=field.datatype,
            confidence=result.confidence,
            dataset=result.dataset,
            dataset_version=meta.version if meta else None,
            source_url=meta.source_url if meta else field.source_url,
            license=meta.license if meta else None,
            retrieved_at=retrieved_at,
            # Per-field catalog TTL is authoritative for caching (SRS §15.18);
            # fall back to the dataset's registry TTL.
            ttl=field.dataset_ttl or (meta.ttl if meta else None),
            null_meaning=null_meaning,
            reason=result.null_reason,
        )

    def generate_all(
        self, results: list[FieldResult], *, retrieved_at: str
    ) -> list[FieldProvenance]:
        return [self.generate(r, retrieved_at=retrieved_at) for r in results]

    def summarize(self, provenances: list[FieldProvenance]) -> ProvenanceSummary:
        """Roll up response-level provenance (SRS §17.4)."""
        datasets = sorted({p.dataset for p in provenances if p.succeeded})
        resolved = sum(1 for p in provenances if p.succeeded)
        return ProvenanceSummary(
            datasets=tuple(datasets),
            field_count=len(provenances),
            resolved_count=resolved,
            null_count=len(provenances) - resolved,
        )
