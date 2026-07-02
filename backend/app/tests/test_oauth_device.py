"""Device-flow and OAuth 2.0 tests (SRS §13.20, §34).

Exercises the two agent-facing credential flows end to end — device flow
(RFC 8628) and OAuth authorization-code + PKCE / refresh / client-credentials —
plus the discovery documents, all producing tokens accepted by ``/fetch``.
"""

from __future__ import annotations

import base64
import hashlib
import secrets
from urllib.parse import parse_qs, urlparse

from fastapi.testclient import TestClient

from app.tests._auth_app import admin_headers, auth_client

_POINT = {"lat": 17.385, "lng": 78.486}
_FETCH_BODY = {**_POINT, "fields": ["elevation"]}


def _bearer(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _pkce_pair() -> tuple[str, str]:
    verifier = secrets.token_urlsafe(48)
    challenge = (
        base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b"=").decode()
    )
    return verifier, challenge


# --------------------------------------------------------------------------- #
# Discovery                                                                    #
# --------------------------------------------------------------------------- #
def test_discovery_documents_resolve() -> None:
    with auth_client() as (client, _, _):
        as_meta = client.get("/.well-known/oauth-authorization-server")
        assert as_meta.status_code == 200
        body = as_meta.json()
        assert body["authorization_endpoint"].endswith("/api/v1/auth/oauth/authorize")
        assert body["token_endpoint"].endswith("/api/v1/auth/oauth/token")
        assert "S256" in body["code_challenge_methods_supported"]

        pr_meta = client.get("/.well-known/oauth-protected-resource")
        assert pr_meta.status_code == 200
        assert pr_meta.json()["authorization_servers"]


# --------------------------------------------------------------------------- #
# Device flow (RFC 8628)                                                       #
# --------------------------------------------------------------------------- #
def test_device_flow_end_to_end() -> None:
    with auth_client() as (client, _, _):
        start = client.post("/api/v1/auth/device/code", json={"scopes": ["fetch"]})
        assert start.status_code == 200
        device = start.json()
        assert device["user_code"] and device["device_code"]

        # Polling before approval → authorization_pending.
        pending = client.post(
            "/api/v1/auth/oauth/token",
            data={
                "grant_type": "urn:ietf:params:oauth:grant-type:device_code",
                "device_code": device["device_code"],
            },
        )
        assert pending.status_code == 400
        assert pending.json()["error"] == "authorization_pending"

        # Operator approves (admin-gated).
        approved = client.post(
            "/api/v1/auth/device/approve",
            json={"user_code": device["user_code"]},
            headers=admin_headers(),
        )
        assert approved.status_code == 200 and approved.json()["approved"] is True

        # Polling now yields a token that authorizes /fetch.
        granted = client.post(
            "/api/v1/auth/oauth/token",
            data={
                "grant_type": "urn:ietf:params:oauth:grant-type:device_code",
                "device_code": device["device_code"],
            },
        )
        assert granted.status_code == 200
        access = granted.json()["access_token"]
        assert (
            client.post("/api/v1/fetch", json=_FETCH_BODY, headers=_bearer(access)).status_code
            == 200
        )

        # The device code is single-use.
        replay = client.post(
            "/api/v1/auth/oauth/token",
            data={
                "grant_type": "urn:ietf:params:oauth:grant-type:device_code",
                "device_code": device["device_code"],
            },
        )
        assert replay.status_code == 400


# --------------------------------------------------------------------------- #
# OAuth authorization-code + PKCE                                             #
# --------------------------------------------------------------------------- #
def _register_public_client(client: TestClient, redirect_uri: str) -> str:
    resp = client.post(
        "/api/v1/auth/oauth/register",
        json={
            "client_name": "test-mcp",
            "redirect_uris": [redirect_uri],
            "grant_types": ["authorization_code", "refresh_token"],
            "scope": "fetch ask",
            "token_endpoint_auth_method": "none",
        },
    )
    assert resp.status_code == 201, resp.text
    assert resp.json()["client_secret"] is None  # public client
    return resp.json()["client_id"]


