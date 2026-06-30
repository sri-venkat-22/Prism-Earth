"""Citation Engine (SRS §16).

Transforms validated provenance metadata into standardized, deduplicated,
human-traceable citations — deterministically and without any AI (SRS §16.4
Independence). Import the public surface from here:

    from app.citations import CitationEngine
"""

from __future__ import annotations

from app.citations.engine import CitationEngine

__all__ = ["CitationEngine"]
