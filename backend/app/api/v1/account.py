"""End-user account endpoints (SRS §13.20).

Human login layered on the machine-token system. A signed-in user holds a
bearer *session token* (``subject = user.id``, ``name = "session"``) that also
authorizes ``/fetch`` and ``/ask``; the API tokens they mint here are ordinary
``api_token`` rows with the same subject. Auth here is enforced by
:func:`current_user`, which verifies the bearer token directly and so works
regardless of the global ``auth_enabled`` gateway toggle (like ``require_admin``).

Flows: email/password register + login, profile read/update/delete, per-user API
token management, and "Sign in with Google" (OAuth 2.0).
"""

from __future__ import annotations

import secrets
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Annotated
from uuid import uuid4

from fastapi import APIRouter, Depends, Request, Response
from fastapi.responses import RedirectResponse
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import _client_key  # spoof-safe per-IP key (SRS §13.19)
from app.auth import google
from app.auth.dependencies import (
    clear_session_cookie,
    get_auth_service,
    get_ephemeral_store,
    get_token_store,
    set_session_cookie,
)
from app.auth.dependencies import _request_token as _session_token  # header-or-cookie
from app.auth.oauth import DEFAULT_SCOPES, SUPPORTED_SCOPES
from app.auth.ratelimit import enforce_rate_limit
from app.auth.schemas import TokenCreatedResponse, TokenInfo, TokenListResponse
from app.auth.service import AuthService
from app.auth.stores import EphemeralStore
from app.auth.tokens import TokenRecord, TokenStore, hash_secret
from app.auth.users import (
    SqlUserStore,
    UserRecord,
    UserStore,
    hash_password,
    verify_password,
)
from app.core.config import Settings, get_settings
from app.core.database import get_session
from app.core.errors import AppError, AuthenticationError

router = APIRouter(prefix="/account", tags=["account"])

_SESSION_NAME = "session"  # noqa: S105 - token label, distinguishes session from API tokens
_GOOGLE_STATE_TTL = 600


def _settings(request: Request) -> Settings:
    settings = getattr(request.app.state, "settings", None)
    return settings if isinstance(settings, Settings) else get_settings()


async def get_user_store(session: Annotated[AsyncSession, Depends(get_session)]) -> UserStore:
    return SqlUserStore(session)


async def throttle_auth(
    request: Request, ephemeral: Annotated[EphemeralStore, Depends(get_ephemeral_store)]
) -> None:
    """Brute-force guard on register/login: cap attempts per client IP (§13.19)."""
    settings = _settings(request)
    if not settings.rate_limit_enabled:
        return
    key = f"auth-attempt:{_client_key(request, settings)}"
    await enforce_rate_limit(ephemeral, key, settings.auth_login_rate_limit_per_minute)


# --------------------------------------------------------------------------- #
# Schemas                                                                      #
# --------------------------------------------------------------------------- #
class RegisterRequest(BaseModel):
    email: str = Field(..., max_length=320)
    password: str = Field(..., min_length=8, max_length=256)
    organization: str | None = Field(None, max_length=128)


class LoginRequest(BaseModel):
    email: str = Field(..., max_length=320)
    password: str = Field(..., max_length=256)


class UpdateProfileRequest(BaseModel):
    organization: str | None = Field(None, max_length=128)


class UserResponse(BaseModel):
    id: str
    email: str
    organization: str | None = None
    created_at: str
    has_password: bool
    google_linked: bool


class CreateAccountTokenRequest(BaseModel):
    name: str = Field(..., max_length=128)
    scopes: list[str] = Field(default_factory=lambda: sorted(DEFAULT_SCOPES))
    expires_in_days: int | None = None


class AccountConfigResponse(BaseModel):
    google_enabled: bool


# --------------------------------------------------------------------------- #
# Current-user dependency                                                      #
# --------------------------------------------------------------------------- #
@dataclass(slots=True)
class AccountContext:
    user: UserRecord
    token: TokenRecord


async def current_user(
    request: Request,
    token_store: Annotated[TokenStore, Depends(get_token_store)],
    user_store: Annotated[UserStore, Depends(get_user_store)],
) -> AccountContext:
    token = _session_token(request)  # Authorization header, else HttpOnly cookie
    if token is None:
        raise AuthenticationError("Sign in to continue.")
    record = await token_store.get_by_hash(hash_secret(token))
    if record is None or not record.is_active(now=datetime.now(UTC)):
        raise AuthenticationError("Your session is invalid or expired. Sign in again.")
    user = await user_store.get(record.subject)
    if user is None:
        raise AuthenticationError("This token is not tied to a user account.")
    return AccountContext(user=user, token=record)


CurrentUser = Annotated[AccountContext, Depends(current_user)]


# --------------------------------------------------------------------------- #
# Helpers                                                                      #
# --------------------------------------------------------------------------- #
def _user_response(user: UserRecord) -> UserResponse:
    return UserResponse(
        id=user.id,
        email=user.email,
        organization=user.organization,
        created_at=user.created_at.isoformat(),
        has_password=user.password_hash is not None,
        google_linked=user.google_sub is not None,
    )


