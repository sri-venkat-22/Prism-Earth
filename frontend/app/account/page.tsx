"use client";

import { useEffect, useState } from "react";

import { AccountAuth } from "@/components/account/account-auth";
import { AccountDashboard } from "@/components/account/account-dashboard";
import { InlineSpinner } from "@/components/feedback";
import { getAccountConfig, getMe, type AccountUser } from "@/services/api";

const GOOGLE_ERRORS: Record<string, string> = {
  google: "Google sign-in failed. Please try again.",
  google_state: "Google sign-in expired. Please try again.",
};

/** Read the `#error=…` fragment the Google callback appends on failure, then scrub it. */
function consumeErrorHash(): string | undefined {
  if (typeof window === "undefined" || !window.location.hash) return undefined;
  const error = new URLSearchParams(window.location.hash.slice(1)).get("error") || undefined;
  if (error) {
    history.replaceState(null, "", window.location.pathname + window.location.search);
  }
  return error;
}

export default function AccountPage() {
  const [user, setUser] = useState<AccountUser | null>(null);
  const [loading, setLoading] = useState(true);
  const [googleEnabled, setGoogleEnabled] = useState(false);
  const [authError, setAuthError] = useState<string | null>(null);

  useEffect(() => {
    let alive = true;
    (async () => {
      const error = consumeErrorHash();
      if (error) setAuthError(GOOGLE_ERRORS[error] ?? "Sign-in failed. Please try again.");

      getAccountConfig()
        .then((c) => alive && setGoogleEnabled(c.google_enabled))
        .catch(() => {});

      // The session lives in an HttpOnly cookie JS can't read — just ask the
      // backend who we are; a 401 simply means "not signed in".
      try {
        const me = await getMe();
        if (alive) setUser(me);
      } catch {
        /* not signed in */
      }
      if (alive) setLoading(false);
    })();
    return () => {
      alive = false;
    };
  }, []);

  if (loading) {
    return (
      <div className="flex min-h-[40vh] items-center justify-center">
        <InlineSpinner label="Loading your account…" />
      </div>
    );
  }

  if (user) {
    return (
      <AccountDashboard
        user={user}
        onSignedOut={() => {
          setUser(null);
          setAuthError(null);
        }}
      />
    );
  }

  return (
    <AccountAuth
      googleEnabled={googleEnabled}
      initialError={authError}
      onAuthed={(session) => {
        setAuthError(null);
        setUser(session);
      }}
    />
  );
}
