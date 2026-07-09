# datasets/

Dataset isolation (SRS §10 principles, §24). Raw and processed geospatial data
live here, separated from application code. Large binaries are **not** committed
(see root `.gitignore`); only small metadata and `.gitkeep` placeholders are.

```
telangana/   pilot-region seed fixtures (boundaries, waterbodies, infra, sample parcels)
_cache/      downloaded upstream sources (parquet/PBF)  [git-ignored]
raster/      raster datasets (DEM, NDVI, …)  [git-ignored]
vector/      vector datasets (admin boundaries, …)  [git-ignored]
metadata/    dataset metadata / catalogs
```

## telangana/ — committed vs. regenerated

**Committed** (small, reviewed in git): `state`, `districts`, `mandals`,
`municipalities`, `wards`, `roads`, `railways`, `transmission_lines`,
`substations`, `water_bodies` GeoJSON, plus the provenance records
`ADMIN_PROVENANCE.json` / `OSM_PROVENANCE.json`.

**Regenerated, not committed** (git-ignored): `villages.geojson` (~32 MB,
~10.8k SoI village polygons). Large-file strategy decision: **regenerate on
demand from pinned upstream sources — no Git LFS.** LFS would add quota cost
and a second fetch mechanism for a file that is fully reproducible; the
generator script is the single source of truth for how it is built.

The seed (`scripts/seed_telangana.py`) treats a missing fixture as an empty
layer, so a **fresh checkout works without regenerating**: committed layers are
seeded, and fields backed by absent layers (e.g. `village_name`) resolve to
typed nulls until you regenerate.

Regenerate the boundary fixtures (needs GDAL's `ogr2ogr` with the Parquet
driver on PATH; downloads ~0.9 GB to `datasets/_cache/` on first run):

```bash
python scripts/fetch_telangana_admin.py
```

The upstream source revision is **pinned**: the script verifies the SHA-256 of
each downloaded Survey of India / SBM parquet against the digests recorded in
`_EXPECTED_SHA256` (see `scripts/fetch_telangana_admin.py`) and refuses to
build from a silently re-published upstream asset. Update the pins (and
`ADMIN_PROVENANCE.json`) deliberately when adopting a new upstream release.

OSM-derived infrastructure/waterbody fixtures are regenerated the same way by
`scripts/fetch_telangana_osm.py` (provenance in `OSM_PROVENANCE.json`).

`telangana/parcels.geojson` is a **hand-authored, non-authoritative dev
fixture** (there is no bulk Bhu Bharati cadastral source without a government
data-sharing agreement). It is seeded only when `TERRA_ENABLE_DEV_FIXTURES=true`
— never in production.
