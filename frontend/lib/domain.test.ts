import { describe, expect, it } from "vitest";

import {
  availabilityMeta,
  confidenceMeta,
  layerMeta,
  lifecycleMeta,
  nullReasonLabel,
} from "@/lib/domain";

describe("layerMeta", () => {
  it("maps known layers to a label and accent", () => {
    const terrain = layerMeta("terrain");
    expect(terrain.label).toBe("Terrain");
    expect(terrain.accent).toContain("--layer-terrain");
  });

  it("falls back gracefully for unknown layers", () => {
    const meta = layerMeta("brand_new_layer");
    expect(meta.label).toBe("Brand New Layer");
    expect(meta.className).toBe("layer-default");
    expect(meta.icon).toBeTruthy();
  });
});

describe("confidenceMeta", () => {
  it("maps the three confidence levels", () => {
    expect(confidenceMeta("high").label).toBe("High");
    expect(confidenceMeta("medium").label).toBe("Medium");
    expect(confidenceMeta("low").label).toBe("Low");
  });

  it("humanizes unknown confidence values", () => {
    expect(confidenceMeta("uncertain").label).toBe("Uncertain");
    expect(confidenceMeta("uncertain").className).toBe("badge-muted");
  });
});

describe("lifecycleMeta", () => {
  it("maps stable/beta/planned and falls back", () => {
    expect(lifecycleMeta("stable").label).toBe("Stable");
    expect(lifecycleMeta("beta").label).toBe("Beta");
    expect(lifecycleMeta("planned").label).toBe("Planned");
    expect(lifecycleMeta("weird").className).toBe("badge-muted");
  });
});

describe("availabilityMeta", () => {
  it("maps availability tokens and falls back", () => {
    expect(availabilityMeta("nationwide").label).toBe("Nationwide");
    expect(availabilityMeta("region_gated").label).toBe("Region-gated");
    expect(availabilityMeta("planned").label).toBe("Planned");
    expect(availabilityMeta("mystery").className).toBe("badge-muted");
  });
});

describe("nullReasonLabel", () => {
  it("returns a friendly default when no reason is given", () => {
    expect(nullReasonLabel(null)).toBe("Not available");
    expect(nullReasonLabel(undefined)).toBe("Not available");
  });

  it("maps known null reasons and humanizes unknown ones", () => {
    expect(nullReasonLabel("unsupported_state")).toBe(
      "Region-gated field — not enabled for this state",
    );
    expect(nullReasonLabel("some_new_reason")).toBe("Some New Reason");
  });
});
