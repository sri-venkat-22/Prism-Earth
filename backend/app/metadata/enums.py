"""Controlled vocabularies for the Metadata Catalog (SRS §11.4–11.6).

These enums are the only place the catalog's categorical values are defined, so
that layers, lifecycle states, availability, and data types stay consistent
across the catalog, the validator, and the Metadata APIs (SRS §13.6–13.8).
"""

from __future__ import annotations

from enum import StrEnum


class Layer(StrEnum):
    """The domain layers (SRS §11.5). Every field belongs to exactly one.

    Version 1 shipped seven layers. ``BUILT_ENVIRONMENT`` (building footprints /
    rooftops) and ``UTILITIES`` (power/grid/telecom, split out of Infrastructure)
    were added to match the commercial siting + underwriting use cases served by
    comparable platforms, bringing the total to nine.
    """

    TERRAIN = "terrain"
    CLIMATE = "climate"
    LAND_COVER = "land_cover"
    NATURAL_HAZARD = "natural_hazard"
    INFRASTRUCTURE = "infrastructure"
    UTILITIES = "utilities"
    ADMINISTRATIVE = "administrative"
    CADASTRAL = "cadastral"
    BUILT_ENVIRONMENT = "built_environment"


class Lifecycle(StrEnum):
    """Field lifecycle (SRS §11.6).

    ``PLANNED`` fields are defined in the catalog but can never be selected by
    the Planner or fetched by the Fetch Engine.
    """

    STABLE = "stable"
    BETA = "beta"
    PLANNED = "planned"


class Availability(StrEnum):
    """Where a field can return a value (SRS §11.4 Availability, §24.3).

    - ``NATIONWIDE``  — available anywhere within the India envelope.
    - ``REGION_GATED`` — available only in states that enable it (Telangana in
      Version 1); elsewhere the field returns ``null`` with its ``null_meaning``.
    - ``PLANNED``     — not retrievable anywhere yet (always paired with the
      ``PLANNED`` lifecycle).
    """

    NATIONWIDE = "nationwide"
    REGION_GATED = "region_gated"
    PLANNED = "planned"


class DataType(StrEnum):
    """Output data type of a catalog field (SRS §11.4 Data Type, §13.6)."""

    FLOAT = "float"
    INTEGER = "integer"
    STRING = "string"
    BOOLEAN = "boolean"
    ENUM = "enum"
    GEOMETRY = "geometry"
