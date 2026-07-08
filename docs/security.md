# Security

Prism Earth applies defense in depth across the API, gateway, and infrastructure
(SRS §29, §13.19, §13.20).

## Authentication (SRS §13.20)

Version 1 separates **public discovery** from **authenticated data access**:

- `GET /api/v1/meta/*` — public, unauthenticated (catalog self-discovery).
- `POST /api/v1/fetch`, `POST /api/v1/ask` — require a bearer token **when auth
  is enabled** (`PRISM_AUTH_ENABLED=true`).

Supported credential flows: dashboard-issued API tokens, device-flow login for
CLI clients, and OAuth 2.0 (PKCE) for MCP clients. Auth is a gateway concern
applied without changing endpoint contracts — the default is **off** in
development so the browser UX and deterministic gate work unchanged. See
[MCP & Authentication](mcp_and_auth.md).

**Production is secure by default.** `docker-compose.prod.yml` sets
`PRISM_AUTH_ENABLED=true` and requires `PRISM_AUTH_ADMIN_TOKEN` (compose fails
fast without it). As a backstop, the app **refuses to start** when
`app_env=production` and auth is off — or when auth is on but no admin token is
set — via `Settings.validate_runtime()`, checked in the startup lifespan; the
readiness probe (`/api/v1/ready`) reports the same problems as defense in depth
(returns `503` with a `config: misconfigured` check).

Tokens are stored **hashed**; scopes gate `fetch` vs `ask`; token management is
guarded by a bootstrap admin credential (`PRISM_AUTH_ADMIN_TOKEN`).

## Rate limiting (SRS §13.19)

Three complementary layers:

1. **Nginx edge limit** — per-IP `limit_req` zone at the reverse proxy.
2. **Gateway limiter** (`app/api/deps.py`) — configurable per-IP fixed-window
   limit on `/fetch` and `/ask`, on regardless of auth. Emits `429` +
   `Retry-After` + `RateLimit-*` headers. Configure with
   `PRISM_RATE_LIMIT_ENABLED` / `PRISM_RATE_LIMIT_PER_MINUTE`.
3. **Per-token budget** — each token carries its own requests/minute limit
   (enforced in `require_auth`).

Counters live in Redis in production, so limits hold across API instances.

**Spoof-safe client identity.** The gateway limiter keys on the client IP, but a
client-supplied `X-Forwarded-For` is spoofable — trusting its first hop would let
an attacker rotate keys to escape the budget. Proxy headers are therefore honored
only when `PRISM_TRUST_PROXY_HEADERS=true` (set in the prod topology, where Nginx
overwrites `X-Real-IP` with the real peer). Then `X-Real-IP` is authoritative,
falling back to the *last* `X-Forwarded-For` hop; exposed directly (the default),
forwarded headers are ignored and the socket peer is used.

## Input validation & hardening (SRS §29.1)

- Request bodies are validated by Pydantic; coordinates are range-checked
  (`lat ∈ [-90, 90]`, `lng ∈ [-180, 180]`), field lists and question length are
  capped.
- A body-size guard rejects oversized payloads (`PRISM_MAX_REQUEST_BODY_BYTES`,
  default 1 MiB) with `413`.
- All failures render the standard error envelope (SRS §28.2) with a correlation
  id — stack traces are never leaked to clients.

## Security headers (SRS §29.3)

`SecurityHeadersMiddleware` sets `X-Content-Type-Options`, `X-Frame-Options`,
`Referrer-Policy`, `Cross-Origin-Opener-Policy`, `Permissions-Policy`, and a
strict `Content-Security-Policy` (relaxed only for the `/docs` and `/redoc`
pages so Swagger UI / ReDoc load). `Strict-Transport-Security` is emitted in
production.

### CORS

The bundled frontend is served **same-origin** through Nginx, so it needs no CORS
entry. `PRISM_CORS_ORIGINS` (a JSON list) is only for a *separate* browser app on
another origin; non-browser consumers (MCP HTTP, `curl`, server-to-server) are
unaffected by CORS. The API authenticates with **bearer tokens**, not cookies, so
`PRISM_CORS_ALLOW_CREDENTIALS` is **off** by default. Two invariants are enforced
in `validate_runtime()`:

- production rejects the `*` wildcard (the prod default is `[]`, same-origin only);
- credentials may **never** be paired with `*` (browsers reject it) in any env.

## Transport security / TLS (SRS §29.2)

Nginx terminates TLS on `:443` using certificates mounted at
`deployment/nginx/certs` (`fullchain.pem` + `privkey.pem`); `:80` returns a `301`
redirect to HTTPS. HSTS is emitted once at the edge (any upstream copy is
stripped with `proxy_hide_header`). **Drop your CA / Let's Encrypt certificates
into `deployment/nginx/certs/` before exposing the service** — Nginx will not
start without them.

## Static security scanning (SRS §35.6)

- **Backend**: ruff `flake8-bandit` (`S`) rules run in lint; `pip-audit` scans
  dependencies in CI.
- **Frontend**: `npm audit` on production dependencies.
- **Filesystem/images**: Trivy scan in CI (`HIGH`/`CRITICAL`).

## Secrets management (SRS §29.2)

All secrets (DB password, admin/LLM tokens, GEE key) come from the environment
and are never committed. GEE keys live in the gitignored `secrets/` directory.

The **GEE service-account key** is mounted read-only into the backend as a Docker
secret (`secrets: [gee_key]` → `/run/secrets/gee_key`, sourced from
`./secrets/prism-earth-gee.json`), never baked into an image. The key currently
on disk is **dev-scoped**: rotate it in Google Cloud and replace the file from
your secret store before production, and set `GEE_SERVICE_ACCOUNT` / `GEE_PROJECT`
in `.env`. See [Google Earth Engine setup](google_earth_engine_setup.md).