def _token_info(record: TokenRecord) -> TokenInfo:
    return TokenInfo(
        id=record.id,
        prefix=record.prefix,
        name=record.name,
        subject=record.subject,
        scopes=sorted(record.scopes),
        created_at=record.created_at.isoformat(),
        expires_at=record.expires_at.isoformat() if record.expires_at else None,
        last_used_at=record.last_used_at.isoformat() if record.last_used_at else None,
        revoked=record.revoked,
        rate_limit_per_minute=record.rate_limit_per_minute,
    )


async def _issue_session(request: Request, service: AuthService, user: UserRecord) -> str:
    ttl = timedelta(days=_settings(request).account_session_ttl_days)
    issued = await service.issue_token(
        name=_SESSION_NAME, subject=user.id, scopes=DEFAULT_SCOPES, expires_in=ttl
    )
    return issued.token


def _clean_scopes(requested: list[str]) -> frozenset[str]:
    scopes = frozenset(requested) & SUPPORTED_SCOPES
    return scopes or DEFAULT_SCOPES


# --------------------------------------------------------------------------- #
# Config                                                                       #
# --------------------------------------------------------------------------- #
@router.get("/config", response_model=AccountConfigResponse, summary="Public account config")
async def account_config(request: Request) -> AccountConfigResponse:
    return AccountConfigResponse(google_enabled=_settings(request).google_oauth_enabled)


# --------------------------------------------------------------------------- #
# Register / login / session                                                   #
# --------------------------------------------------------------------------- #
@router.post(
    "/register",
    response_model=UserResponse,
    status_code=201,
    dependencies=[Depends(throttle_auth)],
    summary="Create account",
)
async def register(
    payload: RegisterRequest,
    request: Request,
    response: Response,
    user_store: Annotated[UserStore, Depends(get_user_store)],
    service: Annotated[AuthService, Depends(get_auth_service)],
) -> UserResponse:
    email = payload.email.strip().lower()
    if "@" not in email or "." not in email.split("@")[-1]:
        raise AppError("Enter a valid email address.", code="VALIDATION_ERROR", status_code=422)
    if await user_store.get_by_email(email) is not None:
        raise AppError(
            "An account with this email already exists.", code="EMAIL_TAKEN", status_code=409
        )
    user = UserRecord(
        id=str(uuid4()),
        email=email,
        password_hash=hash_password(payload.password),
        organization=(payload.organization or None),
        google_sub=None,
        created_at=datetime.now(UTC),
    )
    await user_store.create(user)
    # The session token is delivered only as an HttpOnly cookie — never in the
    # response body, so client JS cannot read it (SRS §13.20).
    set_session_cookie(response, await _issue_session(request, service, user), _settings(request))
    return _user_response(user)


@router.post(
    "/login",
    response_model=UserResponse,
    dependencies=[Depends(throttle_auth)],
    summary="Sign in",
)
async def login(
    payload: LoginRequest,
    request: Request,
    response: Response,
    user_store: Annotated[UserStore, Depends(get_user_store)],
    service: Annotated[AuthService, Depends(get_auth_service)],
) -> UserResponse:
    user = await user_store.get_by_email(payload.email.strip().lower())
    # Same error whether the email is unknown or the password is wrong — do not
    # leak which emails have accounts.
    if user is None or not verify_password(payload.password, user.password_hash):
        raise AuthenticationError("Invalid email or password.")
    set_session_cookie(response, await _issue_session(request, service, user), _settings(request))
    return _user_response(user)


@router.post("/logout", status_code=204, summary="Sign out (revoke this session)")
async def logout(
    ctx: CurrentUser, token_store: Annotated[TokenStore, Depends(get_token_store)]
) -> Response:
    await token_store.revoke(ctx.token.id)
    response = Response(status_code=204)
    clear_session_cookie(response)
    return response


# --------------------------------------------------------------------------- #
# Profile                                                                      #
# --------------------------------------------------------------------------- #
@router.get("/me", response_model=UserResponse, summary="Current account")
async def get_me(ctx: CurrentUser) -> UserResponse:
    return _user_response(ctx.user)


@router.patch("/me", response_model=UserResponse, summary="Update profile")
async def update_me(
    payload: UpdateProfileRequest,
    ctx: CurrentUser,
    user_store: Annotated[UserStore, Depends(get_user_store)],
) -> UserResponse:
    org = payload.organization.strip() if payload.organization else None
    await user_store.set_organization(ctx.user.id, org or None)
    ctx.user.organization = org or None
    return _user_response(ctx.user)


@router.delete("/me", status_code=204, summary="Delete account and revoke all tokens")
async def delete_me(
    ctx: CurrentUser,
    user_store: Annotated[UserStore, Depends(get_user_store)],
    token_store: Annotated[TokenStore, Depends(get_token_store)],
) -> Response:
    for record in await token_store.list(subject=ctx.user.id):
        await token_store.revoke(record.id)
    await user_store.delete(ctx.user.id)
    response = Response(status_code=204)
    clear_session_cookie(response)
    return response


