"""High-level auth operations (SRS §13.20).

:class:`AuthService` composes the token store, OAuth-client store, and ephemeral
store into the three credential flows the SRS requires:

- **Dashboard-issued API tokens** — :meth:`issue_token`.
- **Device-flow login** for CLI clients (RFC 8628) — :meth:`create_device_code`,
  :meth:`approve_device`, :meth:`poll_device`.
- **OAuth 2.0 for MCP clients** — :meth:`register_client`,
  :meth:`create_authorization_code`, :meth:`exchange_authorization_code`,
  :meth:`refresh`, :meth:`client_credentials`.

Every flow ultimately mints an opaque bearer token via :meth:`issue_token`, so a
single verification path (:mod:`app.auth.dependencies`) covers them all.
"""

from __future__ import annotations

import secrets
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from uuid import uuid4

from app.auth import oauth
from app.auth.stores import EphemeralStore
from app.auth.tokens import (
    ClientStore,
    OAuthClientRecord,
    TokenRecord,
    TokenStore,
    generate_token,
    hash_secret,
    token_prefix,
)
from app.core.config import Settings

_DEVICE_CODE_TTL = 600  # seconds (RFC 8628 expires_in)
_DEVICE_POLL_INTERVAL = 5  # seconds
_AUTH_CODE_TTL = 600
_OAUTH_ACCESS_TTL = timedelta(hours=1)
_REFRESH_TTL = 30 * 24 * 3600
_USER_CODE_ALPHABET = "BCDFGHJKLMNPQRSTVWXZ0123456789"  # unambiguous


def _gen_user_code() -> str:
    raw = "".join(secrets.choice(_USER_CODE_ALPHABET) for _ in range(8))
    return f"{raw[:4]}-{raw[4:]}"


@dataclass(slots=True)
class IssuedToken:
    """A freshly issued token: the one-time plaintext plus its stored record."""

    token: str
    record: TokenRecord


