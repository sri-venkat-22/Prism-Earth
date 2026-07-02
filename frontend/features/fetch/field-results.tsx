import { ConfidenceBadge } from "@/components/badges";
import { layerMeta, nullReasonLabel } from "@/lib/domain";
import { formatValue, humanize } from "@/lib/format";
import { cn } from "@/lib/utils";
import type { FieldValue } from "@/types";

/**
 * Deterministic field results (SRS §13.10). Every requested field is shown —
 * resolved values with their unit/confidence/dataset, and nulls with their
 * machine-readable reason — grouped by domain layer (SRS §11.5).
 */
export function FieldResults({
  fields,
  className,
}: {
  fields: Record<string, FieldValue>;
  className?: string;
}) {
  const entries = Object.values(fields);

  // Group by layer, preserving first-seen order.
  const groups = new Map<string, FieldValue[]>();
  for (const f of entries) {
    const list = groups.get(f.layer) ?? [];
    list.push(f);
    groups.set(f.layer, list);
  }

  return (
    <div className={cn("space-y-5", className)}>
      {[...groups.entries()].map(([layer, list]) => {
        const meta = layerMeta(layer);
        const Icon = meta.icon;
        return (
          <section key={layer}>
            <div className="mb-2 flex items-center gap-2">
              <span
                className="inline-flex h-6 w-6 items-center justify-center rounded-md"
                style={{ background: `hsl(${meta.accent} / 0.15)`, color: `hsl(${meta.accent})` }}
              >
                <Icon className="h-3.5 w-3.5" aria-hidden />
              </span>
              <h3 className="text-sm font-semibold">{meta.label}</h3>
              <span className="text-xs text-muted-foreground">{list.length} fields</span>
            </div>
            <div className="grid gap-2.5 sm:grid-cols-2 lg:grid-cols-3">
              {list.map((f) => (
                <FieldCard key={f.name} field={f} accent={meta.accent} />
              ))}
            </div>
          </section>
        );
      })}
    </div>
  );
}

function FieldCard({ field, accent }: { field: FieldValue; accent: string }) {
  const isNull = field.value === null || field.value === undefined;
  return (
    <div
      className={cn(
        "relative overflow-hidden rounded-xl border border-border bg-card/60 p-3.5",
        isNull && "opacity-80",
      )}
    >
      <span
        aria-hidden
        className="absolute inset-y-0 left-0 w-0.5"
        style={{ background: `hsl(${accent})` }}
      />
      <div className="flex items-start justify-between gap-2">
        <p className="text-xs font-medium text-muted-foreground">{humanize(field.name)}</p>
        <ConfidenceBadge value={field.confidence} />
      </div>
      {isNull ? (
        <p className="mt-1.5 text-sm text-warning">{nullReasonLabel(field.null_meaning)}</p>
      ) : (
        <p className="mt-1.5 text-xl font-semibold tabular-nums">
          {formatValue(field.value, field.datatype, field.unit)}
        </p>
      )}
      <p className="mt-2 truncate text-[11px] text-muted-foreground" title={field.dataset}>
        {field.dataset}
      </p>
    </div>
  );
}
