"""End-user account flow tests (SRS §13.20).

Register / login / profile / per-user API tokens and the brute-force guard,
all against in-memory stores (no DB) via the existing auth harness.
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager

from fastapi.testclient import TestClient

from app.api.v1.account import get_user_store
from app.auth.dependencies import SESSION_COOKIE
from app.auth.users import InMemoryUserStore, hash_password, verify_password
from app.tests._auth_app import auth_client

_CREDS = {"email": "Sri@Example.com", "password": "correct horse battery"}


def _bearer(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


@contextmanager
def account_client() -> Iterator[TestClient]:
    with auth_client() as (client, _token_store, _):
        user_store = InMemoryUserStore()  # one shared store across all requests
        client.app.dependency_overrides[get_user_store] = lambda: user_store
        yield client


def _register(client: TestClient, **over: object) -> str:
    """Register and return the session token — delivered as a cookie, not a body
    field. Callers still send it as a Bearer header (which the backend accepts
    alongside the cookie), so the existing header-based assertions are unchanged.
    """
    resp = client.post("/api/v1/account/register", json={**_CREDS, **over})
    assert resp.status_code == 201, resp.text
    return resp.cookies[SESSION_COOKIE]


def test_register_sets_httponly_session_cookie() -> None:
    with account_client() as client:
        resp = client.post("/api/v1/account/register", json=_CREDS)
        assert resp.status_code == 201, resp.text
        assert "token" not in resp.json()  # token is never exposed to client JS
        cookie = resp.headers.get("set-cookie", "").lower()
        assert f"{SESSION_COOKIE}=" in resp.headers.get("set-cookie", "")
        assert "httponly" in cookie
        assert "samesite=lax" in cookie
        # The cookie alone authenticates — no Authorization header sent.
        me = client.get("/api/v1/account/me")
        assert me.status_code == 200
        assert me.json()["email"] == "sri@example.com"


def test_password_hash_roundtrip_and_salting() -> None:
    pw = "correct horse battery"
    h = hash_password(pw)
    assert h.startswith("scrypt$")
    assert verify_password(pw, h)
    assert not verify_password("wrong", h)
    assert not verify_password(pw, None)
    assert h != hash_password(pw)  # per-call random salt


def test_register_then_me_normalizes_email() -> None:
    with account_client() as client:
        token = _register(client)
        me = client.get("/api/v1/account/me", headers=_bearer(token))
        assert me.status_code == 200
        assert me.json()["email"] == "sri@example.com"  # lower-cased
        assert me.json()["has_password"] is True


def test_duplicate_email_rejected() -> None:
    with account_client() as client:
        _register(client)
        resp = client.post("/api/v1/account/register", json=_CREDS)
        assert resp.status_code == 409
        assert resp.json()["error"]["code"] == "EMAIL_TAKEN"


def test_login_wrong_password_is_401_generic() -> None:
    with account_client() as client:
        _register(client)
        resp = client.post(
            "/api/v1/account/login", json={"email": _CREDS["email"], "password": "nope!!!!!"}
        )
        assert resp.status_code == 401
        assert "Invalid email or password" in resp.json()["error"]["message"]


def test_me_requires_token() -> None:
    with account_client() as client:
        assert client.get("/api/v1/account/me").status_code == 401


def test_api_token_lifecycle_excludes_session() -> None:
    with account_client() as client:
        token = _register(client)
        # Freshly registered: session token exists but is NOT listed as an API token.
        assert client.get("/api/v1/account/tokens", headers=_bearer(token)).json()["count"] == 0

        created = client.post(
            "/api/v1/account/tokens",
            json={"name": "cli-laptop", "scopes": ["fetch", "ask"]},
            headers=_bearer(token),
        )
        assert created.status_code == 201
        api_token = created.json()
        assert api_token["token"].startswith("pe_")
        assert api_token["subject"]  # bound to the user id

        listing = client.get("/api/v1/account/tokens", headers=_bearer(token)).json()
        assert listing["count"] == 1

        rid = api_token["id"]
        revoked = client.delete(f"/api/v1/account/tokens/{rid}", headers=_bearer(token))
        assert revoked.status_code == 204
        assert client.get("/api/v1/account/tokens", headers=_bearer(token)).json()["count"] == 0


def test_cannot_revoke_someone_elses_token() -> None:
    with account_client() as client:
        a = _register(client)
        b = _register(client, email="other@example.com")
        made = client.post(
            "/api/v1/account/tokens", json={"name": "a"}, headers=_bearer(a)
        ).json()
        # B tries to revoke A's token → treated as not found (no cross-user access).
        assert (
            client.delete(f"/api/v1/account/tokens/{made['id']}", headers=_bearer(b)).status_code
            == 404
        )


def test_delete_account_invalidates_session() -> None:
    with account_client() as client:
        token = _register(client)
        assert client.delete("/api/v1/account/me", headers=_bearer(token)).status_code == 204
        assert client.get("/api/v1/account/me", headers=_bearer(token)).status_code == 401


def test_brute_force_guard_trips() -> None:
    with account_client() as client:
        # auth_login_rate_limit_per_minute defaults to 10; the 11th attempt 429s.
        codes = [
            client.post(
                "/api/v1/account/login", json={"email": "x@y.com", "password": "bad"}
            ).status_code
            for _ in range(11)
        ]
        assert codes[-1] == 429
        assert 401 in codes  # earlier attempts were processed (unknown user)
