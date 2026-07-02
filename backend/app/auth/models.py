"""Authentication ORM entities (SRS §13.20, §22.3).

Persists the two entities that must survive restarts: issued **API tokens**
(stored only as a SHA-256 hash — never in plaintext) and dynamically registered
**OAuth clients** (RFC 7591). Short-lived state — authorization codes, device
codes, and rate-limit counters — is *not* persisted here; it lives in the
ephemeral store (:mod:`app.auth.stores`).

Both tables live in the ``metadata`` schema alongside the registry tables
(SRS §20.3). They are imported by :mod:`app.models` so Alembic and the app see
them.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base

_SCHEMA = {"schema": "metadata"}


class ApiTokenRow(Base):
    """An issued bearer token (SRS §13.20).

    The token secret is never stored; ``token_hash`` is its SHA-256 digest. The
    ``prefix`` is a non-secret display fragment (e.g. ``pe_ab12cd``) so a token
    can be identified in a dashboard without revealing it.
    """

    __tablename__ = "api_token"
    __table_args__ = _SCHEMA

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    token_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    prefix: Mapped[str] = mapped_column(String(16), nullable=False)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    subject: Mapped[str] = mapped_column(String(128), nullable=False)
    scopes: Mapped[str] = mapped_column(Text, nullable=False, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    revoked: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    rate_limit_per_minute: Mapped[int | None] = mapped_column(Integer)


class OAuthClientRow(Base):
    """A registered OAuth 2.0 client (RFC 7591, SRS §13.20).

    Public clients (the common MCP case, using PKCE) have no
    ``client_secret_hash``. ``redirect_uris``, ``grant_types``, and ``scopes``
    are space-delimited.
    """

    __tablename__ = "oauth_client"
    __table_args__ = _SCHEMA

    client_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    client_secret_hash: Mapped[str | None] = mapped_column(String(64))
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    redirect_uris: Mapped[str] = mapped_column(Text, nullable=False, default="")
    grant_types: Mapped[str] = mapped_column(Text, nullable=False, default="")
    scopes: Mapped[str] = mapped_column(Text, nullable=False, default="")
    token_endpoint_auth_method: Mapped[str] = mapped_column(
        String(32), nullable=False, default="none"
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
