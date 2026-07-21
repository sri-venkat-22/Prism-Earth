"""Request-log middleware tests (SRS §22.3) — audit rows for /ask & /fetch.

Uses a recorder writer on ``app.state`` (the conftest nulls the real one), so
no database is required; the middleware's row assembly and scoping are proven.
"""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.api.v1.fetch import get_fetch_orchestrator
from app.main import app
from app.tests._fetch_fakes import FakeTerrainSource, build_orchestrator, make_context

_POINT = {"lat": 17.385, "lng": 78.486}


class _RecorderWriter:
    def __init__(self) -> None:
        self.rows: list[dict[str, Any]] = []

    async def persist(self, **row: Any) -> None:
        self.rows.append(row)


@pytest.fixture()
def recording_client() -> Iterator[tuple[TestClient, _RecorderWriter]]:
    orch = build_orchestrator(
        context=make_context(state="Telangana", district="Hyderabad"),
        terrain_source=FakeTerrainSource(elevation=542.16, slope=3.4),
    )
    app.dependency_overrides[get_fetch_orchestrator] = lambda: orch
    recorder = _RecorderWriter()
    try:
        with TestClient(app) as client:
            app.state.request_log_writer = recorder
            yield client, recorder
    finally:
        app.dependency_overrides.pop(get_fetch_orchestrator, None)


def test_fetch_request_is_audited(recording_client: tuple[TestClient, _RecorderWriter]) -> None:
    client, recorder = recording_client
    response = client.post("/api/v1/fetch", json={**_POINT, "fields": ["elevation", "slope"]})
    assert response.status_code == 200

    (row,) = recorder.rows
    assert row["path"] == "/api/v1/fetch"
    assert row["method"] == "POST"
    assert row["status_code"] == 200
    assert row["lat"] == _POINT["lat"]
    assert row["lng"] == _POINT["lng"]
    assert row["field_count"] == 2
    assert row["cache_hit"] is None
    assert row["duration_ms"] > 0
    assert row["correlation_id"] == response.headers["X-Correlation-ID"]


def test_failed_request_is_audited_without_handler_facts(
    recording_client: tuple[TestClient, _RecorderWriter],
) -> None:
    """A 422 rejected before/inside the handler still leaves an audit row."""
    client, recorder = recording_client
    response = client.post("/api/v1/fetch", json={**_POINT, "fields": ["no_such_field"]})
    assert response.status_code == 422

    (row,) = recorder.rows
    assert row["status_code"] == 422
    assert row["lat"] is None
    assert row["field_count"] is None


def test_unaudited_paths_write_nothing(
    recording_client: tuple[TestClient, _RecorderWriter],
) -> None:
    client, recorder = recording_client
    assert client.get("/api/v1/health").status_code == 200
    assert recorder.rows == []
