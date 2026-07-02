"""Authentication package (SRS §13.20, §13.19).

Public surface:

- :func:`require_auth` / :func:`require_admin` — FastAPI guards.
- :class:`Principal` — the authenticated caller.
- :class:`AuthService` — the credential flows (tokens, device, OAuth).
- Store providers (:func:`get_token_store`, etc.) for dependency overrides.
"""

from __future__ import annotations

from app.auth.dependencies import (
    get_auth_service,
    get_client_store,
    get_ephemeral_store,
    get_token_store,
    require_admin,
    require_auth,
)
from app.auth.service import AuthService
from app.auth.tokens import Principal

__all__ = [
    "AuthService",
    "Principal",
    "get_auth_service",
    "get_client_store",
    "get_ephemeral_store",
    "get_token_store",
    "require_admin",
    "require_auth",
]
