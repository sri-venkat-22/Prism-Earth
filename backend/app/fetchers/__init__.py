"""Fetch Engine (SRS §15).

The deterministic execution core: orchestrates connectors, aggregates results,
and attaches provenance (SRS §17) and citations (SRS §16). Import the public
surface from here:

    from app.fetchers import FetchOrchestrator, build_fetch_orchestrator
"""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.citations.engine import CitationEngine
from app.connectors import build_connector_registry
from app.connectors.base import BaseConnector
from app.datasets.registry import get_dataset_registry
from app.fetchers.orchestrator import FetchOrchestrator, SupportsStateDetection
from app.metadata.catalog import get_catalog
from app.metadata.state_registry import get_state_registry
from app.provenance.generator import ProvenanceGenerator
from app.services.state_detection import StateDetectionService


def build_fetch_orchestrator(
    session: AsyncSession,
    *,
    connectors: list[BaseConnector] | None = None,
    state_detection: SupportsStateDetection | None = None,
) -> FetchOrchestrator:
    """Wire a :class:`FetchOrchestrator` with the production dependencies.

    The Administrative connector's data path is PostGIS, so a database session is
    required (used by the shared State Detection service, SRS §15.7). ``connectors``
    and ``state_detection`` are injectable for tests.
    """
    catalog = get_catalog()
    dataset_registry = get_dataset_registry()
    return FetchOrchestrator(
        catalog=catalog,
        connectors=build_connector_registry(catalog, connectors),
        state_detection=state_detection or StateDetectionService(session),
        state_registry=get_state_registry(),
        provenance=ProvenanceGenerator(catalog, dataset_registry),
        citations=CitationEngine(dataset_registry),
    )


__all__ = [
    "FetchOrchestrator",
    "SupportsStateDetection",
    "build_fetch_orchestrator",
]
