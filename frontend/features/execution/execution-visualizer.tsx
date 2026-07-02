"use client";

import { motion } from "framer-motion";
import {
  AlertTriangle,
  Boxes,
  BrainCircuit,
  CheckCircle2,
  Cpu,
  Database,
  Layers as LayersIcon,
  Sparkles,
  Target,
  Timer,
  XCircle,
} from "lucide-react";

import { LayerBadge } from "@/components/badges";
import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";
import { formatMs, humanize } from "@/lib/format";
import type { ConnectorExecution, PartialFailure, Trace } from "@/types";

/**
 * Execution Visualizer (SRS §12.5–12.7). Renders the full trace of an /ask run:
 * the Planner's reasoning (§12.6), the Fetch Engine's per-connector execution
 * (§12.7), and the Synthesizer's metadata — as an animated three-stage pipeline.
 */
export function ExecutionVisualizer({ trace, className }: { trace: Trace; className?: string }) {
  const { planner, fetch, synthesizer, total_duration_ms } = trace;
  const stages = [
    {
      key: "plan",
      label: "Plan",
      icon: BrainCircuit,
      ms: planner.duration_ms,
      color: "var(--brand)",
    },
    {
      key: "fetch",
      label: "Fetch",
      icon: Database,
      ms: fetch.duration_ms,
      color: "var(--brand-2)",
    },
    {
      key: "synth",
      label: "Synthesize",
      icon: Sparkles,
      ms: synthesizer.duration_ms,
      color: "var(--brand-3)",
    },
  ];
  const totalForBar = stages.reduce((s, x) => s + Math.max(x.ms, 0), 0) || 1;

  return (
    <div className={cn("space-y-4", className)}>
      {/* Pipeline timeline */}
      <div className="rounded-xl border border-border bg-card/60 p-4">
        <div className="mb-3 flex items-center justify-between">
          <h3 className="flex items-center gap-2 text-sm font-semibold">
            <Cpu className="h-4 w-4 text-brand" /> Execution pipeline
          </h3>
          <span className="inline-flex items-center gap-1 text-xs text-muted-foreground">
            <Timer className="h-3.5 w-3.5" /> total {formatMs(total_duration_ms)}
          </span>
        </div>

        <div className="grid gap-3 sm:grid-cols-3">
          {stages.map((s, i) => {
            const Icon = s.icon;
            return (
              <motion.div
                key={s.key}
                initial={{ opacity: 0, y: 8 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: i * 0.08 }}
                className="rounded-lg border border-border/70 bg-background/40 p-3"
              >
                <div className="flex items-center gap-2">
                  <span
                    className="inline-flex h-7 w-7 items-center justify-center rounded-md"
                    style={{ background: `hsl(${s.color} / 0.15)`, color: `hsl(${s.color})` }}
                  >
                    <Icon className="h-4 w-4" />
                  </span>
                  <div>
                    <p className="text-xs text-muted-foreground">Stage {i + 1}</p>
                    <p className="text-sm font-medium">{s.label}</p>
                  </div>
                  <span className="ml-auto font-mono text-xs text-muted-foreground">
                    {formatMs(s.ms)}
                  </span>
                </div>
              </motion.div>
            );
          })}
        </div>

        {/* Proportional duration bar */}
        <div className="mt-3 flex h-2 overflow-hidden rounded-full bg-muted">
          {stages.map((s) => (
            <div
              key={s.key}
              className="h-full"
              style={{
                width: `${(Math.max(s.ms, 0) / totalForBar) * 100}%`,
                background: `hsl(${s.color})`,
              }}
              title={`${s.label}: ${formatMs(s.ms)}`}
            />
          ))}
        </div>
      </div>

      <div className="grid gap-4 lg:grid-cols-2">
        <PlannerCard trace={trace} />
        <SynthesizerCard trace={trace} />
      </div>
      <FetchCard trace={trace} />
    </div>
  );
}

