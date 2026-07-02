import type { ReactNode } from "react";

import { cn } from "@/lib/utils";

/**
 * macOS-style terminal window — mireye's signature motif for API/code surfaces.
 * Used for the landing `/ask` demo and any request/response transcript.
 */
export function TerminalWindow({
  title,
  children,
  className,
  bodyClassName,
}: {
  title?: string;
  children: ReactNode;
  className?: string;
  bodyClassName?: string;
}) {
  return (
    <div className={cn("terminal", className)}>
      <div className="terminal-bar">
        <span className="win-dot" style={{ background: "#ff5f57" }} />
        <span className="win-dot" style={{ background: "#febc2e" }} />
        <span className="win-dot" style={{ background: "#28c840" }} />
        {title && (
          <span className="ml-2 truncate font-mono text-[11px] text-muted-foreground">{title}</span>
        )}
      </div>
      <div className={cn("p-4 font-mono text-[12.5px] leading-relaxed sm:p-5", bodyClassName)}>
        {children}
      </div>
    </div>
  );
}

/** A single request/response line with a subtle role prefix, for transcripts. */
export function TerminalLine({
  prefix,
  tone = "default",
  children,
}: {
  prefix?: string;
  tone?: "default" | "muted" | "brand" | "success" | "comment";
  children: ReactNode;
}) {
  const toneClass =
    tone === "muted"
      ? "text-muted-foreground"
      : tone === "brand"
        ? "text-brand"
        : tone === "success"
          ? "text-success"
          : tone === "comment"
            ? "text-faint"
            : "text-foreground";
  return (
    <div className={cn("flex gap-2", toneClass)}>
      {prefix && <span className="select-none text-faint">{prefix}</span>}
      <span className="min-w-0 flex-1 whitespace-pre-wrap break-words">{children}</span>
    </div>
  );
}
