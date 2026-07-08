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
export POSTGRES_PASSWORD=...                 # required
export PRISM_AUTH_ADMIN_TOKEN=$(openssl rand -hex 32)   # required: bootstraps token issuance
# Drop TLS certs in place first (see TLS below):
#   deployment/nginx/certs/{fullchain.pem,privkey.pem}
docker compose -f docker-compose.prod.yml up -d --build
```

The prod topology is **secure by default**: auth is on (`PRISM_AUTH_ENABLED=true`),
CORS is locked to same-origin (`PRISM_CORS_ORIGINS=[]`), proxy-IP trust is on for
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

All configuration is environment-driven (`PRISM_*`, see `.env.example`). Secrets
(DB password, admin token, GEE key, LLM key) are supplied via the environment and
never committed. `POSTGRES_PASSWORD` and `PRISM_AUTH_ADMIN_TOKEN` are required in
production — the prod compose fails fast without them.

The **GEE service-account key** is mounted read-only as a Docker secret
(`./secrets/prism-earth-gee.json` → `/run/secrets/gee_key`), never baked into an
image. Rotate the dev key and replace the file from your secret store before
exposure; set `GEE_SERVICE_ACCOUNT` / `GEE_PROJECT` in `.env`.

## Scaling (SRS §33.3)

The backend is stateless (shared state in Redis/PostGIS), so it scales
horizontally behind Nginx/a load balancer. The frontend deploys independently.
PostGIS supports read replicas; Redis provides distributed caching and rate-limit
counters.
