# datasets/

Dataset isolation (SRS §10 principles, §24). Raw and processed geospatial data
live here, separated from application code. Large binaries are **not** committed
(see root `.gitignore`); only small metadata and `.gitkeep` placeholders are.

```
telangana/   pilot-region source data (boundaries, flood, infra) — Phase 2
raster/       raster datasets (DEM, NDVI, …)  [git-ignored]
vector/       vector datasets (admin boundaries, …)  [git-ignored]
metadata/     dataset metadata / catalogs
```

Phase 0 is empty. The Telangana seed (`scripts/seed_telangana.py`) populates
these in Phase 2.
