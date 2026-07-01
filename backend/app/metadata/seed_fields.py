"""The field catalog — the authoritative registry of every supported field.

This module is the single source of truth for field names (SRS §11.4): no field
name is hardcoded anywhere else in the platform. Every field named across the
§18 dataset connectors, the §19 Earth Engine datasets, and the §24.3 Telangana
region-gated fields is defined here with the full SRS §11.4 attribute set.

Fields fall into three lifecycle states (SRS §11.6):

- ``stable`` / ``beta`` — implemented (or implemented for the pilot region) and
  selectable by the Planner and Fetch Engine.
- ``planned``           — defined in the catalog but never selectable; these
  trace the catalog's documented growth path toward the 157-field Version 1
  target (SRS §11.4). They keep the schema complete without inventing data.

Region-gated fields (SRS §24.3) are ``REGION_GATED``: available only inside
states that enable them (Telangana in Version 1, per ``configs/telangana.yaml``).
"""

from __future__ import annotations

from app.metadata.enums import Availability, DataType, Layer, Lifecycle
from app.metadata.models import CatalogField


# --------------------------------------------------------------------------- #
# Concise constructors so each entry reads as data, not boilerplate.          #
# --------------------------------------------------------------------------- #
def _field(
    name: str,
    *,
    layer: Layer,
    datatype: DataType,
    description: str,
    source: str,
    lifecycle: Lifecycle = Lifecycle.STABLE,
    availability: Availability = Availability.NATIONWIDE,
    source_url: str | None = None,
    unit: str | None = None,
    ttl: str | None = None,
    nullable: bool = False,
    null_meaning: str | None = None,
    hint: str = "",
) -> CatalogField:
    return CatalogField(
        name=name,
        description=description,
        layer=layer,
        lifecycle=lifecycle,
        availability=availability,
        nullable=nullable,
        null_meaning=null_meaning,
        source=source,
        source_url=source_url,
        dataset_ttl=ttl,
        interpretation_hint=hint,
        unit=unit,
        datatype=datatype,
    )


def _gated(
    name: str,
    *,
    layer: Layer,
    datatype: DataType,
    description: str,
    source: str,
    null_meaning: str,
    source_url: str | None = None,
    unit: str | None = None,
    ttl: str | None = None,
    hint: str = "",
) -> CatalogField:
    """A region-gated beta field (SRS §24.3): nullable outside enabling states."""
    return _field(
        name,
        layer=layer,
        datatype=datatype,
        description=description,
        source=source,
        lifecycle=Lifecycle.BETA,
        availability=Availability.REGION_GATED,
        source_url=source_url,
        unit=unit,
        ttl=ttl,
        nullable=True,
        null_meaning=null_meaning,
        hint=hint,
    )


def _planned(
    name: str,
    *,
    layer: Layer,
    datatype: DataType,
    description: str,
    unit: str | None = None,
    hint: str = "",
) -> CatalogField:
    """A planned field (SRS §11.6): defined but never selectable/fetchable."""
    return _field(
        name,
        layer=layer,
        datatype=datatype,
        description=description,
        source="(planned)",
        lifecycle=Lifecycle.PLANNED,
        availability=Availability.PLANNED,
        unit=unit,
        nullable=True,
        null_meaning="Field is planned and not yet available for retrieval.",
        hint=hint,
    )


_BHUVAN = "https://bhuvan.nrsc.gov.in/"
_OSM = "https://www.openstreetmap.org/"

