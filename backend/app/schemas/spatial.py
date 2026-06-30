"""Spatial-context schemas (SRS §15.7 State Detection).

The standardized result of resolving a coordinate to its administrative
hierarchy. The Fetch Engine (SRS §15) consumes this to decide region support and
to gate region-specific fields (SRS §24.3).
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class AdminUnit(BaseModel):
    """A single resolved administrative unit."""

    model_config = ConfigDict(frozen=True)

    id: int
    name: str
    code: str | None = None


class SpatialContext(BaseModel):
    """Administrative hierarchy for a coordinate (SRS §15.7).

    ``in_pilot_region`` is the gate for region-specific fields (SRS §24.3): when
    ``False`` the coordinate lies outside every registered region and those
    fields return ``null`` with their configured ``null_meaning``.
    """

    model_config = ConfigDict(frozen=True)

    lat: float = Field(..., description="Query latitude (WGS84)")
    lng: float = Field(..., description="Query longitude (WGS84)")
    in_pilot_region: bool = Field(
        False,
        description="Whether the point falls inside a registered region (SRS §24.3)",
    )
    state: AdminUnit | None = None
    district: AdminUnit | None = None
    mandal: AdminUnit | None = None
    village: AdminUnit | None = None
    municipality: AdminUnit | None = None
    ward: AdminUnit | None = None

    @property
    def resolved(self) -> bool:
        """True when at least the containing state was found."""
        return self.state is not None