def _authorize(client: TestClient, client_id: str, redirect_uri: str, challenge: str) -> str:
    resp = client.get(
        "/api/v1/auth/oauth/authorize",
        params={
            "response_type": "code",
            "client_id": client_id,
            "redirect_uri": redirect_uri,
            "scope": "fetch ask",
            "state": "xyz",
            "code_challenge": challenge,
            "code_challenge_method": "S256",
        },
        follow_redirects=False,
    )
    assert resp.status_code == 302
    query = parse_qs(urlparse(resp.headers["location"]).query)
    assert query["state"] == ["xyz"]
    return query["code"][0]


def test_oauth_authorization_code_pkce_end_to_end() -> None:
    redirect_uri = "http://localhost/callback"
    verifier, challenge = _pkce_pair()
    with auth_client() as (client, _, _):
        client_id = _register_public_client(client, redirect_uri)
        code = _authorize(client, client_id, redirect_uri, challenge)

        token_resp = client.post(
            "/api/v1/auth/oauth/token",
            data={
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": redirect_uri,
                "client_id": client_id,
                "code_verifier": verifier,
            },
        )
        assert token_resp.status_code == 200, token_resp.text
        body = token_resp.json()
        assert body["token_type"] == "Bearer"
        access, refresh = body["access_token"], body["refresh_token"]
        assert (
            client.post("/api/v1/fetch", json=_FETCH_BODY, headers=_bearer(access)).status_code
            == 200
        )

        # Refresh yields a fresh, working access token.
        refreshed = client.post(
            "/api/v1/auth/oauth/token",
            data={
                "grant_type": "refresh_token",
                "refresh_token": refresh,
                "client_id": client_id,
            },
        )
        assert refreshed.status_code == 200
        new_access = refreshed.json()["access_token"]
        assert new_access != access
        assert (
            client.post("/api/v1/fetch", json=_FETCH_BODY, headers=_bearer(new_access)).status_code
            == 200
        )


def test_oauth_rejects_bad_pkce_verifier() -> None:
    redirect_uri = "http://localhost/callback"
    _, challenge = _pkce_pair()
    with auth_client() as (client, _, _):
        client_id = _register_public_client(client, redirect_uri)
        code = _authorize(client, client_id, redirect_uri, challenge)
        resp = client.post(
            "/api/v1/auth/oauth/token",
            data={
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": redirect_uri,
                "client_id": client_id,
                "code_verifier": "the-wrong-verifier",
            },
        )
        assert resp.status_code == 400
        assert resp.json()["error"] == "invalid_grant"


def test_oauth_client_credentials_grant() -> None:
    with auth_client() as (client, _, _):
        reg = client.post(
            "/api/v1/auth/oauth/register",
            json={
                "client_name": "svc",
                "grant_types": ["client_credentials"],
                "scope": "fetch",
                "token_endpoint_auth_method": "client_secret_post",
            },
        )
        assert reg.status_code == 201
        client_id = reg.json()["client_id"]
        client_secret = reg.json()["client_secret"]
        assert client_secret  # confidential client

        token_resp = client.post(
            "/api/v1/auth/oauth/token",
            data={
                "grant_type": "client_credentials",
                "client_id": client_id,
                "client_secret": client_secret,
                "scope": "fetch",
            },
        )
        assert token_resp.status_code == 200
        access = token_resp.json()["access_token"]
        assert (
            client.post("/api/v1/fetch", json=_FETCH_BODY, headers=_bearer(access)).status_code
            == 200
        )

        # Wrong secret is rejected.
        bad = client.post(
            "/api/v1/auth/oauth/token",
            data={
                "grant_type": "client_credentials",
                "client_id": client_id,
                "client_secret": "wrong",
            },
        )
        assert bad.status_code == 401
        assert bad.json()["error"] == "invalid_client"
