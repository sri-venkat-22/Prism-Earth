// Presentation formatting helpers. These are display concerns only — they turn
// API values into readable strings and never encode catalog rules (SRS §38.5).

import type { DataType } from "@/types";

/** snake_case / kebab-case → "Title Case". */
export function humanize(input: string): string {
  return input
    .replace(/[_-]+/g, " ")
    .replace(/\s+/g, " ")
    .trim()
    .replace(/\b\w/g, (c) => c.toUpperCase());
}

/** Format a numeric value with sensible precision. */
export function formatNumber(value: number): string {
  if (!Number.isFinite(value)) return String(value);
  if (Number.isInteger(value)) return value.toLocaleString("en-IN");
  const abs = Math.abs(value);
  const digits = abs >= 100 ? 1 : abs >= 1 ? 2 : 4;
  return value.toLocaleString("en-IN", { maximumFractionDigits: digits });
}

/**
 * Render a fetched field value for display. Handles the API's polymorphic
 * `value` (number | string | boolean | null | object) plus an optional unit.
 */
export function formatValue(value: unknown, datatype?: DataType, unit?: string | null): string {
  if (value === null || value === undefined) return "—";
  if (typeof value === "boolean") return value ? "Yes" : "No";
  if (typeof value === "number") {
    const num = formatNumber(value);
    return unit ? `${num} ${unit}` : num;
  }
  if (typeof value === "string") {
    const text = datatype === "enum" ? humanize(value) : value;
    return unit ? `${text} ${unit}` : text;
  }
  // Objects (e.g. geometry) — show compact JSON.
  try {
    return JSON.stringify(value);
  } catch {
    return String(value);
  }
}

/** Format a duration in milliseconds as "12 ms" / "1.24 s". */
export function formatMs(ms: number | null | undefined): string {
  if (ms === null || ms === undefined) return "—";
  if (ms < 1000) return `${Math.round(ms)} ms`;
  return `${(ms / 1000).toFixed(2)} s`;
}

/** Format an ISO timestamp as a short, human-readable date-time. */
export function formatTimestamp(iso: string | null | undefined): string {
  if (!iso) return "—";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  return d.toLocaleString("en-IN", {
    year: "numeric",
    month: "short",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  });
}

/** Just the date portion of an ISO timestamp (for "retrieved" dates). */
export function formatDate(iso: string | null | undefined): string {
  if (!iso) return "—";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  return d.toLocaleDateString("en-IN", { year: "numeric", month: "short", day: "2-digit" });
}

/** Relative time like "3m ago" for history entries. */
export function formatRelative(at: number): string {
  const diff = Date.now() - at;
  const sec = Math.round(diff / 1000);
  if (sec < 60) return "just now";
  const min = Math.round(sec / 60);
  if (min < 60) return `${min}m ago`;
  const hr = Math.round(min / 60);
  if (hr < 24) return `${hr}h ago`;
  const day = Math.round(hr / 24);
  return `${day}d ago`;
}

/** Format a lat/lng pair for display. */
export function formatCoord(lat: number, lng: number): string {
  const latLabel = `${Math.abs(lat).toFixed(4)}°${lat >= 0 ? "N" : "S"}`;
  const lngLabel = `${Math.abs(lng).toFixed(4)}°${lng >= 0 ? "E" : "W"}`;
  return `${latLabel}, ${lngLabel}`;
}
