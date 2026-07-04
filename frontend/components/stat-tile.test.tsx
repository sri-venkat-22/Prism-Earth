import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { StatTile } from "@/components/stat-tile";

describe("StatTile", () => {
  it("renders the label, value, and hint", () => {
    render(<StatTile label="Elevation" value="542.16 m" hint="Copernicus DEM" />);
    expect(screen.getByText("Elevation")).toBeInTheDocument();
    expect(screen.getByText("542.16 m")).toBeInTheDocument();
    expect(screen.getByText("Copernicus DEM")).toBeInTheDocument();
  });

  it("renders a ReactNode value", () => {
    render(<StatTile label="Status" value={<span>Online</span>} />);
    expect(screen.getByText("Online")).toBeInTheDocument();
  });
});
