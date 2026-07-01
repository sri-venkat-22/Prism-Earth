"""The seven domain layers (SRS §11.5).

Each layer owns exactly one connector (SRS §11.5, §18.10). The connector names
here are the registry keys the Fetch Engine will resolve in Phase 3; for Phase 1
they establish the field → layer → connector mapping the catalog validator
checks.
"""

from __future__ import annotations

from app.metadata.enums import Layer
from app.metadata.models import LayerDefinition

LAYERS: tuple[LayerDefinition, ...] = (
    LayerDefinition(
        id=Layer.TERRAIN,
        name="Terrain",
        purpose="Elevation, slope, soils, groundwater",
        connector="terrain_connector",
    ),
    LayerDefinition(
        id=Layer.CLIMATE,
        name="Climate",
        purpose="Rainfall, temperature, aridity, wind",
        connector="climate_connector",
    ),
    LayerDefinition(
        id=Layer.LAND_COVER,
        name="Land Cover",
        purpose="Vegetation, NDVI, cropland, wetlands",
        connector="land_cover_connector",
    ),
    LayerDefinition(
        id=Layer.NATURAL_HAZARD,
        name="Natural Hazard",
        purpose="Flood, fire, cyclone, seismic",
        connector="natural_hazard_connector",
    ),
    LayerDefinition(
        id=Layer.INFRASTRUCTURE,
        name="Infrastructure",
        purpose="Transport & access: roads, railways, airports, population",
        connector="infrastructure_connector",
    ),
    LayerDefinition(
        id=Layer.UTILITIES,
        name="Utilities",
        purpose="Power, grid, substations, transmission, telecom",
        connector="utilities_connector",
    ),
    LayerDefinition(
        id=Layer.ADMINISTRATIVE,
        name="Administrative",
        purpose="State, district, taluk, ULB",
        connector="administrative_connector",
    ),
    LayerDefinition(
        id=Layer.CADASTRAL,
        name="Cadastral",
        purpose="Parcel, survey number, zoning",
        connector="cadastral_connector",
    ),
    LayerDefinition(
        id=Layer.BUILT_ENVIRONMENT,
        name="Built Environment",
        purpose="Building footprints, density, rooftops",
        connector="built_environment_connector",
    ),
)
