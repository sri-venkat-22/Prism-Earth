"""Token domain model, hashing, and stores (SRS §13.20).

This module is storage-agnostic. It defines the framework-free value types
(:class:`TokenRecord`, :class:`OAuthClientRecord`, :class:`Principal`), the
hashing/generation helpers, and two storage protocols
(:class:`TokenStore`, :class:`ClientStore`) each with an in-memory
implementation (used by tests and single-process dev) and a SQL implementation
(the production default, persisting to the ``metadata`` schema).

Tokens are opaque, high-entropy strings prefixed ``pe_``; only their SHA-256
digest is ever persisted (SRS §13.20). Verification hashes the presented token
and looks it up — the plaintext is shown to the caller exactly once, at issue.
"""

from __future__ import annotations

import hashlib
import secrets
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any, Protocol, cast, runtime_checkable

from sqlalchemy import CursorResult, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import ApiTokenRow, OAuthClientRow

TOKEN_PREFIX = "pe_"


# --------------------------------------------------------------------------- #
# Hashing / generation                                                        #
# --------------------------------------------------------------------------- #
def generate_token() -> str:
    """Return a fresh opaque bearer token (``pe_`` + 43 url-safe chars)."""
    return TOKEN_PREFIX + secrets.token_urlsafe(32)


def hash_secret(secret: str) -> str:
    """Return the SHA-256 hex digest used to store/compare a secret."""
    return hashlib.sha256(secret.encode("utf-8")).hexdigest()


def token_prefix(token: str) -> str:
    """Return a non-secret display fragment of a token (first 12 chars)."""
    return token[:12]


# --------------------------------------------------------------------------- #
# Value types                                                                  #
# --------------------------------------------------------------------------- #
@dataclass(slots=True)
class TokenRecord:
    """A persisted API token (SRS §13.20). Never carries the plaintext secret."""

    id: str
    token_hash: str
    prefix: str
    name: str
    subject: str
    scopes: frozenset[str]
    created_at: datetime
    expires_at: datetime | None = None
    last_used_at: datetime | None = None
    revoked: bool = False
    rate_limit_per_minute: int | None = None

    def is_active(self, *, now: datetime | None = None) -> bool:
        """True when the token is neither revoked nor expired."""
        if self.revoked:
            return False
        if self.expires_at is not None:
            now = now or datetime.now(UTC)
            if now >= self.expires_at:
                return False
        return True


@dataclass(slots=True)
class OAuthClientRecord:
    """A registered OAuth client (RFC 7591)."""

    client_id: str
    name: str
    redirect_uris: tuple[str, ...] = ()
    grant_types: tuple[str, ...] = ()
    scopes: frozenset[str] = frozenset()
    token_endpoint_auth_method: str = "none"
    client_secret_hash: str | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    @property
    def is_public(self) -> bool:
        return self.client_secret_hash is None


@dataclass(slots=True)
class Principal:
    """The authenticated caller attached to ``request.state`` after auth."""

    subject: str
    scopes: frozenset[str]
    token_id: str | None = None
    rate_limit_per_minute: int | None = None
    anonymous: bool = False

    @classmethod
    def anonymous_principal(cls) -> Principal:
        """A stand-in used when auth is disabled (SRS §13.20 gateway toggle)."""
        return cls(subject="anonymous", scopes=frozenset(), anonymous=True)


def _scopes_to_str(scopes: frozenset[str]) -> str:
    return " ".join(sorted(scopes))


def _scopes_from_str(value: str) -> frozenset[str]:
    return frozenset(part for part in value.split() if part)


# --------------------------------------------------------------------------- #
# Token store                                                                  #
# --------------------------------------------------------------------------- #
@runtime_checkable
class TokenStore(Protocol):
    """Persistence for issued API tokens (SRS §13.20)."""

    async def create(self, record: TokenRecord) -> None: ...

    async def get_by_hash(self, token_hash: str) -> TokenRecord | None: ...

    async def get(self, token_id: str) -> TokenRecord | None: ...

    async def list(self, subject: str | None = None) -> list[TokenRecord]: ...

    async def revoke(self, token_id: str) -> bool: ...

    async def touch(self, token_id: str, when: datetime) -> None: ...


class InMemoryTokenStore:
    """Process-local token store (tests + single-process dev)."""

    def __init__(self) -> None:
        self._by_id: dict[str, TokenRecord] = {}

    async def create(self, record: TokenRecord) -> None:
        self._by_id[record.id] = record

    async def get_by_hash(self, token_hash: str) -> TokenRecord | None:
        for record in self._by_id.values():
            if secrets.compare_digest(record.token_hash, token_hash):
                return record
        return None

    async def get(self, token_id: str) -> TokenRecord | None:
        return self._by_id.get(token_id)

    async def list(self, subject: str | None = None) -> list[TokenRecord]:
        records = list(self._by_id.values())
        if subject is not None:
            records = [r for r in records if r.subject == subject]
        return sorted(records, key=lambda r: r.created_at, reverse=True)

    async def revoke(self, token_id: str) -> bool:
        record = self._by_id.get(token_id)
        if record is None or record.revoked:
            return False
        record.revoked = True
        return True

    async def touch(self, token_id: str, when: datetime) -> None:
        record = self._by_id.get(token_id)
        if record is not None:
            record.last_used_at = when


