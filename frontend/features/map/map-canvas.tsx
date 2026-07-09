"use client";

import maplibregl, { type Map as MLMap } from "maplibre-gl";
import { useEffect, useRef } from "react";

import "maplibre-gl/dist/maplibre-gl.css";

export interface SelectedRegion {
  district: string;
  centroid: [number, number];
}

// Keyless OpenFreeMap "Positron" vector style (OSM data, OpenMapTiles schema).
// Free for commercial use, no registration/API key, and it serves its own
// glyphs — including the "Noto Sans Regular" stack the district labels use.
// (CARTO's hosted basemap tiles require an enterprise license for commercial
// products, so they are deliberately not used here.)
const STYLE_URL = "https://tiles.openfreemap.org/styles/positron";

// The hosted style injects its own "OpenFreeMap © OpenMapTiles Data from
// OpenStreetMap" credit at runtime; only the Survey of India credit for the
// district overlay served from /public needs attaching here.
const ATTRIBUTION = "District boundaries © Survey of India";

// Warm the basemap to the app's cream background so the map sits inside the
// paper chrome instead of reading as a cold gray artifact.
const CREAM_BG = "#F8F6EE";

const TELANGANA_CENTER: [number, number] = [79.1, 17.9];
const TELANGANA_BOUNDS: [[number, number], [number, number]] = [
  [76.5, 15.4],
  [82.6, 20.6],
];
const GEOJSON_URL = "/telangana-districts.geojson";

/** Adds the district source, choropleth/outline/label layers, and interactions.
 *  Idempotent, so it is safe under React StrictMode's double-invoke in dev. */
function addDistrictLayers(map: MLMap, accent: string, onSelect: (r: SelectedRegion) => void) {
  if (map.getSource("districts")) return;
  map.addSource("districts", { type: "geojson", data: GEOJSON_URL, generateId: true });

  map.addLayer({
    id: "district-fill",
    type: "fill",
    source: "districts",
    paint: {
      "fill-color": accent,
      "fill-opacity": ["case", ["boolean", ["feature-state", "hover"], false], 0.5, 0.28],
      "fill-opacity-transition": { duration: 500, delay: 0 },
      "fill-color-transition": { duration: 500, delay: 0 },
    },
  });

  map.addLayer({
    id: "district-selected",
    type: "fill",
    source: "districts",
    filter: ["==", ["get", "district"], ""],
    paint: { "fill-color": accent, "fill-opacity": 0.55 },
  });

  map.addLayer({
    id: "district-outline",
    type: "line",
    source: "districts",
    paint: {
      "line-color": "#16140F",
      "line-width": ["case", ["boolean", ["feature-state", "hover"], false], 1.6, 0.8],
      "line-opacity": 0.35,
    },
  });

  map.addLayer({
    id: "district-label",
    type: "symbol",
    source: "districts",
    layout: {
      "text-field": ["get", "district"],
      "text-font": ["Noto Sans Regular"],
      "text-size": 12,
      "text-transform": "uppercase",
      "text-letter-spacing": 0.08,
    },
    paint: {
      "text-color": "#16140F",
      "text-halo-color": "#F8F6EE",
      "text-halo-width": 1.4,
    },
  });

  let hovered: number | string | null = null;
  const setHover = (id: number | string | null) => {
    if (hovered !== null)
      map.setFeatureState({ source: "districts", id: hovered }, { hover: false });
    hovered = id;
    if (id !== null) map.setFeatureState({ source: "districts", id }, { hover: true });
  };

  map.on("mousemove", "district-fill", (e) => {
    map.getCanvas().style.cursor = "pointer";
    const f = e.features?.[0];
    if (f && f.id !== undefined) setHover(f.id);
  });
  map.on("mouseleave", "district-fill", () => {
    map.getCanvas().style.cursor = "";
    setHover(null);
  });
  map.on("click", "district-fill", (e) => {
    const f = e.features?.[0];
    if (!f) return;
    const props = f.properties as { district?: string; centroid?: string | number[] };
    const district = props.district ?? "Unknown";
    let centroid: [number, number] = [e.lngLat.lng, e.lngLat.lat];
    const raw = props.centroid; // arrays survive GeoJSON but MapLibre may stringify them
    const arr = typeof raw === "string" ? safeParse(raw) : (raw as number[] | undefined);
    if (Array.isArray(arr) && arr.length === 2) centroid = [arr[0], arr[1]];
    onSelect({ district, centroid });
  });
}

export default function MapCanvas({
  accent,
  selectedDistrict,
  onSelectRegion,
}: {
  accent: string;
  selectedDistrict: string | null;
  onSelectRegion: (region: SelectedRegion) => void;
}) {
  const containerRef = useRef<HTMLDivElement>(null);
  const mapRef = useRef<MLMap | null>(null);
  const loadedRef = useRef(false);
  const accentRef = useRef(accent);
  accentRef.current = accent;
  const onSelectRef = useRef(onSelectRegion);
  onSelectRef.current = onSelectRegion;

  useEffect(() => {
    if (!containerRef.current || mapRef.current) return;
    const map = new maplibregl.Map({
      container: containerRef.current,
      style: STYLE_URL,
      center: TELANGANA_CENTER,
      zoom: 6.4,
      minZoom: 5.5,
      maxZoom: 11,
      maxBounds: TELANGANA_BOUNDS,
      // No `compact` override: MapLibre keeps the attribution text visible on
      // wide viewports (per OSM attribution guidance) and collapses it only on
      // small screens.
      attributionControl: { customAttribution: ATTRIBUTION },
      dragRotate: false,
      pitchWithRotate: false,
      canvasContextAttributes: { preserveDrawingBuffer: true },
    });
    mapRef.current = map;
    map.addControl(new maplibregl.NavigationControl({ showCompass: false }), "bottom-right");

    const init = () => {
      if (map.getLayer("background")) {
        map.setPaintProperty("background", "background-color", CREAM_BG);
      }
      addDistrictLayers(map, accentRef.current, (r) => onSelectRef.current(r));
      loadedRef.current = true;
    };
    if (map.isStyleLoaded()) init();
    else map.on("load", init);

    return () => {
      map.remove();
      mapRef.current = null;
      loadedRef.current = false;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Recolor on active-layer change (cross-fades via paint transitions).
  useEffect(() => {
    const map = mapRef.current;
    if (!map || !loadedRef.current) return;
    if (map.getLayer("district-fill")) map.setPaintProperty("district-fill", "fill-color", accent);
    if (map.getLayer("district-selected"))
      map.setPaintProperty("district-selected", "fill-color", accent);
  }, [accent]);

  // Reflect selection.
  useEffect(() => {
    const map = mapRef.current;
    if (!map || !loadedRef.current || !map.getLayer("district-selected")) return;
    map.setFilter("district-selected", ["==", ["get", "district"], selectedDistrict ?? ""]);
  }, [selectedDistrict]);

  // Size with h/w (not inset-0): maplibre-gl.css forces `.maplibregl-map` to
  // position:relative, which would defeat offset-based sizing.
  return <div ref={containerRef} className="h-full w-full" aria-label="Telangana map" />;
}

function safeParse(s: string): number[] | undefined {
  try {
    const v = JSON.parse(s);
    return Array.isArray(v) ? v : undefined;
  } catch {
    return undefined;
  }
}
