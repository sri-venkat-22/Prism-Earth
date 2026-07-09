# Developer Guide

How to set up, test, and extend Terra (SRS §35).

## Prerequisites

- Python 3.12
- Node.js 22
- PostgreSQL 16 + PostGIS 3.4 (or `docker compose up db`)
- Redis 7 (or `docker compose up redis`)

## Backend setup

```bash
cd backend
python3.12 -m venv .venv && source .venv/bin/activate
pip install -r requirements/dev.txt        # or: uv sync
cp .env.example .env                         # fill in as needed
alembic upgrade head                         # apply migrations
uvicorn app.main:app --reload
```

The API serves at `http://localhost:8000` — docs at `/docs`, health at
`/api/v1/health`, metrics at `/metrics`.

## Frontend setup

```bash
cd frontend
npm install
cp .env.example .env.local
npm run dev                                  # http://localhost:3000
```

## Running the tests

| Suite | Command | Gate |
| --- | --- | --- |
| Backend unit + integration | `cd backend && pytest --cov=app --cov-fail-under=85` | ≥ 85% coverage |
| Frontend unit + component | `cd frontend && npm run test:coverage` | ≥ 70% coverage |
| End-to-end | `cd frontend && npx playwright install chromium && npm run e2e` | all core flows |
| Load test | `locust -f backend/tests/perf/locustfile.py --host http://localhost:8000` | ad hoc |

## Quality gates (run before pushing)

```bash
# Backend
cd backend
ruff check .          # lint + flake8-bandit security rules
black --check .
mypy app
pytest --cov=app --cov-fail-under=85

# Frontend
cd frontend
npm run lint && npm run typecheck && npm run format:check
npm run test:coverage && npm run build
```

CI (`.github/workflows/ci.yml`) runs exactly these on every pull request.

## Coding standards (SRS §35)

- **Backend**: PEP 8, full type hints, async best practices, dependency
  injection, business logic separated from infrastructure.
- **Frontend**: TypeScript, reusable components, no business logic in UI,
  feature-based organization, accessibility.
- **Everything**: tests + docs with every change; the metadata catalog is the
  single source of truth (SRS §38.2); never invent fields, datasets, or
  citations (SRS §38.1).

## Adding a new field

1. Register it in the metadata catalog (`app/metadata/seed_fields.py`) with its
   layer, lifecycle, source, unit, TTL, and null meaning.
2. Ensure its owning connector (`app/connectors/<layer>.py`) can serve it.
3. Add it to a preset in `app/metadata/seed_presets.py` if appropriate.
4. Add tests and run the catalog validator (it runs at startup and in tests).

Because the catalog is authoritative, the Planner, Fetch Engine, API, and
frontend pick up the new field automatically — no hardcoded lists to update.

## Adding a new connector

Implement the connector interface in `app/connectors/` (see `base.py` and an
existing connector like `terrain.py`), register it in
`app/connectors/registry.py`, back it with a data source (inject it so it can be
faked in tests), and add tests using the fakes in `app/tests/_fetch_fakes.py`.