# --------------------------------------------------------------------------- #
# Terrain (SRS §18.3) — ISRO Bhuvan CartoDEM, Copernicus DEM, SoilGrids       #
# --------------------------------------------------------------------------- #
_TERRAIN = (
    _field(
        "elevation",
        layer=Layer.TERRAIN,
        datatype=DataType.FLOAT,
        unit="m",
        description="Ground elevation above mean sea level.",
        source="ISRO CartoDEM",
        source_url=_BHUVAN,
        ttl="365d",
        hint="Height above the EGM96 geoid; combine with slope for site grading.",
    ),
    _field(
        "slope",
        layer=Layer.TERRAIN,
        datatype=DataType.FLOAT,
        unit="degrees",
        description="Steepest-descent ground gradient.",
        source="ISRO CartoDEM (derived)",
        source_url=_BHUVAN,
        ttl="365d",
        hint="0° is flat; higher values indicate steeper, less buildable terrain.",
    ),
    _field(
        "aspect",
        layer=Layer.TERRAIN,
        datatype=DataType.FLOAT,
        unit="degrees",
        description="Compass direction the slope faces.",
        source="ISRO CartoDEM (derived)",
        source_url=_BHUVAN,
        ttl="365d",
        nullable=True,
        null_meaning="Aspect is undefined on perfectly flat cells.",
        hint="0–360° clockwise from north; drives solar exposure analysis.",
    ),
    _field(
        "terrain_roughness",
        layer=Layer.TERRAIN,
        datatype=DataType.FLOAT,
        unit="m",
        description="Local variability of elevation.",
        source="ISRO CartoDEM (derived)",
        source_url=_BHUVAN,
        ttl="365d",
        hint="Standard deviation of elevation in a local window; higher = rougher.",
    ),
    _field(
        "topographic_wetness_index",
        layer=Layer.TERRAIN,
        datatype=DataType.FLOAT,
        unit="index",
        description="Tendency of a cell to accumulate water.",
        source="ISRO CartoDEM (derived)",
        source_url=_BHUVAN,
        lifecycle=Lifecycle.BETA,
        ttl="365d",
        nullable=True,
        null_meaning="Undefined on flat cells or sinks with no flow direction.",
        hint="Higher TWI indicates greater soil-moisture accumulation potential.",
    ),
    _field(
        "soil_drainage_class",
        layer=Layer.TERRAIN,
        datatype=DataType.ENUM,
        description="Categorical soil drainage capacity.",
        source="SoilGrids",
        source_url="https://soilgrids.org/",
        ttl="365d",
        hint="well / moderate / poor; poor drainage raises waterlogging risk.",
    ),
    _field(
        "groundwater_depth_m",
        layer=Layer.TERRAIN,
        datatype=DataType.FLOAT,
        unit="m",
        description="Depth to the water table below ground level.",
        source="Central Ground Water Board (CGWB)",
        source_url="https://cgwb.gov.in/",
        lifecycle=Lifecycle.BETA,
        ttl="90d",
        nullable=True,
        null_meaning="No monitoring well within the search radius for this location.",
        hint="Shallower water tables increase both supply and flood/seepage risk.",
    ),
)

# --------------------------------------------------------------------------- #
# Climate (SRS §18.4) — TerraClimate, ERA5                                    #
# --------------------------------------------------------------------------- #
_TERRACLIMATE = "https://www.climatologylab.org/terraclimate.html"
_CLIMATE = (
    _field(
        "annual_rainfall_mm",
        layer=Layer.CLIMATE,
        datatype=DataType.FLOAT,
        unit="mm",
        description="Mean annual precipitation.",
        source="TerraClimate",
        source_url=_TERRACLIMATE,
        ttl="30d",
        hint="Long-term annual mean; not a forecast for any single year.",
    ),
    _field(
        "annual_temperature_c",
        layer=Layer.CLIMATE,
        datatype=DataType.FLOAT,
        unit="°C",
        description="Mean annual air temperature.",
        source="TerraClimate",
        source_url=_TERRACLIMATE,
        ttl="30d",
        hint="Long-term annual mean near-surface air temperature.",
    ),
    _field(
        "aridity_index",
        layer=Layer.CLIMATE,
        datatype=DataType.FLOAT,
        unit="index",
        description="Ratio of precipitation to potential evapotranspiration.",
        source="TerraClimate",
        source_url=_TERRACLIMATE,
        ttl="30d",
        hint="Lower values are more arid; < 0.2 is arid, > 0.65 is humid.",
    ),
    _field(
        "evapotranspiration",
        layer=Layer.CLIMATE,
        datatype=DataType.FLOAT,
        unit="mm",
        description="Mean annual actual evapotranspiration.",
        source="TerraClimate",
        source_url=_TERRACLIMATE,
        ttl="30d",
        hint="Water lost to the atmosphere; high values stress water budgets.",
    ),
    _field(
        "wind_speed",
        layer=Layer.CLIMATE,
        datatype=DataType.FLOAT,
        unit="m/s",
        description="Mean 10 m wind speed.",
        source="ERA5",
        source_url="https://cds.climate.copernicus.eu/",
        ttl="30d",
        hint="Long-term mean; relevant to wind-energy and fire-spread analysis.",
    ),
)

