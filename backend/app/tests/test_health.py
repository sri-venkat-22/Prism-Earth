"""Tests for health/readiness/liveness and the standard error envelope.

These tests patch the dependency ``ping`` functions so they run without a live
Postgres or Redis, while still exercising the real endpoint logic.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

import app.api.v1.health as health_module


async def _ok() -> bool:
    return True


async def _down() -> bool:
    return False


def _patch_pings(monkeypatch: pytest.MonkeyPatch, *, db: bool, redis: bool) -> None:
    monkeypatch.setattr(health_module, "ping_database", _ok if db else _down)
    monkeypatch.setattr(health_module, "ping_redis", _ok if redis else _down)


def test_live_returns_200(client: TestClient) -> None:
    resp = client.get("/api/v1/live")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "alive"
    assert body["timestamp"]


def test_health_returns_200_even_when_dependencies_down(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    _patch_pings(monkeypatch, db=False, redis=False)
    resp = client.get("/api/v1/health")
    assert resp.status_code == 200  # DoD: /api/v1/health returns 200
    body = resp.json()
    assert body["status"] == "ok"
    assert body["service"]
    assert body["components"]["database"]["status"] == "down"
    assert body["components"]["redis"]["status"] == "down"
    assert body["components"]["earth_engine"]["status"] == "not_configured"
    # Phase 4: every domain layer now has a registered connector (SRS §18.10).
    assert body["components"]["connectors"]["status"] == "ok"


def test_health_reports_ok_when_dependencies_up(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    _patch_pings(monkeypatch, db=True, redis=True)
    resp = client.get("/api/v1/health")
    assert resp.status_code == 200
    components = resp.json()["components"]
    assert components["database"]["status"] == "ok"
    assert components["redis"]["status"] == "ok"


def test_ready_returns_200_when_dependencies_up(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    _patch_pings(monkeypatch, db=True, redis=True)
    resp = client.get("/api/v1/ready")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ready"


def test_ready_returns_503_when_database_down(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    _patch_pings(monkeypatch, db=False, redis=True)
    resp = client.get("/api/v1/ready")
    assert resp.status_code == 503
    body = resp.json()
    assert body["status"] == "not_ready"
    assert body["checks"]["database"]["status"] == "down"
    assert body["checks"]["redis"]["status"] == "ok"


def test_connectors_health_lists_every_connector(client: TestClient) -> None:
    resp = client.get("/api/v1/health/connectors")
    assert resp.status_code == 200
    body = resp.json()
    # All nine domain-layer connectors are reported (SRS §18.10, §18.12).
    assert body["count"] == 9
    names = {c["name"] for c in body["connectors"]}
    assert {
        "terrain_connector",
        "climate_connector",
        "land_cover_connector",
        "natural_hazard_connector",
        "infrastructure_connector",
        "utilities_connector",
        "administrative_connector",
        "cadastral_connector",
        "built_environment_connector",
    } == names
    for connector in body["connectors"]:
        assert connector["status"] == "ok"
        assert connector["layer"]
        assert connector["servable_fields"] >= 0


def test_root_banner(client: TestClient) -> None:
    resp = client.get("/")
    assert resp.status_code == 200
    assert resp.json()["service"]


def test_unknown_route_returns_standard_error_envelope(client: TestClient) -> None:
    resp = client.get("/api/v1/this-route-does-not-exist")
    assert resp.status_code == 404
    body = resp.json()
    # SRS §28.2 / §13.17 shape
    assert set(body["error"].keys()) == {
        "code",
        "message",
        "details",
        "correlation_id",
        "timestamp",
    }
    assert body["error"]["code"] == "HTTP_404"
    assert body["error"]["correlation_id"]
    assert resp.headers.get("X-Correlation-ID")


def test_openapi_schema_available(client: TestClient) -> None:
    resp = client.get("/api/v1/openapi.json")
    assert resp.status_code == 200
    assert resp.json()["info"]["title"]
