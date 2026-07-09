# Deployment Guide

How Terra is containerized and run in production (SRS §32, §33).

## Production topology (SRS §33.1)

```
        Users
          │  HTTPS
     ┌────▼──────┐
     │   Nginx    │  reverse proxy, TLS, gzip, edge rate limit
     └──┬─────┬──┘
        │     │
  ┌─────▼─┐ ┌─▼──────────┐
  │Front- │ │  FastAPI    │  multi-worker (uvicorn --workers)
  │end    │ │  backend    │
  └───────┘ └──┬───────┬──┘
               │       │
          ┌────▼─┐  ┌──▼───┐        ┌──────────────┐
          │Redis │  │PostGIS│  ◄──►  │ Google Earth │
          └──────┘  └──────┘        │    Engine     │
                                    └──────────────┘
```

Nginx routes `/` to the frontend and `/api`, `/docs`, `/redoc`, `/metrics`, and
`/.well-known/` to the backend. It forwards the real client IP so the backend's
gateway rate limiter keys correctly (SRS §13.19).

## Containers (SRS §32.1)

| Image | Base | Notes |
| --- | --- | --- |
| `terra-backend` | `python:3.12-slim` | uv, non-root, healthcheck, 4 workers |
| `terra-frontend` | `node:22-alpine` | Next.js standalone, non-root |
| `db` | `postgis/postgis:16-3.4` | persistent volume |
| `redis` | `redis:7-alpine` | AOF persistence |
| `nginx` | `nginx:1.27-alpine` | reverse proxy |

## Running locally (dev)

```bash
docker compose up --build          # db, redis, backend, frontend
```

## Running in production

```bash
export POSTGRES_PASSWORD=...                 # required
export TERRA_AUTH_ADMIN_TOKEN=$(openssl rand -hex 32)   # required: bootstraps token issuance
# Drop TLS certs in place first (see TLS below):
#   deployment/nginx/certs/{fullchain.pem,privkey.pem}
docker compose -f docker-compose.prod.yml up -d --build
```

The prod topology is **secure by default**: auth is on (`TERRA_AUTH_ENABLED=true`),
CORS is locked to same-origin (`TERRA_CORS_ORIGINS=[]`), proxy-IP trust is on for
spoof-safe rate limiting, and the app **refuses to start** if production is
misconfigured (auth off, no admin token, or wildcard CORS). The compose applies
migrations via a one-shot `migrate` service before the API starts, uses restart
policies and healthchecks, backs rate-limit/auth state with Redis, and runs the
backend with JSON logging.

### With the monitoring stack

```bash
docker compose -f docker-compose.prod.yml -f docker-compose.monitoring.yml up -d
```

Adds Prometheus, Grafana, Loki, and Promtail — see the
[Observability](observability.md) guide.

## Publishing images

`.github/workflows/release.yml` builds and pushes both images to GHCR on a
version tag (`v1.2.3`). CI must be green on the commit first (SRS §30.4, §36.5).

## TLS (SRS §29.2)

