"""Response schemas for the Metadata APIs (SRS §13.5–13.8).

These models define the public contract of ``GET /meta/fields``, ``/meta/layers``,
``/meta/presets``, and the State Registry endpoints. They are built from the
internal catalog/registry models so the domain layer and the API surface stay
decoupled.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from app.metadata.catalog import Catalog
from app.metadata.enums import Availability, DataType, Layer, Lifecycle
from app.metadata.models import CatalogField, LayerDefinition, PresetDefinition
from app.metadata.state_registry import RegionResolution, RegisteredState, StateRegistry


# --------------------------------------------------------------------------- #
# Field object — SRS §13.6                                                     #
# --------------------------------------------------------------------------- #
class FieldObject(BaseModel):
    """A single field as returned by ``GET /api/v1/meta/fields`` (SRS §13.6)."""

    id: str
    name: str
    description: str
    layer: Layer
    lifecycle: Lifecycle
    available: bool = Field(..., description="False for planned fields (SRS §11.6)")
    availability: Availability = Field(..., description="Geographic availability (SRS §11.4)")
    nullable: bool
    null_meaning: str | None
    source: str
    source_url: str | None
    unit: str | None
    datatype: DataType
    ttl: str | None = Field(..., description="Dataset cache duration (SRS §11.4)")
    interpretation_hint: str
    connector: str = Field(..., description="Connector that owns the field (SRS §11.5)")
    presets: list[str]


class FieldsResponse(BaseModel):
    """``GET /api/v1/meta/fields`` payload."""

    count: int
    fields: list[FieldObject]


# --------------------------------------------------------------------------- #
# Layer object — SRS §13.7                                                     #
# --------------------------------------------------------------------------- #
class LayerObject(BaseModel):
    """A domain layer as returned by ``GET /api/v1/meta/layers`` (SRS §13.7)."""

    id: Layer
    name: str
    purpose: str
    connector: str
    field_count: int


class LayersResponse(BaseModel):
    """``GET /api/v1/meta/layers`` payload."""

    count: int
    layers: list[LayerObject]


# --------------------------------------------------------------------------- #
# Preset object — SRS §13.8                                                    #
# --------------------------------------------------------------------------- #
class PresetObject(BaseModel):
    """A preset as returned by ``GET /api/v1/meta/presets`` (SRS §13.8)."""

    id: str
    name: str
    description: str
    fields: list[str]
    layers: list[Layer]
    supported_states: list[str]


class PresetsResponse(BaseModel):
    """``GET /api/v1/meta/presets`` payload."""

    count: int
    presets: list[PresetObject]


# --------------------------------------------------------------------------- #
# State Registry — SRS §13.23, §21                                            #
# --------------------------------------------------------------------------- #
class StateObject(BaseModel):
    """A registered region as returned by ``GET /api/v1/meta/states``."""

    slug: str
    code: str
    name: str
    registered: bool
    lifecycle: str
    supported_datasets: list[str]
    enabled_fields: list[str]


class StatesResponse(BaseModel):
    """``GET /api/v1/meta/states`` payload."""

    count: int
    states: list[StateObject]


class RegionResolutionResponse(BaseModel):
    """``GET /api/v1/meta/states/{name}`` payload (SRS §13.23)."""

    query: str
    supported: bool
    state: StateObject | None
    message: str


# --------------------------------------------------------------------------- #
# Builders — map internal models to the API contract                          #
# --------------------------------------------------------------------------- #
def _supported_states(
    preset: PresetDefinition, catalog: Catalog, registry: StateRegistry
) -> list[str]:
    """Compute the states a preset is fully supported in (SRS §13.8).

    A preset built only from nationwide fields is supported everywhere (``["*"]``).
    If it contains region-gated fields, it is supported only in states that
    enable *all* of those fields — derived from the registry, not hardcoded.
    """
    gated = [f for f in preset.fields if catalog.field(f).availability is Availability.REGION_GATED]
    if not gated:
        return ["*"]
    return sorted(state.slug for state in registry.states() if all(state.enables(f) for f in gated))


def field_object(field: CatalogField, catalog: Catalog) -> FieldObject:
    return FieldObject(
        id=field.id,
        name=field.name,
        description=field.description,
        layer=field.layer,
        lifecycle=field.lifecycle,
        available=field.available,
        availability=field.availability,
        nullable=field.nullable,
        null_meaning=field.null_meaning,
        source=field.source,
        source_url=field.source_url,
        unit=field.unit,
        datatype=field.datatype,
        ttl=field.dataset_ttl,
        interpretation_hint=field.interpretation_hint,
        connector=catalog.connector_for_layer(field.layer),
        presets=list(field.presets),
    )


def layer_object(layer: LayerDefinition, catalog: Catalog) -> LayerObject:
    field_count = sum(1 for f in catalog.fields() if f.layer is layer.id)
    return LayerObject(
        id=layer.id,
        name=layer.name,
        purpose=layer.purpose,
        connector=layer.connector,
        field_count=field_count,
    )


def preset_object(
    preset: PresetDefinition, catalog: Catalog, registry: StateRegistry
) -> PresetObject:
    return PresetObject(
        id=preset.id,
        name=preset.name,
        description=preset.description,
        fields=list(preset.fields),
        layers=catalog.preset_layers(preset),
        supported_states=_supported_states(preset, catalog, registry),
    )


def state_object(state: RegisteredState) -> StateObject:
    return StateObject(
        slug=state.slug,
        code=state.code,
        name=state.name,
        registered=state.registered,
        lifecycle=state.lifecycle,
        supported_datasets=list(state.supported_datasets),
        enabled_fields=sorted(state.enabled_fields),
    )


def region_resolution_response(resolution: RegionResolution) -> RegionResolutionResponse:
    return RegionResolutionResponse(
        query=resolution.query,
        supported=resolution.supported,
        state=state_object(resolution.state) if resolution.state else None,
        message=resolution.message,
    )
