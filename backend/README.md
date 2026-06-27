# Prism Earth — Backend

FastAPI + async SQLAlchemy backend for Prism Earth (SRS §9, §11). **Phase 0** is
a scaffold: configuration, structured logging, the standard error model, health
endpoints, and Alembic wiring — **no business logic**.

## Stack

Python 3.12 · FastAPI · Pydantic v2 · SQLAlchemy (async) · Alembic · Redis ·
structlog. Dependencies are managed with [uv](https://docs.astral.sh/uv/).

## Layout (SRS §10)

```
app/
  api/v1/      versioned routers (health only in Phase 0)
  core/        config, logging, database, redis, errors
  config/      configs/*.yaml loader
  models/      SQLAlchemy declarative base (no entities yet)
  schemas/     Pydantic response models (error model §28.2, health §13.16)
  middleware/  correlation-id middleware
  tests/       pytest suite
  connectors/ planners/ fetchers/ synthesizers/ citations/
  repositories/ services/ workers/ utils/   (placeholders for later phases)
migrations/    Alembic env (no versions yet)
requirements/  exported requirements (uv is source of truth)
```

## Local development

```bash
uv sync                       # create .venv and install all deps
uv run uvicorn app.main:app --reload --port 8000
```

Endpoints (SRS §13.16): `GET /api/v1/health`, `/api/v1/ready`, `/api/v1/live`.
API docs at `/docs` (Swagger) and `/redoc`.

## Quality gates

```bash
uv run ruff check .           # lint + import order
uv run black --check .        # formatting
uv run mypy app               # type checking
uv run pytest                 # tests
```

## Migrations (used from Phase 2)

```bash
uv run alembic revision --autogenerate -m "message"
uv run alembic upgrade head
```

Configuration is environment-driven (prefix `PRISM_`); see `.env.example`.
