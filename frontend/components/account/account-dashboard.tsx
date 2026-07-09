"use client";

import { useCallback, useEffect, useState } from "react";
import { KeyRound, Lightbulb, LogOut, Plus, Terminal, Trash2, User } from "lucide-react";

import { CopyButton } from "@/components/copy-button";
import { InlineSpinner } from "@/components/feedback";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Separator } from "@/components/ui/separator";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import {
  API_BASE_URL,
  ApiError,
  createMyToken,
  deleteMe,
  listMyTokens,
  logoutAccount,
  revokeMyToken,
  updateMe,
  type AccountToken,
  type AccountTokenCreated,
  type AccountUser,
} from "@/services/api";

const SUPPORT_EMAIL = "founders@terra.dev";

function displayName(email: string): string {
  const local = email.split("@")[0].replace(/[0-9]+$/, "");
  const first = local.split(/[._-]/)[0] || local || "there";
  return first.charAt(0).toUpperCase() + first.slice(1);
}

function fmtDate(iso: string | null): string {
  if (!iso) return "—";
  const d = new Date(iso);
  return Number.isNaN(d.getTime()) ? "—" : d.toISOString().slice(0, 10);
}

export function AccountDashboard({
  user: initialUser,
  onSignedOut,
}: {
  user: AccountUser;
  onSignedOut: () => void;
}) {
  const [user, setUser] = useState(initialUser);
  const [tokens, setTokens] = useState<AccountToken[] | null>(null);

  const reloadTokens = useCallback(async () => {
    try {
      setTokens((await listMyTokens()).tokens);
    } catch {
      setTokens([]);
    }
  }, []);

  useEffect(() => {
    void reloadTokens();
  }, [reloadTokens]);

  async function signOut() {
    try {
      await logoutAccount(); // revokes the session and clears the cookie server-side
    } catch {
      /* best-effort; the page drops to signed-out either way */
    }
    onSignedOut();
  }

  return (
    <div className="mx-auto max-w-3xl">
      <header className="mb-8">
        <h1 className="font-display text-[clamp(28px,4vw,40px)] font-semibold tracking-tight">
          Welcome back, {displayName(user.email)}
        </h1>
        <p className="mono-eyebrow mt-2 normal-case tracking-normal">
          {user.email} · member since {fmtDate(user.created_at)}
        </p>
      </header>

      <Tabs defaultValue="profile">
        <TabsList>
          <TabsTrigger value="tokens">
            <KeyRound className="h-4 w-4" /> API tokens
            {tokens && (
              <span className="ml-0.5 rounded-full bg-muted px-1.5 text-xs tabular-nums text-muted-foreground">
                {tokens.length}
              </span>
            )}
          </TabsTrigger>
          <TabsTrigger value="mcp">
            <Terminal className="h-4 w-4" /> MCP setup
          </TabsTrigger>
          <TabsTrigger value="features">
            <Lightbulb className="h-4 w-4" /> Feature request
          </TabsTrigger>
          <TabsTrigger value="profile">
            <User className="h-4 w-4" /> Profile
          </TabsTrigger>
        </TabsList>

        <TabsContent value="tokens">
          <TokensPanel tokens={tokens} onChanged={reloadTokens} />
        </TabsContent>
        <TabsContent value="mcp">
          <McpPanel />
        </TabsContent>
        <TabsContent value="features">
          <FeaturesPanel email={user.email} />
        </TabsContent>
        <TabsContent value="profile">
          <ProfilePanel user={user} onUser={setUser} onDeleted={onSignedOut} />
        </TabsContent>
      </Tabs>

      <Separator className="my-8" />
      <div className="flex flex-wrap items-center justify-between gap-4">
        <span className="mono-eyebrow normal-case tracking-normal">
          Signed in as {user.email}
        </span>
        <Button variant="ghost" onClick={signOut}>
          <LogOut className="h-4 w-4" /> Sign out
        </Button>
      </div>
    </div>
  );
}

/* ------------------------------------------------------------------ Panels */

