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
applied without changing endpoint contracts — the default is **off** so the
browser UX and deterministic gate work unchanged; production turns it on. See
[MCP & Authentication](mcp_and_auth.md).

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
production. CORS origins are environment-driven (`PRISM_CORS_ORIGINS`) — tighten
away from `*` in production.

## Static security scanning (SRS §35.6)

- **Backend**: ruff `flake8-bandit` (`S`) rules run in lint; `pip-audit` scans
  dependencies in CI.
- **Frontend**: `npm audit` on production dependencies.
- **Filesystem/images**: Trivy scan in CI (`HIGH`/`CRITICAL`).

## Secrets management (SRS §29.2)

All secrets (DB password, admin/LLM tokens, GEE key) come from the environment
and are never committed. GEE keys live in the gitignored `secrets/` directory.
