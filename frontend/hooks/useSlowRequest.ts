import { useEffect, useState } from "react";

/**
 * The free-tier backend sleeps after 15min idle and takes up to ~50s to wake
 * on the next request (see .github/workflows/keep-warm.yml). Past a normal
 * request's length, callers should say so instead of looking stuck.
 */
export function useSlowRequest(pending: boolean, thresholdMs = 6000) {
  const [slow, setSlow] = useState(false);
  useEffect(() => {
    if (!pending) {
      setSlow(false);
      return;
    }
    const t = setTimeout(() => setSlow(true), thresholdMs);
    return () => clearTimeout(t);
  }, [pending, thresholdMs]);
  return slow;
}