function PanelCard({
  title,
  description,
  children,
}: {
  title: string;
  description: string;
  children: React.ReactNode;
}) {
  return (
    <div className="rounded-2xl border border-border bg-card p-6 shadow-sm sm:p-7">
      <h2 className="font-display text-xl font-semibold tracking-tight">{title}</h2>
      <p className="mt-1 text-sm text-muted-foreground">{description}</p>
      <div className="mt-6">{children}</div>
    </div>
  );
}

function TokensPanel({
  tokens,
  onChanged,
}: {
  tokens: AccountToken[] | null;
  onChanged: () => Promise<void>;
}) {
  const [name, setName] = useState("");
  const [busy, setBusy] = useState(false);
  const [created, setCreated] = useState<AccountTokenCreated | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function create(e: React.FormEvent) {
    e.preventDefault();
    if (!name.trim()) return;
    setBusy(true);
    setError(null);
    try {
      const token = await createMyToken({ name: name.trim(), scopes: ["fetch", "ask"] });
      setCreated(token);
      setName("");
      await onChanged();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not create token.");
    } finally {
      setBusy(false);
    }
  }

  async function revoke(id: string) {
    if (!window.confirm("Revoke this token? Anything using it will stop working.")) return;
    try {
      await revokeMyToken(id);
      await onChanged();
    } catch {
      /* list refresh will reflect reality */
    }
  }

  return (
    <PanelCard
      title="API tokens"
      description="Bearer tokens for the REST API, MCP server, and CLI. Each is shown once — store it securely."
    >
      <form onSubmit={create} className="flex flex-wrap items-end gap-3">
        <div className="min-w-[200px] flex-1 space-y-1.5">
          <Label htmlFor="token-name">Token name</Label>
          <Input
            id="token-name"
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder="cli-laptop"
          />
        </div>
        <Button type="submit" disabled={busy || !name.trim()}>
          <Plus className="h-4 w-4" /> {busy ? "Creating…" : "Create token"}
        </Button>
      </form>

      {error && (
        <Alert variant="danger" className="mt-4">
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      )}

      {created && (
        <Alert variant="success" className="mt-4">
          <AlertTitle>Token created — copy it now</AlertTitle>
          <AlertDescription>
            <p className="mb-2">This is the only time the full token is shown.</p>
            <div className="flex items-center gap-2">
              <code className="min-w-0 flex-1 truncate rounded-md bg-background px-2 py-1.5 font-mono text-xs">
                {created.token}
              </code>
              <CopyButton value={created.token} />
            </div>
          </AlertDescription>
        </Alert>
      )}

      <div className="mt-6">
        {tokens === null ? (
          <InlineSpinner label="Loading tokens…" />
        ) : tokens.length === 0 ? (
          <p className="text-sm text-muted-foreground">No API tokens yet.</p>
        ) : (
          <ul className="divide-y divide-border rounded-lg border border-border">
            {tokens.map((t) => (
              <li key={t.id} className="flex flex-wrap items-center gap-3 px-4 py-3">
                <div className="min-w-0 flex-1">
                  <p className="flex items-center gap-2 text-sm font-medium">
                    {t.name}
                    <code className="font-mono text-xs text-muted-foreground">{t.prefix}…</code>
                  </p>
                  <p className="mt-0.5 text-xs text-muted-foreground">
                    {t.scopes.join(", ") || "no scopes"} · created {fmtDate(t.created_at)} · last
                    used {fmtDate(t.last_used_at)}
                  </p>
                </div>
                <Button variant="ghost" size="sm" onClick={() => revoke(t.id)}>
                  <Trash2 className="h-4 w-4 text-danger" /> Revoke
                </Button>
              </li>
            ))}
          </ul>
        )}
      </div>
    </PanelCard>
  );
}

