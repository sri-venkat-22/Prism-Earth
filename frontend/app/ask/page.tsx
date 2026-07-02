"use client";

import { motion } from "framer-motion";
import {
  ArrowUp,
  BrainCircuit,
  Check,
  ChevronDown,
  Database,
  FileJson,
  Loader2,
  MapPin,
  ScrollText,
  ShieldCheck,
  Sparkles,
} from "lucide-react";
import { useEffect, useMemo, useRef, useState } from "react";

import { ConfidenceBadge, LayerBadge } from "@/components/badges";
import { CoordinatePicker } from "@/components/coordinate-picker";
import { ErrorState } from "@/components/feedback";
import { PartialFailures } from "@/features/execution/execution-visualizer";
import { AnswerView } from "@/features/ask/answer-view";
import { CitationsList } from "@/features/citations/citations-list";
import { ExecutionVisualizer } from "@/features/execution/execution-visualizer";
import { RawJsonViewer } from "@/features/json/raw-json-viewer";
import { ProvenanceViewer } from "@/features/provenance/provenance-viewer";
import { useAskQuery } from "@/hooks/useQueries";
import { formatCoord, humanize } from "@/lib/format";
import { cn } from "@/lib/utils";
import { useLocationStore } from "@/stores/location";
import type { AskResponse } from "@/types";

const EXAMPLE_QUESTIONS = [
  "Is this area suitable for a solar farm?",
  "What are the flood and hazard risks at this location?",
  "Describe the terrain, climate, and land cover here.",
  "Is there grid and transport infrastructure nearby for a data centre?",
];

const HYDERABAD = { lat: 17.385, lng: 78.486 };

export default function AskPage() {
  const { coordinate, coordinateLabel, setCoordinate, pushHistory } = useLocationStore();
  const [question, setQuestion] = useState("");
  const [editingCoord, setEditingCoord] = useState(false);
  const ask = useAskQuery();

  // Default the working point to the Hyderabad pilot so the hero is usable at once.
  useEffect(() => {
    if (!coordinate) setCoordinate(HYDERABAD, "Hyderabad · pilot region");
  }, [coordinate, setCoordinate]);

  const stage = useAskStages(ask.isPending);
  const active = ask.isPending || ask.isError || !!ask.data;
  const canSubmit = !!coordinate && question.trim().length > 0 && !ask.isPending;

  function submit(q?: string) {
    const text = (q ?? question).trim();
    if (!coordinate || !text) return;
    setQuestion(text);
    ask.mutate(
      { lat: coordinate.lat, lng: coordinate.lng, question: text },
      {
        onSuccess: () =>
          pushHistory({ kind: "ask", lat: coordinate.lat, lng: coordinate.lng, label: text }),
      },
    );
  }

  return (
    <div className="mx-auto w-full max-w-4xl">
      {/* Hero heading — only in the initial (pre-run) state */}
      {!active && (
        <div className="animate-fade-up pt-4 text-center sm:pt-10">
          <p className="mono-eyebrow mb-4">Natural-language ask</p>
          <h1 className="mx-auto max-w-2xl font-display text-[clamp(30px,5vw,52px)] font-semibold leading-[1.05] tracking-[-0.02em]">
            Ask about any point in India.
          </h1>
          <p className="mx-auto mt-4 max-w-xl text-[16px] leading-relaxed text-muted-foreground">
            The planner picks the right fields, the fetch engine retrieves them, and the answer
            cites every source. Nothing is invented.
          </p>
        </div>
      )}

      {/* Composer */}
      <div className={cn(active ? "pt-2" : "mt-8")}>
        <Composer
          question={question}
          setQuestion={setQuestion}
          onSubmit={() => submit()}
          disabled={!canSubmit}
          pending={ask.isPending}
          coordLabel={
            coordinate
              ? (coordinateLabel ?? formatCoord(coordinate.lat, coordinate.lng))
              : "Set a location"
          }
          coordSub={coordinate ? formatCoord(coordinate.lat, coordinate.lng) : undefined}
          onToggleCoord={() => setEditingCoord((v) => !v)}
          editingCoord={editingCoord}
        />
        {editingCoord && (
          <div className="mt-3 rounded-xl border border-border bg-card p-4">
            <CoordinatePicker />
          </div>
        )}
      </div>

      {/* Example queries — initial empty state */}
      {!active && (
        <div className="mt-6">
          <p className="mono-eyebrow mb-3 text-center">Try one</p>
          <div className="mx-auto flex max-w-2xl flex-wrap justify-center gap-2">
            {EXAMPLE_QUESTIONS.map((q) => (
              <button
                key={q}
                type="button"
                onClick={() => submit(q)}
                className="rounded-full border border-border bg-card px-3.5 py-1.5 text-sm text-muted-foreground transition-colors hover:border-foreground/30 hover:text-foreground"
              >
                {q}
              </button>
            ))}
          </div>
        </div>
      )}

      {/* Results */}
      <div className="mt-8 space-y-6">
        {ask.isPending && <AskProgress stage={stage} />}

        {ask.isError && !ask.isPending && (
          <ErrorState
            error={ask.error}
            onRetry={() => submit()}
            title="The question could not be answered"
          />
        )}

        {ask.data && !ask.isPending && <AskResult data={ask.data} />}
      </div>
    </div>
  );
}

