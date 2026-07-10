# Production Review Report — 2026-07-10

Full-stack review of Terra (backend, frontend, database, auth, AI pipeline,
deployment) against the question: *does every implemented feature work when
deployed online?* The review was verification-driven: every layer was exercised
with its real toolchain, not just read.

## Verification results (after fixes)

| Gate | Result |
| --- | --- |
| Backend pytest | **272 passed**, 1 skipped |
| Backend ruff / black / mypy | clean (106 files, 0 issues) |
| Frontend vitest | **53 passed** (9 files) |
| Frontend eslint / prettier / tsc | clean |
| `next build` (production) | ✓ 12/12 pages |
| `docker compose -f docker-compose.prod.yml config` | ✓ valid (incl. nested env interpolation) |
| `mkdocs build --strict` | ✓ |

## Issues found & fixed

### 1. `/ask` would be dead in production (deployment bug — fixed)
`docker-compose.prod.yml` never passed any LLM configuration to the backend
container. Locally `/ask` works via the gitignored `backend/.env`, but that file
is excluded from the image (`.dockerignore`), so a cloud deploy had **no LLM
credential at all** → every `/ask` returns 503.
**Fix:** `TERRA_LLM_MODEL` + `TERRA_LLM_API_KEY` are now plumbed through the
compose env block.

### 2. OAuth/Google URLs pinned to localhost in production (deployment bug — fixed)
`TERRA_AUTH_ISSUER_URL` and `TERRA_FRONTEND_BASE_URL` were not settable through
the prod compose, so the `/.well-known` OAuth discovery documents (used by MCP
clients) and the Google-login callback redirect would advertise
`http://localhost:8000` / `http://localhost:3000` on a real domain — breaking
MCP OAuth and Google sign-in.
**Fix:** `TERRA_AUTH_ISSUER_URL` is now **required** in the prod compose
(fail-fast `:?` check); `TERRA_FRONTEND_BASE_URL` defaults to it (same-origin
topology). `TERRA_GOOGLE_OAUTH_CLIENT_ID/SECRET` are passed through too.

### 3. No TLS mode for managed Postgres (fixed)
The uncommitted move to Neon/Upstash left the asyncpg DSN with the driver
default `sslmode=prefer` — it connects, but is silently downgradeable to
plaintext by an active MITM.
**Fix:** new `TERRA_POSTGRES_SSLMODE` setting appended to the DSN
(`?ssl=require`); verified the SQLAlchemy asyncpg dialect forwards it to the
driver. Prod compose defaults it to `require`; dev is unchanged (unset).
Covered by a new unit test. Alembic migrations use the same DSN property, so
the `migrate` one-shot job is covered as well. (Upstash needs no equivalent:
`rediss://` URLs get TLS natively from redis-py.)

### 4. Google OAuth account-takeover hardening (security — fixed)
`app/auth/google.py` treated a **missing** `email_verified` claim as verified
(`info.get("email_verified", True)`). Since the callback links Google identities
to existing accounts **by email**, an attacker with an unverified Google email
matching a victim's account could take the account over.
**Fix:** the claim must now be explicitly `true`.

### 5. Latent CI failures on main (fixed)
The working tree would have failed the CI gate: 2 Python files failed
`black --check`, 1 import-order ruff error, and 3 frontend files failed
`prettier --check`. All auto-fixed; full gate re-run clean.

### 6. Dead code: unbounded in-memory rate-limit store (fixed)
`InMemoryEphemeralStore._sweep()` was defined but never called, so expired
keys/counters accumulated for the life of a dev process. Now swept on `incr`
(the high-churn path).

### 7. Stale deployment documentation (fixed)
Root `.env.example` and `docs/deployment.md` still described the old bundled
`db`/`redis` containers (`POSTGRES_PASSWORD` required, container SPOF table,
image list). Both rewritten for the managed Neon/Upstash topology, including
the new required variables and the `/ask` + Google-login enablement steps.

## Files modified

