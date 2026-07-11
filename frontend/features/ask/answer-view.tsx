import { Quote } from "lucide-react";

import { cn } from "@/lib/utils";

/**
 * Renders the synthesized answer (SRS §13.13) as clean prose. The backend
 * guarantees no inline citation markers — sourcing rides in the response's
 * citations/provenance and is shown behind the details toggle (SRS §38.5).
 */
export function AnswerView({ answer, className }: { answer: string; className?: string }) {
  return (
    <div className={cn("rounded-xl border border-border bg-card p-6 sm:p-8", className)}>
      <div className="mono-eyebrow mb-4 flex items-center gap-2">
        <Quote className="h-3.5 w-3.5" /> Answer
      </div>
      <div className="space-y-4 text-[16px] leading-[1.7] text-foreground">
        {answer.split(/\n{2,}/).map((para, i) => (
          <p key={i}>{para}</p>
        ))}
      </div>
    </div>
  );
}
