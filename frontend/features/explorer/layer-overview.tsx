"use client";

import { ErrorState, LoadingBlock } from "@/components/feedback";
import { layerMeta } from "@/lib/domain";
import { useLayers } from "@/hooks/useMeta";
import { cn } from "@/lib/utils";

/**
 * Layer visualization: the domain layers from /meta/layers (SRS §13.7). Purely
 * data-driven — layer names, purposes, connectors, and counts come from the API.
 */
export function LayerOverview({ className }: { className?: string }) {
  const { data, isLoading, isError, error, refetch } = useLayers();

  if (isLoading) return <LoadingBlock rows={3} className={className} />;
  if (isError) return <ErrorState error={error} onRetry={refetch} className={className} />;
  if (!data) return null;

  return (
    <div className={cn("grid gap-3 sm:grid-cols-2 lg:grid-cols-3", className)}>
      {data.layers.map((layer) => {
        const meta = layerMeta(layer.id);
        const Icon = meta.icon;
        return (
          <div
            key={layer.id}
            className="lift group relative overflow-hidden rounded-xl border border-border bg-card/60 p-4"
          >
            <span
              aria-hidden
              className="absolute inset-x-0 top-0 h-0.5"
              style={{ background: `hsl(${meta.accent})` }}
            />
            <div className="flex items-center justify-between">
              <span
                className="inline-flex h-9 w-9 items-center justify-center rounded-lg"
                style={{ background: `hsl(${meta.accent} / 0.14)`, color: `hsl(${meta.accent})` }}
              >
                <Icon className="h-5 w-5" aria-hidden />
              </span>
              <span className="text-2xl font-semibold tabular-nums text-muted-foreground">
                {layer.field_count}
              </span>
            </div>
            <h3 className="mt-3 font-semibold">{layer.name}</h3>
            <p className="mt-1 line-clamp-2 text-sm text-muted-foreground">{layer.purpose}</p>
            <p className="mt-2 font-mono text-[11px] text-muted-foreground/80">{layer.connector}</p>
          </div>
        );
      })}
    </div>
  );
}
