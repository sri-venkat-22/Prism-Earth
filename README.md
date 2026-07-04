# Prism Earth

Deterministic, citation-backed geospatial intelligence for India. Prism Earth
turns a coordinate into provenance-tracked, source-cited geospatial data — and,
via an AI layer, into natural-language answers that never fabricate values.

> **Status: Version 1 — production-ready (SRS §36).** The full platform is built
> and hardened: deterministic Fetch spine, AI `/ask` pipeline, MCP server, browser
> UX, comprehensive tests (pytest · Vitest · Playwright), observability
> (Prometheus · OpenTelemetry · Loki · Grafana), security + rate limiting, CI/CD,
> and a MkDocs documentation site. See the [documentation](docs/index.md) and
> `Prism_Earth_SRS_v1.0.docx` for the full specification.

## Quick start

Requires Docker + Docker Compose.

```bash
docker compose up --build
```

This boots four services:

| Service  | URL                                   | Notes                          |
| -------- | ------------------------------------- | ------------------------------ |
| Backend  | http://localhost:8000                 | FastAPI; docs `/docs`, metrics `/metrics` |
| Frontend | http://localhost:3000                 | Next.js browser UX (Ask · Dashboard · Fetch · Explore) |
| Postgres | localhost:5432                        | PostGIS 16-3.4                 |
| Redis    | localhost:6379                        | —                              |

For production (Nginx + multi-worker backend + monitoring), see the
[Deployment Guide](docs/deployment.md):

```bash
docker compose -f docker-compose.prod.yml -f docker-compose.monitoring.yml up -d
```

Verify the backend:

```bash
curl http://localhost:8000/api/v1/health   # -> 200 {"status":"ok", ...}
```

Health endpoints (SRS §13.16): `/api/v1/health`, `/api/v1/ready`, `/api/v1/live`.

## Repository layout (SRS §10)

```
prism-earth/
├── backend/      FastAPI app (api, core, config, models, schemas, middleware, …)
├── frontend/     Next.js + TS + Tailwind + ShadCN shell
├── datasets/     dataset isolation (telangana, raster, vector, metadata)
├── configs/      india.yaml, telangana.yaml, datasets.yaml (config-driven)
├── docs/         MkDocs documentation site (architecture, deploy, API, datasets)
├── deployment/   Nginx reverse proxy + monitoring stack (Prometheus/Grafana/Loki)
├── docker/       shared container assets (PostGIS init)
├── scripts/      operational scripts (Telangana seed, OpenAPI export, …)
├── tests/        cross-cutting fixtures; E2E lives in frontend/e2e (Playwright)
├── .github/      CI workflows
├── docker-compose.yml
├── README.md
└── LICENSE
```

## Local development (without Docker)

Backend (uses [uv](https://docs.astral.sh/uv/)):

```bash
cd backend && uv sync
uv run uvicorn app.main:app --reload      # needs Postgres + Redis for /ready
uv run ruff check . && uv run mypy app && uv run pytest
```

Frontend:

```bash
cd frontend && npm install && npm run dev
npm run lint && npm run typecheck
```

Install git hooks: `pip install pre-commit && pre-commit install`.

## Testing (SRS §30)

| Suite | Command | Gate |
| --- | --- | --- |
| Backend (pytest) | `cd backend && pytest --cov=app --cov-fail-under=85` | ≥ 85% coverage |
| Frontend (Vitest) | `cd frontend && npm run test:coverage` | ≥ 70% coverage |
| E2E (Playwright) | `cd frontend && npx playwright install chromium && npm run e2e` | core flows |

CI (`.github/workflows/ci.yml`) runs lint, type-check, both test suites with
coverage gates, E2E, security scans, Docker builds, and the docs build on every
pull request. See the [Developer Guide](docs/developer-guide.md).

## Architecture principles (SRS §11.2)

Configuration-driven (no hardcoded region/dataset values), deterministic
execution (never fabricates data), full provenance and citations, modular
connectors, API-first. The metadata catalog is the single source of truth from
Phase 1 onward.

## License

MIT (placeholder — change in `LICENSE` if a different license is intended).
