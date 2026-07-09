"use client";

import Link from "next/link";
import { ArrowRight, Boxes } from "lucide-react";

import { ErrorState, LoadingBlock } from "@/components/feedback";
import { PageHeader } from "@/components/page-header";
import { Reveal } from "@/components/reveal";
import { layerMeta } from "@/lib/domain";
import { usePresets } from "@/hooks/useMeta";

export default function UseCasesPage() {
  const presets = usePresets();

  return (
    <div>
      <PageHeader
        eyebrow="Use cases"
        title="Ready-made presets for real questions."
        icon={<Boxes className="h-7 w-7 text-brand" />}
        description={
          presets.data
            ? `${presets.data.count} presets bundle the right fields for a job — siting, risk, and lookup queries you can run in one call.`
            : "Presets bundle the right fields for a job — siting, risk, and lookup queries you can run in one call."
        }
      />

      {presets.isLoading && <LoadingBlock rows={3} className="mt-8" />}
      {presets.isError && (
        <ErrorState
          error={presets.error}
          onRetry={() => presets.refetch()}
          title="Couldn't load presets"
          className="mt-8"
        />
      )}
      {presets.data && (
        <div className="grid gap-px overflow-hidden rounded-lg border border-border bg-border sm:grid-cols-2 lg:grid-cols-3">
          {presets.data.presets.map((preset, i) => {
            const meta = layerMeta(preset.layers[0] ?? "");
            const Icon = meta.icon;
            return (
              <Reveal key={preset.id} delay={(i % 3) * 70} className="bg-card">
                <Link
                  href={`/fetch?preset=${preset.id}`}
                  className="group flex h-full flex-col p-6 transition-colors hover:bg-secondary"
                >
                  <span
                    className="inline-flex h-10 w-10 items-center justify-center rounded-md"
                    style={{
                      background: `hsl(${meta.accent} / 0.12)`,
                      color: `hsl(${meta.accent})`,
                    }}
                  >
                    <Icon className="h-5 w-5" />
                  </span>
                  <h3 className="mt-4 text-[17px] font-semibold">{preset.name}</h3>
                  <p className="mt-1.5 flex-1 text-sm leading-relaxed text-muted-foreground">
                    {preset.description}
                  </p>
                  <span className="mono-eyebrow mt-4 inline-flex items-center gap-1 text-brand">
                    Try this preset
                    <ArrowRight className="h-3 w-3 transition-transform group-hover:translate-x-0.5" />
                  </span>
                </Link>
              </Reveal>
            );
          })}
        </div>
      )}
    </div>
  );
}
