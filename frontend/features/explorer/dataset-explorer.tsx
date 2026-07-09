"use client";

import { ChevronDown, ChevronRight, Database, ExternalLink, Search } from "lucide-react";
import { useMemo, useState } from "react";

import { AvailabilityBadge, LayerBadge, LifecycleBadge } from "@/components/badges";
import { EmptyState, ErrorState, LoadingBlock } from "@/components/feedback";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { useFields, useLayers } from "@/hooks/useMeta";
import { cn } from "@/lib/utils";
import { humanize } from "@/lib/format";
import type { CatalogField } from "@/types";

const LIFECYCLES = ["stable", "beta", "planned"] as const;
const AVAILABILITIES = ["nationwide", "region_gated", "planned"] as const;

/**
 * Dataset Explorer (SRS §12.8). Browses the whole field catalog (/meta/fields)
 * with layer / lifecycle / availability filters and free-text search. Each field
 * surfaces its real source dataset and link — nothing is hardcoded (SRS §38.5).
 */
export function DatasetExplorer({ className }: { className?: string }) {
  const { data, isLoading, isError, error, refetch } = useFields();
  const { data: layersData } = useLayers();

  const [query, setQuery] = useState("");
  const [layer, setLayer] = useState<string>("");
  const [lifecycle, setLifecycle] = useState<string>("");
  const [availability, setAvailability] = useState<string>("");
  const [expanded, setExpanded] = useState<string | null>(null);

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    return (data?.fields ?? []).filter((f) => {
      if (layer && f.layer !== layer) return false;
      if (lifecycle && f.lifecycle !== lifecycle) return false;
      if (availability && f.availability !== availability) return false;
      if (!q) return true;
      return (
        f.name.toLowerCase().includes(q) ||
        f.description.toLowerCase().includes(q) ||
        f.source.toLowerCase().includes(q)
      );
    });
  }, [data, query, layer, lifecycle, availability]);

  if (isLoading) return <LoadingBlock rows={6} className={className} />;
  if (isError) return <ErrorState error={error} onRetry={refetch} className={className} />;
  if (!data) return null;

  return (
    <div className={cn("space-y-4", className)}>
      {/* Filters */}
      <div className="flex flex-col gap-3 lg:flex-row lg:items-center">
        <div className="relative w-full lg:max-w-xs">
          <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
          <Input
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Search fields, sources…"
            className="pl-9"
            aria-label="Search fields"
          />
        </div>
        <div className="flex flex-wrap gap-2">
          <FilterSelect
            label="Layer"
            value={layer}
            onChange={setLayer}
            options={(layersData?.layers ?? []).map((l) => ({ value: l.id, label: l.name }))}
          />
          <FilterSelect
            label="Lifecycle"
            value={lifecycle}
            onChange={setLifecycle}
            options={LIFECYCLES.map((l) => ({ value: l, label: humanize(l) }))}
          />
          <FilterSelect
            label="Availability"
            value={availability}
            onChange={setAvailability}
            options={AVAILABILITIES.map((a) => ({ value: a, label: humanize(a) }))}
          />
        </div>
      </div>

      <p className="text-xs text-muted-foreground">
        Showing {filtered.length} of {data.count} fields
      </p>

      {filtered.length === 0 ? (
        <EmptyState icon={<Database className="h-8 w-8" />} title="No fields match your filters" />
      ) : (
        <div className="overflow-hidden rounded-xl border border-border">
          <div className="mono-eyebrow hidden grid-cols-[1.5fr_1fr_0.8fr_1fr_1.2fr_auto] gap-3 border-b border-border bg-muted/40 px-4 py-2 md:grid">
            <span>Field</span>
            <span>Layer</span>
            <span>Lifecycle</span>
            <span>Availability</span>
            <span>Source</span>
            <span />
          </div>
          <ul>
            {filtered.map((f) => (
              <FieldRow
                key={f.id}
                field={f}
                open={expanded === f.id}
                onToggle={() => setExpanded((cur) => (cur === f.id ? null : f.id))}
              />
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}

function FieldRow({
  field,
  open,
  onToggle,
}: {
  field: CatalogField;
  open: boolean;
  onToggle: () => void;
}) {
  return (
    <li className="border-b border-border/60 last:border-0">
      <button
        type="button"
        onClick={onToggle}
        aria-expanded={open}
        className="grid w-full grid-cols-1 items-center gap-2 px-4 py-3 text-left hover:bg-accent/30 md:grid-cols-[1.5fr_1fr_0.8fr_1fr_1.2fr_auto] md:gap-3"
      >
        <div className="min-w-0">
          <div className="font-medium">{humanize(field.name)}</div>
          <div className="truncate font-mono text-[11px] text-muted-foreground">{field.name}</div>
        </div>
        <div className="md:block">
          <LayerBadge layer={field.layer} />
        </div>
        <div>
          <LifecycleBadge value={field.lifecycle} />
        </div>
        <div>
          <AvailabilityBadge value={field.availability} />
        </div>
        <div className="truncate text-sm text-muted-foreground" title={field.source}>
          {field.source}
        </div>
        <span className="hidden justify-self-end text-muted-foreground md:block">
          {open ? <ChevronDown className="h-4 w-4" /> : <ChevronRight className="h-4 w-4" />}
        </span>
      </button>

      {open && (
        <div className="grid gap-3 border-t border-border/60 bg-background/30 px-4 py-3 text-sm sm:grid-cols-2">
          <Detail label="Description">{field.description}</Detail>
          <Detail label="Interpretation">{field.interpretation_hint}</Detail>
          <Detail label="Data type">
            {humanize(field.datatype)}
            {field.unit ? ` · ${field.unit}` : ""}
          </Detail>
          <Detail label="Cache TTL">{field.ttl ?? "—"}</Detail>
          {field.nullable && (
            <Detail label="When null">{field.null_meaning ?? "May be null"}</Detail>
          )}
          <Detail label="Connector">
            <span className="font-mono text-xs">{field.connector}</span>
          </Detail>
          <Detail label="Source">
            <span className="inline-flex items-center gap-1">
              {field.source}
              {field.source_url && (
                <a
                  href={field.source_url}
                  target="_blank"
                  rel="noreferrer"
                  className="text-brand hover:underline"
                >
                  <ExternalLink className="h-3.5 w-3.5" />
                </a>
              )}
            </span>
          </Detail>
          {field.presets.length > 0 && (
            <Detail label="In presets">
              <div className="flex flex-wrap gap-1">
                {field.presets.map((p) => (
                  <Badge key={p} className="badge-muted font-mono text-[11px]">
                    {p}
                  </Badge>
                ))}
              </div>
            </Detail>
          )}
        </div>
      )}
    </li>
  );
}

function Detail({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div>
      <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">{label}</p>
      <div className="mt-0.5 text-foreground/90">{children}</div>
    </div>
  );
}

function FilterSelect({
  label,
  value,
  onChange,
  options,
}: {
  label: string;
  value: string;
  onChange: (v: string) => void;
  options: { value: string; label: string }[];
}) {
  return (
    <label className="inline-flex items-center gap-1.5">
      <span className="sr-only">{label}</span>
      <select
        value={value}
        onChange={(e) => onChange(e.target.value)}
        aria-label={`Filter by ${label.toLowerCase()}`}
        className="h-9 rounded-md border border-input bg-background/60 px-2.5 text-sm outline-none focus-visible:ring-2 focus-visible:ring-ring"
      >
        <option value="">{label}: All</option>
        {options.map((o) => (
          <option key={o.value} value={o.value}>
            {o.label}
          </option>
        ))}
      </select>
    </label>
  );
}
