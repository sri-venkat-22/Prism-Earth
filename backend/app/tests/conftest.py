"""Pytest fixtures for the backend test suite."""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from app.auth.stores import InMemoryEphemeralStore
from app.main import app


@pytest.fixture(autouse=True)
def _isolate_ephemeral_state() -> Iterator[None]:
    """Give each test a fresh ephemeral store.

    The store holds the gateway/per-token rate-limit counters (SRS §13.19). The
    test suite reuses a single module-level ``app``, so without this reset those
    fixed-window counters would accumulate across tests and could trip the limit.
    """
    app.state.ephemeral_store = InMemoryEphemeralStore()
    yield


@pytest.fixture()
def client() -> Iterator[TestClient]:
    """A TestClient that runs the app lifespan (startup/shutdown)."""
    with TestClient(app) as test_client:
        yield test_client
