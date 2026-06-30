# Prism Earth — Backend

FastAPI + async SQLAlchemy backend for Prism Earth (SRS §9, §11). Through
**Phase 2** it provides: configuration, structured logging, the standard error
model, health endpoints; the Metadata Catalog + State Registry (Phase 1); and the
**spatial data layer** — PostGIS schema/migrations, the Telangana seed, the State
Detection Service, and the Google Earth Engine client (Phase 2).

## Stack

Python 3.12 · FastAPI · Pydantic v2 · SQLAlchemy (async) · Alembic · PostGIS via
GeoAlchemy2 + Shapely · Google Earth Engine · Redis · structlog. Dependencies are
managed with [uv](https://docs.astral.sh/uv/).

## Layout (SRS §10)

```
app/
  api/v1/      versioned routers (health, metadata)
  core/        config, logging, database, redis, errors
  config/      configs/*.yaml loader
  metadata/    Metadata Catalog & State Registry (§11.4–11.8)
  models/      ORM entities: registry (§22.3) + spatial (§20.4)
  gee/         Earth Engine auth, dataset registry, client (§19)
  services/    state detection — point-in-polygon (§15.7)
  schemas/     Pydantic models (error §28.2, health §13.16, spatial §15.7)
  middleware/  correlation-id middleware
  tests/       pytest suite
  connectors/ planners/ fetchers/ synthesizers/ citations/
  repositories/ workers/ utils/   (placeholders for later phases)
migrations/    Alembic env + versions (PostGIS schema, §20, §22)
requirements/  exported requirements (uv is source of truth)
```

## Spatial data & Earth Engine (Phase 2)

```bash
alembic upgrade head                       # PostGIS schemas, tables, GIST indexes
python ../scripts/seed_telangana.py        # load the Telangana fixtures (§24.4)
python ../scripts/resolve_point.py 17.385 78.486   # state-detection demo (§15.7)
python ../scripts/gee_smoke_test.py        # Earth Engine elevation smoke test (§19)
```

See [docs/local_postgis_setup.md](../docs/local_postgis_setup.md) and
[docs/google_earth_engine_setup.md](../docs/google_earth_engine_setup.md).

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