| File | Change |
| --- | --- |
| `docker-compose.prod.yml` | +SSL mode, +issuer/frontend URLs, +LLM env, +Google OAuth env |
| `backend/app/core/config.py` | `postgres_sslmode` setting; DSN appends `?ssl=…` |
| `backend/app/auth/google.py` | require explicit `email_verified: true` |
| `backend/app/auth/stores.py` | wire `_sweep()` into `incr()` |
| `backend/app/tests/test_config_validation.py` | new sslmode DSN test |
| `backend/app/api/v1/account.py`, `backend/app/metadata/seed_fields.py`, `backend/app/tests/test_account.py` | ruff/black auto-fixes (formatting only) |
| `frontend/app/page.tsx`, `frontend/components/account/account-auth.tsx`, `frontend/components/account/account-dashboard.tsx` | prettier auto-fixes (formatting only) |
| `.env.example`, `backend/.env.example` | documented new prod variables |
| `docs/deployment.md` | managed-data-tier topology, env table, SPOF table |
| `REVIEW_REPORT.md` | this report |

## What was reviewed and found sound (no changes needed)

- **Backend architecture**: FastAPI app factory, fail-fast config validation at
  startup + readiness probe, structured logging, correlation IDs, metrics,
  standard error envelope. mypy/ruff clean, 272 tests.
- **Auth**: scrypt password hashing (constant-time verify, handles Google-only
  accounts), HttpOnly/Secure/SameSite=Lax session cookies (token never exposed
  to JS), per-token + per-IP rate limits with spoof-safe client keying behind
  Nginx, admin credential compared with `secrets.compare_digest`, login errors
  don't leak account existence.
- **Fetch/Ask pipeline**: deterministic orchestrator with per-connector
  deadlines, partial-failure isolation, read-through Redis cache (fail-open),
  end-to-end `/ask` deadline → 504, honest 503 when the LLM is unconfigured.
- **Frontend**: every page/feature is wired to a real backend endpoint through
  `services/api.ts` (metadata, fetch, ask, health, full account lifecycle);
  no console noise; all 11 dependencies actually used; production build
  prerenders all 12 routes.
- **Database**: migrations create PostGIS extensions + schemas themselves, so a
  plain `alembic upgrade head` provisions managed Postgres (Neon) end-to-end.
- **Deployment**: non-root multi-stage images with healthchecks, one-shot
  migrate job gating the API, Nginx TLS termination + HSTS + edge rate limit +
  internal-only `/metrics`, GEE key as a Docker secret, monitoring overlay
  (checked: no references to the removed db/redis containers).
- **CI**: full gate (lint, type, tests+coverage, E2E, security scans, Docker
  builds, strict docs build) — mirrored locally during this review.
- **Repo hygiene**: no committed secrets, junk, or build artifacts;
  `.DS_Store` / `.idea` / `site/` / caches / `backend/.env` / `secrets/` are all
  gitignored. Largest committed files are the intended Telangana seed GeoJSONs
  (≤13 MB).

## Remaining recommendations (not blocking)

1. **GEE secret filename**: the prod compose mounts `./secrets/terra-gee.json`;
   the local key file is `secrets/prism-earth-gee.json`. On the deploy host,
   create the file under the `terra-gee.json` name (compose fails at `up`
   otherwise). Rotate the key before first exposure, per `docs/deployment.md`.
2. **Neon cold starts**: Neon's free/scale-to-zero plans suspend the database;
   the first request after idle can take seconds. `pool_pre_ping` is already
   on, which handles reconnects — just choose an always-on compute for
   latency-sensitive SLOs.
3. **`/ask` provider key**: the compose leaves `TERRA_LLM_API_KEY` optional
   (endpoint degrades to an honest 503). If `/ask` is a launch feature, treat
   the key as required in your deploy checklist.
4. **E2E in CI only**: Playwright E2E runs in CI with a mocked API; it was not
   re-run locally (no browsers installed). CI will exercise it on push.
5. **Session cleanup**: revoked/expired session tokens accumulate in the
   `auth.api_tokens` table indefinitely. Harmless at current scale; add a
   periodic purge if the table ever matters.