class AuthService:
    def __init__(
        self,
        *,
        token_store: TokenStore,
        client_store: ClientStore,
        ephemeral: EphemeralStore,
        settings: Settings,
    ) -> None:
        self._tokens = token_store
        self._clients = client_store
        self._ephemeral = ephemeral
        self._settings = settings

    @property
    def _issuer(self) -> str:
        return self._settings.auth_issuer_url.rstrip("/")

    # ------------------------------------------------------------------ #
    # Token issuance (dashboard API tokens, SRS §13.20)                  #
    # ------------------------------------------------------------------ #
    async def issue_token(
        self,
        *,
        name: str,
        subject: str,
        scopes: frozenset[str],
        expires_in: timedelta | None = None,
        rate_limit_per_minute: int | None = None,
    ) -> IssuedToken:
        token = generate_token()
        now = datetime.now(UTC)
        record = TokenRecord(
            id=str(uuid4()),
            token_hash=hash_secret(token),
            prefix=token_prefix(token),
            name=name,
            subject=subject,
            scopes=scopes,
            created_at=now,
            expires_at=(now + expires_in) if expires_in is not None else None,
            rate_limit_per_minute=rate_limit_per_minute,
        )
        await self._tokens.create(record)
        return IssuedToken(token=token, record=record)

    def default_token_ttl(self) -> timedelta | None:
        days = self._settings.auth_token_ttl_days
        return timedelta(days=days) if days else None

    async def list_tokens(self) -> list[TokenRecord]:
        return await self._tokens.list()

    async def revoke_token(self, token_id: str) -> bool:
        return await self._tokens.revoke(token_id)

    # ------------------------------------------------------------------ #
    # Device flow (RFC 8628)                                             #
    # ------------------------------------------------------------------ #
    async def create_device_code(self, scopes: frozenset[str]) -> dict[str, object]:
        device_code = secrets.token_urlsafe(32)
        user_code = _gen_user_code()
        await self._ephemeral.put(
            f"device:{device_code}",
            {
                "user_code": user_code,
                "scopes": sorted(scopes),
                "approved": False,
                "access_token": None,
                "subject": None,
            },
            _DEVICE_CODE_TTL,
        )
        await self._ephemeral.put(
            f"usercode:{user_code}", {"device_code": device_code}, _DEVICE_CODE_TTL
        )
        verification_uri = f"{self._issuer}/api/v1/auth/device"
        return {
            "device_code": device_code,
            "user_code": user_code,
            "verification_uri": verification_uri,
            "verification_uri_complete": f"{verification_uri}?user_code={user_code}",
            "expires_in": _DEVICE_CODE_TTL,
            "interval": _DEVICE_POLL_INTERVAL,
        }

    async def approve_device(self, user_code: str, subject: str) -> bool:
        """Approve a pending device authorization and mint its token.

        Stands in for the user completing login on the dashboard; guarded by the
        admin credential at the endpoint layer.
        """
        idx = await self._ephemeral.get(f"usercode:{user_code.strip().upper()}")
        if idx is None:
            return False
        device_code = str(idx["device_code"])
        data = await self._ephemeral.get(f"device:{device_code}")
        if data is None:
            return False
        scopes = frozenset(data["scopes"])
        issued = await self.issue_token(
            name=f"device:{user_code}",
            subject=subject,
            scopes=scopes,
            expires_in=self.default_token_ttl(),
        )
        data.update({"approved": True, "access_token": issued.token, "subject": subject})
        await self._ephemeral.put(f"device:{device_code}", data, _DEVICE_CODE_TTL)
        return True

    async def poll_device(self, device_code: str) -> dict[str, object]:
        data = await self._ephemeral.get(f"device:{device_code}")
        if data is None:
            raise oauth.OAuthError("expired_token", "The device code has expired.")
        if not data["approved"]:
            raise oauth.OAuthError("authorization_pending", "Authorization is pending.")
        await self._ephemeral.delete(f"device:{device_code}")  # single use
        return _token_response(str(data["access_token"]), frozenset(data["scopes"]))

    # ------------------------------------------------------------------ #
    # OAuth 2.0 (MCP clients)                                            #
    # ------------------------------------------------------------------ #
    async def register_client(
        self,
        *,
        name: str,
        redirect_uris: tuple[str, ...],
        grant_types: tuple[str, ...],
        scopes: frozenset[str],
        token_endpoint_auth_method: str,
    ) -> tuple[OAuthClientRecord, str | None]:
        client_id = "mcp_" + secrets.token_urlsafe(16)
        secret: str | None = None
        secret_hash: str | None = None
        if token_endpoint_auth_method != "none":  # noqa: S105 - OAuth method name, not a secret
            secret = secrets.token_urlsafe(32)
            secret_hash = hash_secret(secret)
        record = OAuthClientRecord(
            client_id=client_id,
            name=name,
            redirect_uris=redirect_uris,
            grant_types=grant_types or ("authorization_code", "refresh_token"),
            scopes=scopes,
            token_endpoint_auth_method=token_endpoint_auth_method,
            client_secret_hash=secret_hash,
        )
        await self._clients.create(record)
        return record, secret

    async def create_authorization_code(
        self,
        *,
        client_id: str,
        redirect_uri: str,
        scopes: frozenset[str],
        code_challenge: str,
        code_challenge_method: str,
    ) -> str:
        client = await self._clients.get(client_id)
        if client is None:
            raise oauth.OAuthError("invalid_request", "Unknown client_id.")
        if client.redirect_uris and redirect_uri not in client.redirect_uris:
            raise oauth.OAuthError("invalid_request", "redirect_uri is not registered.")
        code = secrets.token_urlsafe(32)
        await self._ephemeral.put(
            f"authcode:{code}",
            {
                "client_id": client_id,
                "redirect_uri": redirect_uri,
                "scopes": sorted(scopes),
                "code_challenge": code_challenge,
                "code_challenge_method": code_challenge_method,
                # No interactive login UI in scope: consent is auto-granted and
                # the subject is the client itself (documented in the plan).
                "subject": f"oauth:{client_id}",
            },
            _AUTH_CODE_TTL,
        )
        return code

    async def exchange_authorization_code(
        self, *, code: str, client_id: str, redirect_uri: str, code_verifier: str | None
    ) -> dict[str, object]:
        data = await self._ephemeral.get(f"authcode:{code}")
        if data is None:
            raise oauth.OAuthError("invalid_grant", "Authorization code is invalid or expired.")
        if data["client_id"] != client_id:
            raise oauth.OAuthError("invalid_grant", "client_id mismatch.")
        if data["redirect_uri"] != redirect_uri:
            raise oauth.OAuthError("invalid_grant", "redirect_uri mismatch.")
        if not code_verifier or not oauth.verify_pkce(
            code_verifier, str(data["code_challenge"]), str(data["code_challenge_method"])
        ):
            raise oauth.OAuthError("invalid_grant", "PKCE verification failed.")
        await self._ephemeral.delete(f"authcode:{code}")  # single use
        scopes = frozenset(data["scopes"])
        return await self._issue_oauth_tokens(
            subject=str(data["subject"]), client_id=client_id, scopes=scopes
        )

    async def refresh(self, *, refresh_token: str, client_id: str) -> dict[str, object]:
        data = await self._ephemeral.get(f"refresh:{refresh_token}")
        if data is None or data["client_id"] != client_id:
            raise oauth.OAuthError("invalid_grant", "Refresh token is invalid or expired.")
        await self._ephemeral.delete(f"refresh:{refresh_token}")  # rotate
        return await self._issue_oauth_tokens(
            subject=str(data["subject"]), client_id=client_id, scopes=frozenset(data["scopes"])
        )

    async def client_credentials(
        self, *, client_id: str, client_secret: str | None, scopes: frozenset[str]
    ) -> dict[str, object]:
        client = await self._clients.get(client_id)
        if client is None:
            raise oauth.OAuthError("invalid_client", "Unknown client_id.", status_code=401)
        if client.is_public or client.client_secret_hash is None:
            raise oauth.OAuthError(
                "unauthorized_client", "client_credentials requires a confidential client."
            )
        if not client_secret or not secrets.compare_digest(
            hash_secret(client_secret), client.client_secret_hash
        ):
            raise oauth.OAuthError("invalid_client", "Bad client credentials.", status_code=401)
        granted = frozenset(scopes & client.scopes) if client.scopes else scopes
        issued = await self.issue_token(
            name=f"oauth-cc:{client_id}",
            subject=client_id,
            scopes=granted or oauth.DEFAULT_SCOPES,
            expires_in=_OAUTH_ACCESS_TTL,
        )
        return _token_response(issued.token, issued.record.scopes)

    async def _issue_oauth_tokens(
        self, *, subject: str, client_id: str, scopes: frozenset[str]
    ) -> dict[str, object]:
        issued = await self.issue_token(
            name=f"oauth:{client_id}",
            subject=subject,
            scopes=scopes or oauth.DEFAULT_SCOPES,
            expires_in=_OAUTH_ACCESS_TTL,
        )
        refresh_token = secrets.token_urlsafe(32)
        await self._ephemeral.put(
            f"refresh:{refresh_token}",
            {"client_id": client_id, "subject": subject, "scopes": sorted(issued.record.scopes)},
            _REFRESH_TTL,
        )
        response = _token_response(issued.token, issued.record.scopes)
        response["refresh_token"] = refresh_token
        return response


def _token_response(access_token: str, scopes: frozenset[str]) -> dict[str, object]:
    return {
        "access_token": access_token,
        "token_type": "Bearer",
        "expires_in": int(_OAUTH_ACCESS_TTL.total_seconds()),
        "scope": " ".join(sorted(scopes)),
    }
