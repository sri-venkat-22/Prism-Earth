"""Application configuration (SRS §9, §13).

Settings are loaded from environment variables (prefixed ``PRISM_``) and an
optional ``.env`` file using Pydantic v2 ``BaseSettings``. No business logic or
dataset-specific values live here — those belong in ``configs/*.yaml`` and are
read through :mod:`app.config.loader`.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict

# Repository root: app/core/config.py -> core -> app -> backend -> <repo root>
BASE_DIR = Path(__file__).resolve().parents[3]

Environment = Literal["development", "testing", "staging", "production"]


class Settings(BaseSettings):
    """Centralized, environment-driven application settings."""

    model_config = SettingsConfigDict(
        env_prefix="PRISM_",
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # --- Application -----------------------------------------------------
    app_name: str = "Prism Earth"
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
    cors_origins: list[str] = ["*"]

    # --- PostgreSQL / PostGIS (SRS §20, §22) ----------------------------
    postgres_host: str = "db"
    postgres_port: int = 5432
    postgres_user: str = "prism"
    postgres_password: str = "prism"  # noqa: S105 - dev default; real secret from env (§29.2)
    postgres_db: str = "prism_earth"

    # --- Redis (SRS §23) -------------------------------------------------
    redis_url: str = "redis://redis:6379/0"

    # --- Config files (SRS §10, §11.8) ----------------------------------
    config_dir: Path = BASE_DIR / "configs"

    # --- Spatial data seed (SRS §24.4) ----------------------------------
    seed_data_dir: Path = BASE_DIR / "datasets" / "telangana"

    # --- Google Earth Engine (SRS §19.3) --------------------------------
    # Service-account auth (§19.3). Credentials never reach the frontend or API
    # consumers. When unset, GEE features are disabled rather than failing.
    earth_engine_service_account: str | None = None
    earth_engine_key_file: str | None = None
    earth_engine_project: str | None = None

    # --- AI pipeline / LLM (SRS §9, §14) --------------------------------
    # The Planner and Synthesizer call a configurable model through LiteLLM
    # (SRS §9: "LangChain, LiteLLM, OpenAI / Claude (configurable)"). The model
    # string is a LiteLLM route (e.g. ``anthropic/claude-opus-4-8`` or
    # ``openai/gpt-4o``); the provider credential is read from the provider's
    # own environment variable (``ANTHROPIC_API_KEY`` / ``OPENAI_API_KEY``) or
    # from ``llm_api_key`` below. When no credential is configured, ``/ask``
    # returns a clear 503 rather than fabricating a plan or answer (SRS §38.8).
    llm_model: str = "anthropic/claude-opus-4-8"
    llm_temperature: float = (
        0.0  # deterministic planning (SRS §14.13); dropped for models that reject it
    )
    llm_max_tokens: int = 1024
    llm_timeout: float = 30.0
    llm_api_key: str | None = None

    # --- Authentication (SRS §13.20, §13.19) ----------------------------
    # V1.1 separates public discovery from authenticated data access. Auth is a
    # gateway concern applied *without changing endpoint contracts* (§13.20), so
    # it is a cross-cutting toggle: metadata APIs stay public; POST /fetch and
    # POST /ask require a bearer token only when ``auth_enabled`` is true. The
    # default is off so the deterministic gate and the browser UX keep working
    # unchanged; production deployments enable it.
    auth_enabled: bool = False
    # Bootstrap credential guarding token-management endpoints (dashboard-issued
    # tokens, device approval). Without it those endpoints report 503 rather than
    # allowing anonymous token minting. Never expose to clients.
    auth_admin_token: str | None = None
    # Default per-token request budget (§13.19). Overridable per token.
    auth_default_rate_limit_per_minute: int = 120
    # Default lifetime for issued tokens; ``None`` means non-expiring.
    auth_token_ttl_days: int | None = None
    # Public base URL used as the OAuth issuer / resource identifier (§13.20).
    auth_issuer_url: str = "http://localhost:8000"
    # Back ephemeral state (auth/device codes, rate-limit counters) with Redis
    # (§23) instead of the in-process store. The in-process store is correct for
    # single-instance dev; Redis is required for horizontal scaling.
    auth_use_redis: bool = False

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
    otel_service_name: str = "prism-earth-backend"

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

    @property
    def database_url(self) -> str:
        """Async SQLAlchemy DSN (asyncpg driver)."""
        return (
            f"postgresql+asyncpg://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )

    @property
    def is_production(self) -> bool:
        return self.app_env == "production"

    @property
    def earth_engine_configured(self) -> bool:
        """True when a service account and key file are both set (SRS §19.3)."""
        return bool(self.earth_engine_service_account and self.earth_engine_key_file)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return a cached :class:`Settings` instance."""
    return Settings()


settings = get_settings()