# --------------------------------------------------------------------------- #
# Land Cover (SRS §18.5) — Sentinel-2, ISRO Bhuvan LULC, MODIS                #
# --------------------------------------------------------------------------- #
_SENTINEL = "https://sentinels.copernicus.eu/"
_LAND_COVER = (
    _field(
        "ndvi_current",
        layer=Layer.LAND_COVER,
        datatype=DataType.FLOAT,
        unit="index",
        description="Latest normalized difference vegetation index.",
        source="Copernicus Sentinel-2",
        source_url=_SENTINEL,
        ttl="7d",
        hint="-1 to 1; higher means denser, healthier vegetation.",
    ),
    _field(
        "ndvi_historical",
        layer=Layer.LAND_COVER,
        datatype=DataType.FLOAT,
        unit="index",
        description="Multi-year mean NDVI.",
        source="Copernicus Sentinel-2 / MODIS",
        source_url=_SENTINEL,
        lifecycle=Lifecycle.BETA,
        ttl="30d",
        nullable=True,
        null_meaning="Insufficient cloud-free historical scenes for this location.",
        hint="Baseline vegetation level for comparison against ndvi_current.",
    ),
    _field(
        "dominant_land_cover",
        layer=Layer.LAND_COVER,
        datatype=DataType.ENUM,
        description="Primary land-use / land-cover class.",
        source="ISRO Bhuvan LULC",
        source_url=_BHUVAN,
        ttl="365d",
        hint="cropland / forest / built-up / water / barren / wetland.",
    ),
    _field(
        "tree_canopy_pct",
        layer=Layer.LAND_COVER,
        datatype=DataType.FLOAT,
        unit="%",
        description="Fraction of area under tree canopy.",
        source="Copernicus Sentinel-2",
        source_url=_SENTINEL,
        ttl="30d",
        hint="Higher canopy cover lowers wildfire ignition but raises fuel load.",
    ),
    _field(
        "cropland_class",
        layer=Layer.LAND_COVER,
        datatype=DataType.ENUM,
        description="Cropland category where present.",
        source="ISRO Bhuvan LULC",
        source_url=_BHUVAN,
        ttl="365d",
        nullable=True,
        null_meaning="Location is not classified as cropland.",
        hint="Irrigated / rainfed / plantation classification.",
    ),
    _field(
        "wetland_presence",
        layer=Layer.LAND_COVER,
        datatype=DataType.BOOLEAN,
        description="Whether the location intersects a mapped wetland.",
        source="National Wetland Atlas (ISRO)",
        source_url=_BHUVAN,
        ttl="365d",
        hint="True indicates regulatory and flood-buffer significance.",
    ),
    _gated(
        "dominant_crop_class",
        layer=Layer.LAND_COVER,
        datatype=DataType.ENUM,
        description="Dominant crop classification for the season.",
        source="Telangana Agriculture / Bhuvan",
        source_url=_BHUVAN,
        ttl="180d",
        null_meaning="Crop classification is available only within Telangana.",
        hint="Pilot-region only; derived from in-season satellite classification.",
    ),
)

# --------------------------------------------------------------------------- #
# Natural Hazard (SRS §18.6) — JRC GloFAS, OpenStreetMap, JRC GSW, NASA FIRMS #
# --------------------------------------------------------------------------- #
# No open bulk CWC/NRSC flood-hazard GIS layer exists for Telangana (confirmed
# by research 2026-07-01: NRSC's Flood Hazard Zonation Atlas covers Bihar only;
# Bhuvan/NDEM's flood layers are login/VPN-gated viewers). flood_hazard_class and
# within_flood_hazard_polygon are derived instead from JRC's Global River Flood
# Hazard Maps (GloFAS v2.1, sampled live via Earth Engine, SRS §16.4 Accuracy).
_GLOFAS = (
    "https://developers.google.com/earth-engine/datasets/catalog/JRC_CEMS_GLOFAS_FloodHazard_v2_1"
)
_FIRMS = "https://firms.modaps.eosdis.nasa.gov/"
_NATURAL_HAZARD = (
    _field(
        "flood_hazard_class",
        layer=Layer.NATURAL_HAZARD,
        datatype=DataType.ENUM,
        description="Categorical flood hazard level.",
        source="JRC Global River Flood Hazard Maps",
        source_url=_GLOFAS,
        ttl="365d",
        nullable=True,
        null_meaning="No flood hazard mapping covers this location.",
        hint=(
            "low / moderate / high / very_high, derived from the shortest GloFAS "
            "return period (10-500yr) at which the point is modelled as inundated."
        ),
    ),
    _field(
        "within_flood_hazard_polygon",
        layer=Layer.NATURAL_HAZARD,
        datatype=DataType.BOOLEAN,
        description="Whether the point lies inside a mapped flood hazard polygon.",
        source="JRC Global River Flood Hazard Maps",
        source_url=_GLOFAS,
        ttl="365d",
        hint="True indicates inundation at any GloFAS return period up to 500 years.",
    ),
    _field(
        "nearest_waterbody_distance_m",
        layer=Layer.NATURAL_HAZARD,
        datatype=DataType.FLOAT,
        unit="m",
        description="Straight-line distance to the nearest mapped waterbody.",
        source="OpenStreetMap",
        source_url=_OSM,
        ttl="90d",
        hint="Smaller distances raise flood and seepage exposure.",
    ),
    _field(
        "nearest_waterbody_name",
        layer=Layer.NATURAL_HAZARD,
        datatype=DataType.STRING,
        description="Name of the nearest mapped waterbody.",
        source="OpenStreetMap",
        source_url=_OSM,
        lifecycle=Lifecycle.BETA,
        ttl="90d",
        nullable=True,
        null_meaning="The nearest waterbody is unnamed in the source dataset.",
        hint="Pairs with nearest_waterbody_distance_m for citations.",
    ),
    _field(
        "surface_water_permanence_pct",
        layer=Layer.NATURAL_HAZARD,
        datatype=DataType.FLOAT,
        unit="%",
        description="Share of time surface water is present (1984–present).",
        source="JRC Global Surface Water",
        source_url="https://global-surface-water.appspot.com/",
        ttl="365d",
        nullable=True,
        null_meaning="No surface water has been observed at this location.",
        hint="High permanence indicates persistent water; spikes indicate flooding.",
    ),
    _field(
        "wildfire_risk",
        layer=Layer.NATURAL_HAZARD,
        datatype=DataType.ENUM,
        description="Categorical wildfire risk.",
        source="NASA FIRMS (derived)",
        source_url=_FIRMS,
        ttl="7d",
        hint="low / moderate / high; combines fuel, aridity, and fire activity.",
    ),
    _field(
        "active_fire_count_10km_24h",
        layer=Layer.NATURAL_HAZARD,
        datatype=DataType.INTEGER,
        unit="count",
        description="Active fire detections within 10 km in the last 24 hours.",
        source="NASA FIRMS",
        source_url=_FIRMS,
        ttl="1d",
        hint="Near-real-time; non-zero counts signal active fire in the vicinity.",
    ),
)