// --------------------------------------------------------------------------- //
// Planner (SRS §12.6, §14)                                                     //
// --------------------------------------------------------------------------- //
function PlannerCard({ trace }: { trace: Trace }) {
  const p = trace.planner;
  return (
    <StageCard
      icon={<BrainCircuit className="h-4 w-4 text-brand" />}
      title="Planner"
      subtitle={p.model}
    >
      <Field label="Intent">
        <span className="text-sm">{p.intent || "—"}</span>
      </Field>
      <Field label="Reasoning">
        <p className="text-sm text-muted-foreground">{p.planning_reason || "—"}</p>
      </Field>

      {p.presets.length > 0 && (
        <Field label="Presets" icon={<Boxes className="h-3.5 w-3.5" />}>
          <ChipRow items={p.presets} />
        </Field>
      )}
      {p.layers.length > 0 && (
        <Field label="Layers" icon={<LayersIcon className="h-3.5 w-3.5" />}>
          <div className="flex flex-wrap gap-1">
            {p.layers.map((l) => (
              <LayerBadge key={l} layer={l} />
            ))}
          </div>
        </Field>
      )}
      <Field label="Connectors">
        <ChipRow items={p.connectors} mono />
      </Field>
      <Field
        label={`Fields selected (${p.fields.length})`}
        icon={<Target className="h-3.5 w-3.5" />}
      >
        <ChipRow items={p.fields.map(humanize)} muted />
      </Field>

      {p.warnings.length > 0 && (
        <div className="rounded-lg border border-warning/30 bg-warning/10 p-2.5">
          <p className="mb-1 flex items-center gap-1.5 text-xs font-medium text-warning">
            <AlertTriangle className="h-3.5 w-3.5" /> Planner warnings
          </p>
          <ul className="list-inside list-disc space-y-0.5 text-xs text-foreground/80">
            {p.warnings.map((w, i) => (
              <li key={i}>{w}</li>
            ))}
          </ul>
        </div>
      )}

      <TokenFooter prompt={p.prompt_tokens} completion={p.completion_tokens} ms={p.duration_ms} />
    </StageCard>
  );
}

// --------------------------------------------------------------------------- //
// Synthesizer (SRS §6.5)                                                       //
// --------------------------------------------------------------------------- //
function SynthesizerCard({ trace }: { trace: Trace }) {
  const s = trace.synthesizer;
  return (
    <StageCard
      icon={<Sparkles className="h-4 w-4 text-brand-3" />}
      title="Synthesizer"
      subtitle={s.model ?? "deterministic template"}
    >
      <Field label={`Citations used (${s.citations_used.length})`}>
        <ChipRow items={s.citations_used} mono empty="None" />
      </Field>
      <Field label={`Marked unavailable (${s.unavailable_fields.length})`}>
        <ChipRow
          items={s.unavailable_fields.map(humanize)}
          muted
          empty="None — all fields resolved"
        />
      </Field>
      <p className="text-xs text-muted-foreground">
        The synthesizer only ever states fetched values and explicitly notes what was unavailable —
        it never fabricates data (SRS §38.3).
      </p>
      <TokenFooter prompt={s.prompt_tokens} completion={s.completion_tokens} ms={s.duration_ms} />
    </StageCard>
  );
}

// --------------------------------------------------------------------------- //
// Fetch Engine (SRS §12.7, §15)                                                //
// --------------------------------------------------------------------------- //
function FetchCard({ trace }: { trace: Trace }) {
  const f = trace.fetch;
  return (
    <StageCard
      icon={<Database className="h-4 w-4 text-brand-2" />}
      title="Fetch Engine"
      subtitle={`${formatMs(f.duration_ms)}`}
    >
      <div className="grid grid-cols-3 gap-2">
        <MiniStat label="Requested" value={f.requested_fields.length} />
        <MiniStat label="Resolved" value={f.resolved_fields.length} tone="success" />
        <MiniStat
          label="Null"
          value={f.null_fields.length}
          tone={f.null_fields.length ? "warning" : "muted"}
        />
      </div>

      <Field label={`Datasets used (${f.datasets_used.length})`}>
        <ChipRow items={f.datasets_used} empty="None" />
      </Field>

      <div>
        <p className="mb-1.5 text-xs font-medium text-muted-foreground">Connector execution</p>
        <div className="grid gap-1.5 sm:grid-cols-2">
          {f.connectors.map((c) => (
            <ConnectorRow key={c.connector} exec={c} />
          ))}
        </div>
      </div>

      {f.partial_failures.length > 0 && <PartialFailures failures={f.partial_failures} />}
    </StageCard>
  );
}

