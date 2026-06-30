# Google Earth Engine — Service Account Setup (SRS §19.3)

Prism Earth authenticates to Google Earth Engine (GEE) with a **dedicated Google
Cloud service account** (SRS §19.3). Credentials live only in environment
variables on the backend and are never exposed to the frontend or API consumers.

This guide produces two values the backend needs:

| Env var | Example |
| --- | --- |
| `PRISM_EARTH_ENGINE_SERVICE_ACCOUNT` | `prism-earth-gee@my-project.iam.gserviceaccount.com` |
| `PRISM_EARTH_ENGINE_KEY_FILE` | `/secrets/prism-earth-gee.json` |
| `PRISM_EARTH_ENGINE_PROJECT` (optional) | `my-project` |

## Steps

1. **Create / pick a Google Cloud project.**
   <https://console.cloud.google.com/projectcreate>. Note the **Project ID**
   (not the display name).

2. **Enable the required APIs** under *APIs & Services → Library*:
   - **Google Earth Engine API**
   - **Cloud Resource Manager API**

3. **Register the project for Earth Engine.** Sign in at
   <https://code.earthengine.google.com> once with the project selected, or
   register it at <https://console.cloud.google.com/earth-engine>. (Non-commercial
   use is free; commercial use needs an Earth Engine plan.)

4. **Create a service account** under *IAM & Admin → Service Accounts*:
   - Name: `prism-earth-gee`
   - Grant **both** roles (the second is required — without it Earth Engine
     returns `403 PERMISSION_DENIED` on `serviceusage.services.use`):
     - **Earth Engine Resource Viewer** (`roles/earthengine.viewer`) — read access for point sampling.
     - **Service Usage Consumer** (`roles/serviceusage.serviceUsageConsumer`) — lets the SA use the project's enabled APIs.
   - Copy the service-account email — that is `PRISM_EARTH_ENGINE_SERVICE_ACCOUNT`.

5. **Create a JSON key** for the service account:
   *Keys → Add key → Create new key → JSON*. Move it into the repo's gitignored
   `secrets/` directory (e.g. `secrets/prism-earth-gee.json`) and `chmod 600` it
   — never commit it. That path is `PRISM_EARTH_ENGINE_KEY_FILE`.

6. **Allow-list the service account for Earth Engine** at
   <https://signup.earthengine.google.com/#!/service_accounts> — paste the
   service-account email and submit. This is required before the SA can call EE.

## Configure and smoke-test

```bash
export PRISM_EARTH_ENGINE_SERVICE_ACCOUNT="prism-earth-gee@my-project.iam.gserviceaccount.com"
export PRISM_EARTH_ENGINE_KEY_FILE="/secrets/prism-earth-gee.json"
export PRISM_EARTH_ENGINE_PROJECT="my-project"   # optional but recommended

python scripts/gee_smoke_test.py            # samples elevation at Hyderabad (17.385, 78.486)
# → Earth Engine OK — elevation at (17.385, 78.486) = 5xx.xx m
```

A successful run prints an elevation number (SRS §19, Phase 2 DoD #3). If the
service account is not yet allow-listed you will see an authentication error from
step 6 — re-check that submission.

## Notes

- The supported datasets (Sentinel-2, TerraClimate, JRC Global Surface Water,
  Copernicus DEM, MODIS, VIIRS) are registered in
  [`backend/app/gee/datasets.py`](../backend/app/gee/datasets.py) (SRS §19.4).
- The smoke test samples `USGS/SRTMGL1_003` (always available); CartoDEM /
  Copernicus DEM are the production elevation sources.
- Never commit the JSON key. In production, mount it from a secrets manager.
