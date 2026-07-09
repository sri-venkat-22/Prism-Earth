"""Google "Sign in with Google" helper (OAuth 2.0 / OIDC, SRS §13.20).

A thin, dependency-free wrapper (uses the already-present ``httpx``) over the
authorization-code flow: build the consent URL, then exchange the returned code
for the user's verified email + stable subject id. No JWT verification is needed
— the userinfo is fetched directly from Google over TLS with the fresh access
token, so its authenticity is transitively assured.
"""

from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import urlencode

import httpx

_AUTH_ENDPOINT = "https://accounts.google.com/o/oauth2/v2/auth"
_TOKEN_ENDPOINT = "https://oauth2.googleapis.com/token"  # noqa: S105 - public URL
_USERINFO_ENDPOINT = "https://openidconnect.googleapis.com/v1/userinfo"


class GoogleOAuthError(Exception):
    """Raised when the Google exchange fails or returns an unusable profile."""


@dataclass(frozen=True, slots=True)
class GoogleProfile:
    sub: str
    email: str


def authorization_url(*, client_id: str, redirect_uri: str, state: str) -> str:
    params = {
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "response_type": "code",
        "scope": "openid email",
        "state": state,
        "access_type": "online",
        "prompt": "select_account",
    }
    return f"{_AUTH_ENDPOINT}?{urlencode(params)}"


async def exchange_code(
    *, code: str, client_id: str, client_secret: str, redirect_uri: str
) -> GoogleProfile:
    async with httpx.AsyncClient(timeout=15.0) as client:
        token_resp = await client.post(
            _TOKEN_ENDPOINT,
            data={
                "code": code,
                "client_id": client_id,
                "client_secret": client_secret,
                "redirect_uri": redirect_uri,
                "grant_type": "authorization_code",
            },
        )
        if token_resp.status_code != 200:
            raise GoogleOAuthError(f"Google token exchange failed ({token_resp.status_code}).")
        access_token = token_resp.json().get("access_token")
        if not access_token:
            raise GoogleOAuthError("Google token response had no access_token.")

        info_resp = await client.get(
            _USERINFO_ENDPOINT, headers={"Authorization": f"Bearer {access_token}"}
        )
        if info_resp.status_code != 200:
            raise GoogleOAuthError(f"Google userinfo failed ({info_resp.status_code}).")
        info = info_resp.json()

    sub, email = info.get("sub"), info.get("email")
    if not sub or not email or not info.get("email_verified", True):
        raise GoogleOAuthError("Google profile is missing a verified email.")
    return GoogleProfile(sub=str(sub), email=str(email).lower())
