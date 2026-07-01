"""Metadata APIs (SRS §13.5–13.8) and Regional Availability (SRS §13.23, §21).

These read-only endpoints expose the active metadata catalog — the authoritative
registry the Planner, frontend, MCP server, and third-party developers use to
discover supported fields, layers, and presets — plus the State Registry.

- ``GET /api/v1/meta/fields``          — the field catalog (SRS §13.6)
- ``GET /api/v1/meta/layers``          — the domain layers (SRS §13.7)
- ``GET /api/v1/meta/presets``         — the presets (SRS §13.8)
- ``GET /api/v1/meta/states``          — registered regions (SRS §21)
- ``GET /api/v1/meta/states/{name}``   — resolve a region's availability (§13.23)
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Query

from app.metadata.catalog import Catalog, get_catalog
from app.metadata.enums import Layer, Lifecycle
from app.metadata.state_registry import StateRegistry, get_state_registry
from app.schemas.metadata import (
    FieldsResponse,
    LayersResponse,
    PresetsResponse,
    RegionResolutionResponse,
    StatesResponse,
    field_object,
    layer_object,
    preset_object,
    region_resolution_response,
    state_object,
)

router = APIRouter(prefix="/meta", tags=["metadata"])


def _catalog() -> Catalog:
    return get_catalog()


def _registry() -> StateRegistry:
    return get_state_registry()


@router.get("/fields", response_model=FieldsResponse, summary="Field catalog (SRS §13.6)")
async def list_fields(
    layer: Annotated[Layer | None, Query(description="Filter by domain layer")] = None,
    lifecycle: Annotated[Lifecycle | None, Query(description="Filter by lifecycle state")] = None,
    available: Annotated[
        bool | None,
        Query(description="Filter by availability (excludes planned fields when true)"),
    ] = None,
) -> FieldsResponse:
    """Return the active metadata catalog with lifecycle/availability flags."""
    catalog = _catalog()
    fields = catalog.fields()
    if layer is not None:
        fields = [f for f in fields if f.layer is layer]
    if lifecycle is not None:
        fields = [f for f in fields if f.lifecycle is lifecycle]
    if available is not None:
        fields = [f for f in fields if f.available is available]

    objects = [field_object(f, catalog) for f in fields]
    return FieldsResponse(count=len(objects), fields=objects)


@router.get("/layers", response_model=LayersResponse, summary="Domain layers (SRS §13.7)")
async def list_layers() -> LayersResponse:
    """Return the supported logical layers."""
    catalog = _catalog()
    objects = [layer_object(layer, catalog) for layer in catalog.layers()]
    return LayersResponse(count=len(objects), layers=objects)


@router.get("/presets", response_model=PresetsResponse, summary="Presets (SRS §13.8)")
async def list_presets() -> PresetsResponse:
    """Return the predefined presets, each expanding to valid catalog fields."""
    catalog = _catalog()
    registry = _registry()
    objects = [preset_object(p, catalog, registry) for p in catalog.presets()]
    return PresetsResponse(count=len(objects), presets=objects)


@router.get("/states", response_model=StatesResponse, summary="Registered regions (SRS §21)")
async def list_states() -> StatesResponse:
    """Return every region registered in the State Registry."""
    objects = [state_object(s) for s in _registry().states()]
    return StatesResponse(count=len(objects), states=objects)


@router.get(
    "/states/{name}",
    response_model=RegionResolutionResponse,
    summary="Resolve a region's availability (SRS §13.23)",
)
async def resolve_state(name: str) -> RegionResolutionResponse:
    """Resolve a region by name/code/slug.

    Always ``200``: a registered region returns ``supported: true`` with its
    details; an unregistered one is cleanly reported as ``supported: false``
    (SRS §13.23 Regional Availability), never an opaque error.
    """
    return region_resolution_response(_registry().resolve_region(name))
