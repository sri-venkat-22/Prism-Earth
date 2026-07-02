// Visual mappings for the API's controlled vocabularies (SRS §11.4–11.6). These
// map an enum value to a colour/label for rendering only — they add no rules and
// no field/preset knowledge (SRS §38.5). Display labels always fall back to a
// humanized version of the raw value, so unknown values still render gracefully.

import {
  Building2,
  CircleDot,
  Cloud,
  Landmark,
  Layers,
  Map,
  Mountain,
  ShieldAlert,
  Sprout,
  TrainFront,
  Zap,
  type LucideIcon,
} from "lucide-react";

import { humanize } from "@/lib/format";
import type { Availability, Confidence, Layer, Lifecycle } from "@/types";

export interface Meta {
  label: string;
  /** Tailwind classes for a badge/pill using this token. */
  className: string;
  /** A bare HSL/colour token usable inline (e.g. for chart accents). */
  color: string;
}

// --- Layers ---------------------------------------------------------------- //
interface LayerMeta {
  label: string;
  icon: LucideIcon;
  /** Accent colour (CSS var name in globals.css). */
  accent: string;
  className: string;
}

const LAYER_META: Record<Layer, LayerMeta> = {
  terrain: {
    label: "Terrain",
    icon: Mountain,
    accent: "var(--layer-terrain)",
    className: "layer-terrain",
  },
  climate: {
    label: "Climate",
    icon: Cloud,
    accent: "var(--layer-climate)",
    className: "layer-climate",
  },
  land_cover: {
    label: "Land Cover",
    icon: Sprout,
    accent: "var(--layer-land)",
    className: "layer-land",
  },
  natural_hazard: {
    label: "Natural Hazard",
    icon: ShieldAlert,
    accent: "var(--layer-hazard)",
    className: "layer-hazard",
  },
  infrastructure: {
    label: "Infrastructure",
    icon: TrainFront,
    accent: "var(--layer-infra)",
    className: "layer-infra",
  },
  utilities: {
    label: "Utilities",
    icon: Zap,
    accent: "var(--layer-utilities)",
    className: "layer-utilities",
  },
  administrative: {
    label: "Administrative",
    icon: Landmark,
    accent: "var(--layer-admin)",
    className: "layer-admin",
  },
  cadastral: {
    label: "Cadastral",
    icon: Map,
    accent: "var(--layer-cadastral)",
    className: "layer-cadastral",
  },
  built_environment: {
    label: "Built Environment",
    icon: Building2,
    accent: "var(--layer-built)",
    className: "layer-built",
  },
};

export function layerMeta(layer: string): LayerMeta {
  return (
    LAYER_META[layer as Layer] ?? {
      label: humanize(layer),
      icon: Layers,
      accent: "var(--brand)",
      className: "layer-default",
    }
  );
}

// --- Confidence (SRS §18.11) ----------------------------------------------- //
export function confidenceMeta(value: Confidence | string): Meta {
  switch (value) {
    case "high":
      return { label: "High", className: "badge-confidence-high", color: "hsl(var(--success))" };
    case "medium":
      return {
        label: "Medium",
        className: "badge-confidence-medium",
        color: "hsl(var(--warning))",
      };
    case "low":
      return { label: "Low", className: "badge-confidence-low", color: "hsl(var(--danger))" };
    default:
      return {
        label: humanize(String(value)),
        className: "badge-muted",
        color: "hsl(var(--muted-foreground))",
      };
  }
}

// --- Lifecycle (SRS §11.6) ------------------------------------------------- //
export function lifecycleMeta(value: Lifecycle | string): Meta {
  switch (value) {
    case "stable":
      return { label: "Stable", className: "badge-lifecycle-stable", color: "hsl(var(--success))" };
    case "beta":
      return { label: "Beta", className: "badge-lifecycle-beta", color: "hsl(var(--info))" };
    case "planned":
      return {
        label: "Planned",
        className: "badge-lifecycle-planned",
        color: "hsl(var(--muted-foreground))",
      };
    default:
      return {
        label: humanize(String(value)),
        className: "badge-muted",
        color: "hsl(var(--muted-foreground))",
      };
  }
}

// --- Availability (SRS §11.4, §24.3) --------------------------------------- //
export function availabilityMeta(value: Availability | string): Meta {
  switch (value) {
    case "nationwide":
      return {
        label: "Nationwide",
        className: "badge-avail-nationwide",
        color: "hsl(var(--success))",
      };
    case "region_gated":
      return {
        label: "Region-gated",
        className: "badge-avail-gated",
        color: "hsl(var(--warning))",
      };
    case "planned":
      return {
        label: "Planned",
        className: "badge-avail-planned",
        color: "hsl(var(--muted-foreground))",
      };
    default:
      return {
        label: humanize(String(value)),
        className: "badge-muted",
        color: "hsl(var(--muted-foreground))",
      };
  }
}

// --- Null reasons (SRS §17.6) — human-readable explanations ---------------- //
const NULL_REASON_LABELS: Record<string, string> = {
  data_unavailable: "Source not integrated for this location",
  outside_coverage: "Outside the dataset's coverage extent",
  unsupported_state: "Region-gated field — not enabled for this state",
  not_applicable: "Does not apply at this location",
  connector_timeout: "Connector failed at runtime (retryable)",
  dataset_unavailable: "Upstream dataset temporarily unavailable",
};

export function nullReasonLabel(reason: string | null | undefined): string {
  if (!reason) return "Not available";
  return NULL_REASON_LABELS[reason] ?? humanize(reason);
}

/** A stable palette used for citation / dataset accents. */
export const ACCENT_SEQUENCE = [
  "hsl(var(--brand))",
  "hsl(var(--info))",
  "hsl(var(--success))",
  "hsl(var(--warning))",
  "hsl(var(--layer-hazard))",
  "hsl(var(--layer-built))",
];
