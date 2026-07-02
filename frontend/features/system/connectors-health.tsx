"use client";

import { CircleCheck, CircleSlash, CircleX, Server } from "lucide-react";

import { LayerBadge } from "@/components/badges";
import { ErrorState, LoadingBlock } from "@/components/feedback";
import { useConnectorsHealth, useHealth } from "@/hooks/useMeta";
import { cn } from "@/lib/utils";
import { humanize } from "@/lib/format";

function statusMeta(status: string) {
  switch (status) {
    case "ok":
      return { icon: CircleCheck, color: "text-success", label: "OK" };
    case "degraded":
      return { icon: CircleSlash, color: "text-warning", label: "Degraded" };
    case "not_configured":
      return { icon: CircleSlash, color: "text-muted-foreground", label: "Not configured" };
    default:
      return { icon: CircleX, color: "text-danger", label: humanize(status) };
  }
}

/** System health: dependency components (SRS §13.16) + per-connector status (§18.12). */
export function ConnectorsHealth({ className }: { className?: string }) {
  const health = useHealth();
  const connectors = useConnectorsHealth();

  return (
    <div className={cn("space-y-6", className)}>
      {/* Dependency components */}
      <section>
        <h2 className="mb-3 flex items-center gap-2 text-sm font-semibold">
          <Server className="h-4 w-4 text-brand" /> Service dependencies
        </h2>
        {health.isLoading ? (
          <LoadingBlock rows={2} />
        ) : health.isError ? (
          <ErrorState error={health.error} onRetry={health.refetch} />
        ) : (
          <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-3">
            {Object.entries(health.data?.components ?? {}).map(([name, comp]) => {
              const m = statusMeta(comp.status);
              const Icon = m.icon;
              return (
                <div
                  key={name}
                  className="flex items-start gap-2 rounded-lg border border-border bg-card/60 p-3"
                >
                  <Icon className={cn("mt-0.5 h-4 w-4 shrink-0", m.color)} />
                  <div className="min-w-0">
                    <p className="font-medium">{humanize(name)}</p>
                    <p className="text-xs text-muted-foreground">{comp.detail ?? m.label}</p>
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </section>

      {/* Connectors */}
      <section>
        <h2 className="mb-3 flex items-center gap-2 text-sm font-semibold">
          <Server className="h-4 w-4 text-brand" /> Connectors
          {connectors.data && (
            <span className="text-xs font-normal text-muted-foreground">
              {connectors.data.count} registered
            </span>
          )}
        </h2>
        {connectors.isLoading ? (
          <LoadingBlock rows={4} />
        ) : connectors.isError ? (
          <ErrorState error={connectors.error} onRetry={connectors.refetch} />
        ) : (
          <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-3">
            {connectors.data?.connectors.map((c) => {
              const m = statusMeta(c.status);
              const Icon = m.icon;
              return (
                <div key={c.name} className="rounded-lg border border-border bg-card/60 p-3">
                  <div className="flex items-center justify-between gap-2">
                    <span className="inline-flex items-center gap-1.5">
                      <Icon className={cn("h-4 w-4", m.color)} />
                      <span className={cn("text-xs font-medium", m.color)}>{m.label}</span>
                    </span>
                    <LayerBadge layer={c.layer} showIcon={false} />
                  </div>
                  <p className="mt-2 truncate font-mono text-xs">{c.name}</p>
                  <p className="text-[11px] text-muted-foreground">
                    {c.servable_fields} servable field{c.servable_fields === 1 ? "" : "s"}
                    {c.detail ? ` · ${c.detail}` : ""}
                  </p>
                </div>
              );
            })}
          </div>
        )}
      </section>
    </div>
  );
}
