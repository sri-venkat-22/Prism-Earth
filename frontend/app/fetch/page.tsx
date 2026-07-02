"use client";

import { motion } from "framer-motion";
import { useSearchParams } from "next/navigation";
import { Database, FileJson, ListChecks, Quote, ScrollText, Search, Send } from "lucide-react";
import { Suspense, useEffect, useMemo, useState } from "react";

import { LayerBadge } from "@/components/badges";
import { CoordinatePicker } from "@/components/coordinate-picker";
import { EmptyState, ErrorState, LoadingBlock } from "@/components/feedback";
import { LocationSummary } from "@/components/location-summary";
import { PageHeader } from "@/components/page-header";
import { StatTile } from "@/components/stat-tile";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { PartialFailures } from "@/features/execution/execution-visualizer";
import { CitationsList } from "@/features/citations/citations-list";
import { FieldResults } from "@/features/fetch/field-results";
import { RawJsonViewer } from "@/features/json/raw-json-viewer";
import { ProvenanceViewer } from "@/features/provenance/provenance-viewer";
import { useFields, usePresets } from "@/hooks/useMeta";
import { useFetchQuery } from "@/hooks/useQueries";
import { cn } from "@/lib/utils";
import { humanize } from "@/lib/format";
import { useLocationStore } from "@/stores/location";
import type { CatalogField } from "@/types";

type Mode = "preset" | "fields";

