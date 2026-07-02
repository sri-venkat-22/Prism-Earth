"use client";

import { Activity } from "lucide-react";

import { useHealth } from "@/hooks/useMeta";
import { cn } from "@/lib/utils";

/** A live pill reflecting backend reachability + reported status (SRS §13.16). */
export function BackendStatus({ className }: { className?: string }) {
  const { data, isLoading, isError } = useHealth();

  let color = "hsl(var(--muted-foreground))";
  let label = "Checking…";
  let pulse = true;

  if (isError) {
    color = "hsl(var(--danger))";
    label = "API offline";
    pulse = false;
  } else if (!isLoading && data) {
    const ok = data.status === "ok";
    color = ok ? "hsl(var(--success))" : "hsl(var(--warning))";
    label = ok ? "API online" : `API ${data.status}`;
    pulse = false;
  }

  return (
    <span
      className={cn(
        "inline-flex items-center gap-1.5 rounded-full border border-border bg-card/60 px-2.5 py-1 text-xs font-medium text-muted-foreground",
        className,
      )}
      title={data ? `${data.service} ${data.version} · ${data.environment}` : label}
    >
      <span className="relative flex h-2 w-2" aria-hidden>
        {pulse && (
          <span
            className="absolute inline-flex h-full w-full animate-ping rounded-full opacity-60"
            style={{ background: color }}
          />
        )}
        <span className="relative inline-flex h-2 w-2 rounded-full" style={{ background: color }} />
      </span>
      <Activity className="h-3 w-3" aria-hidden />
      {label}
    </span>
  );
}
