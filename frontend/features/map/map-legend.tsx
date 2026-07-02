"use client";

import { useFields } from "@/hooks/useMeta";
import { layerMeta } from "@/lib/domain";
import { humanize } from "@/lib/format";
import type { Layer } from "@/types";

/**
 * Legend for the active map layer: colour key, the layer's purpose, and a preview
 * of the fields it contributes — all sourced from /meta at runtime.
 */
export function MapLegend({
  layer,
  color,
  purpose,
}: {
  layer: Layer;
  color: string;
  purpose?: string;
}) {
  const meta = layerMeta(layer);
  const fields = useFields({ layer });
  const sample = (fields.data?.fields ?? []).slice(0, 6);

  return (
    <div className="w-64 rounded-xl border border-border bg-card/95 p-4 shadow-lg backdrop-blur-md">
      <div className="mono-eyebrow mb-2">Legend</div>
      <div className="flex items-center gap-2">
        <span className="h-3 w-3 rounded-sm" style={{ background: color }} />
        <span className="text-sm font-semibold">{meta.label}</span>
      </div>
      {purpose && (
        <p className="mt-1.5 text-[12.5px] leading-relaxed text-muted-foreground">{purpose}</p>
      )}
      {sample.length > 0 && (
        <div className="mt-3">
          <p className="mb-1.5 text-[11px] font-medium text-muted-foreground">Contains</p>
          <div className="flex flex-wrap gap-1">
            {sample.map((f) => (
              <span
                key={f.id}
                className="rounded-md border border-border bg-secondary/60 px-1.5 py-0.5 text-[11px] text-muted-foreground"
              >
                {humanize(f.name)}
              </span>
            ))}
            {(fields.data?.count ?? 0) > sample.length && (
              <span className="rounded-md px-1.5 py-0.5 text-[11px] text-faint">
                +{(fields.data?.count ?? 0) - sample.length} more
              </span>
            )}
          </div>
        </div>
      )}
      <p className="mt-3 text-[11px] text-faint">Click a district to fetch live values here.</p>
    </div>
  );
}
