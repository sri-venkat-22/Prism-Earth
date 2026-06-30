"""Request/response schemas for ``POST /api/v1/fetch`` (SRS §13.9–13.12, §16, §17).

These models are the public contract of the deterministic Fetch API. They mirror
the SRS object shapes exactly:

- :class:`FetchRequest`     — ``{lat, lng, fields[]}`` or ``{lat, lng, preset}`` (§13.9)
- :class:`FieldObject`      — the standardized Field Object (§13.10, §18.11)
- :class:`ProvenanceObject` — per-field provenance (§13.11, §17.3)
- :class:`Citation`         — a structured, deduplicated citation (§16.7, §16.9)
- :class:`PartialFailure`   — a non-fatal connector failure (§13.12, §15.16)
- :class:`FetchResponse`    — the full response envelope
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.connectors.base import Confidence
from app.metadata.enums import DataType, Layer
from app.schemas.spatial import SpatialContext


# --------------------------------------------------------------------------- #
# Request — SRS §13.9                                                          #
# --------------------------------------------------------------------------- #
class FetchRequest(BaseModel):
    """A deterministic fetch request (SRS §13.9).

    Exactly one of ``fields`` (explicit field names) or ``preset`` (a catalog
    preset expanded server-side, SRS §15.8) must be provided.
    """

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {"lat": 17.385, "lng": 78.486, "fields": ["elevation", "slope", "district_name"]},
                {"lat": 17.385, "lng": 78.486, "preset": "terrain"},
            ]
        }
    )

    lat: float = Field(..., description="Latitude (WGS84)")
    lng: float = Field(..., description="Longitude (WGS84)")
    fields: list[str] | None = Field(None, description="Explicit catalog field names")
    preset: str | None = Field(None, description="A catalog preset id to expand (SRS §11.7)")

    @model_validator(mode="after")
    def _exactly_one_selector(self) -> FetchRequest:
        has_fields = bool(self.fields)
        has_preset = bool(self.preset)
        if has_fields == has_preset:
            raise ValueError("Provide exactly one of 'fields' or 'preset'.")
        if self.fields is not None and any(not f.strip() for f in self.fields):
            raise ValueError("'fields' must not contain empty names.")
        return self


# --------------------------------------------------------------------------- #
# Response elements                                                            #
# --------------------------------------------------------------------------- #
class FieldObject(BaseModel):
    """A standardized returned field (SRS §13.10, §18.11).

    ``value`` is ``None`` when the field could not be resolved; ``null_meaning``
    then explains the absence (SRS §15.17). The provenance for the same field
    (keyed by name) carries the machine-readable reason.
    """

    name: str
    value: Any | None
    unit: str | None
    datatype: DataType
    confidence: Confidence
    dataset: str
    dataset_version: str | None = None
    retrieved_at: str
    ttl: str | None = None
    layer: Layer
    null_meaning: str | None = None


class ProvenanceObject(BaseModel):
    """Per-field provenance (SRS §13.11, §17.3)."""

    field: str
    dataset: str
    dataset_version: str | None = None
    source_url: str | None = None
    retrieved_at: str
    ttl: str | None = None
    confidence: Confidence
    null_meaning: str | None = None
    reason: str | None = Field(None, description="Why the value is null/failed (SRS §17.6)")


class Citation(BaseModel):
    """A structured, deduplicated citation (SRS §16.7, §16.9).

    One citation per dataset, associated with every field it produced
    (SRS §16.11). Generated only for datasets that actually returned a value —
    never fabricated for unavailable data (SRS §16.14).
    """

    citation_id: str = Field(..., description="Stable id within the response, e.g. 'CIT-001'")
    dataset: str
    provider: str | None = None
    source_url: str | None = None
    dataset_version: str | None = None
    retrieved_at: str
    ttl: str | None = None
    license: str | None = None
    field_names: list[str]


class PartialFailure(BaseModel):
    """A non-fatal connector/dataset failure (SRS §13.12, §15.16)."""

    layer: str | None = None
    connector: str | None = None
    dataset: str | None = None
    reason: str
    retryable: bool = False


class FetchLocation(BaseModel):
    """The resolved administrative context for the request (SRS §15.7, §13.23)."""

    lat: float
    lng: float
    in_pilot_region: bool
    state: str | None = None
    district: str | None = None
    taluk: str | None = None
    village: str | None = None
    municipality: str | None = None
    ward: str | None = None

    @classmethod
    def from_context(cls, ctx: SpatialContext) -> FetchLocation:
        def _name(unit: Any | None) -> str | None:
            return unit.name if unit is not None else None

        return cls(
            lat=ctx.lat,
            lng=ctx.lng,
            in_pilot_region=ctx.in_pilot_region,
            state=_name(ctx.state),
            district=_name(ctx.district),
            taluk=_name(ctx.mandal),
            village=_name(ctx.village),
            municipality=_name(ctx.municipality),
            ward=_name(ctx.ward),
        )


class ResponseSummary(BaseModel):
    """Response-level roll-up (SRS §16.12 Response-Level, §17.4)."""

    requested: int
    resolved: int
    null: int
    datasets_used: list[str]


class FetchResponse(BaseModel):
    """The full ``POST /api/v1/fetch`` response (SRS §13.9–13.12)."""

    request_id: str
    timestamp: str
    location: FetchLocation
    fields: dict[str, FieldObject]
    provenance: dict[str, ProvenanceObject]
    citations: list[Citation]
    partial_failures: list[PartialFailure]
    summary: ResponseSummary