function FetchWorkbench() {
  const params = useSearchParams();
  const presetParam = params.get("preset");

  const { coordinate, pushHistory } = useLocationStore();
  const presets = usePresets();
  const selectable = useFields({ available: true }); // excludes planned fields

  const [mode, setMode] = useState<Mode>("preset");
  const [preset, setPreset] = useState<string>("");
  const [fields, setFields] = useState<Set<string>>(new Set());
  const fetchQuery = useFetchQuery();

  // Seed the selected preset from the URL (e.g. from the Preset Explorer).
  useEffect(() => {
    if (presetParam) {
      setPreset(presetParam);
      setMode("preset");
    }
  }, [presetParam]);

  // Default preset once loaded.
  useEffect(() => {
    if (!preset && presets.data?.presets.length) setPreset(presets.data.presets[0].id);
  }, [presets.data, preset]);

  const canSubmit =
    !!coordinate && !fetchQuery.isPending && (mode === "preset" ? !!preset : fields.size > 0);

  function submit() {
    if (!coordinate) return;
    const payload =
      mode === "preset"
        ? { lat: coordinate.lat, lng: coordinate.lng, preset }
        : { lat: coordinate.lat, lng: coordinate.lng, fields: [...fields] };
    fetchQuery.mutate(payload, {
      onSuccess: () =>
        pushHistory({
          kind: "fetch",
          lat: coordinate.lat,
          lng: coordinate.lng,
          label: mode === "preset" ? `Preset: ${humanize(preset)}` : `${fields.size} fields`,
        }),
    });
  }

  return (
    <div>
      <PageHeader
        eyebrow="Coordinate input · deterministic"
        title="Fetch"
        icon={<Database className="h-7 w-7 text-brand" />}
        description="Retrieve raw field values for a coordinate with full provenance and citations. No AI runs here — this is the deterministic fetch spine."
      />

      <div className="grid gap-6 lg:grid-cols-[380px_1fr]">
        <div className="space-y-4">
          <Card className="glass">
            <CardHeader>
              <CardTitle className="text-base">Location</CardTitle>
            </CardHeader>
            <CardContent>
              <CoordinatePicker />
            </CardContent>
          </Card>

          <Card className="glass">
            <CardHeader>
              <CardTitle className="text-base">What to retrieve</CardTitle>
            </CardHeader>
            <CardContent className="space-y-3">
              <div className="inline-flex w-full rounded-lg border border-border bg-muted/40 p-1">
                <ModeButton active={mode === "preset"} onClick={() => setMode("preset")}>
                  Preset
                </ModeButton>
                <ModeButton active={mode === "fields"} onClick={() => setMode("fields")}>
                  Fields
                </ModeButton>
              </div>

              {mode === "preset" ? (
                <PresetSelect
                  loading={presets.isLoading}
                  value={preset}
                  onChange={setPreset}
                  presets={presets.data?.presets ?? []}
                />
              ) : (
                <FieldPicker
                  loading={selectable.isLoading}
                  fields={selectable.data?.fields ?? []}
                  selected={fields}
                  onChange={setFields}
                />
              )}

              <Button onClick={submit} disabled={!canSubmit} className="w-full">
                <Send className="h-4 w-4" />
                {fetchQuery.isPending ? "Fetching…" : "Fetch"}
              </Button>
              {!coordinate && (
                <p className="text-xs text-muted-foreground">Pick a coordinate to enable Fetch.</p>
              )}
            </CardContent>
          </Card>
        </div>

        <div className="space-y-4">
          {fetchQuery.isPending && <LoadingBlock rows={5} />}

          {fetchQuery.isError && !fetchQuery.isPending && (
            <ErrorState error={fetchQuery.error} onRetry={submit} title="Fetch failed" />
          )}

          {!fetchQuery.isPending && !fetchQuery.isError && !fetchQuery.data && (
            <EmptyState
              icon={<Database className="h-8 w-8" />}
              title="Run a fetch to see field values"
              description="Choose a preset or specific fields, then Fetch. Values, provenance, and citations appear here."
            />
          )}

          {fetchQuery.data && !fetchQuery.isPending && (
            <motion.div
              initial={{ opacity: 0, y: 8 }}
              animate={{ opacity: 1, y: 0 }}
              className="space-y-4"
            >
              <LocationSummary location={fetchQuery.data.location} />

              <div className="grid gap-3 sm:grid-cols-4">
                <StatTile label="Requested" value={fetchQuery.data.summary.requested} />
                <StatTile
                  label="Resolved"
                  value={fetchQuery.data.summary.resolved}
                  accent="hsl(var(--success))"
                />
                <StatTile
                  label="Null"
                  value={fetchQuery.data.summary.null}
                  accent="hsl(var(--warning))"
                />
                <StatTile label="Datasets" value={fetchQuery.data.summary.datasets_used.length} />
              </div>

              {fetchQuery.data.partial_failures.length > 0 && (
                <PartialFailures failures={fetchQuery.data.partial_failures} />
              )}

              <Tabs defaultValue="values">
                <TabsList>
                  <TabsTrigger value="values">
                    <ListChecks className="h-3.5 w-3.5" /> Values
                  </TabsTrigger>
                  <TabsTrigger value="citations">
                    <Quote className="h-3.5 w-3.5" /> Citations ({fetchQuery.data.citations.length})
                  </TabsTrigger>
                  <TabsTrigger value="provenance">
                    <ScrollText className="h-3.5 w-3.5" /> Provenance
                  </TabsTrigger>
                  <TabsTrigger value="json">
                    <FileJson className="h-3.5 w-3.5" /> Raw JSON
                  </TabsTrigger>
                </TabsList>
                <TabsContent value="values">
                  <FieldResults fields={fetchQuery.data.fields} />
                </TabsContent>
                <TabsContent value="citations">
                  <CitationsList citations={fetchQuery.data.citations} />
                </TabsContent>
                <TabsContent value="provenance">
                  <ProvenanceViewer
                    provenance={fetchQuery.data.provenance}
                    citations={fetchQuery.data.citations}
                    fields={fetchQuery.data.fields}
                  />
                </TabsContent>
                <TabsContent value="json">
                  <RawJsonViewer
                    data={fetchQuery.data}
                    defaultOpen
                    title="POST /api/v1/fetch response"
                  />
                </TabsContent>
              </Tabs>
            </motion.div>
          )}
        </div>
      </div>
    </div>
  );
}

