# Terra — Production-Readiness Audit & Continuation Plan (Phases 9–14)

**Audit date:** 2026-07-04 · **Auditor:** senior full-stack / security engineering pass
**Baseline:** Phases 0–8 of the Build Plan are **committed** (`git log` shows Phase 0 → Phase 8 landed). This document does **not** reopen those phases. It continues the roadmap: everything below is organized into **new sequential phases 9 → 14**, designed to be executed top to bottom to take the committed platform from "feature-complete" to "production-deployable."
**Method:** every finding was traced in source before being written. Where something could not be executed in the sandbox (backend test suite, live GEE/PostGIS calls, CVE scanners), it is called out explicitly and moved to *Known Unknowns* rather than asserted.

---

## How to read this document

Phases 0–8 built the platform. **Phases 9–14 below harden it for production.** They are ordered by dependency and risk: Phase 9 is the "cannot ship without it" security gate; each later phase assumes the earlier ones are done. Findings from all five audit areas (design/UX, feature parity, data integrity, architecture, security) are **folded into whichever phase they belong to**, not grouped by audit area.

Each task is written as **what to change → exact file/location → why → priority**, where:

- **P0** — blocks first production deployment.
- **P1** — must be fixed before external/enterprise users or before turning auth on.
- **P2** — quality/hardening/cleanup; schedule but not a launch blocker.

Each phase ends with a **concrete self-check** and its **dependencies** on earlier phases.

### Roadmap at a glance

| Phase | Name | Focus | Gate |
|------|------|-------|------|
| 0–8 | *(committed)* | Scaffold → catalog → spatial → fetch → connectors → /ask → frontend → MCP+auth → hardening | done |
| **9** | Production Security Baseline | auth-on, CORS, TLS, rate-limit key, secrets | **P0** |
| **10** | Data Integrity & Authoritative-Source Truth | remove synthetic data, reconcile advertised vs actual sources | P0/P1 |
| **11** | Caching, Performance & Failure Isolation | §23 caching, GEE concurrency/timeouts, SPOFs | P1 |
| **12** | AI Pipeline & Auth-Model Hardening | prompt-injection, OAuth trust model, FE auth wiring | P1 |
| **13** | Frontend / UX Parity Verification | mireye visual pass, basemap, copy | P2 |
| **14** | Release Gate | blocking scans, test run, docs, §36 acceptance | P1 |

> **One theme spans Phases 9–14, so read it first.** The platform's data plumbing is genuinely wired and — crucially — *honestly cited in code*. The anti-fabrication design (planner constrained to the catalog, synthesizer restricted to fetched values) is real and well built. **But several of the specifically-branded Indian authoritative sources in the product framing are not the sources actually serving data.** CartoDEM, CWC/NRSC flood layers, and NAKSHA/Dharani cadastral are substituted with global open datasets (Copernicus DEM, JRC GloFAS, OSM, Google Open Buildings) or, in one case, a hand-drawn fixture — because the Indian sources have no open API/bulk path. The code's provenance is truthful about this; the SRS, config, and marketing copy are not yet. Reconciling *advertised sources* with *actual sources* is the highest-value cleanup and recurs throughout (mostly Phase 10).

---

## What Phases 0–8 already got right (verified — do not "fix")

So the forward phases stay action-focused, here is what the audit confirmed is production-grade and should be preserved:

- **Anti-fabrication core.** The Planner (`planners/planner.py`) asks the model only for `intent/presets/fields`, then deterministically filters through `Catalog.is_selectable` — unknown/`planned` fields are dropped, never selected; layers/connectors are *derived* from fields so the model can't invent a connector. The Synthesizer (`synthesizers/synthesizer.py`) sees only fetched values, computes unavailable fields deterministically from nulls, and validates citation markers. The LLM client returns an honest **503** when unconfigured. This satisfies "Planner selects, Fetch retrieves, Synthesizer only phrases."
- **Real connector wiring.** All nine connectors route through the catalog-driven registry with typed nulls and partial-failure isolation; lazy client/session construction turns missing creds into fetch-time partial failures, not crashes. No silent fake-data fallback found (except the cadastral fixture — Phase 10).
- **Honest in-code provenance.** Where a substitute source is used, the code cites the real source (e.g. terrain cites Copernicus DEM, not CartoDEM).
- **Low injection surface.** All DB access is SQLAlchemy ORM/expressions with parameterized `ST_*` calls — no raw string SQL. SSRF surface is low — no user-controlled URLs on the fetch path; GEE asset IDs fixed; coordinates bounded (`FetchRequest` `ge/le` + `model_validator`).
- **Strong security headers & CI.** `default-src 'none'` CSP for the JSON API; `X-Frame-Options: DENY`, nosniff, COOP, Permissions-Policy; HSTS in prod. CI runs lint/type/format, pytest (85% gate), vitest (70% gate), Playwright E2E, pip-audit + npm audit + Trivy, dual Docker builds, strict MkDocs.
- **Observability.** Prometheus `/metrics`, opt-in OTLP tracing, structlog with correlation IDs, per-pipeline-stage latency.

