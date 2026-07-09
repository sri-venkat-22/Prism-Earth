import { cn } from "@/lib/utils";

/** The Terra wordmark: a triangular glyph refracting a single accent ray. */
export function Logo({ className, withText = true }: { className?: string; withText?: boolean }) {
  return (
    <span className={cn("inline-flex items-center gap-2.5", className)}>
      <svg
        viewBox="0 0 32 32"
        className="h-6 w-6 shrink-0"
        role="img"
        aria-label="Terra"
        fill="none"
      >
        <path
          d="M16 4 L27 23 H5 Z"
          stroke="hsl(var(--foreground))"
          strokeWidth="1.6"
          strokeLinejoin="round"
        />
        {/* refracted ray entering and dispersing */}
        <path d="M3 15 L12 15" stroke="hsl(var(--muted-foreground))" strokeWidth="1.4" />
        <path d="M18 15 L30 12.5" stroke="hsl(var(--brand))" strokeWidth="1.4" />
        <path d="M18 16.6 L30 16.6" stroke="hsl(var(--brand-2))" strokeWidth="1.4" />
        <path d="M18 18.2 L30 20.5" stroke="hsl(var(--brand-3))" strokeWidth="1.4" />
      </svg>
      {withText && (
        <span className="font-display text-[15px] font-semibold tracking-tight">Terra</span>
      )}
    </span>
  );
}
