"""Auth-enforcement + token-management tests (SRS §13.20, §13.19).

Verifies the gateway contract when ``auth_enabled=true``: metadata and ``/ask``
stay public; ``/fetch`` requires a valid, correctly-scoped bearer token;
per-token rate limits return 429; and token management is admin-gated.
"""

from __future__ import annotations

from app.tests._auth_app import ADMIN_TOKEN, admin_headers, auth_client, issue_token

_POINT = {"lat": 17.385, "lng": 78.486}
_FETCH_BODY = {**_POINT, "fields": ["elevation"]}


def _bearer(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def test_metadata_and_health_stay_public() -> None:
    with auth_client() as (client, _, _):
        assert client.get("/api/v1/meta/fields").status_code == 200
        assert client.get("/api/v1/meta/layers").status_code == 200
        assert client.get("/api/v1/health").status_code == 200


def test_fetch_requires_token() -> None:
    with auth_client() as (client, _, _):
        resp = client.post("/api/v1/fetch", json=_FETCH_BODY)
        assert resp.status_code == 401
        assert resp.json()["error"]["code"] == "AUTHENTICATION_ERROR"
        # RFC 9728: 401 advertises where to discover the authorization server.
        assert "resource_metadata" in resp.headers.get("WWW-Authenticate", "")


def test_fetch_rejects_invalid_token() -> None:
    with auth_client() as (client, _, _):
        resp = client.post("/api/v1/fetch", json=_FETCH_BODY, headers=_bearer("pe_not_real"))
        assert resp.status_code == 401


def test_fetch_succeeds_with_valid_token() -> None:
    with auth_client() as (client, _, _):
        token = issue_token(client, scopes=["fetch", "ask"])
        resp = client.post("/api/v1/fetch", json=_FETCH_BODY, headers=_bearer(token))
        assert resp.status_code == 200
        assert resp.json()["fields"]["elevation"]["value"] is not None


def test_ask_is_public_without_token() -> None:
    # /ask is the free demo surface: it answers even with auth_enabled and no token.
    with auth_client() as (client, _, _):
        resp = client.post("/api/v1/ask", json={**_POINT, "question": "What is the elevation?"})
        assert resp.status_code == 200
        assert resp.json()["answer"].strip()


def test_ask_succeeds_with_valid_token() -> None:
    with auth_client() as (client, _, _):
        token = issue_token(client, scopes=["fetch", "ask"])
        resp = client.post(
            "/api/v1/ask",
            json={**_POINT, "question": "What is the elevation?"},
            headers=_bearer(token),
        )
        assert resp.status_code == 200
        assert resp.json()["answer"].strip()


def test_scope_mismatch_is_forbidden() -> None:
    with auth_client() as (client, _, _):
        ask_only = issue_token(client, scopes=["ask"])  # missing "fetch"
        resp = client.post("/api/v1/fetch", json=_FETCH_BODY, headers=_bearer(ask_only))
        assert resp.status_code == 403
        assert resp.json()["error"]["code"] == "AUTHORIZATION_ERROR"


def test_revoked_token_is_rejected() -> None:
    with auth_client() as (client, _, _):
        create = client.post(
            "/api/v1/auth/tokens",
            json={"name": "temp", "scopes": ["fetch"]},
            headers=admin_headers(),
        )
        token = create.json()["token"]
        token_id = create.json()["id"]
        assert (
            client.post("/api/v1/fetch", json=_FETCH_BODY, headers=_bearer(token)).status_code
            == 200
        )

        assert (
            client.delete(f"/api/v1/auth/tokens/{token_id}", headers=admin_headers()).status_code
            == 204
        )
        assert (
            client.post("/api/v1/fetch", json=_FETCH_BODY, headers=_bearer(token)).status_code
            == 401
        )


def test_rate_limit_returns_429_with_retry_after() -> None:
    with auth_client(default_rate_limit=1000) as (client, _, _):
        token = issue_token(client, scopes=["fetch"], rate_limit_per_minute=3)
        codes = [
            client.post("/api/v1/fetch", json=_FETCH_BODY, headers=_bearer(token)).status_code
            for _ in range(4)
        ]
        assert codes[:3] == [200, 200, 200]
        assert codes[3] == 429
        last = client.post("/api/v1/fetch", json=_FETCH_BODY, headers=_bearer(token))
        assert last.status_code == 429
        assert last.headers.get("Retry-After")
        assert last.json()["error"]["code"] == "RATE_LIMIT_EXCEEDED"


def test_token_management_requires_admin() -> None:
    with auth_client() as (client, _, _):
        # No admin credential.
        assert client.post("/api/v1/auth/tokens", json={"name": "x"}).status_code == 401
        # Wrong admin credential.
        bad = client.post("/api/v1/auth/tokens", json={"name": "x"}, headers=_bearer("nope"))
        assert bad.status_code == 401
        # Correct admin credential.
        ok = client.post("/api/v1/auth/tokens", json={"name": "x"}, headers=admin_headers())
        assert ok.status_code == 201


def test_list_tokens_never_leaks_secret() -> None:
    with auth_client() as (client, _, _):
        issue_token(client, scopes=["fetch"])
        listing = client.get("/api/v1/auth/tokens", headers=admin_headers())
        assert listing.status_code == 200
        body = listing.json()
        assert body["count"] >= 1
        for token in body["tokens"]:
            assert "token" not in token  # only prefix is exposed
            assert token["prefix"].startswith("pe_")


def test_token_management_not_configured_returns_503() -> None:
    with auth_client(admin_token=None) as (client, _, _):
        resp = client.post("/api/v1/auth/tokens", json={"name": "x"}, headers=admin_headers())
        assert resp.status_code == 503
        assert resp.json()["error"]["code"] == "NOT_CONFIGURED"


def test_admin_token_constant_is_used() -> None:
    # Guards against accidental drift between helper and app default.
    assert ADMIN_TOKEN == "admin-secret"
