"""Prometheus metrics + request instrumentation (SRS §27.2, §27.3).

Exposes the platform's operational metrics for the monitoring stack:

- HTTP request volume, latency, and in-flight count (labeled by method, route
  template, and status) — the core §27.2 "API latency / request volume / error
  rate" signals.
- Domain gauges/counters for the rest of the §27.2 list: connector health,
  Earth Engine response time, cache hit ratio, and per-stage pipeline latency.

:class:`MetricsMiddleware` records the HTTP metrics for every request and emits
one structured access-log line (SRS §27.1), reusing the correlation id bound by
:class:`app.middleware.correlation.CorrelationIdMiddleware`. ``/metrics`` renders
the default Prometheus registry (which also carries process/GC collectors).

Metrics are module-level singletons registered once at import, so building
multiple app instances (as the test suite does) reuses the same series.
"""

from __future__ import annotations

import time
from collections.abc import Callable

from fastapi import APIRouter, Response
from prometheus_client import CONTENT_TYPE_LATEST, Counter, Gauge, Histogram, generate_latest
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request

from app.core.logging import get_logger

logger = get_logger(__name__)

# Latency buckets tuned for a geospatial API: sub-second cache/metadata hits up
# to multi-second Earth Engine fetches (SRS §7.1, §27.2).
_LATENCY_BUCKETS = (0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0)

# --------------------------------------------------------------------------- #
# HTTP metrics (SRS §27.2 — API latency, request volume, error rate)          #
# --------------------------------------------------------------------------- #
HTTP_REQUESTS = Counter(
    "prism_http_requests_total",
    "Total HTTP requests.",
    labelnames=("method", "route", "status"),
)
HTTP_REQUEST_DURATION = Histogram(
    "prism_http_request_duration_seconds",
    "HTTP request latency in seconds.",
    labelnames=("method", "route"),
    buckets=_LATENCY_BUCKETS,
)
HTTP_IN_PROGRESS = Gauge(
    "prism_http_requests_in_progress",
    "In-flight HTTP requests.",
    labelnames=("method", "route"),
)

# --------------------------------------------------------------------------- #
# Domain metrics (SRS §27.2 — connector health, GEE time, cache, pipeline)     #
# --------------------------------------------------------------------------- #
CONNECTOR_HEALTH = Gauge(
    "prism_connector_health",
    "Connector health (1 = ok, 0 = degraded/down).",
    labelnames=("connector",),
)
GEE_REQUEST_DURATION = Histogram(
    "prism_gee_request_duration_seconds",
    "Google Earth Engine request latency in seconds.",
    buckets=_LATENCY_BUCKETS,
)
CACHE_EVENTS = Counter(
    "prism_cache_events_total",
    "Cache lookups by outcome (for the cache hit ratio).",
    labelnames=("cache", "result"),
)
PIPELINE_STAGE_DURATION = Histogram(
    "prism_pipeline_stage_duration_seconds",
    "AI pipeline stage latency in seconds (planner, fetch, synthesizer).",
    labelnames=("stage",),
    buckets=_LATENCY_BUCKETS,
)

_EXCLUDED_PATHS = frozenset({"/metrics"})


def _route_template(request: Request) -> str:
    """Return the low-cardinality route template (e.g. ``/api/v1/fetch``).

    Falls back to ``"unmatched"`` for requests that never matched a route (404s),
    so unbounded URLs don't explode metric cardinality.
    """
    route = request.scope.get("route")
    path = getattr(route, "path", None)
    if isinstance(path, str) and path:
        return path
    return "unmatched"


class MetricsMiddleware(BaseHTTPMiddleware):
    """Time every request, record Prometheus metrics, and emit an access log."""

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        if request.url.path in _EXCLUDED_PATHS:
            return await call_next(request)

        method = request.method
        start = time.perf_counter()
        status_code = 500
        # The route template is only known after routing; resolve it lazily but
        # track in-progress against the raw path prefix to keep the gauge cheap.
        try:
            response = await call_next(request)
            status_code = response.status_code
            return response
        finally:
            duration = time.perf_counter() - start
            route = _route_template(request)
            HTTP_REQUESTS.labels(method=method, route=route, status=str(status_code)).inc()
            HTTP_REQUEST_DURATION.labels(method=method, route=route).observe(duration)
            logger.info(
                "http.request",
                method=method,
                path=request.url.path,
                route=route,
                status_code=status_code,
                duration_ms=round(duration * 1000, 2),
                client=request.client.host if request.client else None,
            )


metrics_router = APIRouter()


@metrics_router.get("/metrics", include_in_schema=False)
async def metrics() -> Response:
    """Expose the Prometheus registry in text exposition format (SRS §27.3)."""
    return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)


# --------------------------------------------------------------------------- #
# Domain instrumentation helpers                                              #
# --------------------------------------------------------------------------- #
def record_connector_health(connector: str, *, ok: bool) -> None:
    """Publish a connector's health as a 1/0 gauge (SRS §27.2)."""
    CONNECTOR_HEALTH.labels(connector=connector).set(1.0 if ok else 0.0)


def observe_gee_duration(seconds: float) -> None:
    """Record an Earth Engine request's latency (SRS §27.2)."""
    GEE_REQUEST_DURATION.observe(seconds)


def record_cache_event(cache: str, *, hit: bool) -> None:
    """Record a cache lookup outcome, feeding the cache hit ratio (SRS §27.2)."""
    CACHE_EVENTS.labels(cache=cache, result="hit" if hit else "miss").inc()


def observe_pipeline_stage(stage: str, seconds: float) -> None:
    """Record an AI-pipeline stage's latency (planner/fetch/synthesizer)."""
    PIPELINE_STAGE_DURATION.labels(stage=stage).observe(seconds)


# Re-exported for callers that want to time a block without importing timeit.
def timer() -> Callable[[], float]:
    """Return a function that yields elapsed seconds since this call."""
    start = time.perf_counter()
    return lambda: time.perf_counter() - start


__all__ = [
    "MetricsMiddleware",
    "metrics_router",
    "record_connector_health",
    "observe_gee_duration",
    "record_cache_event",
    "observe_pipeline_stage",
    "timer",
]
