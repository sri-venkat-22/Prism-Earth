"""End-user accounts: domain type, password hashing, and store (SRS §13.20).

Adds the *human* side of auth on top of the existing machine-token system: an
email/password (or Google) account whose id becomes the ``subject`` of the
session and API tokens it owns. Passwords are hashed with stdlib
:func:`hashlib.scrypt` — a memory-hard KDF — so no password crypto dependency is
introduced. Only the digest is ever persisted.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import secrets
from dataclasses import dataclass
from datetime import datetime
from typing import Protocol, runtime_checkable

from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import UserRow

# scrypt work factors (RFC 7914 interactive-login range). Kept as an encoded
# prefix so the parameters can change without invalidating existing hashes.
_SCRYPT_N = 2**14
_SCRYPT_R = 8
_SCRYPT_P = 1
_SCRYPT_DKLEN = 32
_SALT_BYTES = 16


def hash_password(password: str) -> str:
    """Return an ``scrypt$n$r$p$salt$dk`` digest for ``password``."""
    salt = secrets.token_bytes(_SALT_BYTES)
    dk = hashlib.scrypt(
        password.encode("utf-8"),
        salt=salt,
        n=_SCRYPT_N,
        r=_SCRYPT_R,
        p=_SCRYPT_P,
        dklen=_SCRYPT_DKLEN,
    )
    b64 = lambda raw: base64.b64encode(raw).decode("ascii")  # noqa: E731
    return f"scrypt${_SCRYPT_N}${_SCRYPT_R}${_SCRYPT_P}${b64(salt)}${b64(dk)}"


def verify_password(password: str, stored: str | None) -> bool:
    """Constant-time check of ``password`` against a stored digest."""
    if not stored:
        return False
    try:
        scheme, n, r, p, salt_b64, dk_b64 = stored.split("$")
        if scheme != "scrypt":
            return False
        salt = base64.b64decode(salt_b64)
        expected = base64.b64decode(dk_b64)
        actual = hashlib.scrypt(
            password.encode("utf-8"),
            salt=salt,
            n=int(n),
            r=int(r),
            p=int(p),
            dklen=len(expected),
        )
    except (ValueError, TypeError):
        return False
    return hmac.compare_digest(actual, expected)


@dataclass(slots=True)
class UserRecord:
    """A persisted end-user account. Never carries the plaintext password."""

    id: str
    email: str
    password_hash: str | None
    organization: str | None
    google_sub: str | None
    created_at: datetime


@runtime_checkable
class UserStore(Protocol):
    async def create(self, record: UserRecord) -> None: ...
    async def get(self, user_id: str) -> UserRecord | None: ...
    async def get_by_email(self, email: str) -> UserRecord | None: ...
    async def get_by_google_sub(self, google_sub: str) -> UserRecord | None: ...
    async def set_organization(self, user_id: str, organization: str | None) -> None: ...
    async def link_google(self, user_id: str, google_sub: str) -> None: ...
    async def delete(self, user_id: str) -> None: ...


class InMemoryUserStore:
    """Process-local user store (tests + single-process dev)."""

    def __init__(self) -> None:
        self._by_id: dict[str, UserRecord] = {}

    async def create(self, record: UserRecord) -> None:
        self._by_id[record.id] = record

    async def get(self, user_id: str) -> UserRecord | None:
        return self._by_id.get(user_id)

    async def get_by_email(self, email: str) -> UserRecord | None:
        email = email.lower()
        return next((u for u in self._by_id.values() if u.email == email), None)

    async def get_by_google_sub(self, google_sub: str) -> UserRecord | None:
        return next((u for u in self._by_id.values() if u.google_sub == google_sub), None)

    async def set_organization(self, user_id: str, organization: str | None) -> None:
        if (u := self._by_id.get(user_id)) is not None:
            u.organization = organization

    async def link_google(self, user_id: str, google_sub: str) -> None:
        if (u := self._by_id.get(user_id)) is not None:
            u.google_sub = google_sub

    async def delete(self, user_id: str) -> None:
        self._by_id.pop(user_id, None)


class SqlUserStore:
    """Database-backed user store (production default)."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    @staticmethod
    def _to_record(row: UserRow) -> UserRecord:
        return UserRecord(
            id=row.id,
            email=row.email,
            password_hash=row.password_hash,
            organization=row.organization,
            google_sub=row.google_sub,
            created_at=row.created_at,
        )

    async def create(self, record: UserRecord) -> None:
        self._session.add(
            UserRow(
                id=record.id,
                email=record.email,
                password_hash=record.password_hash,
                organization=record.organization,
                google_sub=record.google_sub,
                created_at=record.created_at,
            )
        )
        await self._session.commit()

    async def get(self, user_id: str) -> UserRecord | None:
        row = await self._session.get(UserRow, user_id)
        return self._to_record(row) if row is not None else None

    async def get_by_email(self, email: str) -> UserRecord | None:
        row = (
            await self._session.execute(select(UserRow).where(UserRow.email == email.lower()))
        ).scalar_one_or_none()
        return self._to_record(row) if row is not None else None

    async def get_by_google_sub(self, google_sub: str) -> UserRecord | None:
        row = (
            await self._session.execute(select(UserRow).where(UserRow.google_sub == google_sub))
        ).scalar_one_or_none()
        return self._to_record(row) if row is not None else None

    async def set_organization(self, user_id: str, organization: str | None) -> None:
        await self._session.execute(
            update(UserRow).where(UserRow.id == user_id).values(organization=organization)
        )
        await self._session.commit()

    async def link_google(self, user_id: str, google_sub: str) -> None:
        await self._session.execute(
            update(UserRow).where(UserRow.id == user_id).values(google_sub=google_sub)
        )
        await self._session.commit()

    async def delete(self, user_id: str) -> None:
        await self._session.execute(delete(UserRow).where(UserRow.id == user_id))
        await self._session.commit()
