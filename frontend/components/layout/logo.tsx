import { cn } from "@/lib/utils";

/**
 * The Terra "Ridge / Orbit" mark: an elevation ridge crossed by a satellite
 * pass, with a data-node where the pass reads the ground. Strokes inherit
 * currentColor; `twoTone` renders the node in the brand blue.
 */
export function TerraMark({
  className,
  twoTone = false,
}: {
  className?: string;
  twoTone?: boolean;
}) {
  return (
    <svg viewBox="0 0 64 64" className={className} role="img" aria-label="Terra" fill="none">
      <polyline
        className="tm-ridge"
        points="8,48 32,20 56,48"
        stroke="currentColor"
        strokeWidth="7.5"
        strokeLinecap="square"
        strokeLinejoin="miter"
      />
      <path
        className="tm-arc"
        d="M 6,16 A 30,30 0 0 1 50,10"
        stroke="currentColor"
        strokeWidth="5"
        strokeLinecap="square"
      />
      <circle
        className="tm-node"
        cx="50"
        cy="10"
        r="6"
        fill={twoTone ? "hsl(var(--brand))" : "currentColor"}
      />
    </svg>
  );
}

/**
 * Nav/footer lockup. Draws on once when mounted (ridge → orbit → node) and
 * re-scans the orbit on hover — both pure CSS, see .logo-draw / .logo-lockup.
 */
export function Logo({ className, withText = true }: { className?: string; withText?: boolean }) {
  return (
    <span className={cn("logo-lockup inline-flex items-center gap-2.5", className)}>
      <TerraMark className="logo-draw h-6 w-6 shrink-0" />
      {withText && (
        <span className="font-display text-[15px] font-semibold tracking-tight">Terra</span>
      )}
    </span>
  );
}

/**
 * Loading state built from the mark: the ridge holds still as ground truth
 * while the satellite pass sweeps. From the Terra motion library (03/08).
 */
export function OrbitSpinner({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 64 64" className={className} aria-hidden fill="none">
      <polyline
        points="8,48 32,20 56,48"
        stroke="currentColor"
        strokeWidth="7.5"
        strokeLinecap="square"
        strokeLinejoin="miter"
        opacity="0.28"
      />
      <g className="orbit-sweep">
        <path
          d="M 6,16 A 30,30 0 0 1 50,10"
          stroke="hsl(var(--brand))"
          strokeWidth="5"
          strokeLinecap="square"
        />
        <circle cx="50" cy="10" r="6" fill="hsl(var(--brand))" />
      </g>
    </svg>
  );
}
