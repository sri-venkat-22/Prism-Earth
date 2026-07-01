#!/usr/bin/env python3
"""Build real Telangana infrastructure fixtures from OpenStreetMap (SRS §18.7).

Replaces the placeholder roads/railways/substations/transmission-lines/water-body
fixtures in ``datasets/telangana/`` with real OpenStreetMap data, reshaped into
the exact GeoJSON the existing seed (``scripts/seed_telangana.py``) expects. No
application code changes — infrastructure is configuration/data, swapped through
the same ingestion path used for the real admin boundaries (SRS §20.7, §21.3).

Source & method
----------------
The public Overpass API (a shared, free query service) was evaluated first but
found unreliable in practice (both reachable public backends returned "server
too busy" under a state-sized query when this script was developed). Instead,
this script downloads Geofabrik's **Southern Zone** OSM extract — a static file
over a CDN, not a shared query service — and filters/clips it locally with
``ogr2ogr`` (GDAL's OSM driver):

    https://download.geofabrik.de/asia/india/southern-zone-latest.osm.pbf (~550 MB)

The Southern Zone covers Telangana plus neighbouring states; each layer is
clipped to Telangana's real boundary (``datasets/telangana/state.geojson``,
itself real Survey of India data from ``fetch_telangana_admin.py``) directly in
the ``ogr2ogr`` call, so no separate boundary source is needed and no
out-of-state features reach the output.

GDAL's default ``osmconf.ini`` does not expose the ``power`` or ``voltage`` tags
as queryable fields (confirmed by inspecting the installed config) — this script
writes a custom one, and adds ``power`` to ``closed_ways_are_polygons`` so a
substation mapped as a closed way (a compound boundary) lands in the
``multipolygons`` layer rather than as an unhelpful closed line.

What it produces (in ``datasets/telangana/``)
---------------------------------------------
- ``roads.geojson``              — motorway/trunk → ``national_highway``,
  primary/secondary → ``state_highway``. ``{name, road_class}``.
- ``railways.geojson``           — ``railway=rail`` ways. ``{name}``.
- ``substations.geojson``        — ``power=substation`` nodes, plus the
  centroid of any mapped as a compound (way/polygon). ``{name}``.
- ``transmission_lines.geojson`` — ``power=line`` ways; ``voltage`` (volts,
  sometimes a ``;``-separated multi-circuit list) parsed to ``voltage_kv``.
  ``{name, voltage_kv}``.
- ``water_bodies.geojson``       — ``natural=water`` closed ways only (OSM
  multipolygon *relations*, used for the largest/most complex lakes, are not
  reassembled — a deliberate scope limit; simple closed ways cover the large
  majority of mapped waterbodies). ``{name, kind}`` (``kind`` from the OSM
  ``water=*`` sub-tag, e.g. lake/reservoir/pond).

Every OSM way becomes its own feature/row (a single named road is often split
into many short ways in OSM) — expect substantially more rows than the
placeholder fixtures; the nearest-neighbour queries this feeds work per-row
regardless.

Requirements: ``ogr2ogr`` (GDAL with the OSM driver) on PATH, and ``shapely``
(already a backend dependency). Run from the repo root:

    python scripts/fetch_telangana_osm.py
    python scripts/fetch_telangana_osm.py --cache-dir /path/to/pbf
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

from shapely.geometry import MultiPolygon, mapping, shape
from shapely.geometry.base import BaseGeometry

_REPO_ROOT = Path(__file__).resolve().parents[1]
_SEED_DIR = _REPO_ROOT / "datasets" / "telangana"
_DEFAULT_CACHE = _REPO_ROOT / "datasets" / "_cache"
_STATE_BOUNDARY = _SEED_DIR / "state.geojson"

_PBF_URL = "https://download.geofabrik.de/asia/india/southern-zone-latest.osm.pbf"
_PBF_NAME = "southern-zone-latest.osm.pbf"

# GDAL's default osmconf.ini (checked on this machine, GDAL 3.13) does not
# expose `power`/`voltage` as fields in any layer, and does not treat closed
# `power=*` ways as polygons. This custom config adds both, and trims the
# per-layer attribute lists to just what the seed schemas need.
_OSMCONF = """\
[general]
closed_ways_are_polygons=aeroway,amenity,boundary,building,craft,geological,historic,landuse,leisure,military,natural,office,place,shop,sport,tourism,power,highway=platform,public_transport=platform

