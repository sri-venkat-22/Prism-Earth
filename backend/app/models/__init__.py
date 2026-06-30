"""ORM models (SRS §20, §22).

Importing this package registers every entity on :data:`app.models.base.Base`'s
metadata, so Alembic (``migrations/env.py``) and the application see the full
schema. New model modules must be imported here.
"""

from __future__ import annotations

from app.models.base import Base
from app.models.registry import (
    Citation,
    ConnectorRow,
    DatasetRow,
    FieldRow,
    LayerRow,
    PresetField,
    PresetRow,
    Provenance,
    RequestLog,
    StateRow,
)
from app.models.spatial import (
    District,
    FloodHazardZone,
    HistoricalFlood,
    Mandal,
    Municipality,
    Parcel,
    Railway,
    Road,
    State,
    Substation,
    TransmissionLine,
    Village,
    Ward,
    WaterBody,
)

__all__ = [
    "Base",
    # Registry (metadata schema, SRS §22.3)
    "LayerRow",
    "ConnectorRow",
    "DatasetRow",
    "FieldRow",
    "PresetRow",
    "PresetField",
    "StateRow",
    "Provenance",
    "Citation",
    "RequestLog",
    # Administrative boundaries (admin schema)
    "State",
    "District",
    "Mandal",
    "Village",
    "Municipality",
    "Ward",
    # Hazards
    "FloodHazardZone",
    "WaterBody",
    "HistoricalFlood",
    # Infrastructure
    "Road",
    "Railway",
    "TransmissionLine",
    "Substation",
    # Cadastral
    "Parcel",
]
