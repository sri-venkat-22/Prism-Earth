"""The 14 predefined presets (SRS §11.7, §13.8).

A preset is a named bundle of catalog fields expanded before connector execution
(SRS §11.7). Each preset declares only its identity and member fields; the
catalog derives its ``layers`` (from the fields' layers) and the registry derives
its ``supported_states`` (from the fields' availability), so there is no
duplicated, drift-prone metadata.

Three presets are named verbatim in SRS §11.7 (Terrain, Flood Risk, Wildfire
Underwrite); the remaining eleven cover the other layers and common
underwriting / siting workflows. Presets reference only stable/beta fields —
never ``planned`` fields (enforced by the catalog validator). Two presets
(Cadastral Profile, Urban Utilities) are built entirely from region-gated
fields and therefore resolve as supported only within Telangana in Version 1.
"""

from __future__ import annotations

from app.metadata.models import PresetDefinition

PRESETS: tuple[PresetDefinition, ...] = (
    PresetDefinition(
        id="terrain",
        name="Terrain",
        description="Core terrain characteristics for site grading and stability.",
        fields=("elevation", "slope", "aspect", "terrain_roughness", "soil_drainage_class"),
    ),
    PresetDefinition(
        id="flood_risk",
        name="Flood Risk",
        description="Flood exposure signals for underwriting and site screening.",
        fields=(
            "within_flood_hazard_polygon",
            "flood_hazard_class",
            "nearest_waterbody_name",
            "nearest_waterbody_distance_m",
            "surface_water_permanence_pct",
        ),
    ),
    PresetDefinition(
        id="wildfire_underwrite",
        name="Wildfire Underwrite",
        description="Vegetation, aridity, and fire-activity signals for wildfire risk.",
        fields=(
            "ndvi_current",
            "tree_canopy_pct",
            "active_fire_count_10km_24h",
            "aridity_index",
        ),
    ),
    PresetDefinition(
        id="climate_profile",
        name="Climate Profile",
        description="Long-term climate baseline for a location.",
        fields=(
            "annual_rainfall_mm",
            "annual_temperature_c",
            "aridity_index",
            "evapotranspiration",
            "wind_speed",
        ),
    ),
    PresetDefinition(
        id="land_cover",
        name="Land Cover",
        description="Vegetation and land-use characterization.",
        fields=(
            "ndvi_current",
            "ndvi_historical",
            "dominant_land_cover",
            "tree_canopy_pct",
            "cropland_class",
            "wetland_presence",
        ),
    ),
    PresetDefinition(
        id="administrative_lookup",
        name="Administrative Lookup",
        description="Administrative hierarchy for a coordinate.",
        fields=("state_name", "district_name", "taluk_name", "village_name"),
    ),
    PresetDefinition(
        id="infrastructure_access",
        name="Infrastructure Access",
        description="Proximity to transport, power, and telecom infrastructure.",
        fields=(
            "nearest_highway_distance",
            "nearest_railway_distance",
            "nearest_substation_distance",
            "nearest_powerline_distance",
            "telecom_coverage",
        ),
    ),
    PresetDefinition(
        id="water_resources",
        name="Water Resources",
        description="Groundwater and surface-water context for a location.",
        fields=(
            "groundwater_depth_m",
            "nearest_waterbody_distance_m",
            "nearest_waterbody_name",
            "surface_water_permanence_pct",
            "annual_rainfall_mm",
        ),
    ),
    PresetDefinition(
        id="agriculture_suitability",
        name="Agriculture Suitability",
        description="Soil, vegetation, and water signals for agricultural suitability.",
        fields=(
            "soil_drainage_class",
            "ndvi_current",
            "cropland_class",
            "annual_rainfall_mm",
            "groundwater_depth_m",
        ),
    ),
    PresetDefinition(
        id="renewable_siting",
        name="Renewable Energy Siting",
        description="Terrain, climate, and grid-access signals for renewable siting.",
        fields=(
            "elevation",
            "slope",
            "aspect",
            "annual_temperature_c",
            "nearest_substation_distance",
            "nearest_powerline_distance",
        ),
    ),
    PresetDefinition(
        id="property_underwriting",
        name="Property Underwriting",
        description="Hazard and accessibility signals for property underwriting.",
        fields=(
            "flood_hazard_class",
            "wildfire_risk",
            "elevation",
            "slope",
            "nearest_highway_distance",
            "dominant_land_cover",
        ),
    ),
    PresetDefinition(
        id="hazard_overview",
        name="Hazard Overview",
        description="Combined flood and wildfire hazard snapshot.",
        fields=(
            "flood_hazard_class",
            "within_flood_hazard_polygon",
            "wildfire_risk",
            "active_fire_count_10km_24h",
            "nearest_waterbody_distance_m",
        ),
    ),
    PresetDefinition(
        id="cadastral_profile",
        name="Cadastral Profile",
        description="Parcel-level land-record details (region-gated).",
        fields=("parcel_id", "survey_number", "parcel_area", "zoning", "ownership_category"),
    ),
    PresetDefinition(
        id="urban_utilities",
        name="Urban Utilities",
        description="Urban administration and utility context (region-gated).",
        fields=(
            "municipality_name",
            "ward_name",
            "urban_local_body",
            "electricity_distribution_company",
            "industrial_tariff",
        ),
    ),
)
