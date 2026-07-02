"use client";

import { Ban, CheckCircle2, Globe2, Lock, MapPinned, Search } from "lucide-react";
import { useEffect, useMemo, useState } from "react";

import { LayerBadge } from "@/components/badges";
import { ErrorState, LoadingBlock } from "@/components/feedback";
import { StatTile } from "@/components/stat-tile";
import { Input } from "@/components/ui/input";
import { useFields, useResolveState, useStates } from "@/hooks/useMeta";
import { cn } from "@/lib/utils";
import { humanize } from "@/lib/format";
import type { CatalogField } from "@/types";

// Example unregistered regions to demonstrate that region-gated (cadastral)
// fields grey out outside the pilot region. These are just sample inputs.
const EXAMPLE_OUTSIDE = ["Karnataka", "Maharashtra"];

interface Verdict {
  ok: boolean;
  reason: string;
  tone: "ok" | "planned" | "gated";
}

function verdictFor(field: CatalogField, enabled: Set<string>, supported: boolean): Verdict {
  if (field.availability === "planned") {
    return { ok: false, reason: "Planned — not yet retrievable anywhere", tone: "planned" };
  }
  if (field.availability === "nationwide") {
    return { ok: true, reason: "Available nationwide", tone: "ok" };
  }
  // region_gated
  if (enabled.has(field.name) || enabled.has(field.id)) {
    return { ok: true, reason: "Enabled in this region", tone: "ok" };
  }
  return {
    ok: false,
    reason: supported ? "Not enabled in this region" : "Region not supported",
    tone: "gated",
  };
}

/**
 * Regional Availability (SRS §12.12, §13.23). Pick a region and see which fields
 * return values there. Region-gated fields (e.g. cadastral) grey out outside the
 * states that enable them — driven entirely by /meta/states + /meta/fields.
 */
