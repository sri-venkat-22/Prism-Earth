"use client";

import { useEffect, useRef, useState, type CSSProperties } from "react";

import { TerraMark } from "@/components/layout/logo";
import { cn } from "@/lib/utils";

/**
 * Terra motion library — the four ambient backdrops (specs 05–08), built from
 * the Ridge/Orbit mark and driven by the same tokens as the rest of the site.
 * The interaction specs (01 draw-on, 02 hover, 03 spinner, 04 btn-scan) already
 * live in globals.css / logo.tsx; these are the section- and hero-scale pieces.
 *
 * Accent maps to a brand token so every backdrop themes with one prop:
 *   brand → blue · brand-2 → terracotta · brand-3 → forest.
 */
export type Accent = "brand" | "brand-2" | "brand-3";
export type Speed = "slow" | "normal" | "fast";

const prefersReducedMotion = () =>
  typeof window !== "undefined" &&
  window.matchMedia?.("(prefers-reduced-motion: reduce)").matches;

/* ── 05 · Radar scan background ─────────────────────────────────────────────
   Contour rings, a conic beam (pure CSS), and blips that flash only as the beam
   sweeps past their angle — the flash is computed per-frame, exactly like a
   real radar refresh. `size` is the square field in px; it centres in its box. */

const RADAR_DUR: Record<Speed, number> = { slow: 11000, normal: 7000, fast: 4000 };
const BLIP_COUNT = 5;
const MIN_R = 0.29; // as a fraction of the field's half-size
const MAX_R = 0.9;
const GLOW_FADE_DEG = 70; // afterglow window once the beam passes a blip
const SWEEP_OFFSET_DEG = 54; // aligns the flash with the bright part of the trail

type Blip = { angle: number; radius: number };
type BlipStyle = { opacity: number; transform: string; boxShadow: string };

const makeBlip = (): Blip => ({
  angle: Math.random() * 360,
  radius: MIN_R + Math.random() * (MAX_R - MIN_R),
});

export function RadarScan({
  accent = "brand",
  speed = "normal",
  size,
  showMark = false,
  coordLabel,
  fade = false,
  className,
}: {
  accent?: Accent;
  speed?: Speed;
  /** Fixed field size in px. Omit to fill the parent (largest circle that fits). */
  size?: number;
  showMark?: boolean;
  coordLabel?: string;
  /** Soft-mask the top and bottom edges so the radar blends into the surface
      instead of ending on a hard circle edge (for full-bleed backdrops). */
  fade?: boolean;
  className?: string;
}) {
  const ref = useRef<HTMLDivElement>(null);
  const [measured, setMeasured] = useState(size ?? 0);
  const [blips, setBlips] = useState<BlipStyle[]>([]);
  const blipsRef = useRef<Blip[]>([]);

  // With no explicit size, fit the whole radar inside the parent so it never
  // clips — the field is the largest circle the box can hold, tracked on resize.
  useEffect(() => {
    if (size) {
      setMeasured(size);
      return;
    }
    const el = ref.current;
    if (!el) return;
    const measure = () => {
      const r = el.getBoundingClientRect();
      if (r.width && r.height) setMeasured(Math.min(r.width, r.height));
    };
    measure();
    const ro = new ResizeObserver(measure);
    ro.observe(el);
    return () => ro.disconnect();
  }, [size]);

  const field = measured || 300;
  const half = field / 2;
  const rings = [0.35, 0.56, 0.76, 0.97].map((f) => Math.round(field * f));

  useEffect(() => {
    if (prefersReducedMotion()) return;
    blipsRef.current = Array.from({ length: BLIP_COUNT }, makeBlip);
    const duration = RADAR_DUR[speed];
    const start = performance.now();
    let lastPhase = 0;
    let raf = 0;

    const frame = (now: number) => {
      const phase = ((now - start) % duration) / duration;
      // beam completed a revolution → relocate every blip, like a radar refresh
      if (phase < lastPhase) blipsRef.current = blipsRef.current.map(makeBlip);
      lastPhase = phase;

      const beamAngle = (phase * 360 + SWEEP_OFFSET_DEG) % 360;
      setBlips(
        blipsRef.current.map((b) => {
          const diff = (beamAngle - b.angle + 360) % 360; // 0 = beam on it now
          const intensity = diff <= GLOW_FADE_DEG ? (1 - diff / GLOW_FADE_DEG) ** 1.4 : 0;
          const rad = (b.angle * Math.PI) / 180;
          const px = Math.sin(rad) * b.radius * half;
          const py = -Math.cos(rad) * b.radius * half;
          const blur = (4 + intensity * 12).toFixed(1);
          const spread = (intensity * 4).toFixed(1);
          return {
            opacity: Number(intensity.toFixed(2)),
            transform: `translate(${px.toFixed(1)}px, ${py.toFixed(1)}px) scale(${(1 + intensity * 0.5).toFixed(2)})`,
            boxShadow: `0 0 ${blur}px ${spread}px hsl(var(--rad) / ${(intensity * 0.6).toFixed(2)})`,
          };
        }),
      );
      raf = requestAnimationFrame(frame);
    };
    raf = requestAnimationFrame(frame);
    return () => cancelAnimationFrame(raf);
  }, [speed, half]);

  return (
    <div
      ref={ref}
      aria-hidden
      className={cn("pointer-events-none absolute inset-0", className)}
      style={{
        ["--rad" as string]: `var(--${accent})`,
        ...(fade
          ? {
              maskImage: "linear-gradient(to bottom, transparent 0%, #000 22%, #000 78%, transparent 100%)",
              WebkitMaskImage: "linear-gradient(to bottom, transparent 0%, #000 22%, #000 78%, transparent 100%)",
            }
          : {}),
      }}
    >
      <div
        className="absolute left-1/2 top-1/2 flex -translate-x-1/2 -translate-y-1/2 items-center justify-center"
        style={{ width: field, height: field }}
      >
        {rings.map((r, i) => (
          <div
            key={r}
            className="absolute rounded-full border"
            style={{
              width: r,
              height: r,
              borderColor: `hsl(var(--foreground) / ${[0.1, 0.08, 0.06, 0.045][i]})`,
            }}
          />
        ))}
        <div className="radar-sweep absolute" style={{ width: field, height: field, ["--radar-dur" as string]: `${RADAR_DUR[speed] / 1000}s` }} />
        {blips.map((b, i) => (
          <span
            key={i}
            className="absolute h-2 w-2 rounded-full"
            style={{ background: "hsl(var(--rad))", opacity: b.opacity, transform: b.transform, boxShadow: b.boxShadow }}
          />
        ))}
        {showMark && <TerraMark className="relative h-14 w-14 text-foreground opacity-[0.16]" />}
        {coordLabel && (
          <span className="absolute bottom-2 left-3 font-mono text-[11px] text-faint">{coordLabel}</span>
        )}
      </div>
    </div>
  );
}

