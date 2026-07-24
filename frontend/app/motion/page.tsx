"use client";

import { useEffect, useState, type ReactNode } from "react";
import { ArrowRight, RotateCw } from "lucide-react";

import { OrbitSpinner, TerraMark } from "@/components/layout/logo";
import { OrbitBackdrop, PulseField, RadarScan, RidgeDrift } from "@/components/motion/backdrops";
import { SectionHeading } from "@/components/section-heading";
import { cn } from "@/lib/utils";

/**
 * Terra Motion Library — the living reference for the eight brand motion
 * primitives, all built from the Ridge/Orbit mark. Interaction specs (01–04)
 * are the classes shipped in globals.css; backdrops (05–08) are the components
 * in components/motion. Every card below is the real asset, running.
 */

/** Framed preview stage with corner ticks — the motion-spec look. */
function Stage({ children, className }: { children: ReactNode; className?: string }) {
  const tick = "absolute h-3.5 w-3.5 border-foreground/20";
  return (
    <div
      className={cn(
        "relative flex items-center justify-center overflow-hidden rounded-2xl border border-border bg-card",
        className,
      )}
    >
      <span className={cn(tick, "left-2.5 top-2.5 border-l-2 border-t-2")} />
      <span className={cn(tick, "right-2.5 top-2.5 border-r-2 border-t-2")} />
      <span className={cn(tick, "bottom-2.5 left-2.5 border-b-2 border-l-2")} />
      <span className={cn(tick, "bottom-2.5 right-2.5 border-b-2 border-r-2")} />
      {children}
    </div>
  );
}

function Spec({
  n,
  title,
  desc,
  wide,
  stageClass,
  children,
}: {
  n: string;
  title: string;
  desc: string;
  wide?: boolean;
  stageClass?: string;
  children: ReactNode;
}) {
  return (
    <div className={cn("flex flex-col", wide && "lg:col-span-2")}>
      <Stage className={cn("h-[280px]", stageClass)}>{children}</Stage>
      <div className="mt-4">
        <p className="mono-eyebrow">
          {n} <span className="text-faint">/ 08</span>
        </p>
        <h3 className="mt-2 text-[17px] font-semibold">{title}</h3>
        <p className="mt-1.5 max-w-xl text-sm leading-relaxed text-muted-foreground">{desc}</p>
      </div>
    </div>
  );
}

const PILL =
  "inline-flex items-center gap-2 rounded-full px-4 py-2 text-sm font-medium transition-transform duration-200 ease-expo hover:-translate-y-0.5";

/* 01 — remount the mark to replay the draw-on animation. */
function DrawOnDemo() {
  const [key, setKey] = useState(0);
  return (
    <div className="flex flex-col items-center gap-6">
      <TerraMark key={key} twoTone className="logo-draw h-24 w-24 text-foreground" />
      <button
        type="button"
        onClick={() => setKey((k) => k + 1)}
        className="inline-flex items-center gap-1.5 rounded-full border border-input bg-background px-4 py-1.5 font-mono text-xs font-semibold transition-colors hover:bg-accent"
      >
        <RotateCw className="h-3.5 w-3.5" /> Replay
      </button>
    </div>
  );
}

const FETCH_WORDS = ["terrain", "climate", "land cover", "hazard", "infrastructure"];

/* 03 — the orbit spinner with a rotating fetch readout. */
function SpinnerDemo() {
  const [i, setI] = useState(0);
  useEffect(() => {
    const t = setInterval(() => setI((v) => (v + 1) % FETCH_WORDS.length), 1100);
    return () => clearInterval(t);
  }, []);
  return (
    <div className="flex flex-col items-center gap-5">
      <OrbitSpinner className="h-20 w-20 text-foreground" />
      <div className="font-mono text-[11px] uppercase tracking-[0.06em] text-muted-foreground">
        <span className="text-brand-2">●</span>&nbsp;&nbsp;Fetching&nbsp;·&nbsp;{FETCH_WORDS[i]}
      </div>
    </div>
  );
}

export default function MotionPage() {
  return (
    <div className="space-y-14">
      <SectionHeading
        eyebrow="Terra motion library"
        title="Eight motions, one mark."
        description="Every animation on the site descends from the Ridge/Orbit mark — an elevation ridge crossed by a satellite pass. Entrances draw it on, loaders orbit it, backdrops tile and sweep it. All CSS-first and reduced-motion aware."
      />

      <div className="grid grid-cols-1 gap-x-8 gap-y-12 lg:grid-cols-2">
        {/* 01 */}
        <Spec
          n="01"
          title="Logo draw-on reveal"
          desc="Page-load and nav-mount entrance — the ridge draws, the orbit follows, the node locks in with a spring."
        >
          <DrawOnDemo />
        </Spec>

        {/* 02 */}
        <Spec
          n="02"
          title="Nav logo hover"
          desc="Hover the mark — the orbit re-scans and the node locks on, the same lift the site's buttons use."
        >
          <span className="logo-lockup inline-flex cursor-pointer items-center gap-3.5">
            <TerraMark className="h-12 w-12 text-foreground" />
            <span className="font-display text-3xl font-semibold tracking-tight">Terra</span>
          </span>
        </Spec>

        {/* 03 */}
        <Spec
          n="03"
          title="Loading / processing spinner"
          desc="The orbit becomes the loader — the ridge holds still as ground truth while the satellite pass fetches."
        >
          <SpinnerDemo />
        </Spec>

        {/* 04 */}
        <Spec
          n="04"
          title="CTA scan hover"
          desc="The site's existing lift, plus a quick scan-line sweeping across primary and secondary actions."
        >
          <div className="flex flex-col items-center gap-4">
            <button type="button" className={cn(PILL, "btn-scan bg-primary text-primary-foreground")}>
              Ask a question <ArrowRight className="h-4 w-4" />
            </button>
            <button
              type="button"
              className={cn(PILL, "btn-scan border border-input bg-background hover:bg-accent")}
            >
              Explore the map
            </button>
          </div>
        </Spec>

        {/* 05 */}
        <Spec
          n="05"
          title="Radar scan background"
          desc="Full-bleed hero ambience — contour rings, a sweeping beam, and blips that flash where data lands, then relocate on each pass. It's what runs behind the mark on the home page."
          wide
          stageClass="h-[360px]"
        >
          <RadarScan accent="brand" size={300} showMark coordLabel="17.385°N  78.486°E" />
        </Spec>

        {/* 06 */}
        <Spec
          n="06"
          title="Live data pulse field"
          desc="Subtle texture behind text or a full-section backdrop — reuses the hero LIVE-card pulse, staggered across a field of coordinates."
          wide
          stageClass="h-[300px]"
        >
          <PulseField accent="brand-2" />
        </Spec>

        {/* 07 */}
        <Spec
          n="07"
          title="Satellite orbit backdrop"
          desc="Slow, layered orbits sitting behind hero copy — three nodes on three rings, calm enough to read over."
          wide
          stageClass="h-[360px]"
        >
          <OrbitBackdrop className="h-full w-full" />
        </Spec>

        {/* 08 */}
        <Spec
          n="08"
          title="Contour ridge drift"
          desc="A quiet parallax texture for section dividers, built from the mark's own ridge, tiled and drifting in opposing directions for depth."
          wide
          stageClass="h-[240px]"
        >
          <RidgeDrift className="w-full px-8" />
        </Spec>
      </div>
    </div>
  );
}
