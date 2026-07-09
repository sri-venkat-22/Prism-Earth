"use client";

import { useState, type ReactNode } from "react";
import { AlertTriangle, Inbox, KeyRound, Loader2 } from "lucide-react";

import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import { ApiError, getApiToken, setApiToken } from "@/services/api";
import { cn } from "@/lib/utils";

export function InlineSpinner({ label, className }: { label?: string; className?: string }) {
  return (
    <span className={cn("inline-flex items-center gap-2 text-sm text-muted-foreground", className)}>
      <Loader2 className="h-4 w-4 animate-spin" aria-hidden />
      {label ?? "Loading…"}
    </span>
  );
}

/** A block of shimmer skeleton rows for list/card loading (SRS §12.14). */
export function LoadingBlock({ rows = 4, className }: { rows?: number; className?: string }) {
  return (
    <div className={cn("space-y-3", className)} aria-busy="true" aria-live="polite">
      {Array.from({ length: rows }).map((_, i) => (
        <Skeleton key={i} className="h-14 w-full" />
      ))}
      <span className="sr-only">Loading…</span>
    </div>
  );
}

/** A friendly error panel with an optional retry (SRS §12.13). */
export function ErrorState({
  error,
  onRetry,
  title = "Something went wrong",
  className,
}: {
  error: unknown;
  onRetry?: () => void;
  title?: string;
  className?: string;
}) {
  const message =
    error instanceof ApiError || error instanceof Error
      ? error.message
      : "An unexpected error occurred.";
  const code = error instanceof ApiError ? error.code : undefined;
  const corr = error instanceof ApiError ? error.correlationId : undefined;
  const isAuthError = error instanceof ApiError && (error.status === 401 || error.status === 403);

  return (
    <Alert variant="danger" className={cn("flex flex-col gap-2", className)}>
      <div className="flex items-start gap-2">
        <AlertTriangle className="h-4 w-4 text-danger" aria-hidden />
        <div className="flex-1">
          <AlertTitle>{title}</AlertTitle>
          <AlertDescription>
            <span className="text-foreground/90">{message}</span>
            {(code || corr) && (
              <span className="mt-1 block font-mono text-xs text-muted-foreground">
                {code}
                {corr ? ` · ${corr}` : ""}
              </span>
            )}
          </AlertDescription>
        </div>
      </div>
      {isAuthError ? (
        <ApiTokenPrompt onRetry={onRetry} />
      ) : (
        onRetry && (
          <div>
            <Button size="sm" variant="outline" onClick={onRetry}>
              Try again
            </Button>
          </div>
        )
      )}
    </Alert>
  );
}

/** Inline recovery for 401/403: store a bearer token and retry (SRS §13.20). */
function ApiTokenPrompt({ onRetry }: { onRetry?: () => void }) {
  const [draft, setDraft] = useState("");
  const [hasStored, setHasStored] = useState(() => getApiToken() !== null);

  return (
    <div className="flex flex-col gap-2">
      <p className="flex items-center gap-1.5 text-xs text-muted-foreground">
        <KeyRound className="h-3.5 w-3.5" aria-hidden />
        {hasStored
          ? "The saved API token was rejected. Paste a valid token to continue."
          : "This deployment requires an API token. Paste one to continue — it is kept in this browser only."}
      </p>
      <div className="flex flex-wrap items-center gap-2">
        <Input
          type="password"
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          placeholder="API token"
          aria-label="API token"
          className="h-9 w-full max-w-[240px] font-mono text-xs"
        />
        <Button
          size="sm"
          disabled={!draft.trim()}
          onClick={() => {
            setApiToken(draft);
            setHasStored(true);
            setDraft("");
            onRetry?.();
          }}
        >
          Save & retry
        </Button>
        {hasStored && (
          <Button
            size="sm"
            variant="ghost"
            onClick={() => {
              setApiToken(null);
              setHasStored(false);
            }}
          >
            Clear saved token
          </Button>
        )}
      </div>
    </div>
  );
}

/** An empty / call-to-action state (SRS §12.13). */
export function EmptyState({
  icon,
  title,
  description,
  action,
  className,
}: {
  icon?: ReactNode;
  title: string;
  description?: ReactNode;
  action?: ReactNode;
  className?: string;
}) {
  return (
    <div
      className={cn(
        "flex flex-col items-center justify-center rounded-xl border border-dashed border-border bg-card/30 px-6 py-12 text-center",
        className,
      )}
    >
      <div className="mb-3 text-muted-foreground/70">{icon ?? <Inbox className="h-8 w-8" />}</div>
      <h3 className="text-base font-medium">{title}</h3>
      {description && <p className="mt-1 max-w-md text-sm text-muted-foreground">{description}</p>}
      {action && <div className="mt-4">{action}</div>}
    </div>
  );
}
