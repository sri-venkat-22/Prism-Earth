"""The deterministic Citation Engine (SRS §16).

Turns the Provenance System's per-field records into standardized citation
objects (SRS §16.7). It is **purely deterministic and registry-driven** — it
reads dataset metadata from the Dataset Registry (SRS §16.10) and never invents
references from model memory (SRS §16.4 Independence, §38.2). The same inputs
always yield identical citations (SRS §16.4 Reproducibility).

Workflow (SRS §16.6): fetched fields → read provenance → look up the dataset
registry → generate citation objects → deduplicate → attach to the response.

Key rules enforced here:

- Only fields that actually returned a value are cited; unavailable data yields
  no fabricated citation (SRS §16.14).
- Multiple fields from one dataset collapse into a single citation that lists all
  of them (SRS §16.11 Deduplication).
- Every cited dataset must be registered, or a system error is raised rather than
  an incomplete citation (SRS §16.15 Validation).
- Citations are ordered by first appearance and numbered ``CIT-001`` … so ids
  are stable for a given request (SRS §16.7).
"""

from __future__ import annotations

from app.datasets.registry import DatasetRegistry
from app.provenance.generator import FieldProvenance
from app.schemas.fetch import Citation


class CitationEngine:
    """Deterministic, registry-based citation generation (SRS §16)."""

    def __init__(self, dataset_registry: DatasetRegistry) -> None:
        self._datasets = dataset_registry

    def generate(self, provenances: list[FieldProvenance]) -> list[Citation]:
        """Generate deduplicated citations for the resolved fields (SRS §16.6).

        ``provenances`` is the full per-field provenance list; only records that
        carry a value are cited (SRS §16.14). Dataset order follows first
        appearance for deterministic, stable ids (SRS §16.4 Reproducibility).
        """
        # Group resolved fields by dataset, preserving first-seen order.
        order: list[str] = []
        fields_by_dataset: dict[str, list[str]] = {}
        retrieved_by_dataset: dict[str, str] = {}
        for prov in provenances:
            if not prov.succeeded:
                continue  # SRS §16.14 — never cite unavailable data
            if prov.dataset not in fields_by_dataset:
                order.append(prov.dataset)
                fields_by_dataset[prov.dataset] = []
                retrieved_by_dataset[prov.dataset] = prov.retrieved_at
            fields_by_dataset[prov.dataset].append(prov.field)

        citations: list[Citation] = []
        for index, dataset_name in enumerate(order, start=1):
            # SRS §16.15 — a cited dataset must be registered, else a system error.
            meta = self._datasets.require(dataset_name)
            citations.append(
                Citation(
                    citation_id=f"CIT-{index:03d}",
                    dataset=meta.name,
                    provider=meta.provider,
                    source_url=meta.source_url,
                    dataset_version=meta.version,
                    retrieved_at=retrieved_by_dataset[dataset_name],
                    ttl=meta.ttl,
                    license=meta.license,
                    field_names=list(fields_by_dataset[dataset_name]),
                )
            )
        return citations
