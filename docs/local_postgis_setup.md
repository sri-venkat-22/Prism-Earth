# Local PostGIS Setup (SRS §20)

Phase 2 needs a PostgreSQL + PostGIS database. The repo ships a
`postgis/postgis` service in `docker-compose.yml`, but for local development
without Docker (macOS / Homebrew) follow this guide.

## Install (Homebrew)

```bash
brew install postgis postgresql@17     # postgis pulls geos/proj/gdal; @17 is the server
brew services start postgresql@17
export PATH="/opt/homebrew/opt/postgresql@17/bin:$PATH"
```

`postgis` installs its extension files into the `postgresql@17` tree, so
`CREATE EXTENSION postgis` works against an `@17` server.

## Create the role and database

```bash
psql -d postgres -c "CREATE ROLE terra LOGIN PASSWORD 'terra' SUPERUSER;"
createdb -O terra terra
```

`SUPERUSER` is for local dev only — `CREATE EXTENSION postgis` needs it. In
production, create the extension once as an admin and run the app with a
least-privilege role (SRS §20.11).

## Point the backend at it

The backend reads `TERRA_POSTGRES_*` (SRS §9). For local runs:

```bash
export TERRA_POSTGRES_HOST=localhost
export TERRA_POSTGRES_PORT=5432
export TERRA_POSTGRES_USER=terra
export TERRA_POSTGRES_PASSWORD=terra
export TERRA_POSTGRES_DB=terra
```

(or copy `backend/.env.example` to `backend/.env` and edit it.)

## Migrate + seed + verify

```bash
cd backend && alembic upgrade head          # creates schemas, tables, GIST indexes (SRS §20.3–20.6, §22.3)
cd .. && python scripts/seed_telangana.py   # loads the Telangana fixtures (SRS §24.4)
# Optional: also seed the hand-authored sample cadastral parcel (dev-only,
# non-authoritative demo data — never seeded in production):
#   TERRA_ENABLE_DEV_FIXTURES=true python scripts/seed_telangana.py

python scripts/resolve_point.py 17.385 78.486   # → Telangana → Hyderabad → Khairatabad …
python scripts/resolve_point.py 19.07 72.87      # → outside Telangana (flagged)
```

## Inspect the schema

```bash
psql -d terra -c "\dn"                              # 8 logical schemas
psql -d terra -c "SELECT f_table_schema, f_table_name, srid, type FROM geometry_columns ORDER BY 1,2;"
psql -d terra -c "SELECT schemaname, indexname FROM pg_indexes WHERE indexdef ILIKE '%USING gist%';"
```

## Run the state-detection integration test

```bash
export TERRA_TEST_DATABASE_URL="postgresql+asyncpg://terra:terra@localhost:5432/terra"
cd backend && pytest app/tests/test_state_detection.py -q   # runs the live PostGIS check
```
