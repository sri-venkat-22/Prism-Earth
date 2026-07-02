import type { ReactNode } from "react";

import { cn } from "@/lib/utils";

/**
 * Editorial section header (mireye): a small uppercase mono eyebrow above a Sora
 * display heading, with optional supporting copy and a right-aligned action slot.
 */
export function SectionHeading({
  eyebrow,
  title,
  description,
  action,
  align = "left",
  className,
}: {
  eyebrow?: string;
  title: ReactNode;
  description?: ReactNode;
  action?: ReactNode;
  align?: "left" | "center";
  className?: string;
}) {
  const centered = align === "center";
  return (
    <div
      className={cn(
        "flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between",
        centered && "sm:flex-col sm:items-center sm:text-center",
        className,
      )}
    >
      <div className={cn("max-w-2xl", centered && "mx-auto")}>
        {eyebrow && <p className="mono-eyebrow mb-3">{eyebrow}</p>}
        <h2 className="font-display text-[clamp(26px,3.6vw,40px)] font-semibold leading-[1.08] tracking-tight">
          {title}
        </h2>
        {description && (
          <p className="mt-3 text-[15px] leading-relaxed text-muted-foreground">{description}</p>
        )}
      </div>
      {action && <div className="shrink-0">{action}</div>}
    </div>
  );
}