function McpPanel() {
  const config = JSON.stringify(
    {
      mcpServers: {
        terra: {
          command: "npx",
          args: ["-y", "terra-mcp"],
          env: { TERRA_API_BASE_URL: API_BASE_URL, TERRA_API_TOKEN: "<your-api-token>" },
        },
      },
    },
    null,
    2,
  );
  return (
    <PanelCard
      title="MCP setup"
      description="Connect Claude Desktop, Cursor, or any MCP client to Terra. Create an API token above, then add this to your MCP config."
    >
      <div className="relative">
        <pre className="scrollbar-thin overflow-x-auto rounded-lg border border-border bg-background p-4 font-mono text-xs leading-relaxed">
          {config}
        </pre>
        <div className="absolute right-3 top-3">
          <CopyButton value={config} label="Copy config" />
        </div>
      </div>
    </PanelCard>
  );
}

function FeaturesPanel({ email }: { email: string }) {
  const [text, setText] = useState("");
  const href = `mailto:${SUPPORT_EMAIL}?subject=${encodeURIComponent(
    "Terra feature request",
  )}&body=${encodeURIComponent(`${text}\n\n— ${email}`)}`;
  return (
    <PanelCard
      title="Feature request"
      description="Tell us what would make Terra more useful. This opens your email client — we read every one."
    >
      <textarea
        value={text}
        onChange={(e) => setText(e.target.value)}
        rows={4}
        placeholder="I'd love to see…"
        className="flex w-full rounded-md border border-input bg-background/60 px-3 py-2 text-sm ring-offset-background placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2"
      />
      <a
        href={href}
        className="mt-4 inline-flex h-10 items-center justify-center gap-2 rounded-full bg-primary px-4 text-sm font-medium text-primary-foreground transition-colors hover:bg-primary/90 aria-disabled:pointer-events-none aria-disabled:opacity-50"
        aria-disabled={!text.trim()}
      >
        <Lightbulb className="h-4 w-4" /> Send feature request
      </a>
    </PanelCard>
  );
}

function ProfilePanel({
  user,
  onUser,
  onDeleted,
}: {
  user: AccountUser;
  onUser: (u: AccountUser) => void;
  onDeleted: () => void;
}) {
  const [org, setOrg] = useState(user.organization ?? "");
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);

  async function save(e: React.FormEvent) {
    e.preventDefault();
    setSaving(true);
    setSaved(false);
    try {
      const updated = await updateMe({ organization: org.trim() || null });
      onUser(updated);
      setSaved(true);
      setTimeout(() => setSaved(false), 2000);
    } catch {
      /* keep the form as-is; user can retry */
    } finally {
      setSaving(false);
    }
  }

  async function remove() {
    if (
      !window.confirm(
        "Delete your account? This revokes all tokens and removes your data. This cannot be undone.",
      )
    )
      return;
    try {
      await deleteMe(); // clears the session cookie server-side
    } finally {
      onDeleted();
    }
  }

  return (
    <PanelCard title="Profile" description="Your sign-in details and account controls.">
      <form onSubmit={save} className="grid gap-5 sm:grid-cols-2">
        <div className="space-y-1.5">
          <Label htmlFor="pf-email">Email</Label>
          <Input id="pf-email" value={user.email} readOnly disabled className="bg-muted" />
        </div>
        <div className="space-y-1.5">
          <Label htmlFor="pf-org">
            Organization <span className="text-muted-foreground">(optional)</span>
          </Label>
          <Input
            id="pf-org"
            value={org}
            onChange={(e) => setOrg(e.target.value)}
            placeholder="Company or team"
          />
        </div>
        <div className="sm:col-span-2">
          <Button type="submit" disabled={saving}>
            {saving ? "Saving…" : saved ? "Saved ✓" : "Save changes"}
          </Button>
        </div>
      </form>

      <Separator className="my-7" />

      <div className="rounded-xl border border-danger/40 bg-danger/5 p-5">
        <div className="flex flex-wrap items-center justify-between gap-4">
          <div>
            <h3 className="text-sm font-semibold text-danger">Delete account</h3>
            <p className="mt-1 text-sm text-muted-foreground">
              Revokes all tokens and removes your data. This cannot be undone.
            </p>
          </div>
          <Button variant="outline" onClick={remove} className="border-danger/50 text-danger hover:bg-danger/10">
            Delete account
          </Button>
        </div>
      </div>
    </PanelCard>
  );
}
