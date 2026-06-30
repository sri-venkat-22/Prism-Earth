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
    postgres_password: str = "prism"
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
