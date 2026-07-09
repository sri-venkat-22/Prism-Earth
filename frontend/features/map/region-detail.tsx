"use client";

import { AnimatePresence, motion } from "framer-motion";
import { ExternalLink, Loader2, MapPin, X } from "lucide-react";
import { useEffect } from "react";

import { ConfidenceBadge, LayerBadge } from "@/components/badges";
import { ErrorState } from "@/components/feedback";
import { useFetchQuery } from "@/hooks/useQueries";
import { nullReasonLabel } from "@/lib/domain";
import { formatCoord, formatDate, formatValue, humanize } from "@/lib/format";
import type { Layer } from "@/types";
import type { SelectedRegion } from "@/features/map/map-canvas";

/**
 * Region detail panel. On selecting a district it runs a real deterministic
 * POST /fetch at the district centroid for the active layer's fields, then shows
 * each value with its source and last-updated time (SRS §13.9, §17).
 */
export function RegionDetail({
  region,
  layer,
  fields,
  fieldsLoading = false,
  fieldsError = null,
  onRetryFields,
  onClose,
}: {
  region: SelectedRegion | null;
  layer: Layer;
  fields: string[];
  fieldsLoading?: boolean;
  fieldsError?: unknown;
  onRetryFields?: () => void;
  onClose: () => void;
}) {
  const fetchQ = useFetchQuery();
  const { mutate, reset } = fetchQ;

  const key = region ? `${region.district}|${layer}|${fields.join(",")}` : null;

  useEffect(() => {
    if (!region || fields.length === 0) return;
    mutate({ lat: region.centroid[1], lng: region.centroid[0], fields });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [key]);

  useEffect(() => {
    if (!region) reset();
  }, [region, reset]);

  return (
    <AnimatePresence>
      {region && (
        <motion.aside
          key="region-detail"
          initial={{ x: 24, opacity: 0 }}
          animate={{ x: 0, opacity: 1 }}
          exit={{ x: 24, opacity: 0 }}
          transition={{ duration: 0.35, ease: [0.22, 1, 0.36, 1] }}
          className="scrollbar-thin absolute right-3 top-3 z-20 flex max-h-[calc(100%-1.5rem)] w-[92vw] flex-col overflow-hidden rounded-xl border border-border bg-card shadow-md sm:right-4 sm:top-4 sm:w-[380px]"
        >
          {/* Header */}
          <div className="flex items-start justify-between gap-3 border-b border-border p-4">
            <div className="min-w-0">
              <div className="mono-eyebrow mb-1.5">District</div>
              <h3 className="truncate font-display text-xl font-semibold">{region.district}</h3>
              <p className="mt-1 flex items-center gap-1.5 font-mono text-[11px] text-muted-foreground">
                <MapPin className="h-3 w-3" />
                {formatCoord(region.centroid[1], region.centroid[0])}
              </p>
              <div className="mt-2">
                <LayerBadge layer={layer} />
              </div>
            </div>
            <button
              type="button"
              onClick={onClose}
              aria-label="Close"
              className="inline-flex h-8 w-8 shrink-0 items-center justify-center rounded-md text-muted-foreground hover:bg-secondary"
            >
              <X className="h-4 w-4" />
            </button>
          </div>

          {/* Body */}
          <div className="scrollbar-thin flex-1 overflow-y-auto p-4">
            {/* The live fetch never ran: the field catalog is still loading,
                failed to load, or has no fetchable fields for this layer. */}
            {fields.length === 0 && fieldsLoading && (
              <div className="flex items-center gap-2 py-8 text-sm text-muted-foreground">
                <Loader2 className="h-4 w-4 animate-spin" /> Loading the field catalog…
              </div>
            )}
            {fields.length === 0 && !fieldsLoading && fieldsError != null && (
              <ErrorState
                error={fieldsError}
                onRetry={onRetryFields}
                title="Couldn't load the field catalog"
              />
            )}
            {fields.length === 0 && !fieldsLoading && fieldsError == null && (
              <p className="py-8 text-sm text-muted-foreground">
                No fetchable fields in this layer yet.
              </p>
            )}

            {fetchQ.isPending && (
              <div className="flex items-center gap-2 py-8 text-sm text-muted-foreground">
                <Loader2 className="h-4 w-4 animate-spin" /> Fetching live values…
              </div>
            )}

            {fetchQ.isError && (
              <ErrorState
                error={fetchQ.error}
                onRetry={() => mutate({ lat: region.centroid[1], lng: region.centroid[0], fields })}
                title="Fetch failed"
              />
            )}

            {fetchQ.data && !fetchQ.isPending && (
              <>
                <div className="mb-3 flex flex-wrap items-center gap-x-3 gap-y-1 text-[12px] text-muted-foreground">
                  <span>
                    <span className="font-semibold text-foreground">
                      {fetchQ.data.summary.resolved}
                    </span>{" "}
                    / {fetchQ.data.summary.requested} resolved
                  </span>
                  {fetchQ.data.summary.null > 0 && (
                    <span className="text-warning">{fetchQ.data.summary.null} unavailable</span>
                  )}
                </div>

                <div className="divide-y divide-border">
                  {fields.map((id) => {
                    const fv = fetchQ.data!.fields[id];
                    if (!fv) return null;
                    const prov = fetchQ.data!.provenance[id];
                    const isNull = fv.value === null;
                    return (
                      <div key={id} className="py-3">
                        <div className="flex items-baseline justify-between gap-3">
                          <p className="text-[13px] font-medium">{humanize(fv.name)}</p>
                          {!isNull ? (
                            <p className="shrink-0 text-right text-[15px] font-semibold tabular-nums">
                              {formatValue(fv.value, fv.datatype, fv.unit)}
                            </p>
                          ) : (
                            <p className="shrink-0 text-right text-[12px] text-warning">
                              {nullReasonLabel(prov?.reason ?? fv.null_meaning)}
                            </p>
                          )}
                        </div>
                        <div className="mt-1 flex flex-wrap items-center gap-x-2 gap-y-1 text-[11px] text-muted-foreground">
                          <span className="truncate">{fv.dataset}</span>
                          {prov?.source_url && (
                            <a
                              href={prov.source_url}
                              target="_blank"
                              rel="noreferrer"
                              className="inline-flex items-center text-muted-foreground hover:text-brand"
                              aria-label={`Source for ${fv.name}`}
                            >
                              <ExternalLink className="h-3 w-3" />
                            </a>
                          )}
                          <span className="text-faint">·</span>
                          <span>updated {formatDate(fv.retrieved_at)}</span>
                          {!isNull && <ConfidenceBadge value={fv.confidence} className="ml-auto" />}
                        </div>
                      </div>
                    );
                  })}
                </div>

                {fetchQ.data.citations.length > 0 && (
                  <p className="mt-4 border-t border-border pt-3 text-[11px] text-faint">
                    {fetchQ.data.citations.length} source
                    {fetchQ.data.citations.length === 1 ? "" : "s"} · request{" "}
                    <span className="font-mono">{fetchQ.data.request_id.slice(0, 8)}</span>
                  </p>
                )}
              </>
            )}
          </div>
        </motion.aside>
      )}
    </AnimatePresence>
  );
}
