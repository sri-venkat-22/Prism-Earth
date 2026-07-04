# Dataset Documentation

Prism Earth's metadata catalog is the **single source of truth** for what the
platform can serve (SRS §11.4, §38.2). Version 1 covers the **Telangana** pilot
region: **9 layers, 93 fields, 18 presets**. This page summarizes the layers and
their primary datasets; the authoritative, always-current listing is the live
API and the Explore page.

- Live field catalog: `GET /api/v1/meta/fields`
- Layers: `GET /api/v1/meta/layers` · Presets: `GET /api/v1/meta/presets`
- Browser: the **Explore** page (Datasets / Presets / Layers / Regional).

## Layers (SRS §11.5)

| Layer | Examples | Primary sources |
| --- | --- | --- |
| Terrain | elevation, slope, aspect | Copernicus DEM GLO-30 |
| Climate | rainfall, temperature, aridity, wind | TerraClimate |
| Land Cover | NDVI, cropland, tree canopy, wetland | Copernicus Sentinel-2, MODIS |
| Natural Hazard | flood class, surface water, active fire | JRC Global Surface Water, VIIRS |
| Infrastructure | nearest highway/railway distance | OpenStreetMap |
| Utilities | nearest substation/powerline distance | OpenStreetMap |
| Administrative | state, district, mandal, ward | Telangana admin boundaries |
| Cadastral | parcel id, survey number, zoning | Telangana cadastral parcels |
| Built Environment | building footprint, built-up % | OpenStreetMap buildings |

## Field definitions (SRS §11.4)

Every field in the catalog declares: `id`, `name`, `description`, `layer`,
`lifecycle` (stable / beta / planned), `available`, `nullable`, `null_meaning`,
`source`, `source_url`, `unit`, `datatype`, `ttl`, `interpretation_hint`, and
associated `presets`. The Planner may only select **registered** fields, and the
Fetch Engine only runs **registered** connectors (SRS §38.3, §38.4).

## Provenance (SRS §17)

Every returned field carries provenance: the dataset, provider, dataset version,
source URL, retrieval timestamp, resolution/CRS where applicable, TTL, and a
confidence indicator. When a value is null, the provenance carries a
machine-readable `reason` (e.g. `outside_coverage`, `unsupported_state`).

## Citations (SRS §16)

Answers and fetch responses include one **deduplicated citation per contributing
dataset**, associated with every field it produced. Citations are generated only
for datasets that actually returned a value — never fabricated for unavailable
data (SRS §16.14).

## Regional availability (SRS §13.23)

Outside the pilot region, state-specific fields return `null` with a
`null_meaning`, while core national datasets (terrain, climate, land cover,
natural hazards, administrative hierarchy) continue to function where coverage
exists.

## Caching / TTL (SRS §13.21)

Each field defines a TTL in the catalog. Frequently requested fetch responses and
static metadata are cached subject to that TTL; static administrative data is
cached longer than volatile layers.
