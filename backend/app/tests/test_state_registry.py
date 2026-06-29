"""Tests for the State Registry (SRS §11.8, §21, §24, Phase 1 DoD).

Telangana resolves as registered; an unregistered state is cleanly reported as
unsupported. The registry is driven by config, not code.
"""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.metadata.state_registry import (
    BoundingBox,
    RegisteredState,
    StateRegistry,
    build_state_registry,
)


def test_telangana_is_registered() -> None:
    """DoD: the State Registry resolves 'Telangana' as registered."""
    registry = build_state_registry()
    assert registry.is_registered("Telangana")
    state = registry.resolve("Telangana")
    assert state is not None
    assert state.code == "TG"
    assert state.slug == "telangana"


def test_telangana_resolvable_by_slug_code_and_name() -> None:
    registry = build_state_registry()
    for identifier in ("telangana", "TELANGANA", "tg", "Telangana"):
        assert registry.is_registered(identifier), identifier


def test_unregistered_state_cleanly_reported_as_unsupported() -> None:
    """DoD: an unregistered state is cleanly reported as unsupported."""
    registry = build_state_registry()
    resolution = registry.resolve_region("Karnataka")
    assert resolution.supported is False
    assert resolution.state is None
    assert "Karnataka" in resolution.message
    assert "Telangana" in resolution.message  # surfaces what IS supported


def test_telangana_only_registered_region() -> None:
    """SRS §24: Telangana is the only registered region in Version 1."""
    registry = build_state_registry()
    assert registry.slugs() == ["telangana"]


def test_coordinate_resolution_uses_bbox() -> None:
    registry = build_state_registry()
    # Hyderabad lies within Telangana.
    state = registry.state_for_coordinate(17.385, 78.4867)
    assert state is not None and state.slug == "telangana"
    # A point in the Bay of Bengal lies outside any registered region.
    assert registry.state_for_coordinate(15.0, 90.0) is None


def test_dynamic_registration_requires_no_code_change() -> None:
    """SRS §11.8/§21.3: a new state can be registered dynamically."""
    registry = StateRegistry()
    assert not registry.is_registered("Karnataka")
    registry.register(
        RegisteredState(
            slug="karnataka",
            code="KA",
            name="Karnataka",
            bbox=BoundingBox(min_lat=11.5, max_lat=18.5, min_lng=74.0, max_lng=78.6),
            enabled_fields=frozenset({"parcel_id"}),
        )
    )
    assert registry.is_registered("Karnataka")
    assert registry.state_for_coordinate(12.97, 77.59) is not None


def test_meta_states_endpoint_lists_telangana(client: TestClient) -> None:
    resp = client.get("/api/v1/meta/states")
    assert resp.status_code == 200
    body = resp.json()
    assert body["count"] == 1
    assert body["states"][0]["name"] == "Telangana"


def test_resolve_state_endpoint_reports_support(client: TestClient) -> None:
    ok = client.get("/api/v1/meta/states/Telangana")
    assert ok.status_code == 200
    assert ok.json()["supported"] is True

    unsupported = client.get("/api/v1/meta/states/Karnataka")
    assert unsupported.status_code == 200  # cleanly reported, not an error
    body = unsupported.json()
    assert body["supported"] is False
    assert body["state"] is None
