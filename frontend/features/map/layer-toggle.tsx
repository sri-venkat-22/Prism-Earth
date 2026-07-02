"use client";

import { Layers } from "lucide-react";

import { MAP_LAYERS } from "@/features/map/config";
import { layerMeta } from "@/lib/domain";
import { cn } from "@/lib/utils";
import type { Layer } from "@/types";

/**
 * Single-select layer switcher for the map. Switching the active lens cross-fades
 * the choropleth (handled in MapCanvas) and swaps the legend.
 */
export function LayerToggle({
  active,
  onChange,
  counts,
  names,
}: {
  active: Layer;
  onChange: (id: Layer) => void;
  counts?: Record<string, number>;
  names?: Record<string, string>;
}) {
  return (
    <div className="w-64 rounded-xl border border-border bg-card/95 p-2 shadow-lg backdrop-blur-md">
      <div className="mono-eyebrow flex items-center gap-1.5 px-2 py-2">
        <Layers className="h-3.5 w-3.5" /> Layers
      </div>
      <div className="space-y-0.5">
        {MAP_LAYERS.map((l) => {
          const meta = layerMeta(l.id);
          const Icon = meta.icon;
          const on = active === l.id;
          return (
            <button
              key={l.id}
              type="button"
              onClick={() => onChange(l.id)}
              aria-pressed={on}
              className={cn(
                "flex w-full items-center gap-2.5 rounded-lg px-2.5 py-2 text-left transition-colors",
                on ? "bg-secondary" : "hover:bg-secondary/60",
              )}
            >
              <span
                className="inline-flex h-7 w-7 shrink-0 items-center justify-center rounded-md"
                style={{ background: `${l.color}1f`, color: l.color }}
              >
                <Icon className="h-4 w-4" />
              </span>
              <span className="min-w-0 flex-1">
                <span className="block truncate text-sm font-medium">
                  {names?.[l.id] ?? meta.label}
                </span>
                {counts?.[l.id] != null && (
                  <span className="block text-[11px] text-muted-foreground">
                    {counts[l.id]} fields
                  </span>
                )}
              </span>
              <span
                className={cn(
                  "h-2 w-2 shrink-0 rounded-full ring-2 ring-transparent transition-all",
                  on ? "ring-offset-0" : "opacity-30",
                )}
                style={{ background: l.color }}
              />
            </button>
          );
        })}
      </div>
    </div>
  );
}
