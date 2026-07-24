"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { ArrowRight, ArrowUpRight } from "lucide-react";

import { TerraMark } from "@/components/layout/logo";
import { RadarScan, RidgeBackdrop } from "@/components/motion/backdrops";
import { Reveal } from "@/components/reveal";
import { SectionHeading } from "@/components/section-heading";
import { TerminalLine, TerminalWindow } from "@/components/terminal-window";
import { useConnectorsHealth, useFields, useLayers, usePresets } from "@/hooks/useMeta";

const DOCS_URL = process.env.NEXT_PUBLIC_API_DOCS_URL ?? "http://localhost:8000/docs";

const ENDPOINTS = [
  {
    method: "POST",
    path: "/ask",
    title: "Natural-language ask",
    desc: "A planner selects catalog fields, the fetch engine retrieves them deterministically, and the synthesizer answers — with citations, provenance, and a full execution trace.",
  },
  {
    method: "POST",
    path: "/fetch",
    title: "Deterministic fetch",
    desc: "Raw field values for any coordinate. No model in the loop — just sourced values, units, confidence, and the dataset each one came from.",
  },
  {
    method: "GET",
    path: "/meta/*",
    title: "Self-describing catalog",
    desc: "Every layer, field, preset, and region is discoverable at runtime. The platform never invents a field it cannot source.",
  },
];

const FAQ = [
  {
    q: "What does “ground truth” mean here?",
    a: "Every value Terra returns is fetched from a named, versioned dataset and carries its own provenance — source, license, retrieval time, and confidence. The synthesizer only states values that were actually fetched and explicitly flags anything unavailable. It never fabricates data.",
  },
  {
    q: "Which regions are supported?",
    a: "The platform is built for all of India, with Telangana as the fully-enabled pilot region. Nationwide fields resolve everywhere; region-gated fields resolve where the underlying datasets are enabled. Coverage is always reported per field.",
  },
  {
    q: "How is an answer produced?",
    a: "Three deterministic stages — plan, fetch, synthesize. The planner can only choose fields that exist in the catalog; the fetch engine calls connectors in parallel; the synthesizer composes an answer strictly from the fetched values. The entire trace is returned so you can audit exactly what ran.",
  },
  {
    q: "Is it built for AI agents?",
    a: "Yes. The REST surface is designed to be a reliable tool for physical-world agents: structured, cited, and honest about gaps — so an agent can reason over geospatial facts without guessing.",
  },
];

const ROTATING_WORDS = ["terrain", "climate", "land cover", "natural hazard", "AI agents"];

/**
 * Typewriter headline: types the current layer one letter at a time, holds,
 * then backspaces it letter by letter before typing the next. Falls back to a
 * plain word-swap under prefers-reduced-motion.
 */
function RotatingWord() {
  const [wordIndex, setWordIndex] = useState(0);
  const [text, setText] = useState("");
  const [deleting, setDeleting] = useState(false);
  const [reduced, setReduced] = useState(false);

  useEffect(() => {
    setReduced(window.matchMedia("(prefers-reduced-motion: reduce)").matches);
  }, []);

  useEffect(() => {
    const full = ROTATING_WORDS[wordIndex];

    if (reduced) {
      setText(full);
      const t = setTimeout(() => setWordIndex((i) => (i + 1) % ROTATING_WORDS.length), 2000);
      return () => clearTimeout(t);
    }
    if (!deleting && text === full) {
      const t = setTimeout(() => setDeleting(true), 1500); // hold on the full word
      return () => clearTimeout(t);
    }
    if (deleting && text === "") {
      const t = setTimeout(() => {
        setDeleting(false);
        setWordIndex((i) => (i + 1) % ROTATING_WORDS.length);
      }, 300);
      return () => clearTimeout(t);
    }
    const t = setTimeout(
      () => setText((prev) => (deleting ? full.slice(0, prev.length - 1) : full.slice(0, prev.length + 1))),
      deleting ? 45 : 95,
    );
    return () => clearTimeout(t);
  }, [text, deleting, wordIndex, reduced]);

  return (
    <>
      <span className="text-brand">{text}</span>
      <span aria-hidden className="blink-cursor text-brand">
        |
      </span>
    </>
  );
}

/** Hero readout card: a LIVE coordinate sample pinned beside the mark. */
function LiveReadout({ lines, className }: { lines: [string, string][]; className?: string }) {
  return (
    <div
      className={`w-[196px] rounded-md border border-border bg-card p-3 text-left font-mono text-[11px] leading-[1.7] text-muted-foreground shadow-[0_16px_40px_-28px_hsl(var(--foreground)/0.4)] ${className ?? ""}`}
    >
      <div className="flex items-center gap-1.5 font-semibold text-danger">
        <span className="pulse-dot-live inline-block h-1.5 w-1.5 rounded-full bg-danger" />
        LIVE&nbsp;&nbsp;17.385, 78.486
      </div>
      {lines.map(([k, v]) => (
        <div key={k} className="mt-0.5 flex gap-2">
          <span className="w-14">{k}</span>
          <span>{v}</span>
        </div>
      ))}
    </div>
  );
}