# --------------------------------------------------------------------------- #
# Infrastructure (SRS §18.7) — transport & access: OSM roads/railways          #
# --------------------------------------------------------------------------- #
_INFRASTRUCTURE = (
    _field(
        "nearest_highway_distance",
        layer=Layer.INFRASTRUCTURE,
        datatype=DataType.FLOAT,
        unit="m",
        description="Distance to the nearest national or state highway.",
        source="OpenStreetMap",
        source_url=_OSM,
        ttl="90d",
        hint="Proxy for road accessibility and logistics cost.",
    ),
    _field(
        "nearest_railway_distance",
        layer=Layer.INFRASTRUCTURE,
        datatype=DataType.FLOAT,
        unit="m",
        description="Distance to the nearest railway line.",
        source="OpenStreetMap",
        source_url=_OSM,
        ttl="90d",
        hint="Relevant to freight-intensive site selection.",
    ),
)

# --------------------------------------------------------------------------- #
# Utilities (SRS §18.7 utilities, §24.3) — power/grid/telecom: OSM/POSOCO,     #
# TRAI, TSSPDCL/TSNPDCL, TSERC. Split out of Infrastructure for energy/siting. #
# --------------------------------------------------------------------------- #
_UTILITIES = (
    _field(
        "nearest_substation_distance",
        layer=Layer.UTILITIES,
        datatype=DataType.FLOAT,
        unit="m",
        description="Distance to the nearest electrical substation.",
        source="OpenStreetMap / POSOCO",
        source_url=_OSM,
        ttl="90d",
        nullable=True,
        null_meaning="No substation within the search radius for this location.",
        hint="Shorter distance lowers grid-interconnection cost.",
    ),
    _field(
        "nearest_powerline_distance",
        layer=Layer.UTILITIES,
        datatype=DataType.FLOAT,
        unit="m",
        description="Distance to the nearest transmission line.",
        source="OpenStreetMap",
        source_url=_OSM,
        ttl="90d",
        nullable=True,
        null_meaning="No transmission line within the search radius for this location.",
        hint="Pairs with nearest_substation_distance for grid-access scoring.",
    ),
    _field(
        "telecom_coverage",
        layer=Layer.UTILITIES,
        datatype=DataType.ENUM,
        description="Best available mobile network generation.",
        source="TRAI",
        source_url="https://www.trai.gov.in/",
        lifecycle=Lifecycle.BETA,
        ttl="180d",
        nullable=True,
        null_meaning="Coverage data is unavailable for this location.",
        hint="2G / 3G / 4G / 5G — the best generation reported in the area.",
    ),
    _gated(
        "electricity_distribution_company",
        layer=Layer.UTILITIES,
        datatype=DataType.STRING,
        description="Electricity distribution company (DISCOM) serving the area.",
        source="TSSPDCL / TSNPDCL",
        ttl="365d",
        null_meaning="DISCOM mapping is available only within Telangana.",
        hint="Pilot-region only; determines tariff schedule and reliability.",
    ),
    _gated(
        "industrial_tariff",
        layer=Layer.UTILITIES,
        datatype=DataType.FLOAT,
        unit="INR/kWh",
        description="Applicable high-tension industrial electricity tariff.",
        source="TSERC",
        ttl="365d",
        null_meaning="Industrial tariff is available only within Telangana.",
        hint="Pilot-region only; drives industrial siting economics.",
    ),
)