/* -------------------------------------------------------------------------- */
/* Composer — hero-style centered input (not a boxed chatbox)                 */
/* -------------------------------------------------------------------------- */
function Composer({
  question,
  setQuestion,
  onSubmit,
  disabled,
  pending,
  coordLabel,
  coordSub,
  onToggleCoord,
  editingCoord,
}: {
  question: string;
  setQuestion: (v: string) => void;
  onSubmit: () => void;
  disabled: boolean;
  pending: boolean;
  coordLabel: string;
  coordSub?: string;
  onToggleCoord: () => void;
  editingCoord: boolean;
}) {
  const ref = useRef<HTMLTextAreaElement>(null);

  // Auto-grow the textarea.
  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    el.style.height = "0px";
    el.style.height = Math.min(el.scrollHeight, 180) + "px";
  }, [question]);

  return (
    <div className="rounded-2xl border border-border bg-card p-2 shadow-sm transition-shadow focus-within:border-foreground/25 focus-within:shadow-md">
      <textarea
        ref={ref}
        value={question}
        onChange={(e) => setQuestion(e.target.value)}
        onKeyDown={(e) => {
          if (e.key === "Enter" && !e.shiftKey) {
            e.preventDefault();
            if (!disabled) onSubmit();
          }
        }}
        placeholder="Ask about any point in India…"
        rows={1}
        aria-label="Your question"
        className="max-h-[180px] w-full resize-none bg-transparent px-3 pt-2.5 text-[16px] leading-relaxed outline-none placeholder:text-muted-foreground"
      />
      <div className="flex items-center justify-between gap-2 px-1 pb-1 pt-1">
        <button
          type="button"
          onClick={onToggleCoord}
          aria-expanded={editingCoord}
          className="inline-flex min-w-0 items-center gap-1.5 rounded-full border border-border bg-secondary px-3 py-1.5 text-left text-[13px] transition-colors hover:border-foreground/25"
        >
          <MapPin className="h-3.5 w-3.5 shrink-0 text-brand" />
          <span className="truncate font-medium">{coordLabel}</span>
          {coordSub && coordSub !== coordLabel && (
            <span className="hidden font-mono text-[11px] text-muted-foreground sm:inline">
              {coordSub}
            </span>
          )}
          <ChevronDown
            className={cn(
              "h-3.5 w-3.5 shrink-0 text-muted-foreground transition-transform",
              editingCoord && "rotate-180",
            )}
          />
        </button>
        <button
          type="button"
          onClick={onSubmit}
          disabled={disabled}
          aria-label="Ask"
          className="inline-flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-primary text-primary-foreground transition-transform duration-200 ease-expo hover:-translate-y-0.5 disabled:pointer-events-none disabled:opacity-40"
        >
          {pending ? <Loader2 className="h-4 w-4 animate-spin" /> : <ArrowUp className="h-4 w-4" />}
        </button>
      </div>
    </div>
  );
}