# --------------------------------------------------------------------------- #
# Per-user API tokens                                                          #
# --------------------------------------------------------------------------- #
@router.get("/tokens", response_model=TokenListResponse, summary="List your API tokens")
async def list_my_tokens(
    ctx: CurrentUser, token_store: Annotated[TokenStore, Depends(get_token_store)]
) -> TokenListResponse:
    # ponytail: sessions share this table; exclude them (and revoked rows) by
    # field so no extra column is needed.
    records = [
        r
        for r in await token_store.list(subject=ctx.user.id)
        if r.name != _SESSION_NAME and not r.revoked
    ]
    tokens = [_token_info(r) for r in records]
    return TokenListResponse(count=len(tokens), tokens=tokens)


@router.post(
    "/tokens", response_model=TokenCreatedResponse, status_code=201, summary="Create an API token"
)
async def create_my_token(
    payload: CreateAccountTokenRequest,
    ctx: CurrentUser,
    service: Annotated[AuthService, Depends(get_auth_service)],
) -> TokenCreatedResponse:
    if payload.name.strip() == _SESSION_NAME:
        raise AppError("That token name is reserved.", code="VALIDATION_ERROR", status_code=422)
    expires_in = (
        timedelta(days=payload.expires_in_days)
        if payload.expires_in_days
        else service.default_token_ttl()
    )
    issued = await service.issue_token(
        name=payload.name.strip(),
        subject=ctx.user.id,
        scopes=_clean_scopes(payload.scopes),
        expires_in=expires_in,
    )
    return TokenCreatedResponse(token=issued.token, **_token_info(issued.record).model_dump())


@router.delete("/tokens/{token_id}", status_code=204, summary="Revoke one of your API tokens")
async def revoke_my_token(
    token_id: str,
    ctx: CurrentUser,
    token_store: Annotated[TokenStore, Depends(get_token_store)],
) -> Response:
    record = await token_store.get(token_id)
    # Only the owner may revoke, and never via this endpoint the live session.
    if record is None or record.subject != ctx.user.id or record.name == _SESSION_NAME:
        raise AppError("Token not found.", code="NOT_FOUND", status_code=404)
    await token_store.revoke(token_id)
    return Response(status_code=204)


# --------------------------------------------------------------------------- #
# Sign in with Google (OAuth 2.0)                                              #
# --------------------------------------------------------------------------- #
@router.get("/google/login", summary="Start Google sign-in")
async def google_login(
    request: Request, ephemeral: Annotated[EphemeralStore, Depends(get_ephemeral_store)]
) -> Response:
    settings = _settings(request)
    if not settings.google_oauth_enabled:
        raise AppError("Google sign-in is not configured.", code="NOT_CONFIGURED", status_code=503)
    state = secrets.token_urlsafe(24)
    await ephemeral.put(f"gstate:{state}", {"ok": True}, _GOOGLE_STATE_TTL)
    url = google.authorization_url(
        client_id=settings.google_oauth_client_id or "",
        redirect_uri=settings.google_oauth_redirect_uri,
        state=state,
    )
    return RedirectResponse(url=url, status_code=302)


@router.get("/google/callback", summary="Google sign-in callback")
async def google_callback(
    request: Request,
    ephemeral: Annotated[EphemeralStore, Depends(get_ephemeral_store)],
    user_store: Annotated[UserStore, Depends(get_user_store)],
    service: Annotated[AuthService, Depends(get_auth_service)],
    state: str,
    code: str | None = None,
    error: str | None = None,
) -> Response:
    settings = _settings(request)
    account_url = f"{settings.frontend_base_url.rstrip('/')}/account"

    if await ephemeral.get(f"gstate:{state}") is None:
        return RedirectResponse(url=f"{account_url}#error=google_state", status_code=302)
    await ephemeral.delete(f"gstate:{state}")
    if error or not code or not settings.google_oauth_enabled:
        return RedirectResponse(url=f"{account_url}#error=google", status_code=302)

    try:
        profile = await google.exchange_code(
            code=code,
            client_id=settings.google_oauth_client_id or "",
            client_secret=settings.google_oauth_client_secret or "",
            redirect_uri=settings.google_oauth_redirect_uri,
        )
    except google.GoogleOAuthError:
        return RedirectResponse(url=f"{account_url}#error=google", status_code=302)

    user = await user_store.get_by_google_sub(profile.sub)
    if user is None:
        user = await user_store.get_by_email(profile.email)
        if user is None:
            user = UserRecord(
                id=str(uuid4()),
                email=profile.email,
                password_hash=None,
                organization=None,
                google_sub=profile.sub,
                created_at=datetime.now(UTC),
            )
            await user_store.create(user)
        elif user.google_sub is None:
            await user_store.link_google(user.id, profile.sub)  # link to existing email account

    # Set the session as an HttpOnly cookie on the redirect itself, then land on
    # a clean /account URL — no token in the URL fragment for JS/history to see.
    redirect = RedirectResponse(url=account_url, status_code=302)
    set_session_cookie(redirect, await _issue_session(request, service, user), settings)
    return redirect