The gaps in Phases 9–14 are configuration defaults, source-claim honesty, one data fixture, a missing caching layer, and auth-model trust — not the deterministic core.

---

## Phase 9 — Production Security Baseline

**Goal:** no data endpoint is open by default, transport is encrypted, and abuse controls can't be trivially bypassed — the minimum to expose the platform to anyone.

### Tasks

**9-A · Default authentication ON for production. [P0]**
- *What:* `auth_enabled` defaults `False` in `config.py`, **and** `docker-compose.prod.yml` sets `TERRA_AUTH_ENABLED: ${TERRA_AUTH_ENABLED:-false}`. A default prod deploy serves `/fetch`, `/ask`, and every MCP tool **fully unauthenticated.**
- *Where:* `backend/app/core/config.py` (`auth_enabled`); `docker-compose.prod.yml` (`backend_env`); `.env.example`.
- *Why:* the flagship data endpoints are open by default in the production topology. Top launch blocker.
- *Fix:* in the production compose require auth (`:?set TERRA_AUTH_ENABLED`) or default `true`; ship a documented bootstrap `TERRA_AUTH_ADMIN_TOKEN`; fail readiness if prod + auth disabled.

**9-B · Lock down CORS for production. [P0]**
- *What:* `cors_origins` defaults to `["*"]` **with** `allow_credentials=True` (`main.py`), never overridden in prod. Wildcard + credentials is a misconfiguration (browsers reject the combo; the intent — any origin — is wrong for a credentialed API).
- *Where:* `backend/app/core/config.py` (`cors_origins`), `backend/app/main.py` (`CORSMiddleware`), `docker-compose.prod.yml`.
- *Fix:* explicit env allow-list in prod; never pair `*` with credentials; startup assertion rejecting `["*"]` + credentials when `is_production`.

**9-C · Enable TLS/HTTPS at the edge. [P0/P1]**
- *What:* `nginx.conf` ships the `:443` server block **commented out**; the prod topology serves plain HTTP. The app emits HSTS in prod, which is meaningless without edge TLS.
- *Where:* `deployment/nginx/nginx.conf`, `docker-compose.prod.yml` (443 port commented).
- *Fix:* enable the TLS block with mounted certs before any public exposure.

**9-D · Fix rate-limit key spoofing via `X-Forwarded-For`. [P1]**
- *What:* `_client_key` takes `X-Forwarded-For.split(",")[0]` — the **client-controlled** first hop. Behind nginx (which *appends* the real IP), an attacker sets `X-Forwarded-For` to rotate keys and bypass the per-IP gateway limit.
- *Where:* `backend/app/api/deps.py:_client_key`.
- *Fix:* trust only nginx-set `X-Real-IP` (already in `nginx.conf`) or the *last* XFF entry; make trusted-proxy behavior explicit/configurable.

**9-E · Protect and rotate the GEE service-account key. [P1]**
- *What:* `secrets/terra-gee.json` is a **real-shaped GCP service-account private key in the working tree.** Verified git-ignored (`/secrets/`) and never committed (`git log --all -- secrets/` is empty) — good — but a live key on disk is a standing risk.
- *Where:* `secrets/terra-gee.json`; `.gitignore`.
- *Fix:* confirm it is dev-scoped, rotate before prod, load prod creds from a secrets manager / mounted secret, never the repo.

### Done looks like
With prod settings, `/fetch` and `/ask` reject missing/invalid tokens (metadata stays public); CORS rejects an unlisted origin; the site serves over HTTPS; a spoofed `X-Forwarded-For` no longer resets the rate-limit counter; the GEE key is rotated and sourced from a secret store.

