"""Authentication endpoints (SRS §13.20).

Three credential flows, plus token management:

- ``/auth/tokens``           — dashboard-issued API tokens (admin-gated).
- ``/auth/device/*``         — device-flow login for CLI clients (RFC 8628).
- ``/auth/oauth/*``          — OAuth 2.0 for MCP clients (register / authorize /
  token; PKCE required for the authorization-code grant).

Token-management and device-approval endpoints are guarded by the bootstrap
admin credential (``require_admin``). The OAuth token endpoint is form-encoded
and returns the RFC 6749 body (or ``{error, error_description}``) directly rather
than the app error envelope.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Annotated

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import JSONResponse, RedirectResponse, Response

from app.auth import oauth
from app.auth.dependencies import get_auth_service, require_admin
from app.auth.oauth import DEVICE_CODE_GRANT, SUPPORTED_SCOPES, OAuthError
from app.auth.schemas import (
    ClientRegistrationRequest,
    ClientRegistrationResponse,
    CreateTokenRequest,
    DeviceApproveRequest,
    DeviceApproveResponse,
    DeviceCodeRequest,
    DeviceCodeResponse,
    TokenCreatedResponse,
    TokenInfo,
    TokenListResponse,
)
from app.auth.service import AuthService
from app.auth.tokens import TokenRecord

router = APIRouter(prefix="/auth", tags=["auth"])

ServiceDep = Annotated[AuthService, Depends(get_auth_service)]

_NO_STORE = {"Cache-Control": "no-store", "Pragma": "no-cache"}


def _iso(value: datetime | None) -> str | None:
    return value.isoformat() if value is not None else None


def _token_info(record: TokenRecord) -> TokenInfo:
    return TokenInfo(
        id=record.id,
        prefix=record.prefix,
        name=record.name,
        subject=record.subject,
        scopes=sorted(record.scopes),
        created_at=record.created_at.isoformat(),
        expires_at=_iso(record.expires_at),
        last_used_at=_iso(record.last_used_at),
        revoked=record.revoked,
        rate_limit_per_minute=record.rate_limit_per_minute,
    )


def _clean_scopes(requested: list[str]) -> frozenset[str]:
    scopes = frozenset(requested) & SUPPORTED_SCOPES
    return scopes or oauth.DEFAULT_SCOPES


def _oauth_error(exc: OAuthError) -> JSONResponse:
    return JSONResponse(status_code=exc.status_code, content=exc.to_dict(), headers=_NO_STORE)


# --------------------------------------------------------------------------- #
# Dashboard-issued API tokens (admin-gated)                                   #
# --------------------------------------------------------------------------- #
@router.post(
    "/tokens",
    response_model=TokenCreatedResponse,
    status_code=201,
    dependencies=[Depends(require_admin)],
    summary="Issue a dashboard API token (SRS §13.20)",
)
async def create_token(payload: CreateTokenRequest, service: ServiceDep) -> TokenCreatedResponse:
    expires_in: timedelta | None
    if payload.expires_in_days is not None:
        expires_in = timedelta(days=payload.expires_in_days)
    else:
        expires_in = service.default_token_ttl()
    issued = await service.issue_token(
        name=payload.name,
        subject=payload.subject,
        scopes=_clean_scopes(payload.scopes),
        expires_in=expires_in,
        rate_limit_per_minute=payload.rate_limit_per_minute,
    )
    info = _token_info(issued.record)
    return TokenCreatedResponse(token=issued.token, **info.model_dump())


@router.get(
    "/tokens",
    response_model=TokenListResponse,
    dependencies=[Depends(require_admin)],
    summary="List issued tokens (SRS §13.20)",
)
async def list_tokens(service: ServiceDep) -> TokenListResponse:
    records = await service.list_tokens()
    tokens = [_token_info(r) for r in records]
    return TokenListResponse(count=len(tokens), tokens=tokens)


@router.delete(
    "/tokens/{token_id}",
    status_code=204,
    dependencies=[Depends(require_admin)],
    summary="Revoke a token (SRS §13.20)",
)
async def revoke_token(token_id: str, service: ServiceDep) -> Response:
    await service.revoke_token(token_id)
    return Response(status_code=204)


# --------------------------------------------------------------------------- #
# Device flow (RFC 8628)                                                       #
# --------------------------------------------------------------------------- #
@router.post(
    "/device/code",
    response_model=DeviceCodeResponse,
    summary="Start device-flow login (RFC 8628, SRS §13.20)",
)
async def device_code(payload: DeviceCodeRequest, service: ServiceDep) -> DeviceCodeResponse:
    result = await service.create_device_code(_clean_scopes(payload.scopes))
    return DeviceCodeResponse(**result)  # type: ignore[arg-type]


@router.get("/device", summary="Device approval landing (informational)")
async def device_landing() -> dict[str, str]:
    return {
        "message": (
            "Enter your user code to approve a device login. Approval is performed "
            "by an operator via POST /api/v1/auth/device/approve."
        )
    }


@router.post(
    "/device/approve",
    response_model=DeviceApproveResponse,
    dependencies=[Depends(require_admin)],
    summary="Approve a pending device login (SRS §13.20)",
)
async def device_approve(
    payload: DeviceApproveRequest, service: ServiceDep
) -> DeviceApproveResponse:
    approved = await service.approve_device(payload.user_code, payload.subject)
    return DeviceApproveResponse(approved=approved, user_code=payload.user_code)


# --------------------------------------------------------------------------- #
# OAuth 2.0 for MCP clients                                                    #
# --------------------------------------------------------------------------- #
@router.post(
    "/oauth/register",
    response_model=ClientRegistrationResponse,
    status_code=201,
    summary="Dynamic client registration (RFC 7591, SRS §13.20)",
)
async def register_client(
    payload: ClientRegistrationRequest, service: ServiceDep
) -> ClientRegistrationResponse:
    scopes = _clean_scopes(payload.scope.split() if payload.scope else [])
    record, secret = await service.register_client(
        name=payload.client_name,
        redirect_uris=tuple(payload.redirect_uris),
        grant_types=tuple(payload.grant_types),
        scopes=scopes,
        token_endpoint_auth_method=payload.token_endpoint_auth_method,
    )
    return ClientRegistrationResponse(
        client_id=record.client_id,
        client_secret=secret,
        client_name=record.name,
        redirect_uris=list(record.redirect_uris),
        grant_types=list(record.grant_types),
        scope=" ".join(sorted(record.scopes)),
        token_endpoint_auth_method=record.token_endpoint_auth_method,
    )


@router.get("/oauth/authorize", summary="OAuth authorization endpoint (PKCE, SRS §13.20)")
async def authorize(
    request: Request,
    service: ServiceDep,
    client_id: str,
    redirect_uri: str,
    code_challenge: str,
    response_type: str = "code",
    scope: str | None = None,
    state: str | None = None,
    code_challenge_method: str = "S256",
) -> Response:
    if response_type != "code":
        return _oauth_error(
            OAuthError("unsupported_response_type", "Only response_type=code is supported.")
        )
    if code_challenge_method != "S256":
        return _oauth_error(
            OAuthError("invalid_request", "Only code_challenge_method=S256 is supported.")
        )
    try:
        code = await service.create_authorization_code(
            client_id=client_id,
            redirect_uri=redirect_uri,
            scopes=oauth.normalize_scopes(scope, SUPPORTED_SCOPES),
            code_challenge=code_challenge,
            code_challenge_method=code_challenge_method,
        )
    except OAuthError as exc:
        # redirect_uri is not validated yet — never redirect to an unverified URI.
        return _oauth_error(exc)
    separator = "&" if "?" in redirect_uri else "?"
    location = f"{redirect_uri}{separator}code={code}"
    if state:
        location += f"&state={state}"
    return RedirectResponse(url=location, status_code=302, headers=_NO_STORE)


@router.post("/oauth/token", summary="OAuth token endpoint (SRS §13.20)")
async def token(
    service: ServiceDep,
    grant_type: Annotated[str, Form()],
    code: Annotated[str | None, Form()] = None,
    redirect_uri: Annotated[str | None, Form()] = None,
    client_id: Annotated[str | None, Form()] = None,
    client_secret: Annotated[str | None, Form()] = None,
    code_verifier: Annotated[str | None, Form()] = None,
    refresh_token: Annotated[str | None, Form()] = None,
    device_code: Annotated[str | None, Form()] = None,
    scope: Annotated[str | None, Form()] = None,
) -> JSONResponse:
    try:
        if grant_type == "authorization_code":
            if not (code and redirect_uri and client_id):
                raise OAuthError("invalid_request", "code, redirect_uri, client_id are required.")
            result = await service.exchange_authorization_code(
                code=code,
                client_id=client_id,
                redirect_uri=redirect_uri,
                code_verifier=code_verifier,
            )
        elif grant_type == "refresh_token":
            if not (refresh_token and client_id):
                raise OAuthError("invalid_request", "refresh_token and client_id are required.")
            result = await service.refresh(refresh_token=refresh_token, client_id=client_id)
        elif grant_type == "client_credentials":
            if not client_id:
                raise OAuthError("invalid_request", "client_id is required.")
            result = await service.client_credentials(
                client_id=client_id,
                client_secret=client_secret,
                scopes=oauth.normalize_scopes(scope, SUPPORTED_SCOPES),
            )
        elif grant_type == DEVICE_CODE_GRANT:
            if not device_code:
                raise OAuthError("invalid_request", "device_code is required.")
            result = await service.poll_device(device_code)
        else:
            raise OAuthError("unsupported_grant_type", f"Unsupported grant_type: {grant_type}.")
    except OAuthError as exc:
        return _oauth_error(exc)
    return JSONResponse(status_code=200, content=result, headers=_NO_STORE)