function ConnectorRow({ exec }: { exec: ConnectorExecution }) {
  const ok = exec.status === "ok";
  return (
    <div
      className={cn(
        "flex items-start gap-2 rounded-lg border p-2",
        ok ? "border-border bg-background/40" : "border-danger/30 bg-danger/5",
      )}
    >
      {ok ? (
        <CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0 text-success" />
      ) : (
        <XCircle className="mt-0.5 h-4 w-4 shrink-0 text-danger" />
      )}
      <div className="min-w-0">
        <p className="truncate font-mono text-xs">{exec.connector}</p>
        <p className="text-[11px] text-muted-foreground">
          {exec.fields.length} field{exec.fields.length === 1 ? "" : "s"}
          {exec.reason ? ` · ${exec.reason}` : ""}
        </p>
      </div>
    </div>
  );
}

export function PartialFailures({ failures }: { failures: PartialFailure[] }) {
  return (
    <div className="rounded-lg border border-warning/30 bg-warning/10 p-2.5">
      <p className="mb-1.5 flex items-center gap-1.5 text-xs font-medium text-warning">
        <AlertTriangle className="h-3.5 w-3.5" /> Partial failures ({failures.length})
      </p>
      <ul className="space-y-1.5">
        {failures.map((pf, i) => (
          <li key={i} className="flex flex-wrap items-center gap-2 text-xs">
            <span className="font-medium">
              {pf.connector ?? pf.layer ?? pf.dataset ?? "connector"}
            </span>
            <span className="text-muted-foreground">{pf.reason}</span>
            <Badge className={pf.retryable ? "badge-lifecycle-beta" : "badge-muted"}>
              {pf.retryable ? "retryable" : "not retryable"}
            </Badge>
          </li>
        ))}
      </ul>
    </div>
  );
}

// --------------------------------------------------------------------------- //
// Shared bits                                                                  //
// --------------------------------------------------------------------------- //
function StageCard({
  icon,
  title,
  subtitle,
  children,
}: {
  icon: React.ReactNode;
  title: string;
  subtitle?: string;
  children: React.ReactNode;
}) {
  return (
    <div className="space-y-3 rounded-xl border border-border bg-card/60 p-4">
      <div className="flex items-center gap-2 border-b border-border/60 pb-2.5">
        {icon}
        <h3 className="text-sm font-semibold">{title}</h3>
        {subtitle && (
          <span className="ml-auto truncate font-mono text-xs text-muted-foreground">
            {subtitle}
          </span>
        )}
      </div>
      {children}
    </div>
  );
}

function Field({
  label,
  icon,
  children,
}: {
  label: string;
  icon?: React.ReactNode;
  children: React.ReactNode;
}) {
  return (
    <div className="space-y-1">
      <p className="flex items-center gap-1.5 text-xs font-medium text-muted-foreground">
        {icon}
        {label}
      </p>
      {children}
    </div>
  );
}

function ChipRow({
  items,
  mono,
  muted,
  empty,
}: {
  items: string[];
  mono?: boolean;
  muted?: boolean;
  empty?: string;
}) {
  if (items.length === 0) {
    return <span className="text-xs text-muted-foreground">{empty ?? "—"}</span>;
  }
  return (
    <div className="flex flex-wrap gap-1">
      {items.map((it) => (
        <span
          key={it}
          className={cn(
            "rounded-md border border-border bg-background/50 px-1.5 py-0.5 text-[11px]",
            mono && "font-mono",
            muted && "text-muted-foreground",
          )}
        >
          {it}
        </span>
      ))}
    </div>
  );
}

function MiniStat({
  label,
  value,
  tone = "muted",
}: {
  label: string;
  value: number;
  tone?: "success" | "warning" | "muted";
}) {
  const color =
    tone === "success" ? "text-success" : tone === "warning" ? "text-warning" : "text-foreground";
  return (
    <div className="rounded-lg border border-border bg-background/40 p-2 text-center">
      <p className={cn("text-lg font-semibold tabular-nums", color)}>{value}</p>
      <p className="text-[11px] text-muted-foreground">{label}</p>
    </div>
  );
}

function TokenFooter({
  prompt,
  completion,
  ms,
}: {
  prompt: number | null;
  completion: number | null;
  ms: number;
}) {
  return (
    <div className="flex flex-wrap items-center gap-x-3 gap-y-1 border-t border-border/60 pt-2 text-[11px] text-muted-foreground">
      <span className="inline-flex items-center gap-1">
        <Timer className="h-3 w-3" /> {formatMs(ms)}
      </span>
      {prompt != null && <span>prompt {prompt} tok</span>}
      {completion != null && <span>completion {completion} tok</span>}
    </div>
  );
}
