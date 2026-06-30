"""The Fetch Orchestrator — deterministic execution core (SRS §15).

Executes the SRS §15.4 workflow with no AI of any kind (SRS §15, §38.3):

    coordinate validation (§15.6)
      → state detection (§15.7)
      → field validation + lifecycle enforcement (§15.5, §11.6)
      → preset expansion (§15.8)
      → region gating (§24.3)
      → catalog-driven connector routing (§18.10)
      → parallel connector execution (§15.12)
      → result aggregation (§15.13)
      → provenance generation (§15.15, §17)
      → citation generation (§16)
      → standardized response (§13.9–13.12)

The orchestrator never interprets, scores, or invents values. Every requested
field appears in the response: as a real value, or as a null with a recorded
reason (SRS §15.17, §17.6). A connector failure is isolated into a
``partial_failure`` and never aborts the request (SRS §15.16, §13.12).
"""

from __future__ import annotations

import asyncio
from typing import Protocol

from app.citations.engine import CitationEngine
from app.connectors.base import (
    BaseConnector,
    Confidence,
    FetchContext,
    FieldResult,
    NullReason,
)
from app.connectors.registry import ConnectorRegistry
from app.core.logging import get_logger
from app.metadata.catalog import Catalog
from app.metadata.enums import Availability
from app.metadata.state_registry import StateRegistry
from app.provenance.generator import FieldProvenance, ProvenanceGenerator
from app.schemas.fetch import (
    Citation,
    FetchLocation,
    FetchResponse,
    FieldObject,
    PartialFailure,
    ProvenanceObject,
    ResponseSummary,
)
from app.schemas.spatial import SpatialContext
from app.services.state_detection import validate_coordinate
from app.utils.time import utcnow_iso

logger = get_logger(__name__)


class SupportsStateDetection(Protocol):
    """The state-detection capability the orchestrator needs (SRS §15.7)."""

    async def resolve(self, lat: float, lng: float) -> SpatialContext: ...


