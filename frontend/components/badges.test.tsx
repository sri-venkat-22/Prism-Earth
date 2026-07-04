import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import {
  AvailabilityBadge,
  ConfidenceBadge,
  LayerBadge,
  LifecycleBadge,
} from "@/components/badges";

describe("catalog badges", () => {
  it("LayerBadge renders the humanized label", () => {
    render(<LayerBadge layer="natural_hazard" />);
    expect(screen.getByText("Natural Hazard")).toBeInTheDocument();
  });

  it("LayerBadge falls back for an unknown layer", () => {
    render(<LayerBadge layer="brand_new" showIcon={false} />);
    expect(screen.getByText("Brand New")).toBeInTheDocument();
  });

  it("LifecycleBadge renders the lifecycle label", () => {
    render(<LifecycleBadge value="beta" />);
    expect(screen.getByText("Beta")).toBeInTheDocument();
  });

  it("ConfidenceBadge exposes a descriptive title", () => {
    render(<ConfidenceBadge value="high" />);
    const badge = screen.getByTitle("Confidence: High");
    expect(badge).toBeInTheDocument();
    expect(badge).toHaveTextContent("High");
  });

  it("AvailabilityBadge renders region-gated availability", () => {
    render(<AvailabilityBadge value="region_gated" />);
    expect(screen.getByText("Region-gated")).toBeInTheDocument();
  });
});
