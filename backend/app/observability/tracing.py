"""OpenTelemetry distributed tracing (SRS §27.3, §7.7).

Tracing is **opt-in**: a real tracer provider with an OTLP/HTTP exporter is
installed only when ``TERRA_OTEL_ENABLED`` is true and an exporter endpoint is
configured. Otherwise :func:`configure_tracing` is a no-op, so development and
the hermetic test suite carry no tracing overhead and need no collector.

When enabled, the FastAPI app is auto-instrumented (one span per request) and the
request correlation id (bound by
:class:`app.middleware.correlation.CorrelationIdMiddleware`) is available on the
active span, tying traces to the structured logs and to ``X-Correlation-ID``.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from app.core.config import Settings
from app.core.logging import get_logger

if TYPE_CHECKING:
    from fastapi import FastAPI

logger = get_logger(__name__)


def configure_tracing(app: FastAPI, settings: Settings) -> bool:
    """Install OpenTelemetry tracing on ``app`` when configured.

    Returns ``True`` when a real exporter was installed, ``False`` when tracing
    is disabled (the default) or the OTLP endpoint is unset. Import failures are
    logged and swallowed so a missing optional dependency never breaks startup.
    """
    if not settings.otel_enabled or not settings.otel_exporter_endpoint:
        logger.debug("tracing.disabled", enabled=settings.otel_enabled)
        return False

    try:
        from opentelemetry import trace
        from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
        from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
        from opentelemetry.sdk.resources import SERVICE_NAME, Resource
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor
    except ImportError as exc:  # pragma: no cover - optional dependency guard
        logger.warning("tracing.import_failed", error=str(exc))
        return False

    resource = Resource.create(
        {SERVICE_NAME: settings.otel_service_name, "deployment.environment": settings.app_env}
    )
    provider = TracerProvider(resource=resource)
    exporter = OTLPSpanExporter(endpoint=f"{settings.otel_exporter_endpoint.rstrip('/')}/v1/traces")
    provider.add_span_processor(BatchSpanProcessor(exporter))
    trace.set_tracer_provider(provider)

    # ``/health``, ``/ready``, ``/live``, and ``/metrics`` are high-frequency
    # probes; excluding them keeps the trace backend focused on real traffic.
    FastAPIInstrumentor.instrument_app(
        app,
        tracer_provider=provider,
        excluded_urls="health,ready,live,metrics",
    )
    logger.info(
        "tracing.enabled",
        endpoint=settings.otel_exporter_endpoint,
        service=settings.otel_service_name,
    )
    return True


__all__ = ["configure_tracing"]
