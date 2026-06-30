"""Earth Engine service-account authentication (SRS §19.3).

Authenticates with Google Earth Engine using a dedicated Google Cloud service
account. Credentials are read from settings (environment / secrets) and never
exposed to the frontend or API consumers (SRS §19.3). Initialization is
idempotent so the process authenticates once.
"""

from __future__ import annotations

from typing import Any

from app.core.config import Settings, get_settings
from app.core.errors import AuthenticationError
from app.core.logging import get_logger

logger = get_logger(__name__)

_initialized = False


def _import_ee() -> Any:
    try:
        import ee  # noqa: PLC0415  (imported lazily so the heavy dep stays optional)
    except ImportError as exc:  # pragma: no cover - dependency is declared
        raise AuthenticationError("earthengine-api is not installed.", details=str(exc)) from exc
    return ee


def initialize_earth_engine(
    settings: Settings | None = None,
    *,
    ee_module: Any | None = None,
    force: bool = False,
) -> None:
    """Authenticate the process with Earth Engine (idempotent, SRS §19.3).

    Raises :class:`AuthenticationError` when GEE is not configured or auth fails;
    callers (the smoke test, connectors) surface this as a structured failure
    rather than crashing unrelated work (SRS §19.10).
    """
    global _initialized
    if _initialized and not force:
        return

    settings = settings or get_settings()
    if not settings.earth_engine_configured:
        raise AuthenticationError(
            "Earth Engine is not configured.",
            details=(
                "Set PRISM_EARTH_ENGINE_SERVICE_ACCOUNT and "
                "PRISM_EARTH_ENGINE_KEY_FILE (SRS §19.3)."
            ),
        )

    ee = ee_module or _import_ee()
    try:
        credentials = ee.ServiceAccountCredentials(
            settings.earth_engine_service_account,
            settings.earth_engine_key_file,
        )
        init_kwargs: dict[str, Any] = {}
        if settings.earth_engine_project:
            init_kwargs["project"] = settings.earth_engine_project
        ee.Initialize(credentials, **init_kwargs)
    except AuthenticationError:
        raise
    except Exception as exc:  # auth/network/credential errors (SRS §19.10)
        raise AuthenticationError("Earth Engine authentication failed.", details=str(exc)) from exc

    _initialized = True
    logger.info(
        "gee.initialized",
        service_account=settings.earth_engine_service_account,
        project=settings.earth_engine_project,
    )


def reset_initialized() -> None:
    """Reset the idempotency flag (tests only)."""
    global _initialized
    _initialized = False
