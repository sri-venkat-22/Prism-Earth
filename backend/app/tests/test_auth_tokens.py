"""Unit tests for the auth primitives (SRS §13.20, §13.19).

Storage-agnostic pieces only: token generation/hashing, the in-memory token
store, PKCE verification, scope normalization, and the rate limiter. The HTTP
flows are covered in ``test_auth_endpoints`` and ``test_oauth_device``.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from app.auth import oauth
from app.auth.ratelimit import enforce_rate_limit
from app.auth.stores import InMemoryEphemeralStore
from app.auth.tokens import (
    InMemoryTokenStore,
    TokenRecord,
    generate_token,
    hash_secret,
    token_prefix,
)
from app.core.errors import RateLimitError


def _record(**overrides: object) -> TokenRecord:
    token = generate_token()
    base = dict(
        id="tok-1",
        token_hash=hash_secret(token),
        prefix=token_prefix(token),
        name="test",
        subject="dashboard",
        scopes=frozenset({"fetch", "ask"}),
        created_at=datetime.now(UTC),
    )
    base.update(overrides)
    return TokenRecord(**base)  # type: ignore[arg-type]


def test_generated_tokens_are_prefixed_and_unique() -> None:
    a, b = generate_token(), generate_token()
    assert a.startswith("pe_") and b.startswith("pe_")
    assert a != b
    assert hash_secret(a) == hash_secret(a)  # deterministic
    assert hash_secret(a) != hash_secret(b)
    assert len(hash_secret(a)) == 64  # sha256 hex


def test_token_record_is_active_respects_revoked_and_expiry() -> None:
    now = datetime.now(UTC)
    assert _record().is_active(now=now) is True
    assert _record(revoked=True).is_active(now=now) is False
    assert _record(expires_at=now - timedelta(seconds=1)).is_active(now=now) is False
    assert _record(expires_at=now + timedelta(hours=1)).is_active(now=now) is True


async def test_in_memory_token_store_roundtrip() -> None:
    store = InMemoryTokenStore()
    token = generate_token()
    record = _record(id="abc", token_hash=hash_secret(token))
    await store.create(record)

    assert await store.get_by_hash(hash_secret(token)) is not None
    assert await store.get_by_hash(hash_secret("pe_wrong")) is None
    assert await store.get("abc") is not None

    when = datetime.now(UTC)
    await store.touch("abc", when)
    assert (await store.get("abc")).last_used_at == when  # type: ignore[union-attr]

    assert await store.revoke("abc") is True
    assert await store.revoke("abc") is False  # already revoked
    assert (await store.get("abc")).revoked is True  # type: ignore[union-attr]


def test_pkce_s256_roundtrip() -> None:
    import base64
    import hashlib

    verifier = "a" * 64
    challenge = (
        base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b"=").decode()
    )
    assert oauth.verify_pkce(verifier, challenge, "S256") is True
    assert oauth.verify_pkce("wrong-verifier", challenge, "S256") is False
    assert oauth.verify_pkce(verifier, verifier, "plain") is True
    assert oauth.verify_pkce(verifier, challenge, "unknown") is False


def test_normalize_scopes_intersects_with_allowed() -> None:
    allowed = frozenset({"fetch", "ask"})
    assert oauth.normalize_scopes(None, allowed) == allowed
    assert oauth.normalize_scopes("fetch", allowed) == frozenset({"fetch"})
    # Unknown scopes are dropped; an empty result falls back to all allowed.
    assert oauth.normalize_scopes("bogus", allowed) == allowed


async def test_rate_limiter_raises_after_limit() -> None:
    store = InMemoryEphemeralStore()
    # A budget of 3/min: the first three pass, the fourth trips 429.
    for _ in range(3):
        await enforce_rate_limit(store, "tok", 3)
    with pytest.raises(RateLimitError) as excinfo:
        await enforce_rate_limit(store, "tok", 3)
    assert excinfo.value.status_code == 429
    assert "Retry-After" in excinfo.value.headers


async def test_rate_limiter_disabled_when_limit_non_positive() -> None:
    store = InMemoryEphemeralStore()
    for _ in range(100):
        await enforce_rate_limit(store, "tok", 0)  # no limit
