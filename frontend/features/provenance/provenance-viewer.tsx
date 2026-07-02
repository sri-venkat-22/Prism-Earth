"use client";

import { ExternalLink, FileSearch, Search } from "lucide-react";
import { useMemo, useState } from "react";

import { ConfidenceBadge } from "@/components/badges";
import { EmptyState } from "@/components/feedback";
import { Input } from "@/components/ui/input";
import { cn } from "@/lib/utils";
import { nullReasonLabel } from "@/lib/domain";
import { formatDate, formatValue, humanize } from "@/lib/format";
import type { Citation, FieldValue, ProvenanceObject } from "@/types";

interface Row {
  field: string;
  prov: ProvenanceObject;
  value?: FieldValue;
  license: string | null;
  provider: string | null;
  citationId: string | null;
  sourceUrl: string | null;
}

/**
 * Provenance Viewer (SRS §12.10, §17). One row per field showing the dataset,
 * version, retrieval date, confidence and — cross-referenced from the response's
 * citations — the real source, provider, and license. Null fields show the
 * machine-readable reason for the absence (SRS §17.6).
 */
export function ProvenanceViewer({
  provenance,
  citations,
  fields,
  className,
}: {
  provenance: Record<string, ProvenanceObject>;
  citations: Citation[];
  fields?: Record<string, FieldValue>;
  className?: string;
}) {
  const [query, setQuery] = useState("");
  const [onlyNulls, setOnlyNulls] = useState(false);

  const rows = useMemo<Row[]>(() => {
    // Map each field to the citation that produced it (for license/provider/url).
    const byField = new Map<string, Citation>();
    for (const c of citations) {
      for (const f of c.field_names) byField.set(f, c);
    }
    return Object.entries(provenance).map(([field, prov]) => {
      const cit = byField.get(field);
      return {
        field,
        prov,
        value: fields?.[field],
        license: cit?.license ?? null,
        provider: cit?.provider ?? null,
        citationId: cit?.citation_id ?? null,
        sourceUrl: cit?.source_url ?? prov.source_url ?? null,
      };
    });
  }, [provenance, citations, fields]);

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    return rows.filter((r) => {
      const isNull = r.value ? r.value.value === null : !!r.prov.reason;
      if (onlyNulls && !isNull) return false;
      if (!q) return true;
      return (
        r.field.toLowerCase().includes(q) ||
        r.prov.dataset.toLowerCase().includes(q) ||
        (r.license ?? "").toLowerCase().includes(q)
      );
    });
  }, [rows, query, onlyNulls]);

  if (rows.length === 0) {
    return (
      <EmptyState
        icon={<FileSearch className="h-8 w-8" />}
        title="No provenance yet"
        description="Provenance appears here once a request returns fields."
        className={className}
      />
    );
  }

  return (
    <div className={cn("space-y-3", className)}>
      <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
        <div className="relative w-full sm:max-w-xs">
          <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
          <Input
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Filter by field, dataset, license…"
            className="pl-9"
            aria-label="Filter provenance"
          />
        </div>
        <label className="inline-flex cursor-pointer items-center gap-2 text-sm text-muted-foreground">
          <input
            type="checkbox"
            checked={onlyNulls}
            onChange={(e) => setOnlyNulls(e.target.checked)}
            className="h-4 w-4 rounded border-border accent-[hsl(var(--brand))]"
          />
          Only unavailable fields
        </label>
      </div>

      <div className="scrollbar-thin overflow-x-auto rounded-xl border border-border">
        <table className="w-full min-w-[720px] border-collapse text-sm">
          <thead>
            <tr className="border-b border-border bg-muted/40 text-left text-xs uppercase tracking-wide text-muted-foreground">
              <th className="px-3 py-2 font-medium">Field</th>
              <th className="px-3 py-2 font-medium">Value</th>
              <th className="px-3 py-2 font-medium">Dataset · Version</th>
              <th className="px-3 py-2 font-medium">Source · License</th>
              <th className="px-3 py-2 font-medium">Retrieved</th>
              <th className="px-3 py-2 font-medium">Confidence</th>
            </tr>
          </thead>
          <tbody>
            {filtered.map((r) => {
              const isNull = r.value ? r.value.value === null : !!r.prov.reason;
              return (
                <tr
                  key={r.field}
                  className={cn(
                    "border-b border-border/60 align-top last:border-0 hover:bg-accent/30",
                    isNull && "opacity-70",
                  )}
                >
                  <td className="px-3 py-2.5">
                    <div className="font-medium">{humanize(r.field)}</div>
                    <div className="font-mono text-[11px] text-muted-foreground">{r.field}</div>
                  </td>
                  <td className="px-3 py-2.5">
                    {isNull ? (
                      <span className="text-xs text-warning">
                        {nullReasonLabel(r.prov.reason ?? r.prov.null_meaning)}
                      </span>
                    ) : (
                      <span className="font-medium">
                        {r.value ? formatValue(r.value.value, r.value.datatype, r.value.unit) : "—"}
                      </span>
                    )}
                  </td>
                  <td className="px-3 py-2.5">
                    <div>{r.prov.dataset}</div>
                    {r.prov.dataset_version && (
                      <div className="font-mono text-[11px] text-muted-foreground">
                        {r.prov.dataset_version}
                      </div>
                    )}
                  </td>
                  <td className="px-3 py-2.5">
                    <div className="flex items-center gap-1">
                      {r.provider ?? "—"}
                      {r.sourceUrl && (
                        <a
                          href={r.sourceUrl}
                          target="_blank"
                          rel="noreferrer"
                          className="text-muted-foreground hover:text-brand"
                          aria-label={`Source for ${r.field}`}
                        >
                          <ExternalLink className="h-3 w-3" />
                        </a>
                      )}
                    </div>
                    <div className="text-[11px] text-muted-foreground">
                      {r.license ?? "License —"}
                    </div>
                    {r.citationId && (
                      <div className="mt-0.5 font-mono text-[10px] text-brand">{r.citationId}</div>
                    )}
                  </td>
                  <td className="px-3 py-2.5 text-xs text-muted-foreground">
                    {formatDate(r.prov.retrieved_at)}
                  </td>
                  <td className="px-3 py-2.5">
                    <ConfidenceBadge value={r.prov.confidence} />
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
      <p className="text-xs text-muted-foreground">
        {filtered.length} of {rows.length} fields
      </p>
    </div>
  );
}
