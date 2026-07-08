"""Production configuration guardrails (SRS §29, §13.20).

``Settings.validate_runtime`` is the single source of truth for "is this config
safe to expose?". It is enforced twice: the app refuses to boot on a fatal
problem (fail-fast in the lifespan) and the readiness probe reports the same
problems as defense in depth. These tests pin both the rules and the wiring.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

import app.api.v1.health as health_module
from app.core.config import Settings
from app.main import create_app


def _valid_prod(**overrides: object) -> Settings:
    base: dict[str, object] = {
        "app_env": "production",
        "auth_enabled": True,
        "auth_admin_token": "bootstrap",  # noqa: S106 - test-only bootstrap credential
        "cors_origins": [],
    }
    base.update(overrides)
    return Settings(**base)


# --------------------------------------------------------------------------- #
# validate_runtime rules                                                      #
# --------------------------------------------------------------------------- #
def test_dev_defaults_are_valid() -> None:
    assert Settings().validate_runtime() == []


def test_valid_production_has_no_problems() -> None:
    assert _valid_prod().validate_runtime() == []


def test_production_requires_auth_enabled() -> None:
    problems = Settings(app_env="production", auth_enabled=False).validate_runtime()
    assert any("PRISM_AUTH_ENABLED" in p for p in problems)


def test_production_requires_admin_token_when_auth_on() -> None:
    problems = _valid_prod(auth_admin_token=None).validate_runtime()
    assert any("PRISM_AUTH_ADMIN_TOKEN" in p for p in problems)


def test_production_rejects_wildcard_cors() -> None:
    problems = _valid_prod(cors_origins=["*"]).validate_runtime()
    assert any("CORS" in p and "'*'" in p for p in problems)


def test_wildcard_with_credentials_invalid_in_any_env() -> None:
    # Dev environment, but the pairing is rejected everywhere (browsers reject it).
    problems = Settings(cors_origins=["*"], cors_allow_credentials=True).validate_runtime()
    assert any("allow_credentials" in p for p in problems)


# --------------------------------------------------------------------------- #
# Fail-fast startup + readiness wiring                                         #
# --------------------------------------------------------------------------- #
def test_misconfigured_production_refuses_to_start() -> None:
    app = create_app(Settings(app_env="production", auth_enabled=False))
    with pytest.raises(RuntimeError, match="Refusing to start"), TestClient(app):
        pass


def test_valid_production_boots() -> None:
    # The happy path must still start cleanly (regression guard for the check).
    with TestClient(create_app(_valid_prod())) as client:
        assert client.get("/api/v1/live").status_code == 200


def test_ready_reports_misconfiguration(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    async def _ok() -> bool:
        return True

    monkeypatch.setattr(health_module, "ping_database", _ok)
    monkeypatch.setattr(health_module, "ping_redis", _ok)
    # Force the readiness handler to evaluate an unsafe config (the startup guard
    # would normally prevent such a process from ever serving).
    monkeypatch.setattr(
        health_module, "get_settings", lambda: Settings(app_env="production", auth_enabled=False)
    )
    resp = client.get("/api/v1/ready")
    assert resp.status_code == 503
    body = resp.json()
    assert body["status"] == "not_ready"
    assert body["checks"]["config"]["status"] == "misconfigured"
    assert "PRISM_AUTH_ENABLED" in body["checks"]["config"]["detail"]
