"""Controlled vocabularies for the Metadata Catalog (SRS §11.4–11.6).

These enums are the only place the catalog's categorical values are defined, so
that layers, lifecycle states, availability, and data types stay consistent
across the catalog, the validator, and the Metadata APIs (SRS §13.6–13.8).
"""

from __future__ import annotations

from enum import StrEnum


class Layer(StrEnum):
    """The seven domain layers (SRS §11.5). Every field belongs to exactly one."""

    TERRAIN = "terrain"
    CLIMATE = "climate"
    LAND_COVER = "land_cover"
    NATURAL_HAZARD = "natural_hazard"
    INFRASTRUCTURE = "infrastructure"
    ADMINISTRATIVE = "administrative"
    CADASTRAL = "cadastral"


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
