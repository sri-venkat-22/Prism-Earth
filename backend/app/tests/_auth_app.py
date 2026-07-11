"""Test helper: an auth-enabled app wired with hermetic fakes (SRS §13.20).

Builds a fresh FastAPI app with ``auth_enabled=True`` and overrides the token /
client stores with in-memory instances and the fetch orchestrator / ask pipeline
with the existing fakes — so the whole auth surface is exercised with no DB,
Redis, GEE, or LLM (mirrors the ``get_fetch_orchestrator`` override pattern).
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager

from fastapi.testclient import TestClient

from app.api.v1.ask import get_ask_pipeline
from app.api.v1.fetch import get_fetch_orchestrator
from app.auth.dependencies import get_client_store, get_token_store
from app.auth.tokens import InMemoryClientStore, InMemoryTokenStore
from app.core.config import Settings
from app.main import create_app
from app.tests._ask_fakes import build_fake_pipeline
from app.tests._fetch_fakes import FakeTerrainSource, build_orchestrator, make_context

ADMIN_TOKEN = "admin-secret"


@contextmanager
def auth_client(
    *,
    admin_token: str | None = ADMIN_TOKEN,
    default_rate_limit: int = 1000,
    **settings_overrides: object,
) -> Iterator[tuple[TestClient, InMemoryTokenStore, InMemoryClientStore]]:
    settings = Settings(
        auth_enabled=True,
        auth_admin_token=admin_token,
        auth_default_rate_limit_per_minute=default_rate_limit,
        auth_issuer_url="http://testserver",
        **settings_overrides,  # type: ignore[arg-type]
    )
    app = create_app(settings)

    token_store = InMemoryTokenStore()
    client_store = InMemoryClientStore()
    orchestrator = build_orchestrator(
        context=make_context(state="Telangana", district="Hyderabad"),
        terrain_source=FakeTerrainSource(elevation=542.16, slope=3.4),
    )
    pipeline, _ = build_fake_pipeline()

    app.dependency_overrides[get_token_store] = lambda: token_store
    app.dependency_overrides[get_client_store] = lambda: client_store
    app.dependency_overrides[get_fetch_orchestrator] = lambda: orchestrator
    app.dependency_overrides[get_ask_pipeline] = lambda: pipeline

    with TestClient(app) as client:
        yield client, token_store, client_store


def admin_headers(admin_token: str = ADMIN_TOKEN) -> dict[str, str]:
    return {"Authorization": f"Bearer {admin_token}"}


def issue_token(client: TestClient, **payload: object) -> str:
    """Mint a token via the admin endpoint and return its plaintext secret."""
    body = {"name": "test-token", **payload}
    resp = client.post("/api/v1/auth/tokens", json=body, headers=admin_headers())
    assert resp.status_code == 201, resp.text
    return resp.json()["token"]
