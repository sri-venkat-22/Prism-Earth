// The six map-relevant domain layers surfaced as choropleth "lenses" on the
// Dashboard. Colors mirror the --layer-* tokens (resolved to hex so MapLibre's
// paint can consume them directly). Layer names/purposes still come from /meta.
import type { Layer } from "@/types";

export interface MapLayerDef {
  id: Layer;
  color: string;
}

export const MAP_LAYERS: MapLayerDef[] = [
  { id: "terrain", color: "#9B763A" },
  { id: "climate", color: "#3E6B95" },
  { id: "land_cover", color: "#4A6B4E" },
  { id: "natural_hazard", color: "#A8452F" },
  { id: "infrastructure", color: "#4B4E8C" },
  { id: "built_environment", color: "#8A4A6B" },
];

export const MAP_LAYER_COLOR: Record<string, string> = Object.fromEntries(
  MAP_LAYERS.map((l) => [l.id, l.color]),
);
