# Observability

Terra ships structured logging, metrics, and distributed tracing (SRS §27,
§7.7).

## Structured logging (SRS §27.1)

Logs are emitted through `structlog` (`app/core/logging.py`). In production
(`TERRA_LOG_JSON=true`) each line is JSON, ready for Loki ingestion. Every line
carries the request **correlation id** (bound by the correlation middleware and
echoed in the `X-Correlation-ID` response header), so logs, traces, and client
error reports all join on one id. The metrics middleware also emits one
structured access-log line per request (method, route, status, duration).

The platform logs API requests/responses, planner and connector execution,
dataset calls, errors, partial failures, and authentication events (SRS §27.1).

## Metrics (SRS §27.2)

Prometheus metrics are exposed at `GET /metrics` (`app/observability/metrics.py`):

| Metric | Type | Meaning |
| --- | --- | --- |
| `terra_http_requests_total` | counter | Requests by method, route, status |
| `terra_http_request_duration_seconds` | histogram | Request latency |
| `terra_http_requests_in_progress` | gauge | In-flight requests |
| `terra_connector_health` | gauge | 1 = ok, 0 = degraded, per connector |
| `terra_gee_request_duration_seconds` | histogram | Earth Engine latency |
| `terra_cache_events_total` | counter | Cache hits/misses (hit ratio) |
| `terra_pipeline_stage_duration_seconds` | histogram | Planner/fetch/synth latency |
| `terra_planner_dropped_proposals_total` | counter | Planner proposals dropped by the catalog constraint, by kind (`unknown_field` / `planned_field` / `unknown_preset`) |

These cover the §27.2 list: API latency, request volume, error rate, cache hit
ratio, connector health, and Earth Engine response time.

**Alerting note (12-D):** dropped planner proposals are normal at a trickle —
the catalog constraint exists to absorb them — but a sustained rise means the
planner prompt and the catalog have drifted apart (e.g. after a catalog edit)
or the model is hallucinating field names. Suggested alert:
`sum(rate(terra_planner_dropped_proposals_total[15m])) > 0.1` (more than ~1
drop per 10 s sustained for 15 min) → review recent catalog changes and the
planner prompt.

## Tracing (SRS §27.3)

OpenTelemetry tracing is **opt-in** (`app/observability/tracing.py`). Set
`TERRA_OTEL_ENABLED=true` and `TERRA_OTEL_EXPORTER_ENDPOINT=http://otel:4318`
to auto-instrument FastAPI and export spans via OTLP/HTTP. When unset it is a
no-op, so dev and tests carry no overhead.

## Dashboards & log aggregation

The monitoring overlay (`docker-compose.monitoring.yml`) runs:

- **Prometheus** — scrapes `backend:8000/metrics` every 15s.
- **Grafana** (`:3001`) — provisioned with Prometheus + Loki datasources and the
  **Terra — API Overview** dashboard (request rate, p95 latency, error
  rate, cache hit ratio, connector health, and live logs).
- **Loki** + **Promtail** — ship and index container JSON logs.

```bash
docker compose -f docker-compose.prod.yml -f docker-compose.monitoring.yml up -d
# Grafana:    http://localhost:3001  (admin / $GRAFANA_ADMIN_PASSWORD)
# Prometheus: http://localhost:9090
```

## Health & readiness (SRS §7.3, §13.16)

- `GET /api/v1/health` — always 200 while serving; reports each dependency.
- `GET /api/v1/ready` — 200 only when DB and Redis are reachable (readiness probe).
- `GET /api/v1/live` — pure liveness.
- `GET /api/v1/health/connectors` — per-connector operational status.
