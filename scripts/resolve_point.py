#!/usr/bin/env python3
"""Resolve a coordinate to its administrative hierarchy (SRS §15.7).

A thin CLI over :class:`app.services.state_detection.StateDetectionService` used
to demonstrate the spatial backbone against the seeded PostGIS database:

    python scripts/resolve_point.py 17.385 78.486   # Hyderabad → in pilot region
    python scripts/resolve_point.py 19.07 72.87      # Mumbai   → outside Telangana
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_REPO_ROOT / "backend"))

from app.core.config import get_settings  # noqa: E402
from app.core.database import dispose_engine, get_sessionmaker  # noqa: E402
from app.core.logging import configure_logging  # noqa: E402
from app.schemas.spatial import SpatialContext  # noqa: E402
from app.services.state_detection import StateDetectionService  # noqa: E402


def _format(ctx: SpatialContext) -> str:
    lines = [
        f"Coordinate: ({ctx.lat}, {ctx.lng})",
        f"In pilot region: {ctx.in_pilot_region}",
    ]
    if not ctx.resolved:
        lines.append(
            "  → Outside Telangana — region-specific fields return null (SRS §24.1)."
        )
        return "\n".join(lines)
    for label, unit in (
        ("State", ctx.state),
        ("District", ctx.district),
        ("Mandal", ctx.mandal),
        ("Village", ctx.village),
        ("Municipality", ctx.municipality),
        ("Ward", ctx.ward),
    ):
        if unit is not None:
            code = f" [{unit.code}]" if unit.code else ""
            lines.append(f"  {label:<13} {unit.name}{code}")
    return "\n".join(lines)


async def _main(lat: float, lng: float) -> None:
    configure_logging(get_settings())
    sessionmaker = get_sessionmaker()
    try:
        async with sessionmaker() as session:
            service = StateDetectionService(session)
            ctx = await service.resolve(lat, lng)
    finally:
        await dispose_engine()
    print(_format(ctx))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Resolve a coordinate via PostGIS (SRS §15.7)."
    )
    parser.add_argument("lat", type=float, help="Latitude (WGS84)")
    parser.add_argument("lng", type=float, help="Longitude (WGS84)")
    ns = parser.parse_args()
    asyncio.run(_main(ns.lat, ns.lng))
