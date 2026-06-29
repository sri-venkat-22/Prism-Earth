"""State Registry & multi-state architecture (SRS §11.8, §21).

The backend hardcodes no region-specific logic (SRS §11.8). Every registered
region is declared in ``configs/states.yaml`` (the manifest) and described by its
own ``configs/<slug>.yaml``. This module loads those files into an in-memory
registry that resolves a state by name/code/slug or by coordinate (bounding box
in Phase 1; precise PostGIS boundaries in Phase 2).

Onboarding a future state requires only adding its config file and listing it in
the manifest — no code changes (SRS §21.3). Dynamic registration via
:meth:`StateRegistry.register` supports tests and runtime onboarding.

Version 1 registers Telangana only (SRS §24).
"""

from __future__ import annotations

from functools import lru_cache
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.config.loader import load_region_config, load_states_manifest
from app.core.logging import get_logger

logger = get_logger(__name__)


class BoundingBox(BaseModel):
    """Approximate WGS84 envelope of a state (SRS §24.1)."""

    model_config = ConfigDict(frozen=True)

    min_lat: float
    max_lat: float
    min_lng: float
    max_lng: float

    def contains(self, lat: float, lng: float) -> bool:
        return self.min_lat <= lat <= self.max_lat and self.min_lng <= lng <= self.max_lng


class RegisteredState(BaseModel):
    """A state registered in the platform (SRS §21.1).

    Holds the state identifier, boundary envelope, supported datasets, and the
    region-gated fields it enables. ``slug`` is the config/file key (e.g.
    ``"telangana"``); ``code`` is the official short code (e.g. ``"TG"``).
    """

    model_config = ConfigDict(frozen=True)

    slug: str = Field(..., description="Config key / lookup slug, e.g. 'telangana'")
    code: str = Field(..., description="Official state code, e.g. 'TG'")
    name: str = Field(..., description="Display name, e.g. 'Telangana'")
    registered: bool = Field(True, description="Whether the state is live (SRS §11.8)")
    lifecycle: str = Field("stable", description="Region lifecycle, e.g. 'stable'")
    bbox: BoundingBox | None = Field(None, description="Approximate boundary envelope")
    supported_datasets: tuple[str, ...] = Field((), description="Datasets integrated (SRS §24.2)")
    enabled_fields: frozenset[str] = Field(
        default_factory=frozenset,
        description="Region-gated fields this state enables (SRS §24.3)",
    )

    def enables(self, field_name: str) -> bool:
        return field_name in self.enabled_fields


class RegionResolution(BaseModel):
    """Outcome of resolving a region query (SRS §13.23 Regional Availability).

    ``supported`` distinguishes a registered region from one that is cleanly
    reported as unsupported, rather than raising an opaque error.
    """

    query: str
    supported: bool
    state: RegisteredState | None = None
    message: str


class StateRegistry:
    """Resolves states by identifier or coordinate. Built from config."""

    def __init__(self, states: list[RegisteredState] | None = None) -> None:
        self._states: dict[str, RegisteredState] = {}
        for state in states or []:
            self.register(state)

    # --- Registration ------------------------------------------------------ #
    def register(self, state: RegisteredState) -> None:
        """Dynamically register (or replace) a state (SRS §11.8)."""
        self._states[state.slug] = state
        logger.info("state_registry.registered", slug=state.slug, code=state.code)

    # --- Lookup ------------------------------------------------------------ #
    def states(self) -> list[RegisteredState]:
        """All registered states."""
        return [s for s in self._states.values() if s.registered]

    def slugs(self) -> list[str]:
        return [s.slug for s in self.states()]

    def resolve(self, identifier: str) -> RegisteredState | None:
        """Resolve a state by slug, code, or display name (case-insensitive)."""
        key = identifier.strip().casefold()
        for state in self.states():
            if key in {state.slug.casefold(), state.code.casefold(), state.name.casefold()}:
                return state
        return None

    def is_registered(self, identifier: str) -> bool:
        return self.resolve(identifier) is not None

    def resolve_region(self, identifier: str) -> RegionResolution:
        """Resolve a region, cleanly reporting unsupported states (SRS §13.23)."""
        state = self.resolve(identifier)
        if state is not None:
            return RegionResolution(
                query=identifier,
                supported=True,
                state=state,
                message=f"{state.name} is a registered region.",
            )
        supported = ", ".join(s.name for s in self.states()) or "none"
        return RegionResolution(
            query=identifier,
            supported=False,
            state=None,
            message=(
                f"'{identifier}' is not a registered region. " f"Version 1 supports: {supported}."
            ),
        )

    def state_for_coordinate(self, lat: float, lng: float) -> RegisteredState | None:
        """Return the registered state whose envelope contains the point, if any."""
        for state in self.states():
            if state.bbox is not None and state.bbox.contains(lat, lng):
                return state
        return None

    def enabled_fields(self, identifier: str) -> frozenset[str]:
        state = self.resolve(identifier)
        return state.enabled_fields if state else frozenset()


def _state_from_config(slug: str, config: dict[str, Any]) -> RegisteredState:
    """Build a :class:`RegisteredState` from a region config (SRS §21.1)."""
    state = config.get("state", {})
    bbox_cfg = config.get("bbox")
    return RegisteredState(
        slug=slug,
        code=str(state.get("code", slug.upper())),
        name=str(state.get("name", slug.title())),
        registered=bool(state.get("registered", True)),
        lifecycle=str(state.get("lifecycle", "stable")),
        bbox=BoundingBox(**bbox_cfg) if bbox_cfg else None,
        supported_datasets=tuple(config.get("supported_datasets", []) or []),
        enabled_fields=frozenset(config.get("region_gated_fields", []) or []),
    )


def build_state_registry() -> StateRegistry:
    """Construct the registry from ``states.yaml`` and each region config."""
    manifest = load_states_manifest()
    registry = StateRegistry()
    for slug in manifest.get("registered_states", []) or []:
        registry.register(_state_from_config(slug, load_region_config(slug)))
    logger.info("state_registry.loaded", states=registry.slugs())
    return registry


@lru_cache(maxsize=1)
def get_state_registry() -> StateRegistry:
    """Return the process-wide State Registry."""
    return build_state_registry()