/* ── 06 · Live data pulse field ─────────────────────────────────────────────
   Staggered dots ripple like the hero's LIVE card; optional coordinate labels
   breathe over them. Pure CSS — each dot just carries its own delay. */

const PF_DOTS = [
  { x: 8, y: 60, d: 0 }, { x: 16, y: 24, d: 0.4 }, { x: 24, y: 78, d: 0.9 },
  { x: 33, y: 42, d: 1.3 }, { x: 41, y: 15, d: 0.2 }, { x: 49, y: 66, d: 1.7 },
  { x: 57, y: 30, d: 0.6 }, { x: 64, y: 82, d: 1.1 }, { x: 72, y: 50, d: 1.9 },
  { x: 80, y: 20, d: 0.3 }, { x: 87, y: 70, d: 1.5 }, { x: 93, y: 38, d: 0.8 },
  { x: 60, y: 12, d: 2.1 },
];
const PF_LABELS = [
  { x: 16, y: 24, text: "17.38, 78.48", d: 0 },
  { x: 64, y: 82, text: "21.14, 79.08", d: 1.2 },
  { x: 80, y: 20, text: "25.30, 82.97", d: 2.3 },
];

export function PulseField({
  accent = "brand-2",
  showLabels = true,
  className,
}: {
  accent?: Accent;
  showLabels?: boolean;
  className?: string;
}) {
  return (
    <div
      aria-hidden
      className={cn("pointer-events-none absolute inset-0 overflow-hidden", className)}
      style={{ ["--pf" as string]: `var(--${accent})` }}
    >
      {PF_DOTS.map((dot, i) => (
        <span
          key={i}
          className="pulse-field-dot"
          style={{
            left: `${dot.x}%`,
            top: `${dot.y}%`,
            width: 6,
            height: 6,
            margin: -3,
            background: "hsl(var(--pf))",
            animationDelay: `${dot.d}s`,
          }}
        />
      ))}
      {showLabels &&
        PF_LABELS.map((l, i) => (
          <span
            key={i}
            className="pf-label absolute whitespace-nowrap font-mono text-[10px] text-muted-foreground"
            style={{ left: `${l.x}%`, top: `${l.y}%`, transform: "translate(10px,-6px)", animationDelay: `${l.d}s` }}
          >
            {l.text}
          </span>
        ))}
    </div>
  );
}

/* ── 07 · Satellite orbit backdrop ──────────────────────────────────────────
   Layered slow orbits behind hero copy — calm enough to read over. The 0-size
   anchors are flex-centred, so each node rotates around the mark. */

const ORBITS: { r: number; dur: number; accent: Accent }[] = [
  { r: 70, dur: 22, accent: "brand" },
  { r: 110, dur: 30, accent: "brand-2" },
  { r: 150, dur: 38, accent: "brand-3" },
];

