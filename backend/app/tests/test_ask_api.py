"""POST /api/v1/ask tests (SRS §13.13, §13.14) — Phase 5 Definition of Done.

Drives the whole pipeline (Planner → Fetch → Synthesizer) through the HTTP
surface with the pipeline dependency overridden by a fake-LLM-backed pipeline,
so no live model or PostGIS is required. Planning is deterministic and broad:
every selectable catalog field is fetched, and the single LLM call is the
Synthesizer's.
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager

from fastapi.testclient import TestClient

from app.api.v1.ask import get_ask_pipeline
from app.main import app
from app.metadata.catalog import get_catalog
from app.planners import PLANNER_MODEL
from app.tests._ask_fakes import build_fake_pipeline

_POINT = {"lat": 17.385, "lng": 78.486}
_CATALOG = get_catalog()


@contextmanager
def _client(**kwargs) -> Iterator[TestClient]:
    pipeline, _ = build_fake_pipeline(**kwargs)
    app.dependency_overrides[get_ask_pipeline] = lambda: pipeline
    try:
        with TestClient(app) as client:
            yield client
    finally:
        app.dependency_overrides.pop(get_ask_pipeline, None)


def test_ask_returns_cited_answer_and_trace() -> None:
    """DoD: a question returns a cited answer + a populated execution trace."""
    with _client() as client:
        resp = client.post(
            "/api/v1/ask",
            json={**_POINT, "question": "Is this area suitable for solar farm development?"},
        )
    assert resp.status_code == 200
    body = resp.json()

    # A non-empty answer — clean prose, citations ride separately (never inline).
    assert body["answer"].strip()
    assert "[CIT-" not in body["answer"]
    assert body["citations"]

    # CLAUDE.md response shape: metadata is opt-in, as separate top-level fields.
    assert body["confidence"] in {"high", "medium", "low"}
    assert body["fields_used"]
    assert {g["field"] for g in body["data_gaps"]} == set(
        body["trace"]["synthesizer"]["unavailable_fields"]
    )
    for gap in body["data_gaps"]:
        assert gap["reason"]
    requested = set(body["trace"]["fetch"]["requested_fields"])
    # Citations reference ONLY fetched fields (SRS §16.14).
    for citation in body["citations"]:
        assert citation["field_names"]
        for field_name in citation["field_names"]:
            assert field_name in requested

    # A populated execution trace (SRS §13.14).
    trace = body["trace"]
    # Broad fetch: the plan is every selectable catalog field, no LLM involved.
    expected = [f.name for f in _CATALOG.fields() if f.selectable]
    assert trace["planner"]["fields"] == expected
    assert trace["planner"]["model"] == PLANNER_MODEL
    assert trace["planner"]["intent"]
    assert trace["fetch"]["resolved_fields"]
    assert trace["fetch"]["connectors"]
    assert trace["synthesizer"]["model"] == "fake-model"
    assert trace["total_duration_ms"] >= 0

    # Provenance is attached for the fetched fields (SRS §13.13).
    assert set(body["provenance"]) == requested


def test_ask_plan_excludes_planned_field_end_to_end() -> None:
    """DoD: a planned (non-selectable) field can never be fetched via /ask."""
    with _client() as client:
        resp = client.post(
            "/api/v1/ask", json={**_POINT, "question": "elevation and seismic zone?"}
        )
    assert resp.status_code == 200
    trace = resp.json()["trace"]
    assert "seismic_zone" not in trace["planner"]["fields"]
    assert "elevation" in trace["planner"]["fields"]


def test_ask_marks_unavailable_field_in_data_gaps() -> None:
    """DoD: unavailable data is marked, never fabricated (SRS §38.8)."""
    # soil_drainage_class is owned but unwired, so the broad fetch nulls it.
    with _client() as client:
        resp = client.post("/api/v1/ask", json={**_POINT, "question": "Describe the terrain."})
    assert resp.status_code == 200
    body = resp.json()
    assert "soil_drainage_class" in body["trace"]["synthesizer"]["unavailable_fields"]
    assert "soil_drainage_class" in {g["field"] for g in body["data_gaps"]}


def test_ask_is_deterministic_across_identical_requests() -> None:
    """DoD: the same question, run twice, selects the same fields (SRS §14.13)."""
    payload = {**_POINT, "question": "Is this area suitable for solar farm development?"}
    with _client() as client:
        first = client.post("/api/v1/ask", json=payload).json()
        second = client.post("/api/v1/ask", json=payload).json()
    assert first["trace"]["planner"]["fields"] == second["trace"]["planner"]["fields"]


def test_ask_rejects_empty_question() -> None:
    with _client() as client:
        resp = client.post("/api/v1/ask", json={**_POINT, "question": "   "})
    assert resp.status_code == 422


def test_ask_rejects_out_of_range_coordinate() -> None:
    with _client() as client:
        resp = client.post("/api/v1/ask", json={"lat": 999, "lng": 78.486, "question": "hi"})
    assert resp.status_code == 422
