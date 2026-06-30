#!/usr/bin/env python3
"""Earth Engine smoke test (SRS §19, Phase 2 DoD #3).

Authenticates with Google Earth Engine using the configured service account
(SRS §19.3) and samples an elevation value at a Telangana coordinate. Prints the
number on success; prints actionable setup guidance if GEE is not configured.

    # Set the service-account credentials first (see docs/google_earth_engine_setup.md):
    export PRISM_EARTH_ENGINE_SERVICE_ACCOUNT="prism-earth-gee@<project>.iam.gserviceaccount.com"
    export PRISM_EARTH_ENGINE_KEY_FILE="/absolute/path/to/key.json"
    export PRISM_EARTH_ENGINE_PROJECT="<project-id>"   # optional

    python scripts/gee_smoke_test.py [LAT] [LNG]
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_REPO_ROOT / "backend"))

from app.core.config import get_settings  # noqa: E402
from app.core.errors import AppError  # noqa: E402
from app.core.logging import configure_logging  # noqa: E402

# Default sample point: Hyderabad, Telangana (the Phase 2 DoD coordinate).
DEFAULT_LAT = 17.385
DEFAULT_LNG = 78.486


def main(lat: float, lng: float) -> int:
    settings = get_settings()
    configure_logging(settings)

    if not settings.earth_engine_configured:
        print(
            "Earth Engine is not configured.\n"
            "Set PRISM_EARTH_ENGINE_SERVICE_ACCOUNT and PRISM_EARTH_ENGINE_KEY_FILE,\n"
            "then re-run. See docs/google_earth_engine_setup.md for the GCP steps.",
            file=sys.stderr,
        )
        return 2

    # Imported here so the smoke test reports config errors before importing ee.
    from app.gee import EarthEngineClient

    try:
        client = EarthEngineClient()  # authenticates (SRS §19.3)
        elevation = client.sample_elevation(lat, lng)
    except AppError as exc:
        print(
            f"Earth Engine smoke test FAILED: {exc.message} ({exc.details})",
            file=sys.stderr,
        )
        return 1

    if elevation is None:
        print(f"No elevation coverage at ({lat}, {lng}).", file=sys.stderr)
        return 1

    print(f"Earth Engine OK — elevation at ({lat}, {lng}) = {elevation:.2f} m")
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Earth Engine elevation smoke test (SRS §19)."
    )
    parser.add_argument(
        "lat", type=float, nargs="?", default=DEFAULT_LAT, help="Latitude (WGS84)"
    )
    parser.add_argument(
        "lng", type=float, nargs="?", default=DEFAULT_LNG, help="Longitude (WGS84)"
    )
    ns = parser.parse_args()
    raise SystemExit(main(ns.lat, ns.lng))
