"""Provenance System (SRS §17).

Records the complete lineage of every retrieved value so responses are
transparent, reproducible, and auditable. Sits between the Fetch Engine and the
Citation Engine (SRS §17.1). Import the public surface from here:

    from app.provenance import FieldProvenance, ProvenanceGenerator
"""

from __future__ import annotations

from app.provenance.generator import (
    FieldProvenance,
    ProvenanceGenerator,
    ProvenanceSummary,
)

__all__ = [
    "FieldProvenance",
    "ProvenanceGenerator",
    "ProvenanceSummary",
]