export function RegionalAvailability({ className }: { className?: string }) {
  const { data: states } = useStates();
  const { data: fieldsData, isLoading, isError, error, refetch } = useFields();

  const [region, setRegion] = useState("");
  const [onlyGated, setOnlyGated] = useState(true);

  // Default to the first registered region once states load.
  useEffect(() => {
    if (!region && states?.states.length) setRegion(states.states[0].name);
  }, [states, region]);

  const { data: resolution, isFetching } = useResolveState(region, region.trim().length > 0);

  const enabled = useMemo(() => new Set(resolution?.state?.enabled_fields ?? []), [resolution]);
  const supported = resolution?.supported ?? false;

  const fields = fieldsData?.fields ?? [];
  const shown = onlyGated ? fields.filter((f) => f.availability === "region_gated") : fields;

  // Group by layer for display.
  const groups = useMemo(() => {
    const m = new Map<string, CatalogField[]>();
    for (const f of shown) {
      const l = m.get(f.layer) ?? [];
      l.push(f);
      m.set(f.layer, l);
    }
    return m;
  }, [shown]);

  const gatedFields = fields.filter((f) => f.availability === "region_gated");
  const gatedAvailable = gatedFields.filter((f) => enabled.has(f.name) || enabled.has(f.id)).length;

  if (isLoading) return <LoadingBlock rows={4} className={className} />;
  if (isError) return <ErrorState error={error} onRetry={refetch} className={className} />;

  return (
    <div className={cn("space-y-5", className)}>
      {/* Region selector */}
      <div className="rounded-xl border border-border bg-card/60 p-4">
        <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
          <div className="relative w-full sm:max-w-xs">
            <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
            <Input
              value={region}
              onChange={(e) => setRegion(e.target.value)}
              placeholder="Type a state name…"
              aria-label="Region"
              className="pl-9"
            />
          </div>
          <div className="flex flex-wrap gap-1.5">
            {states?.states.map((s) => (
              <RegionChip
                key={s.slug}
                label={s.name}
                active={region === s.name}
                onClick={() => setRegion(s.name)}
                registered
              />
            ))}
            {EXAMPLE_OUTSIDE.map((name) => (
              <RegionChip
                key={name}
                label={name}
                active={region === name}
                onClick={() => setRegion(name)}
              />
            ))}
          </div>
        </div>

        {/* Resolution banner */}
        {region.trim() && resolution && (
          <div
            className={cn(
              "mt-3 flex items-center gap-2 rounded-lg border px-3 py-2 text-sm",
              supported
                ? "border-success/30 bg-success/10 text-success"
                : "border-warning/30 bg-warning/10 text-warning",
            )}
          >
            {supported ? <CheckCircle2 className="h-4 w-4" /> : <Ban className="h-4 w-4" />}
            <span className="text-foreground/90">{resolution.message}</span>
            {isFetching && (
              <span className="ml-auto text-xs text-muted-foreground">resolving…</span>
            )}
          </div>
        )}
      </div>

      {/* Summary */}
      <div className="grid gap-3 sm:grid-cols-3">
        <StatTile
          label="Nationwide fields"
          value={fields.filter((f) => f.availability === "nationwide").length}
          icon={<Globe2 className="h-4 w-4" />}
          hint="Available at any India coordinate"
          accent="hsl(var(--success))"
        />
        <StatTile
          label="Region-gated here"
          value={`${gatedAvailable} / ${gatedFields.length}`}
          icon={<MapPinned className="h-4 w-4" />}
          hint={supported ? `Enabled in ${humanize(region)}` : "None enabled outside pilot"}
          accent="hsl(var(--warning))"
        />
        <StatTile
          label="Planned fields"
          value={fields.filter((f) => f.availability === "planned").length}
          icon={<Lock className="h-4 w-4" />}
          hint="Not retrievable anywhere yet"
          accent="hsl(var(--muted-foreground))"
        />
      </div>

      {/* Toggle */}
      <label className="inline-flex cursor-pointer items-center gap-2 text-sm text-muted-foreground">
        <input
          type="checkbox"
          checked={onlyGated}
          onChange={(e) => setOnlyGated(e.target.checked)}
          className="h-4 w-4 rounded border-border accent-[hsl(var(--brand))]"
        />
        Show only region-gated fields
      </label>

      {/* Field grid, greyed where unavailable */}
      <div className="space-y-4">
        {[...groups.entries()].map(([layer, list]) => (
          <section key={layer}>
            <div className="mb-2">
              <LayerBadge layer={layer} />
            </div>
            <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-3">
              {list.map((f) => {
                const v = verdictFor(f, enabled, supported);
                return (
                  <div
                    key={f.id}
                    className={cn(
                      "flex items-start justify-between gap-2 rounded-lg border p-3 transition-opacity",
                      v.ok
                        ? "border-border bg-card/60"
                        : "border-dashed border-border bg-muted/20 opacity-55",
                    )}
                    title={v.reason}
                  >
                    <div className="min-w-0">
                      <p className="truncate text-sm font-medium">{humanize(f.name)}</p>
                      <p className="mt-0.5 text-[11px] text-muted-foreground">{v.reason}</p>
                    </div>
                    {v.ok ? (
                      <CheckCircle2
                        className="h-4 w-4 shrink-0 text-success"
                        aria-label="Available"
                      />
                    ) : v.tone === "planned" ? (
                      <Lock
                        className="h-4 w-4 shrink-0 text-muted-foreground"
                        aria-label="Planned"
                      />
                    ) : (
                      <Ban className="h-4 w-4 shrink-0 text-warning" aria-label="Unavailable" />
                    )}
                  </div>
                );
              })}
            </div>
          </section>
        ))}
      </div>
    </div>
  );
}

function RegionChip({
  label,
  active,
  onClick,
  registered,
}: {
  label: string;
  active: boolean;
  onClick: () => void;
  registered?: boolean;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={cn(
        "inline-flex items-center gap-1 rounded-full border px-2.5 py-1 text-xs transition-colors",
        active
          ? "border-brand/50 bg-brand/10 text-foreground"
          : "border-border bg-card/50 text-muted-foreground hover:text-foreground",
      )}
    >
      {registered ? (
        <span className="h-1.5 w-1.5 rounded-full bg-success" aria-hidden />
      ) : (
        <span className="h-1.5 w-1.5 rounded-full bg-muted-foreground/50" aria-hidden />
      )}
      {label}
    </button>
  );
}