export default function HomePage() {
  const layers = useLayers();
  const presets = usePresets();
  const fields = useFields();
  const connectors = useConnectorsHealth();

  const stats = [
    { label: "Domain layers", value: layers.data?.count },
    { label: "Query presets", value: presets.data?.count },
    { label: "Catalog fields", value: fields.data?.count },
    { label: "Live connectors", value: connectors.data?.count },
  ];

  return (
    <div className="space-y-24 sm:space-y-32">
      {/* Contour ridge drift (motion spec 08) as the page's ambient background —
          a faint, repeating, drifting field of the mark's ridge behind all content. */}
      <RidgeBackdrop />

      {/* Hero — Ridge/Orbit mark inside contour rings, live readouts pinned */}
      <section className="mx-auto max-w-[900px] animate-fade-up text-center">
        <div className="inline-flex items-center rounded-full border border-border bg-card px-4 py-2 font-mono text-xs text-muted-foreground">
          Sourced from Copernicus · ESA · JRC datasets
        </div>

        <div className="relative mx-auto mt-8 h-[300px] w-full max-w-[560px] overflow-hidden sm:h-[380px]">
          {/* Live radar sweep (motion spec 05) — contour rings, sweeping beam,
              blips that flash where data lands, behind the draw-on mark. Fills
              the box and fades at top/bottom so it blends into the surface. */}
          <RadarScan accent="brand" fade />
          <TerraMark
            twoTone
            className="logo-draw absolute left-1/2 top-1/2 h-[86px] w-[86px] -translate-x-1/2 -translate-y-[58%] text-foreground"
          />
          <LiveReadout
            className="absolute left-0 top-[2%] hidden sm:block"
            lines={[
              ["slope", "2.4°"],
              ["source", "COPERNICUS_DEM"],
            ]}
          />
          <LiveReadout
            className="absolute bottom-[4%] right-0 hidden sm:block"
            lines={[
              ["cover", "cropland"],
              ["source", "ESA_WORLDCOVER"],
            ]}
          />
        </div>

        <h1 className="font-display text-[clamp(38px,6vw,68px)] font-bold leading-[1.06] tracking-[-0.02em]">
          Ground truth for
          <br />
          <RotatingWord />
        </h1>
        <p className="mx-auto mt-6 max-w-xl text-[17px] leading-relaxed text-muted-foreground">
          Terra gives AI agents and analysts sourced, citation-backed data for any Indian coordinate
          — terrain, climate, land cover, hazard, infrastructure and more. Every value traces to a
          dataset. Nothing is ever invented.
        </p>
        <div className="mt-8 flex flex-wrap items-center justify-center gap-3">
          <Link
            href="/ask"
            className="btn-scan inline-flex items-center gap-2 rounded-full bg-primary px-5 py-2.5 text-sm font-medium text-primary-foreground transition-transform duration-200 ease-expo hover:-translate-y-0.5"
          >
            Ask a question <ArrowRight className="h-4 w-4" />
          </Link>
          <a
            href={DOCS_URL}
            target="_blank"
            rel="noreferrer"
            className="inline-flex items-center gap-1 px-2 py-2.5 text-sm text-muted-foreground transition-colors hover:text-foreground"
          >
            Read the docs <ArrowUpRight className="h-3.5 w-3.5" />
          </a>
        </div>
      </section>

      {/* Live stats */}
      <section>
        <div className="grid grid-cols-2 gap-px overflow-hidden rounded-lg border border-border bg-border sm:grid-cols-4">
          {stats.map((s) => (
            <div key={s.label} className="bg-card px-5 py-6">
              <p className="font-display text-3xl font-semibold tabular-nums">{s.value ?? "—"}</p>
              <p className="mono-eyebrow mt-2">{s.label}</p>
            </div>
          ))}
        </div>
      </section>

      {/* Live /ask example */}
      <section className="mx-auto max-w-[900px]">
        <Reveal>
          <div className="text-center">
            <p className="mono-eyebrow">Live example</p>
            <h2 className="mt-3 font-display text-[clamp(26px,4vw,38px)] font-semibold tracking-[-0.01em]">
              Ask a question, get a cited answer.
            </h2>
          </div>
        </Reveal>
        <Reveal delay={100} className="mt-10 block">
          <TerminalWindow title="terra · POST /api/v1/ask">
            <div className="space-y-2.5">
              <TerminalLine prefix="$" tone="muted">
                curl -s terra.earth/api/v1/ask -d &apos;{"{"}
              </TerminalLine>
              <TerminalLine tone="muted">{'  "lat": 17.385, "lng": 78.486,'}</TerminalLine>
              <TerminalLine tone="muted">
                {'  "question": "Is this site suitable for a solar farm?" }\''}
              </TerminalLine>
              <div className="my-2 border-t border-border" />
              <TerminalLine tone="comment">
                # planner → 3 layers · fetch → 7 fields · synthesize
              </TerminalLine>
              <TerminalLine tone="success">
                Terrain here is gently sloped (mean slope 2.4°){" "}
                <span className="rounded border border-brand/40 bg-brand/10 px-1 text-brand">
                  [CIT-001]
                </span>{" "}
                and land cover is predominantly cropland{" "}
                <span className="rounded border border-brand/40 bg-brand/10 px-1 text-brand">
                  [CIT-002]
                </span>
                ; flood hazard is low{" "}
                <span className="rounded border border-brand/40 bg-brand/10 px-1 text-brand">
                  [CIT-003]
                </span>
                . Solar irradiance is not yet in the catalog — flagged unavailable, never estimated.
              </TerminalLine>
              <div className="my-2 border-t border-border" />
              <TerminalLine tone="comment">
                # CIT-001 Copernicus DEM GLO-30 · CIT-002 ESA WorldCover
              </TerminalLine>
              <TerminalLine tone="comment">
                # CIT-003 JRC Global River Flood Hazard Maps
              </TerminalLine>
            </div>
          </TerminalWindow>
          <p className="mt-3 text-center text-[11px] text-faint">
            Illustrative response · every claim carries a citation
          </p>
        </Reveal>
      </section>

      {/* For AI agents */}
      <section>
        <Reveal>
          <SectionHeading
            eyebrow="For AI agents"
            title="A tool your agent can trust."
            description="Three endpoints, all self-describing and audit-ready. Structured in, sourced out — and honest about what it doesn't know."
          />
        </Reveal>
        <div className="mt-10 grid gap-px overflow-hidden rounded-lg border border-border bg-border lg:grid-cols-3">
          {ENDPOINTS.map((e, i) => (
            <Reveal key={e.path} delay={i * 70} className="bg-card">
              <div className="flex h-full flex-col p-6">
                <div className="flex items-center gap-2">
                  <span className="rounded border border-border bg-secondary px-1.5 py-0.5 font-mono text-[10px] font-semibold uppercase text-muted-foreground">
                    {e.method}
                  </span>
                  <span className="font-mono text-sm font-medium">{e.path}</span>
                </div>
                <h3 className="mt-4 text-[17px] font-semibold">{e.title}</h3>
                <p className="mt-1.5 flex-1 text-sm leading-relaxed text-muted-foreground">
                  {e.desc}
                </p>
              </div>
            </Reveal>
          ))}
        </div>
      </section>

      {/* FAQ */}
      <section id="faq" className="scroll-mt-24">
        <Reveal>
          <SectionHeading eyebrow="FAQ" title="The short version." />
        </Reveal>
        <div className="mx-auto mt-10 max-w-3xl divide-y divide-border border-y border-border">
          {FAQ.map((item) => (
            <details key={item.q} className="group py-5">
              <summary className="flex cursor-pointer list-none items-center justify-between gap-4 text-[17px] font-medium">
                {item.q}
                <span className="text-muted-foreground transition-transform duration-200 ease-expo group-open:rotate-45">
                  <ArrowRight className="h-4 w-4 rotate-45" />
                </span>
              </summary>
              <p className="mt-3 max-w-2xl text-[15px] leading-relaxed text-muted-foreground">
                {item.a}
              </p>
            </details>
          ))}
        </div>
      </section>

      {/* CTA */}
      <section className="rounded-xl border border-border bg-card px-6 py-14 text-center sm:py-20">
        <p className="mono-eyebrow mb-4">Start with a coordinate</p>
        <h2 className="mx-auto max-w-2xl font-display text-[clamp(26px,4vw,44px)] font-semibold leading-[1.05]">
          See what the platform knows — and what it doesn&apos;t.
        </h2>
        <div className="mt-8 flex flex-wrap justify-center gap-3">
          <Link
            href="/ask"
            className="btn-scan inline-flex items-center gap-2 rounded-full bg-primary px-5 py-2.5 text-sm font-medium text-primary-foreground transition-transform duration-200 ease-expo hover:-translate-y-0.5"
          >
            Ask a question <ArrowRight className="h-4 w-4" />
          </Link>
        </div>
      </section>
    </div>
  );
}
