"use client";

import Link from "next/link";
import { ArrowRight, Boxes, Globe2, MapPinned } from "lucide-react";
import { useState } from "react";

import { LayerBadge } from "@/components/badges";
import { EmptyState, ErrorState, LoadingBlock } from "@/components/feedback";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { usePresets } from "@/hooks/useMeta";
import { cn } from "@/lib/utils";
import { humanize } from "@/lib/format";
import type { PresetObject } from "@/types";

/**
 * Preset Explorer (SRS §12.11). Browses /meta/presets — each preset's fields,
 * layers, and the states it is fully supported in are all read from the API.
 * A preset can be launched directly in the Fetch page.
 */
export function PresetExplorer({ className }: { className?: string }) {
  const { data, isLoading, isError, error, refetch } = usePresets();
  const [query, setQuery] = useState("");

  if (isLoading) return <LoadingBlock rows={4} className={className} />;
  if (isError) return <ErrorState error={error} onRetry={refetch} className={className} />;
  if (!data) return null;

  const q = query.trim().toLowerCase();
  const presets = data.presets.filter(
    (p) =>
      !q ||
      p.name.toLowerCase().includes(q) ||
      p.id.toLowerCase().includes(q) ||
      p.description.toLowerCase().includes(q),
  );

  return (
    <div className={cn("space-y-4", className)}>
      <Input
        value={query}
        onChange={(e) => setQuery(e.target.value)}
        placeholder={`Search ${data.count} presets…`}
        aria-label="Search presets"
        className="max-w-sm"
      />
      {presets.length === 0 ? (
        <EmptyState icon={<Boxes className="h-8 w-8" />} title="No presets match your search" />
      ) : (
        <div className="grid gap-3 md:grid-cols-2">
          {presets.map((p) => (
            <PresetCard key={p.id} preset={p} />
          ))}
        </div>
      )}
    </div>
  );
}

function PresetCard({ preset }: { preset: PresetObject }) {
  const nationwide = preset.supported_states.includes("*");
  return (
    <div className="flex flex-col rounded-xl border border-border bg-card/60 p-4">
      <div className="flex items-start justify-between gap-3">
        <div>
          <h3 className="font-semibold">{preset.name}</h3>
          <p className="font-mono text-[11px] text-muted-foreground">{preset.id}</p>
        </div>
        {nationwide ? (
          <span className="inline-flex items-center gap-1 rounded-full border border-success/30 bg-success/10 px-2 py-0.5 text-[11px] font-medium text-success">
            <Globe2 className="h-3 w-3" /> Nationwide
          </span>
        ) : (
          <span
            className="inline-flex items-center gap-1 rounded-full border border-warning/30 bg-warning/10 px-2 py-0.5 text-[11px] font-medium text-warning"
            title={`Supported in: ${preset.supported_states.map(humanize).join(", ") || "—"}`}
          >
            <MapPinned className="h-3 w-3" />
            {preset.supported_states.length
              ? preset.supported_states.map(humanize).join(", ")
              : "Region-limited"}
          </span>
        )}
      </div>

      <p className="mt-1.5 text-sm text-muted-foreground">{preset.description}</p>

      <div className="mt-3 flex flex-wrap gap-1">
        {preset.layers.map((l) => (
          <LayerBadge key={l} layer={l} />
        ))}
      </div>

      <div className="mt-3">
        <p className="mb-1 text-xs font-medium text-muted-foreground">
          {preset.fields.length} fields
        </p>
        <div className="flex flex-wrap gap-1">
          {preset.fields.slice(0, 8).map((f) => (
            <Badge key={f} className="badge-muted font-mono text-[11px]">
              {humanize(f)}
            </Badge>
          ))}
          {preset.fields.length > 8 && (
            <Badge className="badge-muted text-[11px]">+{preset.fields.length - 8} more</Badge>
          )}
        </div>
      </div>

      <div className="mt-4 border-t border-border/60 pt-3">
        <Link
          href={`/fetch?preset=${encodeURIComponent(preset.id)}`}
          className="inline-flex items-center gap-1.5 text-sm font-medium text-brand hover:underline"
        >
          Run in Fetch <ArrowRight className="h-3.5 w-3.5" />
        </Link>
      </div>
    </div>
  );
}
