"use client";

// Route-segment error boundary (SRS §12.13): keeps an unexpected render-time
// exception scoped to the page body — nav and footer stay mounted — and offers
// a reset instead of Next.js's generic full-page failure screen.

import { ErrorState } from "@/components/feedback";

export default function RouteError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  return (
    <div className="mx-auto max-w-xl py-24">
      <ErrorState error={error} onRetry={reset} title="This page hit an unexpected error" />
    </div>
  );
}
