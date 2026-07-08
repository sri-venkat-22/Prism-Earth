"""Security-headers middleware (SRS §29.3, §13.22)."""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.core.config import Settings
from app.main import create_app


def test_api_response_carries_hardening_headers(client: TestClient) -> None:
    resp = client.get("/api/v1/live")
    assert resp.headers["X-Content-Type-Options"] == "nosniff"
    assert resp.headers["X-Frame-Options"] == "DENY"
    assert resp.headers["Referrer-Policy"] == "no-referrer"
    assert resp.headers["Cross-Origin-Opener-Policy"] == "same-origin"
    assert "geolocation=()" in resp.headers["Permissions-Policy"]


def test_api_response_uses_strict_csp(client: TestClient) -> None:
    resp = client.get("/api/v1/live")
    csp = resp.headers["Content-Security-Policy"]
    assert "default-src 'none'" in csp
    assert "frame-ancestors 'none'" in csp


def test_docs_pages_use_relaxed_csp(client: TestClient) -> None:
    resp = client.get("/docs")
    assert resp.status_code == 200
    csp = resp.headers["Content-Security-Policy"]
    # Swagger UI needs its CDN + inline bootstrap script (SRS §13.22).
    assert "https://cdn.jsdelivr.net" in csp
    assert "'unsafe-inline'" in csp


def test_hsts_emitted_only_in_production() -> None:
    dev = create_app(Settings(app_env="development"))
    with TestClient(dev) as client:
        assert "Strict-Transport-Security" not in client.get("/api/v1/live").headers

    # A production app must pass runtime validation to boot (SRS §29, §13.20):
    # auth on with a bootstrap admin token and a non-wildcard CORS allow-list.
    prod = create_app(
        Settings(
            app_env="production",
            auth_enabled=True,
            auth_admin_token="test-admin",  # noqa: S106 - test-only bootstrap credential
            cors_origins=[],
        )
    )
    with TestClient(prod) as client:
        resp = client.get("/api/v1/live")
        assert "max-age=" in resp.headers["Strict-Transport-Security"]