class SqlTokenStore:
    """Database-backed token store (production default)."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    @staticmethod
    def _to_record(row: ApiTokenRow) -> TokenRecord:
        return TokenRecord(
            id=row.id,
            token_hash=row.token_hash,
            prefix=row.prefix,
            name=row.name,
            subject=row.subject,
            scopes=_scopes_from_str(row.scopes),
            created_at=row.created_at,
            expires_at=row.expires_at,
            last_used_at=row.last_used_at,
            revoked=row.revoked,
            rate_limit_per_minute=row.rate_limit_per_minute,
        )

    async def create(self, record: TokenRecord) -> None:
        self._session.add(
            ApiTokenRow(
                id=record.id,
                token_hash=record.token_hash,
                prefix=record.prefix,
                name=record.name,
                subject=record.subject,
                scopes=_scopes_to_str(record.scopes),
                created_at=record.created_at,
                expires_at=record.expires_at,
                last_used_at=record.last_used_at,
                revoked=record.revoked,
                rate_limit_per_minute=record.rate_limit_per_minute,
            )
        )
        await self._session.commit()

    async def get_by_hash(self, token_hash: str) -> TokenRecord | None:
        row = (
            await self._session.execute(
                select(ApiTokenRow).where(ApiTokenRow.token_hash == token_hash)
            )
        ).scalar_one_or_none()
        return self._to_record(row) if row is not None else None

    async def get(self, token_id: str) -> TokenRecord | None:
        row = await self._session.get(ApiTokenRow, token_id)
        return self._to_record(row) if row is not None else None

    async def list(self, subject: str | None = None) -> list[TokenRecord]:
        stmt = select(ApiTokenRow).order_by(ApiTokenRow.created_at.desc())
        if subject is not None:
            stmt = stmt.where(ApiTokenRow.subject == subject)
        rows = (await self._session.execute(stmt)).scalars().all()
        return [self._to_record(row) for row in rows]

    async def revoke(self, token_id: str) -> bool:
        result = await self._session.execute(
            update(ApiTokenRow)
            .where(ApiTokenRow.id == token_id, ApiTokenRow.revoked.is_(False))
            .values(revoked=True)
        )
        await self._session.commit()
        return bool(cast("CursorResult[Any]", result).rowcount)

    async def touch(self, token_id: str, when: datetime) -> None:
        await self._session.execute(
            update(ApiTokenRow).where(ApiTokenRow.id == token_id).values(last_used_at=when)
        )
        await self._session.commit()


# --------------------------------------------------------------------------- #
# OAuth client store                                                           #
# --------------------------------------------------------------------------- #
@runtime_checkable
class ClientStore(Protocol):
    """Persistence for dynamically registered OAuth clients (RFC 7591)."""

    async def create(self, record: OAuthClientRecord) -> None: ...

    async def get(self, client_id: str) -> OAuthClientRecord | None: ...


class InMemoryClientStore:
    def __init__(self) -> None:
        self._by_id: dict[str, OAuthClientRecord] = {}

    async def create(self, record: OAuthClientRecord) -> None:
        self._by_id[record.client_id] = record

    async def get(self, client_id: str) -> OAuthClientRecord | None:
        return self._by_id.get(client_id)


class SqlClientStore:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    @staticmethod
    def _to_record(row: OAuthClientRow) -> OAuthClientRecord:
        return OAuthClientRecord(
            client_id=row.client_id,
            name=row.name,
            redirect_uris=tuple(part for part in row.redirect_uris.split() if part),
            grant_types=tuple(part for part in row.grant_types.split() if part),
            scopes=_scopes_from_str(row.scopes),
            token_endpoint_auth_method=row.token_endpoint_auth_method,
            client_secret_hash=row.client_secret_hash,
            created_at=row.created_at,
        )

    async def create(self, record: OAuthClientRecord) -> None:
        self._session.add(
            OAuthClientRow(
                client_id=record.client_id,
                client_secret_hash=record.client_secret_hash,
                name=record.name,
                redirect_uris=" ".join(record.redirect_uris),
                grant_types=" ".join(record.grant_types),
                scopes=_scopes_to_str(record.scopes),
                token_endpoint_auth_method=record.token_endpoint_auth_method,
                created_at=record.created_at,
            )
        )
        await self._session.commit()

    async def get(self, client_id: str) -> OAuthClientRecord | None:
        row = await self._session.get(OAuthClientRow, client_id)
        return self._to_record(row) if row is not None else None