function ModeButton({
  active,
  onClick,
  children,
}: {
  active: boolean;
  onClick: () => void;
  children: React.ReactNode;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={cn(
        "flex-1 rounded-md px-3 py-1.5 text-sm font-medium transition-colors",
        active
          ? "bg-background text-foreground shadow-sm ring-1 ring-border"
          : "text-muted-foreground",
      )}
    >
      {children}
    </button>
  );
}

function PresetSelect({
  loading,
  value,
  onChange,
  presets,
}: {
  loading: boolean;
  value: string;
  onChange: (v: string) => void;
  presets: { id: string; name: string; fields: string[] }[];
}) {
  const selected = presets.find((p) => p.id === value);
  if (loading) return <LoadingBlock rows={1} />;
  return (
    <div className="space-y-2">
      <select
        value={value}
        onChange={(e) => onChange(e.target.value)}
        aria-label="Preset"
        className="h-10 w-full rounded-md border border-input bg-background/60 px-3 text-sm outline-none focus-visible:ring-2 focus-visible:ring-ring"
      >
        {presets.map((p) => (
          <option key={p.id} value={p.id}>
            {p.name}
          </option>
        ))}
      </select>
      {selected && (
        <p className="text-xs text-muted-foreground">Expands to {selected.fields.length} fields.</p>
      )}
    </div>
  );
}

function FieldPicker({
  loading,
  fields,
  selected,
  onChange,
}: {
  loading: boolean;
  fields: CatalogField[];
  selected: Set<string>;
  onChange: (s: Set<string>) => void;
}) {
  const [query, setQuery] = useState("");

  const grouped = useMemo(() => {
    const q = query.trim().toLowerCase();
    const m = new Map<string, CatalogField[]>();
    for (const f of fields) {
      if (q && !f.name.toLowerCase().includes(q) && !f.description.toLowerCase().includes(q))
        continue;
      const list = m.get(f.layer) ?? [];
      list.push(f);
      m.set(f.layer, list);
    }
    return m;
  }, [fields, query]);

  function toggle(name: string) {
    const next = new Set(selected);
    if (next.has(name)) next.delete(name);
    else next.add(name);
    onChange(next);
  }

  if (loading) return <LoadingBlock rows={3} />;

  return (
    <div className="space-y-2">
      <div className="relative">
        <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
        <Input
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="Search fields…"
          className="pl-9"
          aria-label="Search fields"
        />
      </div>
      <div className="flex items-center justify-between text-xs text-muted-foreground">
        <span>{selected.size} selected</span>
        {selected.size > 0 && (
          <button
            type="button"
            className="hover:text-foreground"
            onClick={() => onChange(new Set())}
          >
            Clear
          </button>
        )}
      </div>
      <div className="scrollbar-thin max-h-72 space-y-3 overflow-y-auto pr-1">
        {[...grouped.entries()].map(([layer, list]) => (
          <div key={layer}>
            <div className="mb-1 flex items-center justify-between">
              <LayerBadge layer={layer} />
              <button
                type="button"
                className="text-[11px] text-muted-foreground hover:text-foreground"
                onClick={() => {
                  const next = new Set(selected);
                  const allSelected = list.every((f) => next.has(f.name));
                  list.forEach((f) => (allSelected ? next.delete(f.name) : next.add(f.name)));
                  onChange(next);
                }}
              >
                {list.every((f) => selected.has(f.name)) ? "Deselect all" : "Select all"}
              </button>
            </div>
            <div className="space-y-1">
              {list.map((f) => (
                <label
                  key={f.id}
                  className="flex cursor-pointer items-center gap-2 rounded-md px-2 py-1 text-sm hover:bg-accent/40"
                >
                  <input
                    type="checkbox"
                    checked={selected.has(f.name)}
                    onChange={() => toggle(f.name)}
                    className="h-4 w-4 rounded border-border accent-[hsl(var(--brand))]"
                  />
                  <span className="truncate">{humanize(f.name)}</span>
                </label>
              ))}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

export default function FetchPage() {
  return (
    <Suspense fallback={<LoadingBlock rows={6} />}>
      <FetchWorkbench />
    </Suspense>
  );
}