# --------------------------------------------------------------------------- #
# Administrative (SRS §18.8, §24.3) — Survey of India, NAKSHA, CDMA Telangana #
# --------------------------------------------------------------------------- #
_SOI = "https://surveyofindia.gov.in/"
_ADMINISTRATIVE = (
    _field(
        "state_name",
        layer=Layer.ADMINISTRATIVE,
        datatype=DataType.STRING,
        description="State or union territory containing the point.",
        source="Survey of India",
        source_url=_SOI,
        ttl="365d",
        hint="Resolved from official administrative boundaries.",
    ),
    _field(
        "district_name",
        layer=Layer.ADMINISTRATIVE,
        datatype=DataType.STRING,
        description="District containing the point.",
        source="Survey of India",
        source_url=_SOI,
        ttl="365d",
        hint="Second-level administrative unit.",
    ),
    _field(
        "taluk_name",
        layer=Layer.ADMINISTRATIVE,
        datatype=DataType.STRING,
        description="Taluk / tehsil / mandal containing the point.",
        source="Survey of India",
        source_url=_SOI,
        ttl="365d",
        nullable=True,
        null_meaning="Sub-district boundaries are unavailable for this state.",
        hint="Third-level administrative unit; naming varies by state.",
    ),
    _field(
        "village_name",
        layer=Layer.ADMINISTRATIVE,
        datatype=DataType.STRING,
        description="Revenue village containing the point.",
        source="Survey of India",
        source_url=_SOI,
        lifecycle=Lifecycle.BETA,
        ttl="365d",
        nullable=True,
        null_meaning="Village boundaries are unavailable for this location.",
        hint="Lowest rural administrative unit.",
    ),
    _gated(
        "municipality_name",
        layer=Layer.ADMINISTRATIVE,
        datatype=DataType.STRING,
        description="Municipality / urban local body containing the point.",
        source="CDMA Telangana / Survey of India",
        source_url=_SOI,
        ttl="365d",
        null_meaning="Municipal mapping is available only within Telangana.",
        hint="Pilot-region only; urban administrative unit.",
    ),
    _gated(
        "ward_name",
        layer=Layer.ADMINISTRATIVE,
        datatype=DataType.STRING,
        description="Municipal ward containing the point.",
        source="GHMC / CDMA Telangana",
        ttl="365d",
        null_meaning="Ward mapping is available only within Telangana.",
        hint="Pilot-region only; finest urban administrative unit.",
    ),
    _gated(
        "urban_local_body",
        layer=Layer.ADMINISTRATIVE,
        datatype=DataType.STRING,
        description="Urban Local Body (ULB) containing the point.",
        source="CDMA Telangana",
        ttl="365d",
        null_meaning="ULB mapping is available only within Telangana.",
        hint="Pilot-region only; governing municipal body.",
    ),
)

