"""Gateway protections on the data endpoints (SRS §13.19, §29.1).

Exercises the per-IP rate limiter and the request-body size guard end-to-end on
the real ``POST /api/v1/fetch`` route, using the shared fetch fakes so no DB,
Redis, GEE, or LLM is involved. Each test builds its own app (via ``create_app``)
so its ephemeral rate-limit counters are isolated.
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager

from fastapi.testclient import TestClient

from app.api.v1.fetch import get_fetch_orchestrator
from app.core.config import Settings
from app.main import create_app
from app.tests._fetch_fakes import FakeTerrainSource, build_orchestrator, make_context

_POINT = {"lat": 17.385, "lng": 78.486, "fields": ["elevation"]}


@contextmanager
def _gateway_client(
    *,
    rate_limit_enabled: bool = True,
    rate_limit_per_minute: int = 1000,
    max_request_body_bytes: int = 1_048_576,
    trust_proxy_headers: bool = False,
) -> Iterator[TestClient]:
    settings = Settings(
        rate_limit_enabled=rate_limit_enabled,
        rate_limit_per_minute=rate_limit_per_minute,
        max_request_body_bytes=max_request_body_bytes,
        trust_proxy_headers=trust_proxy_headers,
    )
    app = create_app(settings)
    orchestrator = build_orchestrator(
        context=make_context(state="Telangana", district="Hyderabad"),
        terrain_source=FakeTerrainSource(elevation=542.16, slope=3.4),
    )
    app.dependency_overrides[get_fetch_orchestrator] = lambda: orchestrator
    with TestClient(app) as client:
        yield client


def test_fetch_advertises_ratelimit_headers() -> None:
    with _gateway_client(rate_limit_per_minute=5) as client:
        resp = client.post("/api/v1/fetch", json=_POINT)
        assert resp.status_code == 200
        assert resp.headers["RateLimit-Limit"] == "5"
        assert resp.headers["RateLimit-Remaining"] == "4"
        assert int(resp.headers["RateLimit-Reset"]) >= 1


def test_fetch_rate_limited_after_budget() -> None:
    with _gateway_client(rate_limit_per_minute=3) as client:
        for _ in range(3):
            assert client.post("/api/v1/fetch", json=_POINT).status_code == 200
        resp = client.post("/api/v1/fetch", json=_POINT)
        assert resp.status_code == 429
        body = resp.json()
        assert body["error"]["code"] == "RATE_LIMIT_EXCEEDED"
        assert body["error"]["correlation_id"]
        assert int(resp.headers["Retry-After"]) >= 1


def test_rate_limit_disabled_never_throttles() -> None:
    with _gateway_client(rate_limit_enabled=False, rate_limit_per_minute=1) as client:
        for _ in range(4):
            resp = client.post("/api/v1/fetch", json=_POINT)
            assert resp.status_code == 200
        # No RateLimit headers are advertised when limiting is off.
        assert "RateLimit-Limit" not in resp.headers


def test_body_too_large_rejected() -> None:
    with _gateway_client(max_request_body_bytes=10) as client:
        resp = client.post("/api/v1/fetch", json=_POINT)
        assert resp.status_code == 413
        assert resp.json()["error"]["code"] == "PAYLOAD_TOO_LARGE"


def test_spoofed_forwarded_ip_cannot_bypass_limiter() -> None:
    # Default (no trusted proxy): X-Forwarded-For is client-controlled, so it is
    # ignored. Rotating it cannot mint fresh budgets or reset the counter — the
    # limiter keys on the real socket peer (SRS §13.19, 9-D fix).
    with _gateway_client(rate_limit_per_minute=1) as client:
        first = client.post("/api/v1/fetch", json=_POINT, headers={"X-Forwarded-For": "1.1.1.1"})
        assert first.status_code == 200
        # A different (spoofed) forwarded IP does not escape the same budget.
        spoofed = client.post("/api/v1/fetch", json=_POINT, headers={"X-Forwarded-For": "9.9.9.9"})
        assert spoofed.status_code == 429


def test_trusted_proxy_keys_by_real_ip() -> None:
    # Behind a trusted proxy, the Nginx-set X-Real-IP is authoritative: distinct
    # real clients get independent budgets, and a spoofed X-Forwarded-For with an
    # unchanged X-Real-IP cannot rotate the key (SRS §13.19, §33.1).
    with _gateway_client(rate_limit_per_minute=1, trust_proxy_headers=True) as client:
        a = client.post("/api/v1/fetch", json=_POINT, headers={"X-Real-IP": "1.1.1.1"})
        b = client.post("/api/v1/fetch", json=_POINT, headers={"X-Real-IP": "2.2.2.2"})
        assert a.status_code == 200
        assert b.status_code == 200
        # Same real IP, spoofed forwarded chain — still the same key, over budget.
        again = client.post(
            "/api/v1/fetch",
            json=_POINT,
            headers={"X-Real-IP": "1.1.1.1", "X-Forwarded-For": "3.3.3.3"},
        )
        assert again.status_code == 429
