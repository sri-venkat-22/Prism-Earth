"use client";

import dynamic from "next/dynamic";
import { useMemo, useState } from "react";

import { LayerToggle } from "@/features/map/layer-toggle";
import { MapLegend } from "@/features/map/map-legend";
import { RegionDetail } from "@/features/map/region-detail";
import { MAP_LAYER_COLOR, MAP_LAYERS } from "@/features/map/config";
import type { SelectedRegion } from "@/features/map/map-canvas";
import { useFields, useLayers } from "@/hooks/useMeta";
import type { Layer } from "@/types";

// MapLibre touches `window`, so load the canvas client-side only.
const MapCanvas = dynamic(() => import("@/features/map/map-canvas"), {
  ssr: false,
  loading: () => <div className="paper-grid absolute inset-0 bg-background" />,
});

export default function DashboardPage() {
  const [activeLayer, setActiveLayer] = useState<Layer>(MAP_LAYERS[0].id);
  const [region, setRegion] = useState<SelectedRegion | null>(null);

  const layers = useLayers();
  // available:true — planned fields are never selectable, and /fetch rejects a
  // selection that includes them (SRS §11.6).
  const layerFields = useFields({ layer: activeLayer, available: true });

  const { counts, names, purpose } = useMemo(() => {
    const list = layers.data?.layers ?? [];
    const counts: Record<string, number> = {};
    const names: Record<string, string> = {};
    let purpose: string | undefined;
    for (const l of list) {
      counts[l.id] = l.field_count;
      names[l.id] = l.name;
      if (l.id === activeLayer) purpose = l.purpose;
    }
    return { counts, names, purpose };
  }, [layers.data, activeLayer]);

  const fieldIds = useMemo(
    () => (layerFields.data?.fields ?? []).map((f) => f.id),
    [layerFields.data],
  );

  return (
    <div className="relative h-[calc(100vh-4rem)] w-full overflow-hidden">
      <MapCanvas
        accent={MAP_LAYER_COLOR[activeLayer]}
        selectedDistrict={region?.district ?? null}
        onSelectRegion={setRegion}
      />

      {/* Title overlay */}
      <div className="pointer-events-none absolute left-3 top-3 z-10 sm:left-4 sm:top-4">
        <div className="pointer-events-auto inline-flex flex-col rounded-xl border border-border bg-card/95 px-4 py-2.5 shadow-lg backdrop-blur-md">
          <span className="mono-eyebrow">Dashboard · Telangana</span>
          <span className="mt-0.5 font-display text-sm font-semibold">Geospatial layers</span>
        </div>
      </div>

      {/* Left control stack */}
      <div className="scrollbar-thin absolute bottom-3 left-3 top-[4.5rem] z-10 flex w-64 flex-col gap-3 overflow-y-auto sm:left-4 sm:top-[5rem]">
        <LayerToggle active={activeLayer} onChange={setActiveLayer} counts={counts} names={names} />
        <MapLegend layer={activeLayer} color={MAP_LAYER_COLOR[activeLayer]} purpose={purpose} />
      </div>

      {/* Region detail */}
      <RegionDetail
        region={region}
        layer={activeLayer}
        fields={fieldIds}
        fieldsLoading={layerFields.isLoading}
        fieldsError={layerFields.isError ? layerFields.error : null}
        onRetryFields={() => layerFields.refetch()}
        onClose={() => setRegion(null)}
      />
    </div>
  );
}
