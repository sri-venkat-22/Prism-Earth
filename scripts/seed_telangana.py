#!/usr/bin/env python3
"""Seed the Telangana pilot region into PostGIS (SRS §24.4 Spatial Data Seed).

Loads the committed GeoJSON boundary/hazard/infrastructure fixtures from
``datasets/telangana/`` into the ``admin``, ``hazards``, ``infrastructure``, and
``cadastral`` schemas, and mirrors the Metadata Catalog + State Registry into the
``metadata`` registry tables (SRS §22.3). Repeatable: by default it truncates the
seed-owned tables and reloads, so re-running is deterministic.

Usage (from the repo root, with PRISM_POSTGRES_* pointing at the database):

    python scripts/seed_telangana.py            # truncate + reseed
    python scripts/seed_telangana.py --no-truncate
    python scripts/seed_telangana.py --dry-run  # validate fixtures only
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path
from typing import Any

# Make the backend package importable when run as `python scripts/seed_telangana.py`.
_REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_REPO_ROOT / "backend"))

from app.config.loader import load_datasets_config  # noqa: E402
from app.core.config import get_settings  # noqa: E402
from app.core.database import dispose_engine, get_sessionmaker  # noqa: E402
from app.core.logging import configure_logging, get_logger  # noqa: E402
from app.metadata import get_catalog, get_state_registry  # noqa: E402
from app.models import (  # noqa: E402
    ConnectorRow,
    DatasetRow,
    District,
    FieldRow,
    FloodHazardZone,
    HistoricalFlood,
    LayerRow,
    Mandal,
    Municipality,
    Parcel,
    PresetField,
    PresetRow,
    Railway,
    Road,
    State,
    StateRow,
    Substation,
    TransmissionLine,
    Village,
    Ward,
    WaterBody,
)
from geoalchemy2.shape import from_shape  # noqa: E402
from shapely.geometry import MultiPolygon, shape  # noqa: E402
from shapely.geometry.base import BaseGeometry  # noqa: E402
from sqlalchemy import text  # noqa: E402
from sqlalchemy.ext.asyncio import AsyncSession  # noqa: E402

logger = get_logger(__name__)

# Truncated (in this order under CASCADE) before reseeding. Runtime tables —
# provenance, citation, request_log — are intentionally excluded.
_SEED_TABLES = (
    "admin.ward",
    "admin.municipality",
    "admin.village",
    "admin.mandal",
    "admin.district",
    "admin.state",
    "hazards.flood_hazard_zone",
    "hazards.water_body",
    "hazards.historical_flood",
    "infrastructure.road",
    "infrastructure.railway",
    "infrastructure.transmission_line",
    "infrastructure.substation",
    "cadastral.parcel",
    "metadata.preset_field",
    "metadata.preset",
    "metadata.field",
    "metadata.dataset",
    "metadata.connector",
    "metadata.layer",
    "metadata.state",
)


def _seed_dir() -> Path:
    return get_settings().seed_data_dir


def _load_features(name: str) -> list[tuple[dict[str, Any], BaseGeometry]]:
    """Load ``<seed_dir>/<name>.geojson`` as (properties, shapely geometry) pairs."""
    path = _seed_dir() / f"{name}.geojson"
    data = json.loads(path.read_text(encoding="utf-8"))
    features = []
    for feat in data.get("features", []):
        geom = shape(feat["geometry"])
        if not geom.is_valid:
            raise ValueError(
                f"Invalid geometry in {path.name}: {feat.get('properties')}"
            )
        features.append((feat.get("properties", {}), geom))
    return features


def _multipolygon(geom: BaseGeometry) -> BaseGeometry:
    """Coerce a Polygon to MultiPolygon so it matches the MULTIPOLYGON columns."""
    return MultiPolygon([geom]) if geom.geom_type == "Polygon" else geom


def _geom(geom: BaseGeometry) -> Any:
    """WKBElement in EPSG:4326 for insertion (SRS §20.6)."""
    return from_shape(geom, srid=4326)


# --------------------------------------------------------------------------- #
# Metadata registry mirror (SRS §22.3)                                        #
# --------------------------------------------------------------------------- #
async def _seed_registry(session: AsyncSession) -> dict[str, int]:
    catalog = get_catalog()
    registry = get_state_registry()
    counts: dict[str, int] = {}

    for layer in catalog.layers():
        session.add(
            LayerRow(
                id=layer.id.value,
                name=layer.name,
                purpose=layer.purpose,
                connector=layer.connector,
            )
        )
    await session.flush()  # parents before children (connector → layer FK)
    for layer in catalog.layers():
        session.add(
            ConnectorRow(
                id=layer.connector, name=layer.connector, layer_id=layer.id.value
            )
        )
    counts["layers"] = len(catalog.layers())
    counts["connectors"] = len(catalog.layers())
    await session.flush()

    for key, dataset in (load_datasets_config().get("datasets") or {}).items():
        session.add(
            DatasetRow(
                id=key,
                name=dataset["name"],
                provider=dataset.get("provider"),
                version=dataset.get("version"),
                source_url=dataset.get("source_url"),
                purpose=dataset.get("purpose"),
                crs=dataset.get("crs", "EPSG:4326"),
                ttl=dataset.get("ttl"),
                spatial_resolution=dataset.get("spatial_resolution"),
                temporal_resolution=dataset.get("temporal_resolution"),
                update_frequency=dataset.get("update_frequency"),
                license=dataset.get("license"),
            )
        )
        counts["datasets"] = counts.get("datasets", 0) + 1

    for field in catalog.fields():
        session.add(
            FieldRow(
                id=field.name,
                name=field.name,
                description=field.description,
                layer_id=field.layer.value,
                lifecycle=field.lifecycle.value,
                availability=field.availability.value,
                nullable=field.nullable,
                null_meaning=field.null_meaning,
                source=field.source,
                source_url=field.source_url,
                dataset_ttl=field.dataset_ttl,
                unit=field.unit,
                datatype=field.datatype.value,
                interpretation_hint=field.interpretation_hint,
            )
        )
    counts["fields"] = len(catalog.fields())
    await session.flush()

    for preset in catalog.presets():
        session.add(
            PresetRow(id=preset.id, name=preset.name, description=preset.description)
        )
    await session.flush()
    for preset in catalog.presets():
        for position, field_name in enumerate(preset.fields):
            session.add(
                PresetField(preset_id=preset.id, field_id=field_name, position=position)
            )
    counts["presets"] = len(catalog.presets())

    for state in registry.states():
        bbox = state.bbox
        session.add(
            StateRow(
                id=state.slug,
                code=state.code,
                name=state.name,
                registered=state.registered,
                lifecycle=state.lifecycle,
                min_lat=bbox.min_lat if bbox else None,
                max_lat=bbox.max_lat if bbox else None,
                min_lng=bbox.min_lng if bbox else None,
                max_lng=bbox.max_lng if bbox else None,
            )
        )
    counts["states"] = len(registry.states())
    await session.flush()
    return counts


# --------------------------------------------------------------------------- #
# Spatial layers (SRS §20.4, §24.4)                                           #
# --------------------------------------------------------------------------- #
async def _seed_admin(session: AsyncSession) -> dict[str, int]:
    counts: dict[str, int] = {}

    state_ids: dict[str, int] = {}
    for props, geom in _load_features("state"):
        row = State(
            code=props["code"], name=props["name"], geom=_geom(_multipolygon(geom))
        )
        session.add(row)
        await session.flush()
        state_ids[props["name"]] = row.id
    counts["state"] = len(state_ids)

    district_ids: dict[str, int] = {}
    for props, geom in _load_features("districts"):
        row = District(
            name=props["name"],
            code=props.get("code"),
            state_id=state_ids[props["state"]],
            geom=_geom(_multipolygon(geom)),
        )
        session.add(row)
        await session.flush()
        district_ids[props["name"]] = row.id
    counts["district"] = len(district_ids)

    mandal_ids: dict[str, int] = {}
    for props, geom in _load_features("mandals"):
        row = Mandal(
            name=props["name"],
            code=props.get("code"),
            district_id=district_ids[props["district"]],
            geom=_geom(_multipolygon(geom)),
        )
        session.add(row)
        await session.flush()
        mandal_ids[props["name"]] = row.id
    counts["mandal"] = len(mandal_ids)

    village_count = 0
    for props, geom in _load_features("villages"):
        session.add(
            Village(
                name=props["name"],
                code=props.get("code"),
                mandal_id=mandal_ids[props["mandal"]],
                geom=_geom(_multipolygon(geom)),
            )
        )
        village_count += 1
    counts["village"] = village_count

    municipality_ids: dict[str, int] = {}
    for props, geom in _load_features("municipalities"):
        row = Municipality(
            name=props["name"],
            district_id=district_ids[props["district"]],
            geom=_geom(_multipolygon(geom)),
        )
        session.add(row)
        await session.flush()
        municipality_ids[props["name"]] = row.id
    counts["municipality"] = len(municipality_ids)

    ward_count = 0
    for props, geom in _load_features("wards"):
        session.add(
            Ward(
                name=props["name"],
                municipality_id=municipality_ids[props["municipality"]],
                geom=_geom(_multipolygon(geom)),
            )
        )
        ward_count += 1
    counts["ward"] = ward_count

    await session.flush()
    return counts


async def _seed_hazards(session: AsyncSession) -> dict[str, int]:
    counts: dict[str, int] = {}
    counts["flood_hazard_zone"] = 0
    for props, geom in _load_features("flood_zones"):
        session.add(
            FloodHazardZone(
                hazard_class=props["hazard_class"],
                name=props.get("name"),
                geom=_geom(_multipolygon(geom)),
            )
        )
        counts["flood_hazard_zone"] += 1
    counts["water_body"] = 0
    for props, geom in _load_features("water_bodies"):
        session.add(
            WaterBody(
                name=props.get("name"),
                kind=props.get("kind"),
                geom=_geom(_multipolygon(geom)),
            )
        )
        counts["water_body"] += 1
    counts["historical_flood"] = 0
    for props, geom in _load_features("historical_floods"):
        session.add(
            HistoricalFlood(
                event_name=props.get("event_name"),
                year=props.get("year"),
                geom=_geom(_multipolygon(geom)),
            )
        )
        counts["historical_flood"] += 1
    await session.flush()
    return counts


async def _seed_infrastructure(session: AsyncSession) -> dict[str, int]:
    counts: dict[str, int] = {}
    counts["road"] = 0
    for props, geom in _load_features("roads"):
        session.add(
            Road(
                name=props.get("name"),
                road_class=props.get("road_class"),
                geom=_geom(geom),
            )
        )
        counts["road"] += 1
    counts["railway"] = 0
    for props, geom in _load_features("railways"):
        session.add(Railway(name=props.get("name"), geom=_geom(geom)))
        counts["railway"] += 1
    counts["transmission_line"] = 0
    for props, geom in _load_features("transmission_lines"):
        session.add(
            TransmissionLine(
                name=props.get("name"),
                voltage_kv=props.get("voltage_kv"),
                geom=_geom(geom),
            )
        )
        counts["transmission_line"] += 1
    counts["substation"] = 0
    for props, geom in _load_features("substations"):
        session.add(Substation(name=props.get("name"), geom=_geom(geom)))
        counts["substation"] += 1
    await session.flush()
    return counts


async def _seed_cadastral(session: AsyncSession) -> dict[str, int]:
    count = 0
    for props, geom in _load_features("parcels"):
        session.add(
            Parcel(
                parcel_id=props["parcel_id"],
                survey_number=props.get("survey_number"),
                zoning=props.get("zoning"),
                ownership_category=props.get("ownership_category"),
                area_sqm=props.get("area_sqm"),
                geom=_geom(geom),
            )
        )
        count += 1
    await session.flush()
    return {"parcel": count}


async def _truncate(session: AsyncSession) -> None:
    tables = ", ".join(_SEED_TABLES)
    await session.execute(text(f"TRUNCATE {tables} RESTART IDENTITY CASCADE"))


async def seed(*, truncate: bool = True, dry_run: bool = False) -> dict[str, int]:
    """Run the full Telangana seed and return per-layer row counts."""
    # Validate every fixture up front (geometry validity) before any writes.
    layers = (
        "state",
        "districts",
        "mandals",
        "villages",
        "municipalities",
        "wards",
        "flood_zones",
        "water_bodies",
        "historical_floods",
        "roads",
        "railways",
        "transmission_lines",
        "substations",
        "parcels",
    )
    for name in layers:
        _load_features(name)

    if dry_run:
        logger.info("seed.dry_run.ok", fixtures=len(layers), seed_dir=str(_seed_dir()))
        return {}

    counts: dict[str, int] = {}
    sessionmaker = get_sessionmaker()
    async with sessionmaker() as session:
        async with session.begin():
            if truncate:
                await _truncate(session)
            counts.update(await _seed_registry(session))
            counts.update(await _seed_admin(session))
            counts.update(await _seed_hazards(session))
            counts.update(await _seed_infrastructure(session))
            counts.update(await _seed_cadastral(session))
    logger.info("seed.complete", **counts)
    return counts


async def _main(args: argparse.Namespace) -> None:
    configure_logging(get_settings())
    try:
        counts = await seed(truncate=not args.no_truncate, dry_run=args.dry_run)
    finally:
        await dispose_engine()
    if not args.dry_run:
        print("Seed complete. Rows inserted:")
        for table, count in counts.items():
            print(f"  {table:<22} {count}")


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Seed the Telangana pilot region (SRS §24.4)."
    )
    parser.add_argument(
        "--no-truncate",
        action="store_true",
        help="Append instead of truncating the seed-owned tables first.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Validate fixtures without writing to the database.",
    )
    return parser.parse_args()


if __name__ == "__main__":
    asyncio.run(_main(_parse_args()))