class FetchOrchestrator:
    """Coordinates connectors deterministically to fulfil a fetch (SRS §15)."""

    def __init__(
        self,
        *,
        catalog: Catalog,
        connectors: ConnectorRegistry,
        state_detection: SupportsStateDetection,
        state_registry: StateRegistry,
        provenance: ProvenanceGenerator,
        citations: CitationEngine,
    ) -> None:
        self._catalog = catalog
        self._connectors = connectors
        self._state_detection = state_detection
        self._states = state_registry
        self._provenance = provenance
        self._citations = citations

    async def fetch(
        self,
        *,
        lat: float,
        lng: float,
        fields: list[str] | None = None,
        preset: str | None = None,
        request_id: str = "",
    ) -> FetchResponse:
        """Run the §15.4 workflow and return a standardized response."""
        # 1. Coordinate validation (SRS §15.6) — raises ValidationAppError (422).
        validate_coordinate(lat, lng)

        # 2. State detection (SRS §15.7) — one PostGIS resolution shared by all
        #    connectors via the FetchContext.
        spatial = await self._state_detection.resolve(lat, lng)
        context = FetchContext(lat=lat, lng=lng, spatial=spatial)

        # 3. Resolve the requested field list: expand a preset (SRS §15.8) or take
        #    explicit fields, then enforce lifecycle — unknown/planned fields are
        #    rejected before any connector runs (SRS §15.5, §11.6, §38.4).
        requested = self._resolve_fields(fields=fields, preset=preset)
        self._catalog.assert_selectable(requested)

        # 4. Region gating (SRS §24.3): split region-gated fields the location does
        #    not enable into nulls; the rest are eligible for routing.
        eligible, gated_nulls = self._apply_region_gating(requested, spatial)

        # 5–7. Route to connectors and execute them in parallel (SRS §18.10, §15.12).
        results: dict[str, FieldResult] = dict(gated_nulls)
        partial_failures: list[PartialFailure] = []
        await self._route_and_execute(eligible, context, results, partial_failures)

        # 8. Aggregate in requested order (SRS §15.13).
        ordered = [results[name] for name in requested]

        # 9. Provenance for every field (SRS §15.15, §17).
        retrieved_at = utcnow_iso()
        provenances = self._provenance.generate_all(ordered, retrieved_at=retrieved_at)

        # 10. Deterministic, registry-based citations (SRS §16).
        citations = self._citations.generate(provenances)

        return self._build_response(
            request_id=request_id,
            timestamp=retrieved_at,
            spatial=spatial,
            requested=requested,
            provenances=provenances,
            citations=citations,
            partial_failures=partial_failures,
        )

    # ------------------------------------------------------------------ #
    # Workflow steps                                                     #
    # ------------------------------------------------------------------ #
    def _resolve_fields(self, *, fields: list[str] | None, preset: str | None) -> list[str]:
        """Expand a preset or de-duplicate explicit fields (SRS §15.8)."""
        if preset is not None:
            # expand_preset raises NotFoundError (404) for an unknown preset.
            names = self._catalog.expand_preset(preset)
        else:
            names = list(fields or [])
        # Preserve order, drop duplicates.
        seen: set[str] = set()
        ordered: list[str] = []
        for name in names:
            if name not in seen:
                seen.add(name)
                ordered.append(name)
        return ordered

    def _apply_region_gating(
        self, requested: list[str], spatial: SpatialContext
    ) -> tuple[list[str], dict[str, FieldResult]]:
        """Partition region-gated fields by location support (SRS §24.3).

        A region-gated field is eligible only when the resolved state enables it
        in the State Registry; otherwise it is returned as a null with reason
        ``unsupported_state`` and never routed to a connector.
        """
        enabling_state = (
            self._states.resolve(spatial.state.name) if spatial.state is not None else None
        )
        eligible: list[str] = []
        gated_nulls: dict[str, FieldResult] = {}
        for name in requested:
            field = self._catalog.field(name)
            if field.availability is Availability.REGION_GATED:
                enabled = enabling_state is not None and enabling_state.enables(name)
                if not enabled:
                    gated_nulls[name] = self._null_result(name, NullReason.UNSUPPORTED_STATE)
                    continue
            eligible.append(name)
        return eligible, gated_nulls

    async def _route_and_execute(
        self,
        eligible: list[str],
        context: FetchContext,
        results: dict[str, FieldResult],
        partial_failures: list[PartialFailure],
    ) -> None:
        """Route eligible fields and run their connectors concurrently."""
        grouped, unrouted = self._connectors.route(eligible)

        # Fields whose owning connector is not deployed → partial failure + nulls.
        self._record_unrouted(unrouted, results, partial_failures)

        tasks: list[asyncio.Task[list[FieldResult]]] = []
        task_groups: list[tuple[BaseConnector, list[str]]] = []
        for connector, routed in grouped.items():
            servable = [f for f in routed if f in connector.servable_fields()]
            for name in routed:
                if name not in servable:
                    # Owned by the connector but no source wired yet (SRS §15.17).
                    results[name] = self._null_result(name, NullReason.DATA_UNAVAILABLE)
            if servable:
                tasks.append(asyncio.ensure_future(connector.fetch(servable, context)))
                task_groups.append((connector, servable))

        # SRS §15.12 — parallel; a failing connector must not cancel the others.
        outcomes = await asyncio.gather(*tasks, return_exceptions=True)
        for (connector, servable), outcome in zip(task_groups, outcomes, strict=True):
            if isinstance(outcome, BaseException):
                await self._record_connector_failure(
                    connector, servable, outcome, results, partial_failures
                )
            else:
                for result in outcome:
                    results[result.field] = result

    # ------------------------------------------------------------------ #
    # Failure / null helpers                                             #
    # ------------------------------------------------------------------ #
    def _record_unrouted(
        self,
        unrouted: dict[str, str],
        results: dict[str, FieldResult],
        partial_failures: list[PartialFailure],
    ) -> None:
        """Turn fields with no deployed connector into partial failures (§15.16)."""
        by_connector: dict[str, list[str]] = {}
        for field_name, connector_key in unrouted.items():
            by_connector.setdefault(connector_key, []).append(field_name)
            results[field_name] = self._null_result(field_name, NullReason.DATASET_UNAVAILABLE)
        for connector_key, names in by_connector.items():
            layer = self._catalog.field(names[0]).layer
            partial_failures.append(
                PartialFailure(
                    layer=layer.value,
                    connector=connector_key,
                    dataset=None,
                    reason=f"Connector {connector_key!r} is not available in this deployment.",
                    retryable=False,
                )
            )
            logger.info("fetch.unrouted", connector=connector_key, fields=names)

    async def _record_connector_failure(
        self,
        connector: BaseConnector,
        fields: list[str],
        error: BaseException,
        results: dict[str, FieldResult],
        partial_failures: list[PartialFailure],
    ) -> None:
        """Isolate a connector exception into a partial failure (SRS §15.16, §18.13)."""
        for name in fields:
            results[name] = self._null_result(name, NullReason.CONNECTOR_TIMEOUT)
        try:
            meta = await connector.metadata()
            dataset = meta.datasets[0] if meta.datasets else None
        except Exception:  # metadata must never mask the original failure
            dataset = None
        partial_failures.append(
            PartialFailure(
                layer=connector.layer.value,
                connector=connector.name,
                dataset=dataset,
                reason=str(error) or error.__class__.__name__,
                retryable=True,
            )
        )
        logger.warning(
            "fetch.connector_failed",
            connector=connector.name,
            fields=fields,
            error=str(error),
        )

    def _null_result(self, field_name: str, reason: NullReason) -> FieldResult:
        """A synthetic null result labelled with the field's documented source."""
        return FieldResult(
            field=field_name,
            value=None,
            dataset=self._catalog.field(field_name).source,
            confidence=Confidence.LOW,
            null_reason=reason,
        )

    # ------------------------------------------------------------------ #
    # Response assembly                                                  #
    # ------------------------------------------------------------------ #
    def _build_response(
        self,
        *,
        request_id: str,
        timestamp: str,
        spatial: SpatialContext,
        requested: list[str],
        provenances: list[FieldProvenance],
        citations: list[Citation],
        partial_failures: list[PartialFailure],
    ) -> FetchResponse:
        fields: dict[str, FieldObject] = {}
        provenance_objs: dict[str, ProvenanceObject] = {}
        for prov in provenances:
            fields[prov.field] = FieldObject(
                name=prov.field,
                value=prov.value,
                unit=prov.unit,
                datatype=prov.datatype,
                confidence=prov.confidence,
                dataset=prov.dataset,
                dataset_version=prov.dataset_version,
                retrieved_at=prov.retrieved_at,
                ttl=prov.ttl,
                layer=prov.layer,
                null_meaning=prov.null_meaning,
            )
            provenance_objs[prov.field] = ProvenanceObject(
                field=prov.field,
                dataset=prov.dataset,
                dataset_version=prov.dataset_version,
                source_url=prov.source_url,
                retrieved_at=prov.retrieved_at,
                ttl=prov.ttl,
                confidence=prov.confidence,
                null_meaning=prov.null_meaning,
                reason=prov.reason.value if prov.reason is not None else None,
            )

        summary_stats = self._provenance.summarize(provenances)
        summary = ResponseSummary(
            requested=len(requested),
            resolved=summary_stats.resolved_count,
            null=summary_stats.null_count,
            datasets_used=list(summary_stats.datasets),
        )
        return FetchResponse(
            request_id=request_id,
            timestamp=timestamp,
            location=FetchLocation.from_context(spatial),
            fields=fields,
            provenance=provenance_objs,
            citations=citations,
            partial_failures=partial_failures,
            summary=summary,
        )
