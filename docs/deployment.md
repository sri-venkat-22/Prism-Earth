# Deployment Guide

How Prism Earth is containerized and run in production (SRS §32, §33).

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
| `prism-earth-backend` | `python:3.12-slim` | uv, non-root, healthcheck, 4 workers |
| `prism-earth-frontend` | `node:22-alpine` | Next.js standalone, non-root |
| `db` | `postgis/postgis:16-3.4` | persistent volume |
| `redis` | `redis:7-alpine` | AOF persistence |
| `nginx` | `nginx:1.27-alpine` | reverse proxy |

## Running locally (dev)

```bash
docker compose up --build          # db, redis, backend, frontend
```

## Running in production

```bash
export POSTGRES_PASSWORD=...        # required
docker compose -f docker-compose.prod.yml up -d --build
```

The prod compose applies migrations via a one-shot `migrate` service before the
API starts, uses restart policies and healthchecks, backs rate-limit/auth state
with Redis, and runs the backend with JSON logging.

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

The `nginx.conf` includes a commented HTTPS server block. Mount certificates at
`/etc/nginx/certs`, uncomment the block and the `443` port mapping, and reload.

## Environment & secrets

All configuration is environment-driven (`PRISM_*`, see `.env.example`). Secrets
(DB password, admin token, GEE key, LLM key) are supplied via the environment and
never committed. `POSTGRES_PASSWORD` is required in production — the prod compose
fails fast without it.

## Scaling (SRS §33.3)

The backend is stateless (shared state in Redis/PostGIS), so it scales
horizontally behind Nginx/a load balancer. The frontend deploys independently.
PostGIS supports read replicas; Redis provides distributed caching and rate-limit
counters.