export function OrbitBackdrop({
  direction = "cw",
  showRings = true,
  showMark = true,
  className,
}: {
  direction?: "cw" | "ccw";
  showRings?: boolean;
  showMark?: boolean;
  className?: string;
}) {
  const dir = direction === "ccw" ? "reverse" : "normal";
  return (
    <div
      aria-hidden
      className={cn("pointer-events-none relative flex items-center justify-center overflow-hidden", className)}
    >
      {showRings &&
        [140, 220, 300].map((s, i) => (
          <div
            key={s}
            className="absolute rounded-full border"
            style={{ width: s, height: s, borderColor: `hsl(var(--foreground) / ${[0.12, 0.09, 0.06][i]})` }}
          />
        ))}
      {ORBITS.map((o) => (
        <div
          key={o.r}
          className="orbit-anchor"
          style={{ ["--orbit-dur" as string]: `${o.dur}s`, animationDirection: dir } as CSSProperties}
        >
          <span
            className="absolute h-2 w-2 rounded-full"
            style={{ top: -o.r, left: -4, background: `hsl(var(--${o.accent}))` }}
          />
        </div>
      ))}
      {showMark && <TerraMark className="absolute h-14 w-14 text-foreground" />}
    </div>
  );
}

/* ── 08 · Contour ridge drift ───────────────────────────────────────────────
   A quiet parallax texture for section dividers: the mark's ridge, tiled and
   scrolling. Identical evenly-spaced tiles make translateX(-50%) seamless. */

const DRIFT_LAYERS: {
  w: number; h: number; sw: number; gap: number; opacity: number; dur: Record<Speed, number>; reverse: boolean; outer: boolean;
}[] = [
  { w: 28, h: 16, sw: 10, gap: 22, opacity: 0.2, dur: { slow: 32, normal: 20, fast: 11 }, reverse: false, outer: true },
  { w: 34, h: 20, sw: 9, gap: 26, opacity: 0.4, dur: { slow: 44, normal: 28, fast: 16 }, reverse: true, outer: false },
  { w: 40, h: 24, sw: 8, gap: 30, opacity: 0.6, dur: { slow: 22, normal: 14, fast: 8 }, reverse: false, outer: true },
];
const DRIFT_TILES = Array.from({ length: 40 });

export function RidgeDrift({
  speed = "normal",
  singleLayer = false,
  className,
}: {
  speed?: Speed;
  singleLayer?: boolean;
  className?: string;
}) {
  const layers = singleLayer ? DRIFT_LAYERS.filter((l) => !l.outer) : DRIFT_LAYERS;
  return (
    <div aria-hidden className={cn("pointer-events-none flex flex-col justify-center gap-[22px] overflow-hidden text-foreground", className)}>
      {layers.map((layer, li) => (
        <div key={li} className="relative overflow-hidden" style={{ height: layer.h + 4 }}>
          <div
            className="drift-track items-center"
            style={{ opacity: layer.opacity, animationDirection: layer.reverse ? "reverse" : "normal", ["--drift-dur" as string]: `${layer.dur[speed]}s` } as CSSProperties}
          >
            {DRIFT_TILES.map((_, i) => (
              <svg
                key={i}
                viewBox="0 0 64 64"
                width={layer.w}
                height={layer.h}
                fill="none"
                className="shrink-0"
                style={{ marginRight: layer.gap }}
              >
                <polyline
                  points="8,48 32,20 56,48"
                  stroke="currentColor"
                  strokeWidth={layer.sw}
                  strokeLinecap="square"
                  strokeLinejoin="miter"
                />
              </svg>
            ))}
          </div>
        </div>
      ))}
    </div>
  );
}

/* Full-page version of 08 — a fixed, faint field of drifting ridge rows that
   sits behind all page content and repeats, so the whole surface reads as the
   mark's contour texture. Same GPU-cheap transform drift; reduced-motion safe. */
const BG_ROWS = [
  { w: 26, h: 15, sw: 10, gap: 26, opacity: 0.05, dur: 40, reverse: false },
  { w: 29, h: 16, sw: 9, gap: 28, opacity: 0.07, dur: 32, reverse: true },
  { w: 33, h: 19, sw: 8, gap: 32, opacity: 0.1, dur: 24, reverse: false },
  { w: 29, h: 16, sw: 9, gap: 28, opacity: 0.07, dur: 30, reverse: true },
];
const BG_TILES = Array.from({ length: 48 });

export function RidgeBackdrop({ rows = 14, className }: { rows?: number; className?: string }) {
  return (
    <div
      aria-hidden
      className={cn("pointer-events-none fixed inset-0 -z-10 overflow-hidden text-foreground", className)}
    >
      <div className="flex h-full flex-col justify-between py-4">
        {Array.from({ length: rows }, (_, i) => {
          const r = BG_ROWS[i % BG_ROWS.length];
          return (
            <div key={i} className="relative overflow-hidden" style={{ height: r.h + 4 }}>
              <div
                className="drift-track items-center"
                style={{ opacity: r.opacity, animationDirection: r.reverse ? "reverse" : "normal", ["--drift-dur" as string]: `${r.dur}s` } as CSSProperties}
              >
                {BG_TILES.map((_, t) => (
                  <svg
                    key={t}
                    viewBox="0 0 64 64"
                    width={r.w}
                    height={r.h}
                    fill="none"
                    className="shrink-0"
                    style={{ marginRight: r.gap }}
                  >
                    <polyline
                      points="8,48 32,20 56,48"
                      stroke="currentColor"
                      strokeWidth={r.sw}
                      strokeLinecap="square"
                      strokeLinejoin="miter"
                    />
                  </svg>
                ))}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
