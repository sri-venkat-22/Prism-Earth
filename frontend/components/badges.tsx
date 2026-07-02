import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";
import { availabilityMeta, confidenceMeta, layerMeta, lifecycleMeta } from "@/lib/domain";
import type { Availability, Confidence, Layer, Lifecycle } from "@/types";

export function LayerBadge({
  layer,
  showIcon = true,
  className,
}: {
  layer: Layer | string;
  showIcon?: boolean;
  className?: string;
}) {
  const meta = layerMeta(layer);
  const Icon = meta.icon;
  return (
    <Badge
      className={cn("layer-chip", className)}
      style={{ ["--layer-accent" as string]: meta.accent }}
    >
      {showIcon && <Icon className="h-3 w-3" aria-hidden />}
      {meta.label}
    </Badge>
  );
}

export function LifecycleBadge({
  value,
  className,
}: {
  value: Lifecycle | string;
  className?: string;
}) {
  const meta = lifecycleMeta(value);
  return <Badge className={cn(meta.className, className)}>{meta.label}</Badge>;
}

export function ConfidenceBadge({
  value,
  className,
}: {
  value: Confidence | string;
  className?: string;
}) {
  const meta = confidenceMeta(value);
  return (
    <Badge className={cn(meta.className, className)} title={`Confidence: ${meta.label}`}>
      <span className="h-1.5 w-1.5 rounded-full" style={{ background: meta.color }} aria-hidden />
      {meta.label}
    </Badge>
  );
}

export function AvailabilityBadge({
  value,
  className,
}: {
  value: Availability | string;
  className?: string;
}) {
  const meta = availabilityMeta(value);
  return <Badge className={cn(meta.className, className)}>{meta.label}</Badge>;
}
