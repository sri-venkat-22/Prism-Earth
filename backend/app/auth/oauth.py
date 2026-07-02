"""OAuth 2.0 helpers for the MCP authorization surface (SRS §13.20, §34).

A deliberately minimal but standards-shaped OAuth 2.0 subset: PKCE (S256)
verification, and the two discovery documents MCP clients read to find the
authorization server and the protected resource.

- RFC 8414 — Authorization Server Metadata
- RFC 9728 — Protected Resource Metadata
- RFC 7636 — PKCE

The set of grant types and scopes supported is intentionally small: authorization
code (+PKCE), refresh token, client credentials, and the device-code grant; the
scopes mirror the two protected data endpoints.
"""

from __future__ import annotations

import base64
import hashlib
import secrets

# Scopes map 1:1 to the protected data endpoints (SRS §13.20).
SCOPE_FETCH = "fetch"
SCOPE_ASK = "ask"
SUPPORTED_SCOPES: frozenset[str] = frozenset({SCOPE_FETCH, SCOPE_ASK})
DEFAULT_SCOPES: frozenset[str] = SUPPORTED_SCOPES

DEVICE_CODE_GRANT = "urn:ietf:params:oauth:grant-type:device_code"
SUPPORTED_GRANT_TYPES: tuple[str, ...] = (
    "authorization_code",
    "refresh_token",
    "client_credentials",
    DEVICE_CODE_GRANT,
)


class OAuthError(Exception):
    """An OAuth error rendered as the RFC 6749 ``{error, error_description}`` body."""

    def __init__(self, error: str, description: str, *, status_code: int = 400) -> None:
        self.error = error
        self.description = description
        self.status_code = status_code
        super().__init__(f"{error}: {description}")

    def to_dict(self) -> dict[str, str]:
        return {"error": self.error, "error_description": self.description}


def _b64url_nopad(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")


def verify_pkce(code_verifier: str, code_challenge: str, method: str) -> bool:
    """Verify a PKCE ``code_verifier`` against the stored challenge (RFC 7636).

    Supports ``S256`` (required for MCP) and ``plain``.
    """
    if method == "S256":
        digest = hashlib.sha256(code_verifier.encode("ascii")).digest()
        expected = _b64url_nopad(digest)
        return secrets.compare_digest(expected, code_challenge)
    if method == "plain":
        return secrets.compare_digest(code_verifier, code_challenge)
    return False


def normalize_scopes(requested: str | None, allowed: frozenset[str]) -> frozenset[str]:
    """Intersect a space-delimited scope request with ``allowed`` (defaults to it)."""
    if not requested:
        return allowed
    asked = {part for part in requested.split() if part}
    return frozenset(asked & allowed) or allowed


def authorization_server_metadata(issuer: str) -> dict[str, object]:
    """RFC 8414 authorization-server metadata document."""
    issuer = issuer.rstrip("/")
    base = f"{issuer}/api/v1/auth/oauth"
    return {
        "issuer": issuer,
        "authorization_endpoint": f"{base}/authorize",
        "token_endpoint": f"{base}/token",
        "registration_endpoint": f"{base}/register",
        "device_authorization_endpoint": f"{issuer}/api/v1/auth/device/code",
        "scopes_supported": sorted(SUPPORTED_SCOPES),
        "response_types_supported": ["code"],
        "grant_types_supported": list(SUPPORTED_GRANT_TYPES),
        "token_endpoint_auth_methods_supported": ["none", "client_secret_post"],
        "code_challenge_methods_supported": ["S256"],
    }


def protected_resource_metadata(issuer: str) -> dict[str, object]:
    """RFC 9728 protected-resource metadata document."""
    issuer = issuer.rstrip("/")
    return {
        "resource": issuer,
        "authorization_servers": [issuer],
        "scopes_supported": sorted(SUPPORTED_SCOPES),
        "bearer_methods_supported": ["header"],
    }
