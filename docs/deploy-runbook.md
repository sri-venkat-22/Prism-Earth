# Deploy Runbook (Render + Vercel)

How Terra actually runs in production today — as distinct from the self-hosted
Docker/Nginx topology in the [Deployment Guide](deployment.md). Facts below
were verified against the live services on 2026-07-20.

## Topology

| Piece | Where | How it deploys |
|---|---|---|
| Backend API | Render free-tier web service → `https://terra-backend-pgtq.onrender.com` | Dashboard-configured GitHub integration builds `backend/Dockerfile` on push to `main`. **There is no `render.yaml`** — service settings, env vars, and the deploy trigger live only in the Render dashboard. |
| Frontend | Vercel | Auto-deploys every push to `main`. |
| Postgres | Neon (`ap-southeast-1`), schemas `admin/cadastral/hazards/infrastructure/metadata` | Migrations run from the backend image's Docker entrypoint (`alembic upgrade head`) on boot. |
| Redis | Upstash (TLS, `rediss://`) | Nothing to deploy; fetch-result + ask-answer caches and rate limiting. |

Notes that bite:

- **Local dev shares the production data layer.** `backend/.env` points at the
  same Neon and Upstash instances Render uses. Local `/fetch` calls write into
  the production field cache; treat local runs as production traffic.
- Render's auto-deploy is **not CI-gated** (observed 2026-07-13: a commit with
  red CI deployed). CI protects `main` only socially — check Actions before
  pushing.
- The backend exposes no git SHA; `/api/v1/health` reports the static
  `version: 0.1.0`. Confirming *which commit* is live requires the Render
  dashboard (Events tab) or a behavioral probe.
- Free tier spins down on idle; `.github/workflows/keep-warm.yml` pings the
  service on a schedule to soften cold starts. `/ask` also carries its own
  deadline (`TERRA_ASK_DEADLINE_SECONDS`, default 90) below Render's ~100 s
  edge timeout.

## Backend env vars (Render dashboard → Environment)

Everything in `backend/.env.example` prefixed `TERRA_`; the ones that are easy
to get wrong:

- `TERRA_EARTH_ENGINE_SERVICE_ACCOUNT` + `TERRA_EARTH_ENGINE_KEY_JSON` — the
  raw service-account JSON in an env var (no disk on the free tier).
- `TERRA_POSTGRES_*` → Neon; `TERRA_REDIS_URL` → Upstash (`rediss://`).
- `WEB_CONCURRENCY` — drives uvicorn workers; keep low on the free instance.

## Did my push actually deploy?

1. Render dashboard → service → **Events**: the deploy for your commit SHA
   should appear within a minute of the push and end **Live**.
2. No event for your push → Settings → Build & Deploy: confirm *Auto-Deploy*
   is on and the GitHub repo/branch connection is intact; then **Manual Deploy
   → Deploy latest commit**.
3. Behavioral check: `POST /api/v1/ask` with a *fresh* `(lat, lng, question)`
   pair (the answer cache is keyed on exactly that) and look for the marker of
   the commit you shipped.

## Deploy drift postmortem (2026-07-13 → 2026-07-20)

Auto-deploy silently stopped after deploying `8979984`; `b386efd` and
`3e306d6` never deployed and nothing in the repo could show why (the trigger
state lives only in the dashboard). If it recurs, start at step 2 above —
and prefer adding a commit-SHA marker to `/health` before debugging prose.
