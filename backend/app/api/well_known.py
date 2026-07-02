"""OAuth discovery documents (RFC 8414 / RFC 9728, SRS §13.20, §34).

These live at the root (``/.well-known/*``), not under ``/api/v1``, because MCP
clients and OAuth libraries probe well-known paths on the issuer origin to
discover the authorization server and the protected resource. Both are public.
"""

from __future__ import annotations

from fastapi import APIRouter, Request

from app.auth.oauth import authorization_server_metadata, protected_resource_metadata
from app.core.config import Settings, get_settings

router = APIRouter(tags=["oauth-discovery"])


def _issuer(request: Request) -> str:
    settings = getattr(request.app.state, "settings", None)
    if not isinstance(settings, Settings):
        settings = get_settings()
    return settings.auth_issuer_url


@router.get("/.well-known/oauth-authorization-server", summary="OAuth AS metadata (RFC 8414)")
async def oauth_authorization_server(request: Request) -> dict[str, object]:
    return authorization_server_metadata(_issuer(request))


@router.get(
    "/.well-known/oauth-protected-resource", summary="Protected-resource metadata (RFC 9728)"
)
async def oauth_protected_resource(request: Request) -> dict[str, object]:
    return protected_resource_metadata(_issuer(request))