/* -------------------------------------------------------------------------- */
/* Staged agent progress                                                      */
/* -------------------------------------------------------------------------- */
function useAskStages(pending: boolean) {
  const [stage, setStage] = useState(0);
  useEffect(() => {
    if (!pending) return;
    setStage(0);
    const t1 = setTimeout(() => setStage(1), 850);
    const t2 = setTimeout(() => setStage(2), 2000);
    return () => {
      clearTimeout(t1);
      clearTimeout(t2);
    };
  }, [pending]);
  return stage;
}

const STAGES = [
  { label: "Planning", sub: "Selecting catalog fields for your question", icon: BrainCircuit },
  { label: "Fetching layers", sub: "Retrieving each field from its connector", icon: Database },
  { label: "Synthesizing", sub: "Composing a cited answer from fetched values", icon: Sparkles },
];

function AskProgress({ stage }: { stage: number }) {
  return (
    <div className="rounded-xl border border-border bg-card p-4 sm:p-5">
      <div className="mono-eyebrow mb-4">Running the pipeline</div>
      <ol className="space-y-1">
        {STAGES.map((s, i) => {
          const done = i < stage;
          const current = i === stage;
          const Icon = s.icon;
          return (
            <li
              key={s.label}
              className={cn(
                "flex items-center gap-3 rounded-lg px-3 py-3 transition-colors",
                current && "bg-secondary",
              )}
            >
              <span
                className={cn(
                  "inline-flex h-8 w-8 shrink-0 items-center justify-center rounded-full border",
                  done && "border-success/40 bg-success/10 text-success",
                  current && "pulse-ring border-brand/40 bg-brand/10 text-brand",
                  !done && !current && "border-border text-faint",
                )}
              >
                {done ? (
                  <Check className="h-4 w-4" />
                ) : current ? (
                  <Loader2 className="h-4 w-4 animate-spin" />
                ) : (
                  <Icon className="h-4 w-4" />
                )}
              </span>
              <div className="min-w-0">
                <p
                  className={cn(
                    "text-sm font-medium",
                    !done && !current && "text-muted-foreground",
                  )}
                >
                  {s.label}
                  {done && "…done"}
                  {current && "…"}
                </p>
                <p className="truncate text-[13px] text-muted-foreground">{s.sub}</p>
              </div>
            </li>
          );
        })}
      </ol>
    </div>
  );
}

/* -------------------------------------------------------------------------- */
/* Result: separated Answer / Sourcing / Confidence, then secondary detail    */
/* -------------------------------------------------------------------------- */
function AskResult({ data }: { data: AskResponse }) {
  const [tab, setTab] = useState<"trace" | "json">("trace");

  return (
    <motion.div
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.5, ease: [0.22, 1, 0.36, 1] }}
      className="space-y-6"
    >
      {/* 1 — Answer */}
      <AnswerView answer={data.answer} citations={data.citations} />

      {/* 2 — Confidence & caveats (first-class, distinct from provenance) */}
      <ConfidenceCaveats data={data} />

      {/* 3 — Sourcing / provenance (first-class, audit-ready) */}
      <section className="rounded-xl border border-border bg-card p-6 sm:p-8">
        <div className="mono-eyebrow mb-1 flex items-center gap-2">
          <ScrollText className="h-3.5 w-3.5" /> Sourcing &amp; provenance
        </div>
        <p className="mb-5 text-[13px] text-muted-foreground">
          Every field, the dataset it came from, its license, retrieval time and confidence.
        </p>
        <ProvenanceViewer provenance={data.provenance} citations={data.citations} />
      </section>

      {/* Secondary — citations + trace + raw JSON */}
      <section className="rounded-xl border border-border bg-card">
        <div className="flex items-center gap-1 border-b border-border px-2 py-1.5">
          <TabButton active={tab === "trace"} onClick={() => setTab("trace")}>
            <BrainCircuit className="h-3.5 w-3.5" /> Execution trace
          </TabButton>
          <TabButton active={tab === "json"} onClick={() => setTab("json")}>
            <FileJson className="h-3.5 w-3.5" /> Raw JSON
          </TabButton>
        </div>
        <div className="p-5">
          {tab === "trace" ? (
            <div className="space-y-6">
              <ExecutionVisualizer trace={data.trace} />
              <div>
                <div className="mono-eyebrow mb-3">Citations ({data.citations.length})</div>
                <CitationsList citations={data.citations} />
              </div>
            </div>
          ) : (
            <RawJsonViewer data={data} defaultOpen title="POST /api/v1/ask response" />
          )}
        </div>
      </section>
    </motion.div>
  );
}

