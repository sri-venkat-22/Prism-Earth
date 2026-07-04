"""Observability package (SRS §27, §7.7).

Bundles the platform's structured-logging companions:

- :mod:`app.observability.metrics` — Prometheus metrics, the ``/metrics``
  endpoint, and the request-timing / access-log middleware (SRS §27.2).
- :mod:`app.observability.tracing` — opt-in OpenTelemetry tracing that exports
  spans only when an OTLP endpoint is configured (SRS §27.3).

Structured logging itself lives in :mod:`app.core.logging` and the correlation
id in :mod:`app.middleware.correlation`; together they satisfy the §7.7
observability requirement (structured logging, metrics, distributed tracing).
"""

from __future__ import annotations

from app.observability.metrics import (
    MetricsMiddleware,
    metrics_router,
    observe_gee_duration,
    observe_pipeline_stage,
    record_cache_event,
    record_connector_health,
)
from app.observability.tracing import configure_tracing

__all__ = [
    "MetricsMiddleware",
    "metrics_router",
    "observe_gee_duration",
    "observe_pipeline_stage",
    "record_cache_event",
    "record_connector_health",
    "configure_tracing",
]
