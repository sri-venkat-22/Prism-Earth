"""Observability: Prometheus metrics, domain helpers, and tracing (SRS §27)."""

from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from prometheus_client import generate_latest

from app.core.config import Settings
from app.observability import metrics as metrics_module
from app.observability.metrics import (
    observe_gee_duration,
    observe_pipeline_stage,
    record_cache_event,
    record_connector_health,
    timer,
)
from app.observability.tracing import configure_tracing


def test_metrics_endpoint_exposes_prometheus_text(client: TestClient) -> None:
    # Generate at least one request so the HTTP series exist.
    client.get("/api/v1/live")
    resp = client.get("/metrics")
    assert resp.status_code == 200
    assert "text/plain" in resp.headers["content-type"]
    body = resp.text
    assert "terra_http_requests_total" in body
    assert "terra_http_request_duration_seconds" in body


def test_metrics_label_uses_route_template(client: TestClient) -> None:
    client.get("/api/v1/live")
    body = client.get("/metrics").text
    # The low-cardinality route template appears, not a raw/opaque path. Routers
    # are mounted under /api/v1, so the matched template is the router-local
    # path (still stable and parameterized, never a raw URL).
    assert 'route="/live"' in body


def test_unmatched_route_does_not_explode_cardinality(client: TestClient) -> None:
    client.get("/api/v1/nope-not-a-route")
    body = client.get("/metrics").text
    assert 'route="unmatched"' in body


def test_domain_metric_helpers_publish_series() -> None:
    record_connector_health("unit_test_connector", ok=True)
    record_connector_health("unit_test_connector_down", ok=False)
    observe_gee_duration(0.12)
    record_cache_event("fetch", hit=True)
    record_cache_event("fetch", hit=False)
    observe_pipeline_stage("planner", 0.03)

    dump = generate_latest().decode()
    assert 'terra_connector_health{connector="unit_test_connector"} 1.0' in dump
    assert 'terra_connector_health{connector="unit_test_connector_down"} 0.0' in dump
    assert 'terra_cache_events_total{cache="fetch",result="hit"}' in dump
    assert 'terra_cache_events_total{cache="fetch",result="miss"}' in dump
    assert "terra_gee_request_duration_seconds" in dump
    assert 'terra_pipeline_stage_duration_seconds_count{stage="planner"}' in dump


def test_timer_measures_elapsed() -> None:
    elapsed = timer()
    assert elapsed() >= 0.0


def test_tracing_is_noop_without_configuration() -> None:
    assert configure_tracing(FastAPI(), Settings(otel_enabled=False)) is False
    # Enabled but no endpoint is still a no-op.
    assert configure_tracing(FastAPI(), Settings(otel_enabled=True)) is False


def test_tracing_installs_when_configured(monkeypatch: pytest.MonkeyPatch) -> None:
    # Swap the batch processor for a no-op so no background export thread starts.
    import opentelemetry.sdk.trace.export as otel_export

    class _NoopProcessor:
        def __init__(self, exporter: object) -> None: ...
        def on_start(self, *args: object, **kwargs: object) -> None: ...
        def on_end(self, *args: object, **kwargs: object) -> None: ...
        def shutdown(self) -> None: ...
        def force_flush(self, *args: object, **kwargs: object) -> bool:
            return True

    monkeypatch.setattr(otel_export, "BatchSpanProcessor", _NoopProcessor)

    from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor

    app = FastAPI()
    installed = configure_tracing(
        app,
        Settings(otel_enabled=True, otel_exporter_endpoint="http://localhost:4318"),
    )
    assert installed is True
    FastAPIInstrumentor.uninstrument_app(app)


def test_metrics_middleware_skips_its_own_endpoint() -> None:
    # The /metrics scrape must not be excluded set — assert it is in the skip set.
    assert "/metrics" in metrics_module._EXCLUDED_PATHS