### Dependencies
None — this is the do-first gate. (Builds on the auth machinery delivered in Phase 7.)

---

## Phase 10 — Data Integrity & Authoritative-Source Truth

**Goal:** no synthetic or dead placeholder data is reachable in a production response, and every advertised source matches the source that actually serves data.

### Tasks

**10-A · Remove the synthetic parcel fixture from the production seed path. [P0]**
- *What:* `datasets/telangana/parcels.geojson` contains exactly **one hand-drawn parcel** (`parcel_id: "HYD-KHB-001"`, `survey_number: "123/A"`, residential, 4500 m²). The Cadastral connector serves it cited to **"Telangana Bhu Bharati"** (an authoritative land-records system). Telangana enables all cadastral fields (`configs/telangana.yaml → region_gated_fields`), so a `/fetch` at a point inside that polygon (≈ 78.486, 17.385 — the coordinate used across the UI demos) returns a **fabricated parcel wearing a government citation.**
- *Where:* `datasets/telangana/parcels.geojson`; `backend/app/connectors/cadastral.py`; `scripts/seed_telangana.py:389`; `configs/telangana.yaml`.
- *Why:* violates "authoritative sources only" and "no synthetic data reachable in production." The connector docstring is honest that this is a dev fixture, but nothing enforces it.
- *Fix (pick one):* (a) exclude the cadastral seed unless `TERRA_ENABLE_DEV_FIXTURES=true`, default the parcel table empty in prod; or (b) disable cadastral region-gated fields in `telangana.yaml` until a real Bhu Bharati agreement lands (they then null-out as `unsupported_state`); or (c) change the fixture's provenance dataset to an unmistakable `"Terra sample parcel (non-authoritative)"`.

**10-B · Reconcile the terrain-source claim (CartoDEM → Copernicus DEM). [P1]**
- *What:* product framing/SRS name **Bhuvan/ISRO CartoDEM**; code uses `TERRAIN_DEM_KEY = "copernicus_dem"` (Copernicus DEM GLO-30) and **honestly cites Copernicus DEM** — CartoDEM isn't in the public GEE catalog. Data path is real; the *claim* is wrong.
- *Where:* `backend/app/gee/datasets.py` (`TERRAIN_DEM_KEY` + comment); `configs/telangana.yaml → supported_datasets`.
- *Fix:* update SRS/config/marketing to state "elevation: Copernicus DEM GLO-30 (CartoDEM pending an accessible source)", or wire CartoDEM via Bhuvan.

**10-C · Reconcile "CWC/NRSC flood" and "NASA FIRMS" claims; delete dead layers. [P1]**
- *What:* `flood_zones.geojson` / `historical_floods.geojson` (rectangles labelled "CWC") are seeded into PostGIS (`FloodHazardZone`, `HistoricalFlood`) **but no connector reads those tables** — `natural_hazard.py` uses **JRC GloFAS** (raster) + **OSM** waterbodies for flood, and **VIIRS VNP14A1** (not the FIRMS product) for fire. Config still advertises "CWC Flood Data / NRSC Waterbody Database / NASA FIRMS."
- *Where:* `datasets/telangana/{flood_zones,historical_floods}.geojson`; `scripts/seed_telangana.py:320-345`; `backend/app/models/spatial.py:131,155`; `configs/telangana.yaml → seed.hazards`, `supported_datasets`.
- *Fix:* remove the dead fixtures + models + config entries (or wire a real CWC/NRSC layer); update `supported_datasets` to name GloFAS/OSM/VIIRS — the sources the runtime actually queries.

**10-D · Machine-readable "derived by Terra" provenance qualifier. [P2]**
- *What:* `flood_hazard_class` is Terra's **own** return-period→severity banding derived from GloFAS *depth* bands (documented honestly in the docstring), yet cited to `"JRC Global River Flood Hazard Maps"` as if JRC produced the class.
- *Where:* `backend/app/connectors/natural_hazard.py` (`_FLOOD_RETURN_PERIODS`, `_SPEC`).
- *Fix:* add a provenance qualifier (e.g. `derivation: "Terra banding of JRC GloFAS depth"`) so the derived nature is machine-readable, not just in a docstring.