[points]
osm_id=yes
osm_version=no
osm_timestamp=no
osm_uid=no
osm_user=no
osm_changeset=no
attributes=name,power,ref

[lines]
osm_id=yes
osm_version=no
osm_timestamp=no
osm_uid=no
osm_user=no
osm_changeset=no
attributes=name,highway,railway,power,ref,voltage

[multipolygons]
osm_id=yes
osm_version=no
osm_timestamp=no
osm_uid=no
osm_user=no
osm_changeset=no
attributes=name,natural,water,power

[multilinestrings]
osm_id=yes
attributes=name,type

[other_relations]
osm_id=yes
attributes=name,type
"""

_HIGHWAY_TO_CLASS = {
    "motorway": "national_highway",
    "trunk": "national_highway",
    "primary": "state_highway",
    "secondary": "state_highway",
}

_PROVENANCE = {
    "roads": {
        "dataset": "OpenStreetMap",
        "tags": "highway=motorway/trunk/primary/secondary",
    },
    "railways": {"dataset": "OpenStreetMap", "tags": "railway=rail"},
    "substations": {"dataset": "OpenStreetMap", "tags": "power=substation"},
    "transmission_lines": {"dataset": "OpenStreetMap", "tags": "power=line"},
    "water_bodies": {
        "dataset": "OpenStreetMap",
        "tags": "natural=water (closed ways only)",
    },
    "source": "Geofabrik Southern Zone extract, clipped to Telangana",
    "source_url": "https://download.geofabrik.de/asia/india/southern-zone.html",
    "license": "ODbL — © OpenStreetMap contributors",
}


def _download(cache_dir: Path) -> Path:
    cache_dir.mkdir(parents=True, exist_ok=True)
    dest = cache_dir / _PBF_NAME
    if dest.exists() and dest.stat().st_size > 100_000_000:
        print(f"  cached  {_PBF_NAME} ({dest.stat().st_size / 1e6:.0f} MB)")
        return dest
    print(f"  fetch   {_PBF_NAME} (~550 MB, one-time)…")
    subprocess.run(
        ["curl", "-sSL", "--fail", "-o", str(dest), _PBF_URL], check=True, timeout=1800
    )
    print(f"  done    {dest.stat().st_size / 1e6:.0f} MB")
    return dest


def _ogr_extract(
    pbf_path: Path, osmconf_path: Path, layer: str, where: str, out_path: Path
) -> list[dict[str, Any]]:
    """Run ogr2ogr: filter by tag, clip to Telangana, emit GeoJSON. Returns features."""
    out_path.unlink(missing_ok=True)  # the GeoJSON driver can't -overwrite in place
    cmd = [
        "ogr2ogr",
        "-f",
        "GeoJSON",
        "-t_srs",
        "EPSG:4326",
        "-oo",
        f"CONFIG_FILE={osmconf_path}",
        "-clipsrc",
        str(_STATE_BOUNDARY),
        "-where",
        where,
        str(out_path),
        str(pbf_path),
        layer,
    ]
    subprocess.run(cmd, check=True, capture_output=True, timeout=900)
    if not out_path.exists():
        return []
    return json.loads(out_path.read_text(encoding="utf-8")).get("features", [])


def _feature(geom: BaseGeometry, properties: dict[str, Any]) -> dict[str, Any]:
    return {"type": "Feature", "properties": properties, "geometry": mapping(geom)}


def _polygonal_multipolygon(geom: BaseGeometry) -> MultiPolygon | None:
    """Coerce to a MultiPolygon of just the polygonal parts, or ``None`` if none.

    Mirrors ``fetch_telangana_admin.py``'s helper of the same purpose: clipping
    (here, ``-clipsrc``) can emit a GeometryCollection mixing polygons with
    degenerate slivers where the boundary is tangent to a feature; the
    MULTIPOLYGON column rejects those. Unlike the admin script (which raises —
    boundaries must not silently lose area), a water body missing its polygonal
    remainder after clipping is skipped rather than failing the whole import.
    """
    parts: list[BaseGeometry] = []

    def _collect(g: BaseGeometry) -> None:
        if g.is_empty:
            return
        if g.geom_type == "Polygon":
            parts.append(g)
        elif g.geom_type == "MultiPolygon":
            parts.extend(g.geoms)
        elif g.geom_type == "GeometryCollection":
            for sub in g.geoms:
                _collect(sub)

    _collect(geom)
    return MultiPolygon(parts) if parts else None


def _write(name: str, features: list[dict[str, Any]]) -> None:
    path = _SEED_DIR / f"{name}.geojson"
    payload = {"type": "FeatureCollection", "features": features}
    path.write_text(json.dumps(payload), encoding="utf-8")
    print(
        f"  wrote   {name}.geojson  ({len(features)} features, {path.stat().st_size / 1e6:.2f} MB)"
    )


def _parse_voltage_kv(raw: str | None) -> int | None:
    """OSM ``voltage`` is volts, sometimes a ';'-separated multi-circuit list."""
    if not raw:
        return None
    first = raw.split(";")[0].strip()
    try:
        return round(float(first) / 1000.0)
    except ValueError:
        return None


def _line_features(
    geom: BaseGeometry, properties: dict[str, Any]
) -> list[dict[str, Any]]:
    """One feature per LineString part, for the strictly-LINESTRING columns.

    ``-clipsrc`` can cut a single OSM way into disjoint pieces where it crosses
    in and out of the Telangana boundary (common near the state border); GDAL
    then emits one MultiLineString feature for that way. The ``road`` /
    ``railway`` / ``transmission_line`` tables are LINESTRING, not
    MULTILINESTRING, so each part becomes its own row (same properties).
    """
    if geom.geom_type == "LineString":
        return [_feature(geom, properties)]
    if geom.geom_type == "MultiLineString":
        return [_feature(part, properties) for part in geom.geoms]
    return []  # pragma: no cover - defensive; the `lines` layer yields only these two


def _build_roads(pbf: Path, osmconf: Path, cache_dir: Path) -> list[dict[str, Any]]:
    classes = "'" + "','".join(_HIGHWAY_TO_CLASS) + "'"
    raw = _ogr_extract(
        pbf,
        osmconf,
        "lines",
        f"highway IN ({classes})",
        cache_dir / "_roads_raw.geojson",
    )
    features = []
    for feat in raw:
        props = feat["properties"]
        highway = props.get("highway")
        road_class = _HIGHWAY_TO_CLASS.get(highway)
        if road_class is None:
            continue
        name = props.get("ref") or props.get("name")
        features.extend(
            _line_features(
                shape(feat["geometry"]), {"name": name, "road_class": road_class}
            )
        )
    return features


def _build_railways(pbf: Path, osmconf: Path, cache_dir: Path) -> list[dict[str, Any]]:
    raw = _ogr_extract(
        pbf, osmconf, "lines", "railway = 'rail'", cache_dir / "_railways_raw.geojson"
    )
    features = []
    for f in raw:
        features.extend(
            _line_features(shape(f["geometry"]), {"name": f["properties"].get("name")})
        )
    return features


def _build_substations(
    pbf: Path, osmconf: Path, cache_dir: Path
) -> list[dict[str, Any]]:
    points = _ogr_extract(
        pbf,
        osmconf,
        "points",
        "power = 'substation'",
        cache_dir / "_substations_pts.geojson",
    )
    polys = _ogr_extract(
        pbf,
        osmconf,
        "multipolygons",
        "power = 'substation'",
        cache_dir / "_substations_poly.geojson",
    )
    features = [
        _feature(shape(f["geometry"]), {"name": f["properties"].get("name")})
        for f in points
    ]
    for f in polys:
        centroid = shape(f["geometry"]).centroid
        features.append(_feature(centroid, {"name": f["properties"].get("name")}))
    return features


def _build_transmission_lines(
    pbf: Path, osmconf: Path, cache_dir: Path
) -> list[dict[str, Any]]:
    raw = _ogr_extract(
        pbf, osmconf, "lines", "power = 'line'", cache_dir / "_translines_raw.geojson"
    )
    features = []
    for feat in raw:
        props = feat["properties"]
        features.extend(
            _line_features(
                shape(feat["geometry"]),
                {
                    "name": props.get("name"),
                    "voltage_kv": _parse_voltage_kv(props.get("voltage")),
                },
            )
        )
    return features


def _build_water_bodies(
    pbf: Path, osmconf: Path, cache_dir: Path
) -> list[dict[str, Any]]:
    raw = _ogr_extract(
        pbf,
        osmconf,
        "multipolygons",
        "natural = 'water'",
        cache_dir / "_water_raw.geojson",
    )
    features = []
    for feat in raw:
        props = feat["properties"]
        geom = _polygonal_multipolygon(shape(feat["geometry"]))
        if geom is None:
            continue  # clipping produced no polygonal remainder — skip
        features.append(
            _feature(
                geom, {"name": props.get("name"), "kind": props.get("water") or "water"}
            )
        )
    return features


def build(cache_dir: Path) -> None:
    if not _STATE_BOUNDARY.exists():
        raise SystemExit(
            f"error: {_STATE_BOUNDARY} not found. Run scripts/fetch_telangana_admin.py first "
            "(this script clips OSM data to that real boundary)."
        )

    print("Downloading Geofabrik Southern Zone extract…")
    pbf = _download(cache_dir)

    osmconf = cache_dir / "telangana_osmconf.ini"
    osmconf.write_text(_OSMCONF, encoding="utf-8")

    print("Extracting roads…")
    roads = _build_roads(pbf, osmconf, cache_dir)
    print("Extracting railways…")
    railways = _build_railways(pbf, osmconf, cache_dir)
    print("Extracting substations…")
    substations = _build_substations(pbf, osmconf, cache_dir)
    print("Extracting transmission lines…")
    transmission_lines = _build_transmission_lines(pbf, osmconf, cache_dir)
    print("Extracting water bodies…")
    water_bodies = _build_water_bodies(pbf, osmconf, cache_dir)

    print(f"Writing fixtures to {_SEED_DIR}…")
    _write("roads", roads)
    _write("railways", railways)
    _write("substations", substations)
    _write("transmission_lines", transmission_lines)
    _write("water_bodies", water_bodies)

    (_SEED_DIR / "OSM_PROVENANCE.json").write_text(
        json.dumps(
            {
                **_PROVENANCE,
                "counts": {
                    "roads": len(roads),
                    "railways": len(railways),
                    "substations": len(substations),
                    "transmission_lines": len(transmission_lines),
                    "water_bodies": len(water_bodies),
                },
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    print(
        f"Done. {len(roads)} roads, {len(railways)} railways, {len(substations)} substations, "
        f"{len(transmission_lines)} transmission lines, {len(water_bodies)} water bodies."
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--cache-dir",
        type=Path,
        default=_DEFAULT_CACHE,
        help="Where to cache the downloaded PBF and intermediate extracts.",
    )
    args = parser.parse_args()
    try:
        build(args.cache_dir)
    except FileNotFoundError as exc:  # ogr2ogr missing
        print(
            f"error: {exc}. Is GDAL (ogr2ogr) installed and on PATH?", file=sys.stderr
        )
        raise SystemExit(1) from exc
    except subprocess.CalledProcessError as exc:
        print(
            f"error: {exc.cmd} failed:\n{exc.stderr.decode(errors='replace')}",
            file=sys.stderr,
        )
        raise SystemExit(1) from exc


if __name__ == "__main__":
    main()
