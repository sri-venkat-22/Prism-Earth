"use client";

import { Braces, ChevronDown, ChevronRight } from "lucide-react";
import { Fragment, useMemo, useState } from "react";

import { CopyButton } from "@/components/copy-button";
import { cn } from "@/lib/utils";

/**
 * Raw JSON Viewer (SRS §12.9). Shows the exact, unmodified API response so users
 * can see precisely what the platform returned — a core transparency feature.
 */
export function RawJsonViewer({
  data,
  title = "Raw API response",
  defaultOpen = false,
  className,
}: {
  data: unknown;
  title?: string;
  defaultOpen?: boolean;
  className?: string;
}) {
  const [open, setOpen] = useState(defaultOpen);
  const json = useMemo(() => JSON.stringify(data, null, 2), [data]);

  return (
    <div className={cn("overflow-hidden rounded-xl border border-border bg-card/60", className)}>
      <div className="flex items-center justify-between gap-2 border-b border-border/70 px-4 py-2.5">
        <button
          type="button"
          onClick={() => setOpen((v) => !v)}
          aria-expanded={open}
          className="inline-flex items-center gap-2 text-sm font-medium text-foreground"
        >
          {open ? <ChevronDown className="h-4 w-4" /> : <ChevronRight className="h-4 w-4" />}
          <Braces className="h-4 w-4 text-brand" aria-hidden />
          {title}
        </button>
        <CopyButton value={json} label="Copy JSON" />
      </div>
      {open && (
        <pre className="scrollbar-thin max-h-[28rem] overflow-auto bg-background/40 p-4 text-xs leading-relaxed">
          <code className="font-mono">{highlight(json)}</code>
        </pre>
      )}
    </div>
  );
}

// Lightweight JSON syntax highlighting. Operates on the already-stringified JSON
// and emits React nodes (React escapes text, so this is XSS-safe).
const TOKEN =
  /("(?:\\u[a-zA-Z0-9]{4}|\\[^u]|[^\\"])*"(\s*:)?|\b(?:true|false|null)\b|-?\d+(?:\.\d*)?(?:[eE][+-]?\d+)?)/g;

function highlight(json: string) {
  const nodes: React.ReactNode[] = [];
  let last = 0;
  let match: RegExpExecArray | null;
  let key = 0;
  while ((match = TOKEN.exec(json)) !== null) {
    if (match.index > last)
      nodes.push(<Fragment key={key++}>{json.slice(last, match.index)}</Fragment>);
    const token = match[0];
    let cls = "text-info"; // number
    if (/^"/.test(token)) {
      cls = match[2] ? "text-brand" : "text-success"; // key vs string
    } else if (token === "true" || token === "false") {
      cls = "text-warning";
    } else if (token === "null") {
      cls = "text-muted-foreground";
    }
    nodes.push(
      <span key={key++} className={cls}>
        {token}
      </span>,
    );
    last = match.index + token.length;
  }
  if (last < json.length) nodes.push(<Fragment key={key++}>{json.slice(last)}</Fragment>);
  return nodes;
}
