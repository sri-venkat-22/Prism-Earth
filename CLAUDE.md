# Prism-Earth — Project Memory

## What this is
An India-focused geospatial intelligence API + MCP server: give it a lat/lng (and optionally a natural-language question), get back real, cited data — terrain, soil, land cover, hydrology/wetland, and related fields — sourced from ISRO Bhuvan, Sentinel-2, and other India-coverage datasets.

The target architecture is modeled on **Mireye Earth** (`docs.mireye.ai`), a comparable US-coverage product — but nothing in their catalog is India-appropriate as-is. US federal sources (FEMA, USFWS NWI, NRCS SSURGO, USGS) have no meaning here. For every field, find or flag the Indian equivalent before adding it (e.g. slope/aspect from an Indian DEM, soil drainage from whatever India soil survey is actually accessible, wetland intersection from India's National Wetland Inventory / state atlases where reachable). Copy the *contract*, not the *catalog*.

Owner: Sri Venkat, solo developer, building this as a real, launchable product — not a class exercise. When in doubt, ship a smaller feature that's fully real over a bigger one with any stubbed data.

## Architecture to match
Two data endpoints + one MCP server, all backed by one field catalog:

- **`POST /ask`** — natural-language question in, prose answer out, backed by real fetched data.
- **`POST /fetch`** — deterministic: pass field names or a preset, get raw per-field values with provenance. `/ask` should call this internally rather than duplicating fetch logic.
- **`GET /meta/fields`** (public, no auth) — self-describing field catalog: name, layer, type, unit, source, description, which presets include it, cache TTL. This one catalog should drive request validation, any frontend field picker, and the `/ask` planner's context — not three copies of the same list.
- **MCP server** exposing `ask` and `fetch` as tools with the same contracts as the HTTP API.

**Per-field shape** — every field, in `/ask`'s internal fetch and in `/fetch`'s response, should carry: `value, unit, source, source_url, confidence (high/medium/low/unknown), fetched_at, dataset_vintage, ttl_seconds, notes, status (ok/absent/failed)`. A field that failed to fetch still appears, with `status: "failed"` and a real error — never omit a requested field silently.

**`/ask` response shape** — `answer` (prose only), `confidence`, `citations[]`, `fields_used[]`, `data_gaps[]` (requested fields that resolved to nothing, with why), optional `trace`. These are separate top-level fields. The answer text itself never contains inline citation markers, source parentheticals, or footnotes.

Reference docs — fetch these directly if you need an exact schema rather than trusting the paraphrase above (I kept this file short on purpose):
- https://docs.mireye.ai/introduction
- https://docs.mireye.ai/authentication
- https://docs.mireye.ai/api-reference/ask
- https://docs.mireye.ai/api-reference/fetch
- https://docs.mireye.ai/api-reference/meta-fields
- https://docs.mireye.ai/mcp/installation
- https://docs.mireye.ai/mcp/tools
- `GET https://api.mireye.com/v1/meta/fields` is live and public (no token needed) — curl it for a real example of the target catalog shape. Fields are US-specific; the JSON structure is what to mirror.

## Non-negotiables, this phase
1. **Real data only.** No mocked, hardcoded, or placeholder field values in the `/ask` or `/fetch` path, ever. Not wired up yet → `status: "failed"` with a real error, not a fake number.
2. **Ask fetches broadly.** Resolve the full relevant preset (or the full catalog, if nothing fits) for a location — don't let a planning step narrow the underlying fetch down to only the 2-3 fields it thinks the literal question needs. The synthesizer can still write a focused answer; the data returned to the client should be comprehensive.
3. **Clean answer text.** `answer` is prose only. No inline citations, no "(Source: X, high confidence)" fragments stitched into sentences.
4. **Metadata is opt-in.** Confidence, caveats, sourcing/provenance, and execution trace ride along in the response payload but render behind a "Show details" toggle in the UI — not printed under the answer by default. A small "N fields returned" count next to the toggle is fine to leave visible.
5. **No empty databases.** Neon and Upstash each get one clear job (below) and must actually be populated by the code that touches them.

## Data layer
- **Neon (Postgres)** = system of record: users, API tokens (hashed — never store plaintext), query/audit logs. Normalize it — audit the current tables first, merge or drop duplicates, and write an actual migration for every change from here on.
- **Upstash (Redis)** = the fetch-result cache and rate limiter — not a second database. Cache each fetched field by something like `(lat_rounded, lng_rounded, field_name)` for its own `ttl_seconds`. If Upstash is empty right now, that's the tell that the cache layer was provisioned but never wired into the fetch path — fix the wiring, don't dump unrelated data in just to fill it.
- Put both behind a small repository/data-access layer so a later move to AWS (RDS + ElastiCache, or self-hosted) is a config change, not a rewrite.

## Explicitly out of scope for this session
Roadmap context only — do not build these now, but don't design this phase's schema in a way that blocks them later:
- AWS migration.
- A dedicated auth system: accounts + hashed API tokens in Neon, one `Authorization: Bearer <token>` header (no query-param keys) — roughly Mireye's model.
- A per-user "map server" product surface with per-user scoped API keys.

A nullable `user_id` column now, left unused, is fine. A parallel auth micro-service today is not.

## Where things actually live
- Backend entrypoint: `backend/app/main.py` (`create_app`)
- `/ask` handler: `backend/app/api/v1/ask.py` → `backend/app/ask/pipeline.py` (Planner → Fetch → Synthesizer). Planning is **deterministic** (`backend/app/planners/planner.py`, no LLM — full selectable catalog, broad-fetch policy); the ONE LLM call per ask is the Synthesizer's (`backend/app/synthesizers/synthesizer.py` via `backend/app/llm/client.py`).
- `/fetch` handler: `backend/app/api/v1/fetch.py` → `backend/app/fetchers/orchestrator.py` (the same engine `/ask` uses internally)
- Field-catalog source of truth: `backend/app/metadata/` — `seed_fields.py` / `seed_layers.py` / `seed_presets.py` loaded through `catalog.py` (93 fields, 9 layers, 18 presets; 51 fields currently selectable)
- Frontend answer-rendering component: `frontend/features/ask/answer-view.tsx` (page: `frontend/app/ask/page.tsx`)
- Neon schema / migrations: `backend/migrations/versions/` (Alembic, `backend/alembic.ini`)
- Upstash client: `backend/app/core/redis.py`; fetch-result cache `backend/app/fetchers/cache.py`; whole-answer ask cache `backend/app/ask/cache.py`

## Commands
Local toolchain is python3.12 venv + npm (no Docker/uv locally):
- Install: `cd backend && python3.12 -m venv .venv && .venv/bin/pip install -r requirements/dev.txt`; `npm --prefix frontend install`
- Run dev server: `cd backend && .venv/bin/python -m uvicorn app.main:app --reload --port 8000`; `npm --prefix frontend run dev`
- Run tests: `cd backend && .venv/bin/python -m pytest app/tests`; `npm --prefix frontend test`
- Lint / typecheck: `cd backend && .venv/bin/python -m ruff check app && .venv/bin/python -m black --check app && .venv/bin/python -m mypy app`

## How to work in this repo
- Read before writing — confirm current behavior in the actual code before assuming what's broken.
- Small, verifiable steps. After a change, verify it with a real API call against a real coordinate, and show the output.
- Ask before destructive changes to existing Neon data, or any schema change that isn't purely additive.
- Keep code minimal and direct — no framework ceremony beyond what the repo already uses.
