import { Fragment } from "react";
import { Quote } from "lucide-react";

import { cn } from "@/lib/utils";
import type { Citation } from "@/types";

/**
 * Renders the synthesized answer (SRS §13.13) with inline citation markers like
 * `[CIT-001]` highlighted as chips. The answer text is exactly what the API
 * returned — the UI adds no interpretation (SRS §38.5).
 */
export function AnswerView({
  answer,
  citations,
  className,
}: {
  answer: string;
  citations: Citation[];
  className?: string;
}) {
  const known = new Set(citations.map((c) => c.citation_id));

  return (
    <div className={cn("rounded-xl border border-border bg-card p-6 sm:p-8", className)}>
      <div className="mono-eyebrow mb-4 flex items-center gap-2">
        <Quote className="h-3.5 w-3.5" /> Answer
      </div>
      <div className="space-y-4 text-[16px] leading-[1.7] text-foreground">
        {answer.split(/\n{2,}/).map((para, i) => (
          <p key={i}>{renderWithCitations(para, known)}</p>
        ))}
      </div>
    </div>
  );
}

const CIT_RE = /\[(CIT-\d+)\]/g;

function renderWithCitations(text: string, known: Set<string>) {
  const nodes: React.ReactNode[] = [];
  let last = 0;
  let match: RegExpExecArray | null;
  let key = 0;
  while ((match = CIT_RE.exec(text)) !== null) {
    if (match.index > last)
      nodes.push(<Fragment key={key++}>{text.slice(last, match.index)}</Fragment>);
    const id = match[1];
    nodes.push(
      <a
        key={key++}
        href={`#${id}`}
        className={cn(
          "mx-0.5 inline-flex items-center rounded border px-1 py-0.5 align-baseline font-mono text-[11px] font-medium",
          known.has(id)
            ? "border-brand/40 bg-brand/10 text-brand hover:bg-brand/20"
            : "border-border bg-muted/50 text-muted-foreground",
        )}
        title={`Citation ${id}`}
      >
        {id}
      </a>,
    );
    last = match.index + match[0].length;
  }
  if (last < text.length) nodes.push(<Fragment key={key++}>{text.slice(last)}</Fragment>);
  return nodes;
}
