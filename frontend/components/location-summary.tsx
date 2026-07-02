import { CheckCircle2, ChevronRight, MapPin, XCircle } from "lucide-react";

import { cn } from "@/lib/utils";
import { formatCoord } from "@/lib/format";
import type { FetchLocation } from "@/types";

/**
 * Renders the resolved administrative context for a coordinate (SRS §15.7,
 * §13.23) — the state → district → taluk → village → municipality → ward chain —
 * and whether the point is inside the pilot region.
 */
export function LocationSummary({
  location,
  className,
}: {
  location: FetchLocation;
  className?: string;
}) {
  const chain: { label: string; value: string | null }[] = [
    { label: "State", value: location.state },
    { label: "District", value: location.district },
    { label: "Taluk / Mandal", value: location.taluk },
    { label: "Village", value: location.village },
    { label: "Municipality", value: location.municipality },
    { label: "Ward", value: location.ward },
  ];
  const resolved = chain.filter((c) => c.value);

  return (
    <div className={cn("rounded-xl border border-border bg-card/60 p-4", className)}>
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="flex items-center gap-2">
          <MapPin className="h-4 w-4 text-brand" aria-hidden />
          <span className="font-mono text-sm">{formatCoord(location.lat, location.lng)}</span>
        </div>
        {location.in_pilot_region ? (
          <span className="inline-flex items-center gap-1.5 rounded-full border border-success/30 bg-success/10 px-2.5 py-0.5 text-xs font-medium text-success">
            <CheckCircle2 className="h-3.5 w-3.5" /> Inside pilot region
          </span>
        ) : (
          <span className="inline-flex items-center gap-1.5 rounded-full border border-warning/30 bg-warning/10 px-2.5 py-0.5 text-xs font-medium text-warning">
            <XCircle className="h-3.5 w-3.5" /> Outside pilot region
          </span>
        )}
      </div>

      {resolved.length > 0 ? (
        <div className="mt-3 flex flex-wrap items-center gap-x-1 gap-y-2 text-sm">
          {resolved.map((c, i) => (
            <span key={c.label} className="inline-flex items-center gap-1">
              {i > 0 && (
                <ChevronRight className="h-3.5 w-3.5 text-muted-foreground/50" aria-hidden />
              )}
              <span className="rounded-md bg-muted/50 px-2 py-0.5">
                <span className="text-muted-foreground">{c.label}: </span>
                <span className="font-medium">{c.value}</span>
              </span>
            </span>
          ))}
        </div>
      ) : (
        <p className="mt-3 text-sm text-muted-foreground">
          No administrative boundary resolved for this coordinate.
        </p>
      )}
    </div>
  );
}
