# MCP Server & Authentication (Phase 7)

Phase 7 exposes Prism Earth to AI clients over the **Model Context Protocol**
(SRS §34) and adds the **v1.1 authentication model** (SRS §13.20, §13.19).

Two design principles from the SRS drive the shape of this:

- **API-first (§11.2):** the MCP server consumes the *same* public REST API as
  the browser. It is a thin client — `MCP client → MCP server → REST API →
  Planner → Fetch Engine` (§34.2) — so provenance and citations are preserved
  end to end (§16.18) without any special code path.
- **Auth is a gateway toggle (§13.20):** it is applied *without changing
  endpoint contracts*. It ships **off by default** (`PRISM_AUTH_ENABLED=false`)
  so metadata, `/fetch`, and `/ask` stay open for local dev and the browser UX.
  Turn it on for production.

---

## Authentication

### What is protected

| Endpoint | Auth when `PRISM_AUTH_ENABLED=true` |
| --- | --- |
| `GET /api/v1/meta/*`, `GET /api/v1/health*` | **Public** |
| `GET /.well-known/oauth-*` | **Public** (discovery) |
| `POST /api/v1/fetch` | Bearer token with scope `fetch` |
| `POST /api/v1/ask` | Bearer token with scope `ask` |
| `POST/GET/DELETE /api/v1/auth/tokens`, `POST /api/v1/auth/device/approve` | Admin credential |

Tokens are opaque strings (`pe_…`) stored only as a SHA-256 hash. Each token has
scopes, an optional expiry, and an optional per-token rate limit (§13.19); over
the limit returns `429` with `Retry-After`.

### Enable it

In `backend/.env`:

```bash
PRISM_AUTH_ENABLED=true
PRISM_AUTH_ADMIN_TOKEN=some-long-random-admin-secret
# optional
PRISM_AUTH_DEFAULT_RATE_LIMIT_PER_MINUTE=120
PRISM_AUTH_ISSUER_URL=http://localhost:8000
```

Run the migration once so the token tables exist:

```bash
cd backend && .venv/bin/alembic upgrade head
```

### Credential flows

**1. Dashboard-issued API tokens** (admin-gated):

```bash
curl -X POST http://localhost:8000/api/v1/auth/tokens \
  -H "Authorization: Bearer $PRISM_AUTH_ADMIN_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"name":"cli-laptop","scopes":["fetch","ask"]}'
# → {"id":"...","token":"pe_XXXX...","prefix":"pe_XXXX","scopes":["ask","fetch"], ...}
```

The plaintext `token` is shown **once**. Use it as a bearer token:

```bash
curl -X POST http://localhost:8000/api/v1/fetch \
  -H "Authorization: Bearer pe_XXXX..." \
  -H "Content-Type: application/json" \
  -d '{"lat":17.385,"lng":78.486,"preset":"terrain"}'
```

List / revoke: `GET /api/v1/auth/tokens`, `DELETE /api/v1/auth/tokens/{id}` (both admin-gated).

**2. Device flow** (RFC 8628, for CLIs):

1. `POST /api/v1/auth/device/code` → `{device_code, user_code, verification_uri, interval, ...}`
2. Operator approves: `POST /api/v1/auth/device/approve` (admin) with `{user_code}`
3. Client polls the token endpoint until it gets a token:
   `POST /api/v1/auth/oauth/token` with
   `grant_type=urn:ietf:params:oauth:grant-type:device_code&device_code=...`

**3. OAuth 2.0 for MCP clients** (authorization code + PKCE):

- Discovery: `GET /.well-known/oauth-authorization-server` and
  `/.well-known/oauth-protected-resource`.
- Register: `POST /api/v1/auth/oauth/register` (RFC 7591 dynamic client registration).
- Authorize: `GET /api/v1/auth/oauth/authorize?response_type=code&client_id=…&redirect_uri=…&code_challenge=…&code_challenge_method=S256`
  → 302 redirect with `?code=…`.
- Token: `POST /api/v1/auth/oauth/token` with
  `grant_type=authorization_code&code=…&redirect_uri=…&client_id=…&code_verifier=…`.
  Also supports `refresh_token` and `client_credentials` grants.

> Note: this is a minimal, standards-shaped OAuth 2.0 subset sufficient for the
> MCP flow. Consent is auto-granted (there is no interactive login UI in v1);
> the subject of an OAuth token is the client itself.

---

## MCP server

The server is run as a separate process; it talks to the REST API over HTTP.

### Run it

```bash
cd backend
# stdio (Claude Desktop / Cursor launch it this way)
.venv/bin/python -m app.mcp
# or over HTTP for remote clients
.venv/bin/python -m app.mcp --transport streamable-http --port 8765
```

Configuration (env or CLI flags):

| Env | Flag | Default |
| --- | --- | --- |
| `PRISM_MCP_API_BASE_URL` | `--base-url` | `http://localhost:8000/api/v1` |
| `PRISM_MCP_API_TOKEN` | `--token` | *(none)* |
| `PRISM_MCP_TRANSPORT` | `--transport` | `stdio` |
| `PRISM_MCP_HTTP_HOST` / `PRISM_MCP_HTTP_PORT` | `--host` / `--port` | `127.0.0.1` / `8765` |

When auth is enabled, set `--token` (or `PRISM_MCP_API_TOKEN`) to a token that
has the `fetch` and `ask` scopes.

### Tools (SRS §34.1)

- `prism_earth_fetch(lat, lng, fields?, preset?)` — deterministic cited values.
- `prism_earth_ask(lat, lng, question)` — natural-language cited answer + trace.
- `prism_earth_meta_fields(layer?, lifecycle?, available?)` — the field catalog.
- `prism_earth_meta_layers()` / `prism_earth_meta_presets()` — layers / presets.

Every tool returns the REST API's JSON **verbatim**, so `citations` and
`provenance` reach the agent unchanged (§16.18).

### Claude Desktop / Cursor config

Add to the client's `mcpServers` config (adjust the absolute path):

```json
{
  "mcpServers": {
    "prism-earth": {
      "command": "/absolute/path/to/backend/.venv/bin/python",
      "args": ["-m", "app.mcp"],
      "env": {
        "PYTHONPATH": "/absolute/path/to/backend",
        "PRISM_MCP_API_BASE_URL": "http://localhost:8000/api/v1",
        "PRISM_MCP_API_TOKEN": "pe_XXXX..."
      }
    }
  }
}
```

Start the REST API first (`.venv/bin/uvicorn app.main:app --port 8000`); the MCP
server proxies to it.