**10-E · Finalize the large-file storage strategy (villages ~50–150 MB). [P1]**
- *What:* `datasets/telangana/villages.geojson` (~32 MB) is git-ignored, meant to be regenerated by `scripts/fetch_telangana_admin.py`. The seed script tolerates its absence (`_load_features` treats a missing fixture as empty, `seed_telangana.py:100-108`) — confirm the fresh-checkout regenerate path works.
- *Where:* `.gitignore`, `scripts/fetch_telangana_admin.py`, `datasets/README.md`.
- *Fix:* document the regenerate command; pin the upstream source revision; decide Git LFS vs regenerate-on-seed and state it.

**10-F · Ingest the remaining real layers. [P1]**
- *What:* real natural-hazard vector, utilities beyond OSM (DISCOM/telecom), and real Dharani/Bhu Bharati cadastral remain fixtures or OSM-only. Continue the admin-ingestion pattern (SoI/GHMC ingestion is genuinely done and cited — `ADMIN_PROVENANCE.json` is solid).
- *Where:* `scripts/`, `datasets/telangana/`, per-connector source classes.

### Done looks like
`POST /api/v1/fetch` at (17.385, 78.486) with a cadastral-covering preset returns **no value traceable to a hand-authored fixture under a government citation**; `grep -rn "flood_zones\|historical_floods" backend/app/connectors` is empty (or a connector now reads them); `supported_datasets` names only sources the runtime queries; a fresh checkout seeds committed layers and regenerates large ones.

