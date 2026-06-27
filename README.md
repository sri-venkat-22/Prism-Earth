# Prism Earth

Deterministic, citation-backed geospatial intelligence for India. Prism Earth
turns a coordinate into provenance-tracked, source-cited geospatial data — and,
via an AI layer, into natural-language answers that never fabricate values.

> **Status: Phase 0 — Scaffold & Foundations.** A runnable empty platform.
> No business logic yet. See `Prism_Earth_Phased_Build_Plan.md` for the roadmap
> and `Prism_Earth_SRS_v1.0.docx` for the full specification.

## Quick start

Requires Docker + Docker Compose.

```bash
docker compose up --build
```

This boots four services:

| Service  | URL                                   | Notes                          |
| -------- | ------------------------------------- | ------------------------------ |
| Backend  | http://localhost:8000                 | FastAPI; docs at `/docs`       |
| Frontend | http://localhost:3000                 | Next.js placeholder page       |
| Postgres | localhost:5432                        | PostGIS 16-3.4                 |
| Redis    | localhost:6379                        | —                              |

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
├── docs/         documentation (MkDocs site in Phase 8)
├── deployment/   deployment manifests (Phase 8)
├── docker/       shared container assets (PostGIS init, future Nginx)
├── scripts/      operational scripts (e.g. Telangana seed, Phase 2)
├── tests/        cross-cutting / E2E tests (Phase 8)
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

## Architecture principles (SRS §11.2)

Configuration-driven (no hardcoded region/dataset values), deterministic
execution (never fabricates data), full provenance and citations, modular
connectors, API-first. The metadata catalog is the single source of truth from
Phase 1 onward.

## License

MIT (placeholder — change in `LICENSE` if a different license is intended).
