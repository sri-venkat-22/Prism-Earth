import { BadgeCheck, CalendarClock, ExternalLink, ScrollText, Tag } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";
import { formatDate, humanize } from "@/lib/format";
import type { Citation } from "@/types";

/**
 * Structured, deduplicated citations (SRS §16.7). Each card surfaces the real
 * source, provider, license, dataset version, and retrieval date now that
 * provenance is authentic and flows through /fetch.
 */
export function CitationsList({
  citations,
  className,
}: {
  citations: Citation[];
  className?: string;
}) {
  if (citations.length === 0) {
    return (
      <p className="rounded-lg border border-dashed border-border bg-card/30 px-4 py-6 text-center text-sm text-muted-foreground">
        No citations — no dataset returned a value for this request.
      </p>
    );
  }

  return (
    <ol className={cn("grid gap-3 sm:grid-cols-2", className)}>
      {citations.map((c) => (
        <li
          key={c.citation_id}
          id={c.citation_id}
          className="flex scroll-mt-24 flex-col gap-2 rounded-xl border border-border bg-card/60 p-4"
        >
          <div className="flex items-start justify-between gap-2">
            <div className="min-w-0">
              <div className="flex items-center gap-2">
                <span className="rounded-md bg-brand/10 px-1.5 py-0.5 font-mono text-xs font-semibold text-brand">
                  {c.citation_id}
                </span>
                {c.dataset_version && (
                  <span className="font-mono text-xs text-muted-foreground">
                    v{c.dataset_version}
                  </span>
                )}
              </div>
              <p className="mt-1.5 font-medium leading-snug">{c.dataset}</p>
              {c.provider && <p className="text-xs text-muted-foreground">{c.provider}</p>}
            </div>
            {c.source_url && (
              <a
                href={c.source_url}
                target="_blank"
                rel="noreferrer"
                className="shrink-0 rounded-md p-1 text-muted-foreground transition-colors hover:bg-accent hover:text-brand"
                aria-label={`Open source for ${c.dataset}`}
                title="Open source"
              >
                <ExternalLink className="h-4 w-4" />
              </a>
            )}
          </div>

          <dl className="grid grid-cols-1 gap-1.5 text-xs">
            <MetaRow icon={<ScrollText className="h-3.5 w-3.5" />} label="License">
              {c.license ?? "—"}
            </MetaRow>
            <MetaRow icon={<CalendarClock className="h-3.5 w-3.5" />} label="Retrieved">
              {formatDate(c.retrieved_at)}
            </MetaRow>
            {c.ttl && (
              <MetaRow icon={<Tag className="h-3.5 w-3.5" />} label="Cache TTL">
                {c.ttl}
              </MetaRow>
            )}
          </dl>

          <div className="mt-1 border-t border-border/60 pt-2">
            <p className="mb-1 flex items-center gap-1 text-xs font-medium text-muted-foreground">
              <BadgeCheck className="h-3.5 w-3.5 text-success" /> Fields cited (
              {c.field_names.length})
            </p>
            <div className="flex flex-wrap gap-1">
              {c.field_names.map((f) => (
                <Badge key={f} className="badge-muted font-mono text-[11px]">
                  {humanize(f)}
                </Badge>
              ))}
            </div>
          </div>
        </li>
      ))}
    </ol>
  );
}

function MetaRow({
  icon,
  label,
  children,
}: {
  icon: React.ReactNode;
  label: string;
  children: React.ReactNode;
}) {
  return (
    <div className="flex items-center gap-1.5">
      <span className="text-muted-foreground/70">{icon}</span>
      <dt className="text-muted-foreground">{label}:</dt>
      <dd className="font-medium">{children}</dd>
    </div>
  );
}
