"use client";

import Link from "next/link";
import { History, MapPin, Sparkles, Trash2 } from "lucide-react";

import { Button } from "@/components/ui/button";
import { EmptyState } from "@/components/feedback";
import { cn } from "@/lib/utils";
import { formatCoord, formatRelative } from "@/lib/format";
import { useLocationStore } from "@/stores/location";

/** Recent Ask / Fetch runs from the shared store. Clicking one replays it. */
export function HistoryPanel({ className }: { className?: string }) {
  const { history, setCoordinate, clearHistory } = useLocationStore();

  if (history.length === 0) {
    return (
      <EmptyState
        icon={<History className="h-8 w-8" />}
        title="No recent activity"
        description="Your Ask and Fetch runs will appear here."
        className={className}
      />
    );
  }

  return (
    <div className={cn("space-y-2", className)}>
      <div className="flex items-center justify-between">
        <h3 className="flex items-center gap-2 text-sm font-semibold">
          <History className="h-4 w-4 text-brand" /> Recent activity
        </h3>
        <Button variant="ghost" size="sm" onClick={clearHistory} aria-label="Clear history">
          <Trash2 className="h-3.5 w-3.5" /> Clear
        </Button>
      </div>
      <ul className="space-y-1.5">
        {history.map((h) => (
          <li key={h.id}>
            <Link
              href={h.kind === "ask" ? "/ask" : "/fetch"}
              onClick={() => setCoordinate({ lat: h.lat, lng: h.lng }, null)}
              className="flex items-center gap-3 rounded-lg border border-border bg-card/50 px-3 py-2 text-sm transition-colors hover:border-brand/40 hover:bg-accent/40"
            >
              <span
                className={cn(
                  "inline-flex h-7 w-7 shrink-0 items-center justify-center rounded-md",
                  h.kind === "ask" ? "bg-brand/10 text-brand" : "bg-brand-2/10 text-brand-2",
                )}
              >
                {h.kind === "ask" ? (
                  <Sparkles className="h-3.5 w-3.5" />
                ) : (
                  <MapPin className="h-3.5 w-3.5" />
                )}
              </span>
              <span className="min-w-0 flex-1">
                <span className="block truncate">{h.label}</span>
                <span className="block truncate font-mono text-[11px] text-muted-foreground">
                  {formatCoord(h.lat, h.lng)}
                </span>
              </span>
              <span className="shrink-0 text-[11px] text-muted-foreground">
                {formatRelative(h.at)}
              </span>
            </Link>
          </li>
        ))}
      </ul>
    </div>
  );
}
