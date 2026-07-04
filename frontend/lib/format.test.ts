import { describe, expect, it } from "vitest";

import {
  formatCoord,
  formatDate,
  formatMs,
  formatNumber,
  formatRelative,
  formatTimestamp,
  formatValue,
  humanize,
} from "@/lib/format";

describe("humanize", () => {
  it("turns snake_case and kebab-case into Title Case", () => {
    expect(humanize("annual_rainfall_mm")).toBe("Annual Rainfall Mm");
    expect(humanize("land-cover")).toBe("Land Cover");
  });

  it("collapses repeated separators and trims", () => {
    expect(humanize("  flood__risk  ")).toBe("Flood Risk");
  });
});

describe("formatNumber", () => {
  it("formats integers with grouping", () => {
    expect(formatNumber(1234567)).toBe("12,34,567"); // en-IN grouping
  });

  it("varies precision by magnitude", () => {
    expect(formatNumber(542.163)).toBe("542.2");
    expect(formatNumber(3.14159)).toBe("3.14");
    expect(formatNumber(0.12345)).toBe("0.1235");
  });

  it("passes non-finite values through as strings", () => {
    expect(formatNumber(Infinity)).toBe("Infinity");
    expect(formatNumber(NaN)).toBe("NaN");
  });
});

describe("formatValue", () => {
  it("renders null/undefined as an em dash", () => {
    expect(formatValue(null)).toBe("—");
    expect(formatValue(undefined)).toBe("—");
  });

  it("renders booleans as Yes/No", () => {
    expect(formatValue(true)).toBe("Yes");
    expect(formatValue(false)).toBe("No");
  });

  it("appends a unit to numbers", () => {
    // 542.16 has magnitude >= 100, so it rounds to one decimal.
    expect(formatValue(542.16, "float", "m")).toBe("542.2 m");
    expect(formatValue(3.14159, "float", "index")).toBe("3.14 index");
  });

  it("humanizes enum strings but leaves plain strings intact", () => {
    expect(formatValue("moderate", "enum")).toBe("Moderate");
    expect(formatValue("Hyderabad", "string")).toBe("Hyderabad");
  });

  it("serializes objects as compact JSON", () => {
    expect(formatValue({ type: "Point" })).toBe('{"type":"Point"}');
  });
});

describe("formatMs", () => {
  it("uses ms below a second and seconds above", () => {
    expect(formatMs(12)).toBe("12 ms");
    expect(formatMs(1240)).toBe("1.24 s");
    expect(formatMs(null)).toBe("—");
  });
});

describe("timestamp helpers", () => {
  it("returns the raw string for unparseable input and dash for empty", () => {
    expect(formatTimestamp("not-a-date")).toBe("not-a-date");
    expect(formatTimestamp(null)).toBe("—");
    expect(formatDate(undefined)).toBe("—");
    expect(formatDate("nope")).toBe("nope");
  });

  it("formats a valid ISO timestamp", () => {
    expect(formatTimestamp("2026-06-26T10:30:00Z")).toContain("2026");
    expect(formatDate("2026-06-26T10:30:00Z")).toContain("2026");
  });
});

describe("formatRelative", () => {
  it("bucket-labels recent times", () => {
    const now = Date.now();
    expect(formatRelative(now)).toBe("just now");
    expect(formatRelative(now - 5 * 60 * 1000)).toBe("5m ago");
    expect(formatRelative(now - 3 * 60 * 60 * 1000)).toBe("3h ago");
    expect(formatRelative(now - 2 * 24 * 60 * 60 * 1000)).toBe("2d ago");
  });
});

describe("formatCoord", () => {
  it("labels hemispheres from sign", () => {
    expect(formatCoord(17.385, 78.486)).toBe("17.3850°N, 78.4860°E");
    expect(formatCoord(-33.87, -151.21)).toBe("33.8700°S, 151.2100°W");
  });
});