TLS is **enabled by default** in the prod topology: Nginx terminates HTTPS on
`:443` and redirects `:80` → HTTPS. Mount your certificates (`fullchain.pem` +
`privkey.pem`, from your CA or Let's Encrypt) into `deployment/nginx/certs/`
**before** starting — Nginx will not boot without them. To rotate, replace the
files and reload (`docker compose -f docker-compose.prod.yml exec nginx nginx -s reload`).

## Environment & secrets

All configuration is environment-driven (`TERRA_*`, see `.env.example`). Secrets
(DB password, admin token, GEE key, LLM key) are supplied via the environment and
never committed. `POSTGRES_PASSWORD` and `TERRA_AUTH_ADMIN_TOKEN` are required in
production — the prod compose fails fast without them.

The **GEE service-account key** is mounted read-only as a Docker secret
(`./secrets/terra-gee.json` → `/run/secrets/gee_key`), never baked into an
image. Rotate the dev key and replace the file from your secret store before
exposure; set `GEE_SERVICE_ACCOUNT` / `GEE_PROJECT` in `.env`.

## Scaling (SRS §33.3)

The backend is stateless (shared state in Redis/PostGIS), so it scales
horizontally behind Nginx/a load balancer. The frontend deploys independently.
PostGIS supports read replicas; Redis provides distributed caching and rate-limit
counters. When running more than one backend instance, set
`TERRA_AUTH_USE_REDIS=true` so auth/rate-limit state is shared rather than
per-process.

## Hot-path resilience (SRS §23, §7.1)

The fetch hot path is buffered against slow upstreams; all knobs are
environment-driven (defaults in parentheses):

- **Fetch-result cache** (`TERRA_FETCH_CACHE_ENABLED`, on): a read-through
  Redis cache keyed `{connector}:{field}:{rounded lat,lng}`
  (`TERRA_FETCH_CACHE_COORD_PRECISION`, 4 decimals ≈ 11 m), expiring on each
  dataset's declared TTL. A repeated `/fetch` or `/ask` at the same coordinate
  never re-hits Google Earth Engine inside the TTL window. Hit/miss counts are
  published as `terra_cache_events_total{cache="fetch_result"}`. The cache is
  fail-open: Redis being down degrades to misses, never to request failures.
  Failure nulls (`connector_timeout` / `dataset_unavailable`) are never cached.
- **Bounded GEE concurrency** (`TERRA_GEE_MAX_CONCURRENCY`, 8): blocking Earth
  Engine calls are admitted through a per-process semaphore, so a slow GEE
  region queues on the event loop instead of exhausting the shared thread pool
  and pinning request handling.
- **Per-connector fetch deadline** (`TERRA_FETCH_DEADLINE_SECONDS`, 20): each
  connector in the fan-out runs under a wall-clock budget; on expiry its fields
  return as `connector_timeout` nulls with a retryable partial failure while the
  other connectors' results are served normally (SRS §15.16).
- **End-to-end /ask deadline** (`TERRA_ASK_DEADLINE_SECONDS`, 60): the whole
  planner → fetch → synthesizer pipeline runs under one budget and returns
  `504 DEADLINE_EXCEEDED` instead of hanging on a stalled LLM provider. A
  *partial* fetch timeout does not trip it — the answer is synthesized from the
  fields that resolved.

## Single points of failure & HA expectations

The bundled `docker-compose.prod.yml` is a **single-node** topology; every
stateful service in it is a SPOF. For production-grade availability:

| Component | Failure mode today | HA expectation |
| --- | --- | --- |
| PostGIS (`db`) | Single container; loss stops state detection, all PostGIS connectors, and `/ready` fails closed | Managed PostgreSQL with PostGIS (RDS/Cloud SQL/Azure) with automated backups + a streaming replica; point `TERRA_POSTGRES_*` at it |
| Redis | Single container; loss degrades the fetch cache to misses (fail-open) and, with `TERRA_AUTH_USE_REDIS=true`, drops auth/rate-limit state; `/ready` fails closed | Managed Redis (ElastiCache/Memorystore) with AOF or RDB persistence and a replica; cache contents are reconstructible, auth state should persist |
| Backend API | Stateless | ≥2 replicas behind the load balancer; readiness (`/api/v1/ready`) already gates traffic correctly |
| Nginx edge | Single container | Run the platform load balancer (ALB/Cloud LB) in front, or ≥2 edge nodes |
| Google Earth Engine | External dependency, no self-hosted fallback | Buffered by the fetch cache + deadline; sustained outage degrades GEE-backed fields to retryable nulls, the platform stays up |
| LLM provider | External dependency for `/ask` only | Bounded by `TERRA_LLM_TIMEOUT` and the `/ask` deadline; `/fetch` is unaffected; the LiteLLM route (`TERRA_LLM_MODEL`) can be repointed to a fallback provider |

`/api/v1/ready` fails closed when PostGIS or Redis is unreachable, so replicas
drop out of rotation rather than serving errors.
