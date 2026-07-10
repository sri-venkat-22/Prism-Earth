"use client";

import { useState } from "react";
import { ArrowRight, Lock, Mail } from "lucide-react";

import { Logo } from "@/components/layout/logo";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  ApiError,
  GOOGLE_LOGIN_URL,
  loginAccount,
  registerAccount,
  type AccountUser,
} from "@/services/api";

type Mode = "signin" | "signup";

export function AccountAuth({
  googleEnabled,
  onAuthed,
  initialError,
}: {
  googleEnabled: boolean;
  onAuthed: (user: AccountUser) => void;
  initialError?: string | null;
}) {
  const [mode, setMode] = useState<Mode>("signin");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [organization, setOrganization] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(initialError ?? null);

  const isSignup = mode === "signup";

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const user = isSignup
        ? await registerAccount({ email, password, organization: organization || null })
        : await loginAccount({ email, password });
      onAuthed(user); // session is set as an HttpOnly cookie by the backend
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Something went wrong. Please try again.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="mx-auto flex max-w-md flex-col items-center py-8">
      <Logo className="mb-8" />
      <div className="w-full rounded-2xl border border-border bg-card p-7 shadow-sm sm:p-8">
        <h1 className="font-display text-2xl font-semibold tracking-tight">
          {isSignup ? "Create your account" : "Welcome back"}
        </h1>
        <p className="mt-1 text-sm text-muted-foreground">
          {isSignup
            ? "Sign up to manage API tokens and query the platform."
            : "Sign in to your Terra account."}
        </p>

        {googleEnabled && (
          <>
            <a
              href={GOOGLE_LOGIN_URL}
              className="mt-6 inline-flex h-10 w-full items-center justify-center gap-2 rounded-full border border-input bg-background text-sm font-medium transition-colors hover:bg-accent"
            >
              <GoogleGlyph /> Continue with Google
            </a>
            <div className="my-5 flex items-center gap-3 text-xs text-muted-foreground">
              <span className="h-px flex-1 bg-border" />
              or
              <span className="h-px flex-1 bg-border" />
            </div>
          </>
        )}

        <form onSubmit={submit} className={googleEnabled ? "space-y-4" : "mt-6 space-y-4"}>
          <div className="space-y-1.5">
            <Label htmlFor="email">Email</Label>
            <div className="relative">
              <Mail
                className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground"
                aria-hidden
              />
              <Input
                id="email"
                type="email"
                autoComplete="email"
                required
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="you@company.com"
                className="pl-9"
              />
            </div>
          </div>

          <div className="space-y-1.5">
            <Label htmlFor="password">Password</Label>
            <div className="relative">
              <Lock
                className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground"
                aria-hidden
              />
              <Input
                id="password"
                type="password"
                autoComplete={isSignup ? "new-password" : "current-password"}
                required
                minLength={isSignup ? 8 : undefined}
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder={isSignup ? "At least 8 characters" : "••••••••"}
                className="pl-9"
              />
            </div>
          </div>

          {isSignup && (
            <div className="space-y-1.5">
              <Label htmlFor="org">
                Organization <span className="text-muted-foreground">(optional)</span>
              </Label>
              <Input
                id="org"
                value={organization}
                onChange={(e) => setOrganization(e.target.value)}
                placeholder="Company or team"
              />
            </div>
          )}

          {error && (
            <Alert variant="danger">
              <AlertDescription>{error}</AlertDescription>
            </Alert>
          )}

          <Button type="submit" disabled={busy} className="w-full">
            {busy ? "Please wait…" : isSignup ? "Create account" : "Sign in"}
            {!busy && <ArrowRight className="h-4 w-4" />}
          </Button>
        </form>
      </div>

      <p className="mt-5 text-sm text-muted-foreground">
        {isSignup ? "Already have an account?" : "New to Terra?"}{" "}
        <button
          type="button"
          className="font-medium text-foreground underline-offset-4 hover:underline"
          onClick={() => {
            setError(null);
            setMode(isSignup ? "signin" : "signup");
          }}
        >
          {isSignup ? "Sign in" : "Create an account"}
        </button>
      </p>
    </div>
  );
}

/** Google "G" mark as inline SVG (no external asset — CSP-safe). */
function GoogleGlyph() {
  return (
    <svg width="16" height="16" viewBox="0 0 48 48" aria-hidden>
      <path
        fill="#EA4335"
        d="M24 9.5c3.54 0 6.71 1.22 9.21 3.6l6.85-6.85C35.9 2.38 30.47 0 24 0 14.62 0 6.51 5.38 2.56 13.22l7.98 6.19C12.43 13.72 17.74 9.5 24 9.5z"
      />
      <path
        fill="#4285F4"
        d="M46.98 24.55c0-1.57-.15-3.09-.38-4.55H24v9.02h12.94c-.58 2.96-2.26 5.48-4.78 7.18l7.73 6c4.51-4.18 7.09-10.36 7.09-17.65z"
      />
      <path
        fill="#FBBC05"
        d="M10.53 28.59c-.48-1.45-.76-2.99-.76-4.59s.27-3.14.76-4.59l-7.98-6.19C.92 16.46 0 20.12 0 24c0 3.88.92 7.54 2.56 10.78l7.97-6.19z"
      />
      <path
        fill="#34A853"
        d="M24 48c6.48 0 11.93-2.13 15.89-5.81l-7.73-6c-2.15 1.45-4.92 2.3-8.16 2.3-6.26 0-11.57-4.22-13.47-9.91l-7.98 6.19C6.51 42.62 14.62 48 24 48z"
      />
    </svg>
  );
}