# --------------------------------------------------------------------------- #
# Cadastral (SRS §18.9, §24.3) — Telangana Bhu Bharati (region-gated). Bhu     #
# Bharati replaced Dharani in 2025 (Telangana Bhu Bharati RoR Act); the access #
# model is unchanged — a manual single-parcel viewer, no bulk export.         #
# --------------------------------------------------------------------------- #
_BHU_BHARATI = "https://bhubharati.telangana.gov.in/"
_CADASTRAL = (
    _gated(
        "parcel_id",
        layer=Layer.CADASTRAL,
        datatype=DataType.STRING,
        description="Cadastral parcel identifier.",
        source="Telangana Bhu Bharati",
        source_url=_BHU_BHARATI,
        ttl="90d",
        null_meaning="Cadastral parcels are available only within Telangana.",
        hint="Pilot-region only; keys into the land-records system.",
    ),
    _gated(
        "survey_number",
        layer=Layer.CADASTRAL,
        datatype=DataType.STRING,
        description="Revenue survey number of the containing parcel.",
        source="Telangana Bhu Bharati",
        source_url=_BHU_BHARATI,
        ttl="90d",
        null_meaning="Survey numbers are available only within Telangana.",
        hint="Pilot-region only; legal land-parcel reference.",
    ),
    _gated(
        "parcel_area",
        layer=Layer.CADASTRAL,
        datatype=DataType.FLOAT,
        unit="m²",
        description="Area of the containing parcel.",
        source="Telangana Bhu Bharati",
        source_url=_BHU_BHARATI,
        ttl="90d",
        null_meaning="Cadastral parcels are available only within Telangana.",
        hint="Pilot-region only; derived from parcel geometry.",
    ),
    _gated(
        "parcel_geometry",
        layer=Layer.CADASTRAL,
        datatype=DataType.GEOMETRY,
        description="Boundary geometry of the containing parcel (GeoJSON).",
        source="Telangana Bhu Bharati",
        source_url=_BHU_BHARATI,
        ttl="90d",
        null_meaning="Cadastral parcels are available only within Telangana.",
        hint="Pilot-region only; WGS84 polygon of the parcel boundary.",
    ),
    _gated(
        "zoning",
        layer=Layer.CADASTRAL,
        datatype=DataType.ENUM,
        description="Land-use zoning classification.",
        source="HMDA / DTCP Telangana",
        ttl="180d",
        null_meaning="Zoning is available only within Telangana.",
        hint="Pilot-region only; residential / commercial / industrial / agricultural.",
    ),
    _gated(
        "ownership_category",
        layer=Layer.CADASTRAL,
        datatype=DataType.ENUM,
        description="Ownership category of the containing parcel.",
        source="Telangana Bhu Bharati",
        source_url=_BHU_BHARATI,
        ttl="90d",
        null_meaning="Ownership category is available only within Telangana.",
        hint="Pilot-region only; government / private / institutional / endowment.",
    ),
)

# --------------------------------------------------------------------------- #
# Built Environment — Google Open Buildings (building footprints / rooftops).  #
# Nationwide: Open Buildings v3 covers all of India. Connector wired in Phase  #
# 4 (built_environment_connector); until then these fields surface as partial  #
# failures, like the other not-yet-deployed connectors.                       #
# --------------------------------------------------------------------------- #
_OPEN_BUILDINGS = "https://sites.research.google/open-buildings/"
_BUILT_ENVIRONMENT = (
    _field(
        "building_present",
        layer=Layer.BUILT_ENVIRONMENT,
        datatype=DataType.BOOLEAN,
        description="Whether the point intersects a mapped building footprint.",
        source="Google Open Buildings",
        source_url=_OPEN_BUILDINGS,
        ttl="365d",
        hint="True indicates an existing structure at the coordinate.",
    ),
    _field(
        "building_footprint_area_m2",
        layer=Layer.BUILT_ENVIRONMENT,
        datatype=DataType.FLOAT,
        unit="m²",
        description="Footprint area of the building containing the point.",
        source="Google Open Buildings",
        source_url=_OPEN_BUILDINGS,
        lifecycle=Lifecycle.BETA,
        ttl="365d",
        nullable=True,
        null_meaning="No mapped building footprint at this location.",
        hint="Ground-floor area of the containing structure.",
    ),
    _field(
        "building_count_250m",
        layer=Layer.BUILT_ENVIRONMENT,
        datatype=DataType.INTEGER,
        unit="count",
        description="Number of building footprints within 250 m.",
        source="Google Open Buildings",
        source_url=_OPEN_BUILDINGS,
        ttl="365d",
        hint="A proxy for built-up density around the point.",
    ),
    _field(
        "nearest_building_distance_m",
        layer=Layer.BUILT_ENVIRONMENT,
        datatype=DataType.FLOAT,
        unit="m",
        description="Distance to the nearest building footprint.",
        source="Google Open Buildings",
        source_url=_OPEN_BUILDINGS,
        lifecycle=Lifecycle.BETA,
        ttl="365d",
        nullable=True,
        null_meaning="No building within the search radius for this location.",
        hint="Larger distances indicate undeveloped surroundings.",
    ),
    _field(
        "built_up_area_pct_1km",
        layer=Layer.BUILT_ENVIRONMENT,
        datatype=DataType.FLOAT,
        unit="%",
        description="Share of built-up surface within 1 km.",
        source="Google Open Buildings (derived)",
        source_url=_OPEN_BUILDINGS,
        lifecycle=Lifecycle.BETA,
        ttl="365d",
        hint="Higher values indicate denser urban development.",
    ),
)

