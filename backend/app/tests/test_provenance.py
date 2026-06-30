"""Provenance System tests (SRS §17)."""

from __future__ import annotations

from app.connectors.base import Confidence, FieldResult, NullReason
from app.datasets.registry import get_dataset_registry
from app.metadata.catalog import get_catalog
from app.provenance.generator import ProvenanceGenerator
from app.tests._fetch_fakes import DEM_DATASET


def _generator() -> ProvenanceGenerator:
    return ProvenanceGenerator(get_catalog(), get_dataset_registry())


def test_provenance_enriches_from_catalog_and_registry() -> None:
    result = FieldResult(
        field="elevation", value=542.16, dataset=DEM_DATASET, confidence=Confidence.HIGH
    )
    prov = _generator().generate(result, retrieved_at="2026-06-30T00:00:00Z")

    assert prov.value == 542.16
    assert prov.unit == "m"  # from the catalog
    assert prov.confidence is Confidence.HIGH
    assert prov.source_url  # from the dataset registry
    assert prov.ttl == "365d"  # per-field catalog TTL wins
    assert prov.succeeded is True
    assert prov.null_meaning is None and prov.reason is None


def test_provenance_records_null_reason_and_meaning() -> None:
    result = FieldResult(
        field="aspect",
        value=None,
        dataset=DEM_DATASET,
        confidence=Confidence.LOW,
        null_reason=NullReason.OUTSIDE_COVERAGE,
    )
    prov = _generator().generate(result, retrieved_at="2026-06-30T00:00:00Z")
    assert prov.succeeded is False
    assert prov.reason is NullReason.OUTSIDE_COVERAGE
    # null_meaning is sourced from the catalog (aspect is nullable on flat cells).
    assert prov.null_meaning is not None


def test_provenance_summary_counts_resolved_and_datasets() -> None:
    gen = _generator()
    results = [
        FieldResult(field="elevation", value=10.0, dataset=DEM_DATASET, confidence=Confidence.HIGH),
        FieldResult(field="slope", value=2.0, dataset=DEM_DATASET, confidence=Confidence.MEDIUM),
        FieldResult(
            field="aspect",
            value=None,
            dataset=DEM_DATASET,
            confidence=Confidence.LOW,
            null_reason=NullReason.OUTSIDE_COVERAGE,
        ),
    ]
    provs = gen.generate_all(results, retrieved_at="2026-06-30T00:00:00Z")
    summary = gen.summarize(provs)
    assert summary.field_count == 3
    assert summary.resolved_count == 2
    assert summary.null_count == 1
    assert summary.datasets == (DEM_DATASET,)
