"""Citation Engine tests (SRS §16)."""

from __future__ import annotations

import pytest

from app.citations.engine import CitationEngine
from app.connectors.base import Confidence, FieldResult, NullReason
from app.core.errors import InternalError
from app.datasets.registry import get_dataset_registry
from app.metadata.catalog import get_catalog
from app.provenance.generator import ProvenanceGenerator
from app.tests._fetch_fakes import DEM_DATASET

_SOI = "Survey of India Administrative Boundaries"


def _provs(results: list[FieldResult]) -> list:
    gen = ProvenanceGenerator(get_catalog(), get_dataset_registry())
    return gen.generate_all(results, retrieved_at="2026-06-30T00:00:00Z")


def _engine() -> CitationEngine:
    return CitationEngine(get_dataset_registry())


def test_citations_deduplicate_by_dataset() -> None:
    """elevation + slope share one dataset → one citation listing both (§16.11)."""
    results = [
        FieldResult(field="elevation", value=10.0, dataset=DEM_DATASET, confidence=Confidence.HIGH),
        FieldResult(field="slope", value=2.0, dataset=DEM_DATASET, confidence=Confidence.MEDIUM),
        FieldResult(
            field="district_name", value="Hyderabad", dataset=_SOI, confidence=Confidence.HIGH
        ),
    ]
    citations = _engine().generate(_provs(results))
    assert [c.citation_id for c in citations] == ["CIT-001", "CIT-002"]

    dem = next(c for c in citations if c.dataset == DEM_DATASET)
    assert dem.field_names == ["elevation", "slope"]
    assert dem.source_url  # resolved from the registry
    soi = next(c for c in citations if c.dataset == _SOI)
    assert soi.field_names == ["district_name"]


def test_no_citation_for_unavailable_data() -> None:
    """Null fields are never cited (§16.14)."""
    results = [
        FieldResult(field="elevation", value=10.0, dataset=DEM_DATASET, confidence=Confidence.HIGH),
        FieldResult(
            field="aspect",
            value=None,
            dataset=DEM_DATASET,
            confidence=Confidence.LOW,
            null_reason=NullReason.OUTSIDE_COVERAGE,
        ),
    ]
    (citation,) = _engine().generate(_provs(results))
    assert citation.field_names == ["elevation"]  # aspect excluded


def test_citation_ids_are_deterministic() -> None:
    results = [
        FieldResult(
            field="district_name", value="Hyderabad", dataset=_SOI, confidence=Confidence.HIGH
        ),
        FieldResult(field="elevation", value=10.0, dataset=DEM_DATASET, confidence=Confidence.HIGH),
    ]
    first = _engine().generate(_provs(results))
    second = _engine().generate(_provs(results))
    assert [c.model_dump() for c in first] == [c.model_dump() for c in second]
    # Order follows first appearance: SoI (district_name) before DEM (elevation).
    assert first[0].dataset == _SOI and first[1].dataset == DEM_DATASET


def test_unregistered_dataset_raises_system_error() -> None:
    """A field citing an unregistered dataset is a system error, not a guess (§16.15)."""
    bogus = [
        FieldResult(
            field="elevation", value=10.0, dataset="Imaginary DEM", confidence=Confidence.HIGH
        )
    ]
    with pytest.raises(InternalError):
        _engine().generate(_provs(bogus))