function TabButton({
  active,
  onClick,
  children,
}: {
  active: boolean;
  onClick: () => void;
  children: React.ReactNode;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={cn(
        "inline-flex items-center gap-1.5 rounded-md px-3 py-1.5 text-sm font-medium transition-colors",
        active ? "bg-secondary text-foreground" : "text-muted-foreground hover:text-foreground",
      )}
    >
      {children}
    </button>
  );
}

function ConfidenceCaveats({ data }: { data: AskResponse }) {
  const { counts, layers } = useMemo(() => {
    const counts = { high: 0, medium: 0, low: 0 } as Record<string, number>;
    for (const p of Object.values(data.provenance)) {
      if (p.reason) continue; // null field — a caveat, not a confidence entry
      if (p.confidence in counts) counts[p.confidence] += 1;
    }
    const layers = Array.from(new Set(data.trace.planner.layers ?? []));
    return { counts, layers };
  }, [data]);

  const unavailable = data.trace.synthesizer.unavailable_fields ?? [];
  const failures = data.trace.fetch.partial_failures ?? [];
  const clean = unavailable.length === 0 && failures.length === 0;

  return (
    <section className="rounded-xl border border-border bg-card p-6 sm:p-8">
      <div className="mono-eyebrow mb-4 flex items-center gap-2">
        <ShieldCheck className="h-3.5 w-3.5" /> Confidence &amp; caveats
      </div>

      <div className="flex flex-wrap items-center gap-2">
        {layers.map((l) => (
          <LayerBadge key={l} layer={l} />
        ))}
      </div>

      <div className="mt-4 grid grid-cols-3 gap-3">
        {(["high", "medium", "low"] as const).map((k) => (
          <div
            key={k}
            className="rounded-lg border border-border bg-secondary/60 px-3 py-3 text-center"
          >
            <p className="font-display text-2xl font-semibold tabular-nums">{counts[k]}</p>
            <div className="mt-1 flex justify-center">
              <ConfidenceBadge value={k} />
            </div>
          </div>
        ))}
      </div>

      <div className="mt-5">
        {clean ? (
          <p className="flex items-center gap-2 rounded-lg border border-success/30 bg-success/10 px-3 py-2.5 text-sm text-success">
            <Check className="h-4 w-4" /> All selected fields resolved — no gaps to report.
          </p>
        ) : (
          <div className="space-y-3">
            {unavailable.length > 0 && (
              <div className="rounded-lg border border-warning/30 bg-warning/10 px-3 py-2.5">
                <p className="mb-1.5 text-xs font-medium text-warning">
                  Marked unavailable ({unavailable.length})
                </p>
                <div className="flex flex-wrap gap-1.5">
                  {unavailable.map((f) => (
                    <span
                      key={f}
                      className="rounded-md border border-border bg-background px-1.5 py-0.5 text-[11px] text-muted-foreground"
                    >
                      {humanize(f)}
                    </span>
                  ))}
                </div>
              </div>
            )}
            {failures.length > 0 && <PartialFailures failures={failures} />}
          </div>
        )}
      </div>
    </section>
  );
}