# --------------------------------------------------------------------------- #
# Planned fields (SRS §11.6) — defined but never selectable. These document   #
# the catalog's growth path toward the 157-field target (SRS §11.4).          #
# --------------------------------------------------------------------------- #
_PLANNED = (
    # Terrain
    _planned(
        "drainage_density",
        layer=Layer.TERRAIN,
        datatype=DataType.FLOAT,
        unit="km/km²",
        description="Length of drainage channels per unit area.",
    ),
    _planned(
        "flow_accumulation",
        layer=Layer.TERRAIN,
        datatype=DataType.FLOAT,
        unit="cells",
        description="Upslope contributing area for each cell.",
    ),
    _planned(
        "landslide_susceptibility",
        layer=Layer.TERRAIN,
        datatype=DataType.ENUM,
        description="Categorical landslide susceptibility.",
    ),
    _planned(
        "soil_organic_carbon",
        layer=Layer.TERRAIN,
        datatype=DataType.FLOAT,
        unit="g/kg",
        description="Soil organic carbon content.",
    ),
    _planned(
        "soil_texture_class",
        layer=Layer.TERRAIN,
        datatype=DataType.ENUM,
        description="USDA soil texture class.",
    ),
    _planned(
        "bedrock_depth_m",
        layer=Layer.TERRAIN,
        datatype=DataType.FLOAT,
        unit="m",
        description="Depth to bedrock below the surface.",
    ),
    # Climate
    _planned(
        "max_temperature_c",
        layer=Layer.CLIMATE,
        datatype=DataType.FLOAT,
        unit="°C",
        description="Mean annual maximum temperature.",
    ),
    _planned(
        "min_temperature_c",
        layer=Layer.CLIMATE,
        datatype=DataType.FLOAT,
        unit="°C",
        description="Mean annual minimum temperature.",
    ),
    _planned(
        "monsoon_onset_doy",
        layer=Layer.CLIMATE,
        datatype=DataType.INTEGER,
        unit="day-of-year",
        description="Typical monsoon onset day of year.",
    ),
    _planned(
        "drought_index_spi",
        layer=Layer.CLIMATE,
        datatype=DataType.FLOAT,
        unit="index",
        description="Standardized Precipitation Index.",
    ),
    _planned(
        "relative_humidity_pct",
        layer=Layer.CLIMATE,
        datatype=DataType.FLOAT,
        unit="%",
        description="Mean annual relative humidity.",
    ),
    _planned(
        "solar_irradiance_kwh_m2",
        layer=Layer.CLIMATE,
        datatype=DataType.FLOAT,
        unit="kWh/m²/day",
        description="Mean daily global horizontal irradiance.",
    ),
    _planned(
        "heat_wave_days",
        layer=Layer.CLIMATE,
        datatype=DataType.INTEGER,
        unit="days/yr",
        description="Mean number of heat-wave days per year.",
    ),
    # Land Cover
    _planned(
        "land_cover_change_5yr",
        layer=Layer.LAND_COVER,
        datatype=DataType.ENUM,
        description="Dominant land-cover change over the last five years.",
    ),
    _planned(
        "built_up_pct",
        layer=Layer.LAND_COVER,
        datatype=DataType.FLOAT,
        unit="%",
        description="Share of built-up / impervious surface.",
    ),
    _planned(
        "forest_cover_pct",
        layer=Layer.LAND_COVER,
        datatype=DataType.FLOAT,
        unit="%",
        description="Share of forest cover.",
    ),
    _planned(
        "grassland_pct",
        layer=Layer.LAND_COVER,
        datatype=DataType.FLOAT,
        unit="%",
        description="Share of grassland cover.",
    ),
    _planned(
        "surface_water_pct",
        layer=Layer.LAND_COVER,
        datatype=DataType.FLOAT,
        unit="%",
        description="Share of open surface water.",
    ),
    _planned(
        "crop_calendar_stage",
        layer=Layer.LAND_COVER,
        datatype=DataType.ENUM,
        description="Current crop phenology stage.",
    ),
    # Natural Hazard
    _planned(
        "seismic_zone",
        layer=Layer.NATURAL_HAZARD,
        datatype=DataType.ENUM,
        description="IS 1893 seismic zone (II–V).",
    ),
    _planned(
        "cyclone_risk_category",
        layer=Layer.NATURAL_HAZARD,
        datatype=DataType.ENUM,
        description="Categorical cyclone risk.",
    ),
    _planned(
        "storm_surge_risk",
        layer=Layer.NATURAL_HAZARD,
        datatype=DataType.ENUM,
        description="Categorical storm-surge risk.",
    ),
    _planned(
        "drought_hazard_class",
        layer=Layer.NATURAL_HAZARD,
        datatype=DataType.ENUM,
        description="Categorical drought hazard.",
    ),
    _planned(
        "lightning_density",
        layer=Layer.NATURAL_HAZARD,
        datatype=DataType.FLOAT,
        unit="strikes/km²/yr",
        description="Mean annual lightning strike density.",
    ),
    _planned(
        "burned_area_pct_5yr",
        layer=Layer.NATURAL_HAZARD,
        datatype=DataType.FLOAT,
        unit="%",
        description="Share of area burned in the last five years.",
    ),
    # Infrastructure
    _planned(
        "nearest_airport_distance",
        layer=Layer.INFRASTRUCTURE,
        datatype=DataType.FLOAT,
        unit="m",
        description="Distance to the nearest airport.",
    ),
    _planned(
        "nearest_port_distance",
        layer=Layer.INFRASTRUCTURE,
        datatype=DataType.FLOAT,
        unit="m",
        description="Distance to the nearest seaport.",
    ),
    _planned(
        "nearest_hospital_distance",
        layer=Layer.INFRASTRUCTURE,
        datatype=DataType.FLOAT,
        unit="m",
        description="Distance to the nearest hospital.",
    ),
    _planned(
        "nearest_industrial_corridor_distance",
        layer=Layer.INFRASTRUCTURE,
        datatype=DataType.FLOAT,
        unit="m",
        description="Distance to the nearest industrial corridor.",
    ),
    _planned(
        "population_density",
        layer=Layer.INFRASTRUCTURE,
        datatype=DataType.FLOAT,
        unit="people/km²",
        description="Estimated population density.",
    ),
    _planned(
        "nighttime_lights_radiance",
        layer=Layer.INFRASTRUCTURE,
        datatype=DataType.FLOAT,
        unit="nW/cm²/sr",
        description="VIIRS nighttime-lights radiance.",
    ),
    _planned(
        "road_density_km_per_km2",
        layer=Layer.INFRASTRUCTURE,
        datatype=DataType.FLOAT,
        unit="km/km²",
        description="Road length per unit area.",
    ),
    # Administrative
    _planned(
        "pincode",
        layer=Layer.ADMINISTRATIVE,
        datatype=DataType.STRING,
        description="Postal index number (PIN code).",
    ),
    _planned(
        "parliamentary_constituency",
        layer=Layer.ADMINISTRATIVE,
        datatype=DataType.STRING,
        description="Lok Sabha parliamentary constituency.",
    ),
    _planned(
        "assembly_constituency",
        layer=Layer.ADMINISTRATIVE,
        datatype=DataType.STRING,
        description="Vidhan Sabha assembly constituency.",
    ),
    _planned(
        "lgd_code",
        layer=Layer.ADMINISTRATIVE,
        datatype=DataType.STRING,
        description="Local Government Directory (LGD) code.",
    ),
    # Cadastral
    _planned(
        "land_use_certificate",
        layer=Layer.CADASTRAL,
        datatype=DataType.STRING,
        description="Land-use conversion certificate reference.",
    ),
    _planned(
        "encumbrance_status",
        layer=Layer.CADASTRAL,
        datatype=DataType.ENUM,
        description="Encumbrance status of the parcel.",
    ),
    _planned(
        "market_value_per_sqm",
        layer=Layer.CADASTRAL,
        datatype=DataType.FLOAT,
        unit="INR/m²",
        description="Government-notified market value per square metre.",
    ),
    _planned(
        "fsi_permitted",
        layer=Layer.CADASTRAL,
        datatype=DataType.FLOAT,
        unit="ratio",
        description="Permitted floor space index for the parcel.",
    ),
    # Built Environment
    _planned(
        "building_height_m",
        layer=Layer.BUILT_ENVIRONMENT,
        datatype=DataType.FLOAT,
        unit="m",
        description="Estimated mean building height at the location.",
    ),
    _planned(
        "rooftop_solar_area_m2",
        layer=Layer.BUILT_ENVIRONMENT,
        datatype=DataType.FLOAT,
        unit="m²",
        description="Usable rooftop area for solar PV.",
    ),
)

# All catalog fields, in catalog order. The catalog (app.metadata.catalog)
# indexes and back-populates presets onto these entries.
FIELDS: tuple[CatalogField, ...] = (
    *_TERRAIN,
    *_CLIMATE,
    *_LAND_COVER,
    *_NATURAL_HAZARD,
    *_INFRASTRUCTURE,
    *_UTILITIES,
    *_ADMINISTRATIVE,
    *_CADASTRAL,
    *_BUILT_ENVIRONMENT,
    *_PLANNED,
)
