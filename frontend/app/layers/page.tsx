"use client";

import { Layers } from "lucide-react";

import { ErrorState, LoadingBlock } from "@/components/feedback";
import { PageHeader } from "@/components/page-header";
import { Reveal } from "@/components/reveal";
import { layerMeta } from "@/lib/domain";
import { useLayers } from "@/hooks/useMeta";

export default function LayersPage() {
  const layers = useLayers();

  return (
    <div>
      <PageHeader
        eyebrow="What Terra provides"
        title="Nine domain layers, one honest contract."
        icon={<Layers className="h-7 w-7 text-brand" />}
        description="Each layer is a set of sourced fields with its own provenance. Let Ask pick the right ones for your question, or fetch them directly by coordinate."
      />

      {layers.isLoading && <LoadingBlock rows={3} className="mt-8" />}
      {layers.isError && (
        <ErrorState
          error={layers.error}
          onRetry={() => layers.refetch()}
          title="Couldn't load the layer catalog"
          className="mt-8"
        />
      )}
      {layers.data && (
        <div className="grid gap-px overflow-hidden rounded-lg border border-border bg-border sm:grid-cols-2 lg:grid-cols-3">
          {layers.data.layers.map((layer, i) => {
            const meta = layerMeta(layer.id);
            const Icon = meta.icon;
            return (
              <Reveal key={layer.id} delay={(i % 3) * 70} className="bg-card">
                <div className="group h-full p-6 transition-colors hover:bg-secondary">
                  <span
                    className="inline-flex h-10 w-10 items-center justify-center rounded-md"
                    style={{
                      background: `hsl(${meta.accent} / 0.12)`,
                      color: `hsl(${meta.accent})`,
                    }}
                  >
                    <Icon className="h-5 w-5" />
                  </span>
                  <h3 className="mt-4 text-[17px] font-semibold">{layer.name}</h3>
                  <p className="mt-1.5 text-sm leading-relaxed text-muted-foreground">
                    {layer.purpose}
                  </p>
                  <p className="mono-eyebrow mt-4">{layer.field_count} fields</p>
                </div>
              </Reveal>
            );
          })}
        </div>
      )}
    </div>
  );
}
