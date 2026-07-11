"""Application configuration (SRS §9, §13).

Settings are loaded from environment variables (prefixed ``TERRA_``) and an
optional ``.env`` file using Pydantic v2 ``BaseSettings``. No business logic or
dataset-specific values live here — those belong in ``configs/*.yaml`` and are
read through :mod:`app.config.loader`.
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Annotated, Literal

from pydantic import field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

# Repository root: app/core/config.py -> core -> app -> backend -> <repo root>
BASE_DIR = Path(__file__).resolve().parents[3]

Environment = Literal["development", "testing", "staging", "production"]


class Settings(BaseSettings):
    """Centralized, environment-driven application settings."""

    model_config = SettingsConfigDict(
        env_prefix="TERRA_",
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # --- Application -----------------------------------------------------
    app_name: str = "Terra"
    app_version: str = "0.1.0"
    app_env: Environment = "development"
    debug: bool = False

    # --- API (SRS §13.2) -------------------------------------------------
    api_v1_prefix: str = "/api/v1"
    api_version: str = "v1"

    # --- Logging (SRS §27) ----------------------------------------------
    log_level: str = "INFO"
    log_json: bool = False

    # --- CORS ------------------------------------------------------------
    # Cross-origin *browser* access. The bundled frontend is served same-origin
    # through Nginx (§33.1) and needs no entry there; this list is for browser
    # apps on other origins — notably the dev frontend (:3000) calling the API
    # (:8000). Non-browser consumers (MCP HTTP, curl, server-to-server) are
    # unaffected by CORS. A ``*`` wildcard is rejected in production (see
    # ``validate_runtime``); the dev default is the local frontend origin so the
    # HttpOnly-cookie session works cross-origin.
    # ``NoDecode`` + the validator below let this be set as a JSON array
    # (``["https://a.com"]``), a comma-separated list (``https://a.com,https://b.com``),
    # or a single bare origin (``https://a.com``) — dashboard env fields rarely
    # make strict JSON easy, so all three are accepted (SRS §29.3).
    cors_origins: Annotated[list[str], NoDecode] = ["http://localhost:3000"]
    # Send ``Access-Control-Allow-Credentials``. The browser session is an
    # HttpOnly cookie (see ``account_session_ttl_days``), so cross-origin
    # requests must carry credentials — on by default. Browsers reject ``*`` +
    # credentials, so the two are never paired (enforced in ``validate_runtime``).
    # Same-origin production deploys are unaffected either way.
    cors_allow_credentials: bool = True

    # --- PostgreSQL / PostGIS (SRS §20, §22) ----------------------------
    postgres_host: str = "db"
    postgres_port: int = 5432
    postgres_user: str = "terra"
    postgres_password: str = "terra"  # noqa: S105 - dev default; real secret from env (§29.2)
    postgres_db: str = "terra"
    # TLS for managed Postgres (Neon et al.): libpq-style mode passed to asyncpg
    # ("require", "verify-full", …). Unset keeps the driver default ("prefer"),
    # which suits the local/dev containers; the prod topology sets "require".
    postgres_sslmode: str | None = None

    # --- Redis (SRS §23) -------------------------------------------------
    redis_url: str = "redis://redis:6379/0"

    # --- Fetch hot path (SRS §23, §7.1) ----------------------------------
    # Read-through fetch-result cache over Redis, keyed per connector/field at
    # a rounded coordinate and expiring on each dataset's declared TTL. Redis
    # being down degrades to cache misses; it never blocks a fetch.
    fetch_cache_enabled: bool = True
    # Coordinate rounding for cache keys: 4 decimals ≈ 11 m, inside the
    # resolution of every sampled raster dataset.
    fetch_cache_coord_precision: int = 4
    # Blocking Earth Engine calls admitted concurrently per process. Excess
    # calls queue on the event loop instead of exhausting the shared thread
    # pool, so a slow GEE region cannot pin request handling.
    gee_max_concurrency: int = 8
    # Wall-clock budget for each connector inside a fetch fan-out. Connectors
    # run in parallel, so this also bounds the whole fetch stage; on expiry the
    # connector's fields become connector_timeout nulls (SRS §15.16, §15.17).
    fetch_deadline_seconds: float = 20.0
    # End-to-end wall-clock budget for /ask (planner + fetch + synthesizer).
    # Expiry returns 504 DEADLINE_EXCEEDED instead of holding the request open.
    ask_deadline_seconds: float = 60.0
    # How long an /ask answer is cached under its exact (question, coordinate)
    # key (SRS §23). /ask has no auth wall and its LLM can carry a small
    # provider quota, so repeat identical questions (e.g. the Ask page's example
    # prompts) reuse a prior answer instead of spending a fresh LLM call. 0
    # disables the cache.
    ask_cache_ttl_seconds: int = 3600

    # --- Config files (SRS §10, §11.8) ----------------------------------
    config_dir: Path = BASE_DIR / "configs"

    # --- Spatial data seed (SRS §24.4) ----------------------------------
    seed_data_dir: Path = BASE_DIR / "datasets" / "telangana"
    # Seed hand-authored, non-authoritative dev fixtures (currently the sample
    # cadastral parcel in parcels.geojson). OFF by default: real Bhu Bharati
    # parcel data requires a government data-sharing agreement, and a synthetic
    # parcel must never be servable under a government citation in production.
    # With the flag off the parcel table stays empty and every cadastral field
    # resolves to a typed null (SRS §15.17).
    enable_dev_fixtures: bool = False

    # --- Google Earth Engine (SRS §19.3) --------------------------------
    # Service-account auth (§19.3). Credentials never reach the frontend or API
    # consumers. When unset, GEE features are disabled rather than failing.
    # ``earth_engine_key_file`` is a path to the JSON key (works with a real
    # disk, e.g. local dev). ``earth_engine_key_json`` is the key's raw JSON
    # content instead, for PaaS free tiers with no persistent disk / secret
    # files (e.g. Render) — set one or the other, not both.
    earth_engine_service_account: str | None = None
    earth_engine_key_file: str | None = None
    earth_engine_key_json: str | None = None
    earth_engine_project: str | None = None

    # --- AI pipeline / LLM (SRS §9, §14) --------------------------------
    # The Synthesizer — /ask's single LLM call — goes through LiteLLM
    # (SRS §9: "LangChain, LiteLLM, OpenAI / Claude (configurable)"). The model
    # string is a LiteLLM route (e.g. ``anthropic/claude-opus-4-8`` or
    # ``openai/gpt-4o``); the provider credential is read from the provider's
    # own environment variable (``ANTHROPIC_API_KEY`` / ``OPENAI_API_KEY``) or
    # from ``llm_api_key`` below. When no credential is configured, ``/ask``
    # returns a clear 503 rather than fabricating an answer (SRS §38.8).
    llm_model: str = "anthropic/claude-opus-4-8"
    llm_temperature: float = (
        0.0  # deterministic synthesis (SRS §14.13); dropped for models that reject it
    )
    llm_max_tokens: int = 2048
    llm_timeout: float = 30.0
    llm_api_key: str | None = None
    # "disable" turns off hidden reasoning (e.g. Gemini 2.5 thinking) so the
    # token budget goes to the visible answer; dropped where unsupported.
    llm_reasoning_effort: str | None = "disable"

    # --- Authentication (SRS §13.20, §13.19) ----------------------------
    # V1.1 separates public discovery from authenticated data access. Auth is a
    # gateway concern applied *without changing endpoint contracts* (§13.20), so
    # it is a cross-cutting toggle: metadata APIs and POST /ask stay public; only
    # POST /fetch requires a bearer token, and only when ``auth_enabled`` is true.
    # The default is off so the deterministic gate and the browser UX keep working
    # unchanged; production deployments enable it.
    auth_enabled: bool = False
    # Bootstrap credential guarding token-management endpoints (dashboard-issued
    # tokens, device approval). Without it those endpoints report 503 rather than
    # allowing anonymous token minting. Never expose to clients.
    auth_admin_token: str | None = None
    # Default per-token request budget (§13.19). Overridable per token.
    auth_default_rate_limit_per_minute: int = 120
    # OAuth trust model for the MCP surface (§13.20). Dynamic client
    # registration (RFC 7591) is unauthenticated by design and /oauth/authorize
    # auto-grants consent (no login UI), so an open registration endpoint means
    # any caller can self-issue fetch/ask tokens — authentication identifies
    # and meters callers, it does not gate access. That is the intentional
    # default (True): MCP clients (Claude Desktop, Cursor) connect out of the
    # box, and every self-registered client's tokens carry the reduced budget
    # below. Set False to make registration admin-gated: only operator-vetted
    # clients exist, and "authenticated" then also means "authorized".
    auth_open_client_registration: bool = True
    # Per-token request budget for tokens minted by SELF-registered OAuth
    # clients (the low-trust surface above). Admin-registered clients get the
    # default budget.
    auth_self_registered_rate_limit_per_minute: int = 30
    # Default lifetime for issued tokens; ``None`` means non-expiring.
    auth_token_ttl_days: int | None = None
    # Public base URL used as the OAuth issuer / resource identifier (§13.20).
    auth_issuer_url: str = "http://localhost:8000"
    # Back ephemeral state (auth/device codes, rate-limit counters) with Redis
    # (§23) instead of the in-process store. The in-process store is correct for
    # single-instance dev; Redis is required for horizontal scaling.
    auth_use_redis: bool = False

    # --- End-user accounts / login (SRS §13.20) -------------------------
    # Human login sits on top of the machine-token system: a signed-in user
    # gets a bearer token (subject = user id) that also authorizes /fetch and
    # /ask. Sessions live this long before requiring re-login.
    account_session_ttl_days: int = 30
    # Brute-force guard: max register/login attempts per client IP per minute.
    # Independent of the data-endpoint gateway limit; throttles credential
    # stuffing at the door (SRS §13.19). Keyed by the same spoof-safe client id.
    auth_login_rate_limit_per_minute: int = 10
    # Where the Google OAuth callback redirects the browser after login. The
    # callback sets the session as an HttpOnly cookie and lands on a clean
    # /account URL. Must be the frontend origin (not the API).
    frontend_base_url: str = "http://localhost:3000"
    # "Sign in with Google" (OAuth 2.0 / OIDC). Create a Web-application OAuth
    # client at https://console.cloud.google.com/apis/credentials, add
    # ``{auth_issuer_url}/api/v1/account/google/callback`` as an authorized
    # redirect URI, and set the id/secret below. When unset, the Google button
    # is hidden and only email/password login is offered.
    google_oauth_client_id: str | None = None
    google_oauth_client_secret: str | None = None

    # --- MCP server (SRS §34, §9) ---------------------------------------
    # The MCP server is a thin client over the REST API (§34.2 workflow, §11.2
    # API-first). These configure how it reaches the platform and how it is
    # exposed to AI clients (stdio for Claude Desktop / Cursor, HTTP for remote).
    mcp_api_base_url: str = "http://localhost:8000/api/v1"
    mcp_api_token: str | None = None
    mcp_transport: Literal["stdio", "streamable-http"] = "stdio"
    mcp_http_host: str = "127.0.0.1"
    mcp_http_port: int = 8765
    mcp_request_timeout: float = 60.0

    # --- Observability (SRS §27, §7.7) ----------------------------------
    # Prometheus metrics are exposed at ``/metrics`` (scraped by the monitoring
    # stack, SRS §27.2/§27.3). OpenTelemetry tracing is opt-in: it exports spans
    # only when an OTLP endpoint is configured, so dev and the test suite run
    # with a no-op tracer and incur no overhead.
    metrics_enabled: bool = True
    otel_enabled: bool = False
    otel_exporter_endpoint: str | None = None  # OTLP/HTTP, e.g. http://otel-collector:4318
    otel_service_name: str = "terra-backend"

    # --- Rate limiting (SRS §13.19, §29) --------------------------------
    # A configurable, environment-specific gateway limiter applied to the data
    # endpoints (/fetch, /ask) regardless of authentication. It complements the
    # per-token budget in ``require_auth`` and the Nginx edge limit (defense in
    # depth). Keyed by token id when authenticated, else by client IP. The
    # default budget is generous so the browser UX and deterministic gate keep
    # working unchanged; production tightens it via the environment.
    rate_limit_enabled: bool = True
    rate_limit_per_minute: int = 120
    # Reject request bodies larger than this many bytes before parsing (§29.1).
    max_request_body_bytes: int = 1_048_576  # 1 MiB
    # Trust proxy-set client-IP headers (``X-Real-IP`` / ``X-Forwarded-For``)
    # when keying the rate limiter. OFF by default: exposed directly, those
    # headers are client-controlled and would let an attacker rotate keys to
    # dodge the per-IP budget (§13.19). Enable ONLY behind a trusted reverse
    # proxy — Nginx overwrites ``X-Real-IP`` with the real peer (§33.1), so it
    # becomes authoritative and client-supplied values are ignored.
    trust_proxy_headers: bool = False

    @field_validator("cors_origins", mode="before")
    @classmethod
    def _parse_cors_origins(cls, value: object) -> object:
        """Accept a JSON array, a comma-separated list, or a single origin.

        pydantic-settings would otherwise JSON-decode this env var and hard-fail
        the whole app on a bare string like ``https://a.vercel.app`` — a common
        way to set it in a hosting dashboard. Non-strings (the code default, or
        an already-parsed list) pass straight through.
        """
        if not isinstance(value, str):
            return value
        text = value.strip()
        if not text:
            return []
        if text.startswith("["):
            return json.loads(text)  # explicit JSON array; surfaces its own error
        return [item.strip() for item in text.split(",") if item.strip()]

    @property
    def database_url(self) -> str:
        """Async SQLAlchemy DSN (asyncpg driver)."""
        dsn = (
            f"postgresql+asyncpg://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )
        if self.postgres_sslmode:
            dsn += f"?ssl={self.postgres_sslmode}"
        return dsn

    @property
    def is_production(self) -> bool:
        return self.app_env == "production"

    @property
    def google_oauth_enabled(self) -> bool:
        return bool(self.google_oauth_client_id and self.google_oauth_client_secret)

    @property
    def google_oauth_redirect_uri(self) -> str:
        return f"{self.auth_issuer_url.rstrip('/')}/api/v1/account/google/callback"

    @property
    def earth_engine_configured(self) -> bool:
        """True when a service account and a key (file path or raw JSON) are set (SRS §19.3)."""
        return bool(
            self.earth_engine_service_account
            and (self.earth_engine_key_file or self.earth_engine_key_json)
        )

    def validate_runtime(self) -> list[str]:
        """Return fatal misconfigurations for the current environment (§29, §13.20).

        Checked at startup (fail-fast, in the lifespan) and by the readiness
        probe (defense in depth). An empty list means the configuration is safe
        to expose. Production must not serve data endpoints open, must not use a
        wildcard CORS origin, and must be able to bootstrap token issuance.
        """
        problems: list[str] = []
        if self.is_production:
            if not self.auth_enabled:
                problems.append(
                    "Authentication is disabled in production: set "
                    "TERRA_AUTH_ENABLED=true so POST /fetch, POST /ask, and the "
                    "MCP tools reject anonymous access (§13.20)."
                )
            elif not self.auth_admin_token:
                problems.append(
                    "Authentication is enabled in production but "
                    "TERRA_AUTH_ADMIN_TOKEN is unset, so no tokens can be issued "
                    "and the platform is unusable: set a bootstrap admin "
                    "credential (§13.20)."
                )
            if "*" in self.cors_origins:
                problems.append(
                    "CORS is set to the '*' wildcard in production: set "
                    "TERRA_CORS_ORIGINS to an explicit allow-list, or '[]' for "
                    "same-origin only (§29.3)."
                )
            if self.enable_dev_fixtures:
                problems.append(
                    "Dev fixtures are enabled in production: unset "
                    "TERRA_ENABLE_DEV_FIXTURES so synthetic sample data (e.g. "
                    "the hand-authored cadastral parcel) is never seeded or "
                    "served under an authoritative citation (SRS §16.4)."
                )
        # Invalid in every environment — browsers reject '*' with credentials.
        if self.cors_allow_credentials and "*" in self.cors_origins:
            problems.append(
                "CORS allow_credentials cannot be combined with the '*' origin; "
                "browsers reject the pair. Set an explicit TERRA_CORS_ORIGINS "
                "allow-list or leave TERRA_CORS_ALLOW_CREDENTIALS off."
            )
        return problems


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return a cached :class:`Settings` instance."""
    return Settings()


settings = get_settings()
