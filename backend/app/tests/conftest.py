"""Pytest fixtures for the backend test suite."""

from __future__ import annotations

import os

# Disable the request-log DB writer for the ENTIRE test session before any app
# is built. The autouse fixture below only nulls the module-level ``app``; tests
# that mint their own app via ``create_app`` (test_gateway, test_oauth_device, …)
# would otherwise install a live writer and commit audit rows to the real Neon
# DB (backend/.env points at production). Set at the env layer so create_app sees
# request_log_enabled=False everywhere. Recorder-based tests install their own.
os.environ.setdefault("TERRA_REQUEST_LOG_ENABLED", "0")

from collections.abc import Iterator  # noqa: E402

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.auth.stores import InMemoryEphemeralStore  # noqa: E402
from app.main import app  # noqa: E402


@pytest.fixture(autouse=True)
def _isolate_ephemeral_state() -> Iterator[None]:
    """Give each test a fresh ephemeral store and no request-log writer.

    The store holds the gateway/per-token rate-limit counters (SRS §13.19). The
    test suite reuses a single module-level ``app``, so without this reset those
    fixed-window counters would accumulate across tests and could trip the limit.
    The request-log writer is nulled so API tests never open real database
    sessions; tests that assert audit rows install their own recorder.
    """
    app.state.ephemeral_store = InMemoryEphemeralStore()
    app.state.request_log_writer = None
    yield


@pytest.fixture()
def client() -> Iterator[TestClient]:
    """A TestClient that runs the app lifespan (startup/shutdown)."""
    with TestClient(app) as test_client:
        yield test_client
