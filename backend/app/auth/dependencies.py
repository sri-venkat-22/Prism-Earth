"""FastAPI wiring for authentication (SRS §13.20, §13.19).

Provides the injectable stores (overridable in tests, mirroring the
``get_fetch_orchestrator`` pattern), the :func:`require_auth` guard applied to
``/fetch`` and ``/ask``, and :func:`require_admin` guarding token management.

When ``auth_enabled`` is false the guard short-circuits to an anonymous
principal, so endpoint contracts are unchanged (SRS §13.20) and the browser UX /
deterministic gate keep working. When true, a valid bearer token is required and
its per-token rate limit (SRS §13.19) is enforced.
"""

from __future__ import annotations

import secrets
from datetime import UTC, datetime
from typing import Annotated

from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.ratelimit import enforce_rate_limit
from app.auth.service import AuthService
from app.auth.stores import EphemeralStore, InMemoryEphemeralStore
from app.auth.tokens import (
    ClientStore,
    Principal,
    SqlClientStore,
    SqlTokenStore,
    TokenStore,
    hash_secret,
)
from app.core.config import Settings, get_settings
from app.core.database import get_session
from app.core.errors import AppError, AuthenticationError, AuthorizationError


def _settings(request: Request) -> Settings:
    """The app's settings (set in ``create_app``; falls back to the singleton)."""
    settings = getattr(request.app.state, "settings", None)
    return settings if isinstance(settings, Settings) else get_settings()


# --------------------------------------------------------------------------- #
# Store / service providers (overridable in tests)                            #
# --------------------------------------------------------------------------- #
async def get_token_store(
    session: Annotated[AsyncSession, Depends(get_session)],
) -> TokenStore:
    return SqlTokenStore(session)


async def get_client_store(
    session: Annotated[AsyncSession, Depends(get_session)],
) -> ClientStore:
    return SqlClientStore(session)


def get_ephemeral_store(request: Request) -> EphemeralStore:
    """Return the app-wide ephemeral store (created in ``create_app``)."""
    store = getattr(request.app.state, "ephemeral_store", None)
    if isinstance(store, EphemeralStore):
        return store
    # Defensive fallback (e.g. an app built without create_app wiring).
    store = InMemoryEphemeralStore()
    request.app.state.ephemeral_store = store
    return store


def get_auth_service(
    request: Request,
    token_store: Annotated[TokenStore, Depends(get_token_store)],
    client_store: Annotated[ClientStore, Depends(get_client_store)],
    ephemeral: Annotated[EphemeralStore, Depends(get_ephemeral_store)],
) -> AuthService:
    return AuthService(
        token_store=token_store,
        client_store=client_store,
        ephemeral=ephemeral,
        settings=_settings(request),
    )


# --------------------------------------------------------------------------- #
# Bearer extraction / errors                                                  #
# --------------------------------------------------------------------------- #
def _bearer_token(request: Request) -> str | None:
    header = request.headers.get("Authorization")
    if not header:
        return None
    scheme, _, credential = header.partition(" ")
    if scheme.lower() != "bearer" or not credential.strip():
        return None
    return credential.strip()


def _unauthenticated(settings: Settings, message: str) -> AuthenticationError:
    # RFC 9728: point MCP clients at the protected-resource metadata so they can
    # discover the authorization server and begin the OAuth flow.
    resource_meta = f"{settings.auth_issuer_url.rstrip('/')}/.well-known/oauth-protected-resource"
    return AuthenticationError(
        message,
        headers={"WWW-Authenticate": f'Bearer resource_metadata="{resource_meta}"'},
    )


# --------------------------------------------------------------------------- #
# Guards                                                                       #
# --------------------------------------------------------------------------- #
def require_auth(*required_scopes: str) -> object:
    """Build a dependency requiring a valid bearer token with ``required_scopes``."""

    async def dependency(
        request: Request,
        token_store: Annotated[TokenStore, Depends(get_token_store)],
        ephemeral: Annotated[EphemeralStore, Depends(get_ephemeral_store)],
    ) -> Principal:
        settings = _settings(request)
        if not settings.auth_enabled:
            principal = Principal.anonymous_principal()
            request.state.principal = principal
            return principal

        token = _bearer_token(request)
        if token is None:
            raise _unauthenticated(settings, "A bearer token is required.")

        now = datetime.now(UTC)
        record = await token_store.get_by_hash(hash_secret(token))
        if record is None or not record.is_active(now=now):
            raise _unauthenticated(settings, "The bearer token is invalid or expired.")

        required = frozenset(required_scopes)
        if required and not required <= record.scopes:
            raise AuthorizationError(f"Requires scope(s): {', '.join(sorted(required))}.")

        limit = (
            record.rate_limit_per_minute
            if record.rate_limit_per_minute is not None
            else settings.auth_default_rate_limit_per_minute
        )
        await enforce_rate_limit(ephemeral, record.id, limit)
        await token_store.touch(record.id, now)

        principal = Principal(
            subject=record.subject,
            scopes=record.scopes,
            token_id=record.id,
            rate_limit_per_minute=limit,
        )
        request.state.principal = principal
        return principal

    return dependency


async def require_admin(request: Request) -> None:
    """Guard token-management endpoints with the bootstrap admin credential.

    Works independently of ``auth_enabled`` so tokens can be minted before
    enforcement is switched on. Returns 503 when no admin credential is set.
    """
    settings = _settings(request)
    if not settings.auth_admin_token:
        raise AppError(
            "Token management is not configured (set PRISM_AUTH_ADMIN_TOKEN).",
            code="NOT_CONFIGURED",
            status_code=503,
        )
    provided = _bearer_token(request) or request.headers.get("X-Admin-Token")
    if not provided or not secrets.compare_digest(provided, settings.auth_admin_token):
        raise AuthenticationError("A valid admin credential is required.")
