"""POST /api/v1/ask tests (SRS §13.13, §13.14) — Phase 5 Definition of Done.

Drives the whole pipeline (Planner → Fetch → Synthesizer) through the HTTP
surface with the pipeline dependency overridden by a fake-LLM-backed pipeline,
so no live model or PostGIS is required.
"""

from __future__ import annotations

import json
from collections.abc import Iterator
from contextlib import contextmanager

from fastapi.testclient import TestClient

from app.api.v1.ask import get_ask_pipeline
from app.main import app
from app.metadata.catalog import get_catalog
from app.synthesizers import TemplateSynthesizer
from app.tests._ask_fakes import build_fake_pipeline

_POINT = {"lat": 17.385, "lng": 78.486}
_CATALOG = get_catalog()

_SOLAR_PLAN = json.dumps(
    {
        "intent": "Renewable Energy Site Selection",
        "presets": ["solar_siting"],
        "planning_reason": "Solar siting needs terrain orientation, temperature, and grid access.",
    }
)


@contextmanager
def _client_for(planner_json: str, **kwargs) -> Iterator[TestClient]:
    pipeline, _ = build_fake_pipeline(planner_json=planner_json, **kwargs)
    app.dependency_overrides[get_ask_pipeline] = lambda: pipeline
    try:
        with TestClient(app) as client:
            yield client
    finally:
        app.dependency_overrides.pop(get_ask_pipeline, None)


def test_solar_suitability_returns_cited_answer_and_trace() -> None:
    """DoD: the solar-suitability question returns a cited answer + trace."""
    with _client_for(_SOLAR_PLAN) as client:
        resp = client.post(
            "/api/v1/ask",
            json={**_POINT, "question": "Is this area suitable for solar farm development?"},
        )
    assert resp.status_code == 200
    body = resp.json()

    # A non-empty, cited answer.
    assert body["answer"].strip()
    assert body["citations"]
    requested = set(body["trace"]["fetch"]["requested_fields"])
    # Citations reference ONLY fetched fields (SRS §16.14).
    for citation in body["citations"]:
        assert citation["field_names"]
        for field_name in citation["field_names"]:
            assert field_name in requested

    # A populated execution trace (SRS §13.14).
    trace = body["trace"]
    assert set(trace["planner"]["fields"]) == set(_CATALOG.expand_preset("solar_siting"))
    assert trace["planner"]["presets"] == ["solar_siting"]
    assert trace["planner"]["intent"]
    assert trace["planner"]["model"] == "fake-model"
    assert trace["fetch"]["resolved_fields"]
    assert trace["fetch"]["connectors"]
    assert trace["synthesizer"]["model"] == "fake-model"
    assert trace["total_duration_ms"] >= 0

    # Provenance is attached for the fetched fields (SRS §13.13).
    assert set(body["provenance"]) == requested


def test_ask_plan_excludes_planned_field_end_to_end() -> None:
    """DoD: the planner provably cannot select a planned field, even via /ask."""
    proposal = json.dumps({"intent": "Terrain Analysis", "fields": ["elevation", "seismic_zone"]})
    with _client_for(proposal) as client:
        resp = client.post(
            "/api/v1/ask", json={**_POINT, "question": "elevation and seismic zone?"}
        )
    assert resp.status_code == 200
    trace = resp.json()["trace"]
    assert "seismic_zone" not in trace["planner"]["fields"]
    assert trace["planner"]["fields"] == ["elevation"]
    assert any("seismic_zone" in w for w in trace["planner"]["warnings"])


def test_ask_marks_unavailable_field_in_trace() -> None:
    """DoD: unavailable data is marked, never fabricated (SRS §38.8)."""
    # The terrain preset includes soil_drainage_class, which is owned but unwired.
    with _client_for(json.dumps({"intent": "Terrain Analysis", "presets": ["terrain"]})) as client:
        resp = client.post("/api/v1/ask", json={**_POINT, "question": "Describe the terrain."})
    assert resp.status_code == 200
    body = resp.json()
    assert "soil_drainage_class" in body["trace"]["synthesizer"]["unavailable_fields"]
    assert "soil drainage class" in body["answer"].lower()


def test_ask_is_deterministic_across_identical_requests() -> None:
    """DoD: the same plan, run twice, selects the same fields (SRS §14.13)."""
    payload = {**_POINT, "question": "Is this area suitable for solar farm development?"}
    with _client_for(_SOLAR_PLAN) as client:
        first = client.post("/api/v1/ask", json=payload).json()
        second = client.post("/api/v1/ask", json=payload).json()
    assert first["trace"]["planner"]["fields"] == second["trace"]["planner"]["fields"]


def test_ask_rejects_empty_question() -> None:
    with _client_for(_SOLAR_PLAN) as client:
        resp = client.post("/api/v1/ask", json={**_POINT, "question": "   "})
    assert resp.status_code == 422


def test_ask_rejects_out_of_range_coordinate() -> None:
    with _client_for(_SOLAR_PLAN) as client:
        resp = client.post("/api/v1/ask", json={"lat": 999, "lng": 78.486, "question": "hi"})
    assert resp.status_code == 422


def test_ask_unfulfillable_question_returns_200_without_fabrication() -> None:
    """A question no registered field answers is reported, not fabricated (§14.15)."""
    proposal = json.dumps({"intent": "Unknown", "fields": ["no_such_field"]})
    with _client_for(proposal, synthesizer=TemplateSynthesizer()) as client:
        resp = client.post("/api/v1/ask", json={**_POINT, "question": "What is the vibe here?"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["citations"] == []
    assert body["trace"]["planner"]["fields"] == []
    assert "cannot be fulfilled" in body["trace"]["planner"]["planning_reason"].lower()
    assert "no requested data" in body["answer"].lower()