### Dependencies
Phase 9 (so a trustworthy data layer isn't also an open one). Independent of 11–14.

---

## Phase 11 — Caching, Performance & Failure Isolation

**Goal:** the hot path is buffered against GEE latency, no single slow dependency can pin request handling, and scaling SPOFs are documented.

### Tasks

**11-A · Implement the fetch-result caching layer (§23). [P1]**
- *What:* every GEE dataset carries a `ttl` descriptor and the SRS specifies §23 caching, but **the orchestrator computes fresh every request** — Redis is used only for auth/rate-limit state, never for fetch results. Each `/fetch` re-hits GEE (several blocking round trips).
- *Where:* `backend/app/fetchers/orchestrator.py` (no cache read/write); `backend/app/core/redis.py` (available, unused for this).
- *Why:* GEE latency dominates `/fetch` and `/ask`; without caching, cost and p95 scale with traffic and GEE is an unbuffered hot-path dependency.
- *Fix:* keyed read-through cache (`{connector}:{field}:{rounded lat,lng}`) honoring each dataset's TTL, backed by the existing Redis client.

**11-B · Bound GEE concurrency and add a per-fetch deadline. [P1]**
- *What:* GEE calls run via `asyncio.to_thread` sharing the default thread pool; there is no overall per-fetch deadline (only per-call timeouts). A slow GEE region can pin request threads.
- *Where:* connector `fetch` methods; `fetchers/orchestrator.py` (`asyncio.gather`).
- *Fix:* bounded semaphore + `asyncio.wait_for` deadline around the fan-out; on timeout the field becomes a `CONNECTOR_TIMEOUT` null (machinery exists in `_record_connector_failure`).

**11-C · Enforce an end-to-end `/ask` deadline. [P1]**
- *What:* `/ask` = planner LLM call + full fetch fan-out + synthesizer LLM call, serially, with no overall wall-clock budget.
- *Where:* `backend/app/ask/pipeline.py` (`AskPipeline.ask`).
- *Fix:* wrap the pipeline in an overall `asyncio.wait_for`; on partial fetch timeout, synthesize from what resolved (the trace already carries `partial_failures`).

**11-D · Document SPOFs and trim per-request rebuilds. [P2]**
- *What:* single PostGIS and single Redis are SPOFs; `build_connector_registry` is re-instantiated per request in health/fetch (cheap but avoidable). `/ready` correctly fails closed when deps are down.
- *Where:* `docker-compose.prod.yml`, `fetchers/`, `api/v1/health.py`.
- *Fix:* document HA expectations (managed Postgres + replica, Redis persistence/replica), consider memoizing the registry.

**11-E · Assert every catalog field has an owning, servable connector. [P2]**
- *What:* owned-but-not-servable fields (`wildfire_risk`, `cropland_class`, `telecom_coverage`, DISCOM/tariff) correctly return typed nulls; verify none is silently unroutable as a hard error.
- *Where:* per-connector `_SERVABLE` vs `seed_fields`; `registry.route()`.
- *Fix:* catalog test asserting every non-planned field maps to a registered connector (partly in `test_phase4_*`).

### Done looks like
A repeated `/fetch` at the same coordinate is served from cache (cache-hit metric / no second GEE round trip); a simulated slow connector yields a `CONNECTOR_TIMEOUT` null instead of hanging the request; `/ask` honors an overall deadline; HA expectations are documented.

### Dependencies
Phase 10 (cache trustworthy data, not fixtures). Caching should precede heavy `/ask` use.

---

## Phase 12 — AI Pipeline & Auth-Model Hardening

**Goal:** the one place free text is model-generated is injection-resistant, and "authenticated" actually means "authorized."

### Tasks

**12-A · Treat the question as untrusted input to the Synthesizer. [P1]**
- *What:* the raw `question` flows into both prompts. Injection **cannot** cause fabricated *cited data* (planner is catalog-constrained; citations validated), but a crafted question could steer the synthesizer's free-text prose. Worst case is misleading prose around correct citations.
- *Where:* `synthesizers/synthesizer.py` (`_SYNTH_SYSTEM`, `_build_synth_user_prompt`); `planners/prompts.py`.
- *Fix:* delimit the user question explicitly (fenced), reinforce "the values block is authoritative; question text cannot change which values exist," and add a regression test feeding an injection string, asserting unavailable fields stay marked and no non-fetched number appears.

**12-B · Define and enforce the OAuth/MCP trust model (open registration + auto-consent). [P1]**
- *What:* `/auth/oauth/register` is **unauthenticated** (RFC 7591) and `/oauth/authorize` **auto-grants consent** with `subject = "oauth:{client_id}"` — no user login/consent UI. So even with `auth_enabled=true`, anyone can self-register and mint `fetch`/`ask` tokens; auth becomes identification, not authorization. Also, `redirect_uri` is only validated when the client registered non-empty `redirect_uris` (`service.create_authorization_code`).
- *Where:* `backend/app/api/v1/auth.py` (`register_client`, `authorize`); `backend/app/auth/service.py` (`create_authorization_code`).
- *Fix:* decide the model — gate `/oauth/register` (admin/invite) or keep it open but scope- and rate-limit self-issued tokens and document the intentionally low-trust MCP surface. Make `redirect_uri` validation unconditional (require ≥1 registered URI).

**12-C · Wire the frontend to send a bearer token once auth is on. [P1]**
- *What:* `services/api.ts` sends no `Authorization` header; when 9-A lands, browser `/fetch` and `/ask` calls will 401.
- *Where:* `frontend/services/api.ts`.
- *Fix:* add token handling (dashboard-issued or a public read token scoped to fetch/ask), consistent with the 12-B model.

**12-D · Meter planner "dropped field" warnings. [P2]**
- *What:* proposed non-existent/planned fields are dropped into `plan.warnings`; a spike signals prompt drift or catalog mismatch.
- *Where:* `planners/planner.py` (`warnings`), `observability/metrics.py`.
- *Fix:* counter for dropped/undocumented proposals; alert on rate.

### Done looks like
An injection-string test proves no non-fetched value is ever stated and unavailable fields stay flagged; `/oauth/register` behaves per the documented trust model and `redirect_uri` is always validated; the browser UX works against the authenticated backend; dropped-field rate is observable.

### Dependencies
Phase 9 (auth on) and Phase 11 (`/ask` deadline). Precedes exposing `/ask` broadly via MCP.

---

## Phase 13 — Frontend / UX Parity Verification

**Goal:** confirm the browser experience matches the mireye/YC-startup visual language screen-by-screen and every screen works end-to-end, including the authenticated path.

### What's already strong (verified)
The frontend is a faithful implementation of the mireye aesthetic, adapted to India: cream/paper palette, `mono-eyebrow` labels, `font-display` type, terminal-window hero, `rounded-full` CTAs, `paper-grid`, Framer-Motion `Reveal` animations, editorial section headings. It **exceeds** a typical mireye marketing site (Ask, Dashboard map, Explore, Fetch, System), keeps dev tools behind `DEV_TOOLS`, and holds no business logic — field lists/presets/regions come from `/meta/*` (SRS §38.5). `tsc --noEmit` passes clean.

### Tasks

**13-A · Manual screen-by-screen visual pass against mireye.com. [P2 — could-not-verify-in-sandbox]**
- *What:* I could not render mireye.com here (client-side-rendered; WebFetch saw only meta tags; the Chrome extension wasn't connected), so a true pixel/layout diff wasn't possible. Static analysis shows a strong stylistic match; spacing/typography/interaction details need a human eye or a rendered capture.
- *Where:* `frontend/app/*`, `frontend/components/*`, `frontend/tailwind.config.ts`.
- *Fix:* open both sites side by side (or reconnect Claude-in-Chrome); check hero rhythm, nav treatment, section spacing, hover/scroll interactions.

**13-B · Verify the MapLibre tile/style source and its license. [P1]**
- *What:* `Dashboard` uses MapLibre (`features/map/map-canvas.tsx`, client-only). MapLibre needs a style/tile source; if it points at a keyed provider, confirm key handling and basemap licensing/attribution for a commercial India product.
- *Where:* `frontend/features/map/config.ts`, `map-canvas.tsx`.
- *Fix:* confirm the style URL, ensure no secret key ships in client bundles, satisfy attribution/licensing.

**13-C · Confirm graceful degradation (backend down, auth on). [P2]**
- *What:* `api.ts` surfaces a clear network error; verify loading/empty/error states on each page and that, post-9-A, the flows still work with the bearer token from 12-C.
- *Where:* `components/feedback.tsx`, `hooks/useQueries.ts`, all pages.

**13-D · Align the homepage demo's cited source names with reality. [P2]**
- *What:* the hero terminal demo (`app/page.tsx`) is labelled "Illustrative response" (good) but cites "NASA SRTM" for terrain, while the runtime serves Copernicus DEM (and SRS says CartoDEM) — three names, one field.
- *Where:* `frontend/app/page.tsx` (terminal demo block).
- *Fix:* cite the source the platform actually returns, or genericize the illustrative copy. (Ties to Phase 10 source reconciliation.)

### Done looks like
A human visual pass signs off on mireye parity; the map renders with a licensed basemap and no client-shipped secret; every screen shows correct loading/empty/error states and works against the authenticated backend; demo copy names the real source.

### Dependencies
Phases 9 & 12 (authenticated path) and Phase 10 (source names).

---

## Phase 14 — Release Gate

**Goal:** production readiness against the SRS §36 acceptance criteria, with the security scan actually blocking and the test suite verified green in a real environment.

### Tasks

**14-A · Make the security scan blocking (after triage). [P1]**
- *What:* the `security-scan` CI job is `continue-on-error: true` — pip-audit/npm audit/Trivy findings surface but never fail the build.
- *Where:* `.github/workflows/ci.yml` (`security-scan`).
- *Fix:* add an allow/ignore list for accepted advisories, then flip to blocking so new HIGH/CRITICAL CVEs stop a release. (I could not run these scanners in the sandbox — no network — so the current advisory state is a *Known Unknown*; run in CI and triage.)

**14-B · Run and record the backend test suite in a real environment. [P1]**
- *What:* I **could not execute** the backend pytest suite here — the committed `backend/.venv` is macOS-linked (`python3.12 -> /Library/Frameworks/...`) and the sandbox has no network to reinstall, so test health is asserted from CI config, not observed. Frontend `tsc --noEmit` passed; frontend vitest couldn't run (macOS-native `@rollup/rollup-linux-*` binary missing).
- *Where:* `backend/app/tests/*` (25 modules), CI.
- *Fix:* confirm green on Linux/CI; treat the 85%/70% coverage gates as source of truth until then.

**14-C · Documentation & SRS reconciliation. [P2]**
- *What:* update SRS/docs so advertised data sources match actual ones (recurring theme), and reconcile the Build Plan status snapshot (says 3.5–8 "not started") with the tree (all committed through Phase 8).
- *Where:* `docs/`, `Prism_Earth_SRS_*.docx`, `Prism_Earth_Phased_Build_Plan_v2.docx`.

**14-D · §36 acceptance sign-off. [P1]**
- *What:* functional, technical, quality, and documentation acceptance (§36.1–36.4) → release approval (§36.5), now that Phases 9–13 close the gaps.
- *Where:* SRS §36 checklist.

### Done looks like
CI is green with the security scan **blocking**; the backend suite runs green on Linux/CI at ≥85%; `/metrics` is reachable only from the monitoring network (already enforced in `nginx.conf`); docs name the real sources and the plan status matches the tree; SRS §36.1–36.4 all pass.

### Dependencies
Everything above — this is the final gate.

---

## Executive summary — top 10 highest-risk items (across Phases 9–14)

1. **Auth OFF by default in the production compose (9-A, P0).** `/fetch`, `/ask`, and all MCP tools serve unauthenticated in a default prod deploy.
2. **CORS wildcard + credentials, not overridden in prod (9-B, P0).** Misconfigured cross-origin policy on a credentialed API.
3. **Synthetic parcel fixture reachable in production under a government citation (10-A, P0).** One hand-drawn parcel is served cited to "Telangana Bhu Bharati" at the coordinate used in all demos.
4. **Advertised Indian sources ≠ actual sources (10-B/10-C, cross-cutting P1).** CartoDEM→Copernicus DEM, CWC/NRSC→GloFAS+OSM, FIRMS→VIIRS, NAKSHA cadastral→fixture. Code is honestly cited; SRS/config/marketing are not.
5. **No fetch-result caching despite §23/TTL spec (11-A, P1).** Every request re-hits GEE; latency/cost scale with traffic; GEE is an unbuffered hot-path dependency.
6. **OAuth: open dynamic registration + auto-consent (12-B, P1).** Anyone can self-register and mint fetch/ask tokens even with auth on; conditional redirect-uri validation.
7. **Rate-limit key spoofable via `X-Forwarded-For` (9-D, P1).** Trivial per-IP limit bypass behind nginx.
8. **No TLS in the default deployment (9-C, P0/P1).** `:443` block commented out; plain HTTP.
9. **Security scan is non-blocking (14-A, P1).** pip-audit/npm audit/Trivy run report-only; new CVEs won't stop a release. (Actual advisory state unverified — see Known Unknowns.)
10. **Live GEE service-account key on disk (9-E, P1).** Git-ignored and never committed (verified), but a real key in the tree; rotate and move to a secrets manager.

**Counterweight — what's genuinely strong and should not be "fixed":** the anti-fabrication architecture, the real connector wiring with typed nulls and partial-failure isolation, honest in-code provenance, parameterized SQL (low injection risk), strong security headers, and a comprehensive CI pipeline. The deterministic core (Phases 0–8) is production-grade; Phases 9–14 close configuration, source-honesty, caching, and auth-trust gaps.

---

## Known unknowns (could not verify with certainty / needs human, live, or legal review)

- **Live data-source behavior.** No GEE/PostGIS credentials, so every GEE/PostGIS path was verified by **tracing code**, not executing a live fetch. Wiring is real and correct in source; actual returned values, GEE quota behavior, and edge-case nulls need a live smoke test (`scripts/gee_smoke_test.py`, `scripts/resolve_point.py`).
- **Backend test suite health.** Not executed (macOS-linked `.venv`, no sandbox network). 25 test modules exist; CI gates at 85% — treat CI as source of truth. Frontend `tsc` passed; vitest couldn't run (macOS-native node binaries).
- **Dependency CVE state.** pip-audit/npm audit/Trivy could not run here (no network). Current advisory list unknown until CI runs them; 14-A also makes them blocking.
- **mireye.com pixel-level parity.** mireye.com is client-rendered and the Chrome extension wasn't connected, so no rendered capture/diff was possible. Static analysis shows a strong stylistic match; a human side-by-side pass (13-A) is still required.
- **Data licensing / reuse rights (legal review).** Needs counsel: (a) **Bhuvan/ISRO CartoDEM**, **Survey of India** boundaries, and **NAKSHA/Dharani/Bhu Bharati** cadastral have India-specific reuse/redistribution terms — confirm commercial serving of derived values; (b) **OpenStreetMap** is ODbL (share-alike/attribution — attributed in `OSM_PROVENANCE.json`, but derivative-database terms need review for a commercial API); (c) **Copernicus/Sentinel-2/ERA5**, **ESA WorldCover**, **JRC GloFAS/GSW**, **Google Open Buildings** (CC BY-4.0 + Google terms), **TerraClimate**, **MODIS/VIIRS** each carry attribution/licensing conditions that must be surfaced in provenance and satisfied.
- **Penetration test.** OAuth/device flows, PKCE, token lifecycle, and the gateway limiter warrant a real pen test — static review found the issues above but can't substitute for adversarial testing.
- **Prompt-injection robustness of the Synthesizer.** Design contains fabrication; residual risk is prose manipulation (12-A). Needs adversarial testing with real models.
- **MapLibre basemap.** Tile/style provider, key handling, and basemap license not fully traced (13-B).
