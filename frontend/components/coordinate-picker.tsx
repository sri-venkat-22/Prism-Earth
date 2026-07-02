"use client";

import { LocateFixed, MapPin } from "lucide-react";
import { useEffect, useState } from "react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { cn } from "@/lib/utils";
import { useLocationStore } from "@/stores/location";

// Demo coordinates so the region-gating behaviour is easy to see. These are just
// sample inputs (like placeholder text) — no catalog rules live here.
const EXAMPLES: { label: string; note: string; lat: number; lng: number }[] = [
  { label: "Hyderabad", note: "in Telangana", lat: 17.385, lng: 78.486 },
  { label: "Warangal", note: "in Telangana", lat: 17.9689, lng: 79.5941 },
  { label: "Adilabad", note: "rural Telangana", lat: 19.6641, lng: 78.532 },
  { label: "Mumbai", note: "outside pilot", lat: 19.076, lng: 72.8777 },
  { label: "Bengaluru", note: "outside pilot", lat: 12.9716, lng: 77.5946 },
];

function parse(value: string): number | null {
  if (value.trim() === "") return null;
  const n = Number(value);
  return Number.isFinite(n) ? n : null;
}

/**
 * A reusable coordinate input surface. It validates lat/lng and writes valid
 * values to the shared location store so the coordinate follows the user across
 * the Ask, Fetch, and Dashboard pages.
 */
export function CoordinatePicker({ className }: { className?: string }) {
  const { coordinate, coordinateLabel, setCoordinate, clearCoordinate } = useLocationStore();
  const [lat, setLat] = useState(coordinate ? String(coordinate.lat) : "");
  const [lng, setLng] = useState(coordinate ? String(coordinate.lng) : "");
  const [geoError, setGeoError] = useState<string | null>(null);

  // Keep local fields in sync when the store changes elsewhere (e.g. example click
  // on another page, or history replay).
  useEffect(() => {
    if (coordinate) {
      setLat(String(coordinate.lat));
      setLng(String(coordinate.lng));
    }
  }, [coordinate]);

  const latNum = parse(lat);
  const lngNum = parse(lng);
  const latValid = latNum !== null && latNum >= -90 && latNum <= 90;
  const lngValid = lngNum !== null && lngNum >= -180 && lngNum <= 180;

  function commit(nextLat: string, nextLng: string, label: string | null = null) {
    const la = parse(nextLat);
    const ln = parse(nextLng);
    if (la !== null && ln !== null && la >= -90 && la <= 90 && ln >= -180 && ln <= 180) {
      setCoordinate({ lat: la, lng: ln }, label);
    } else {
      clearCoordinate();
    }
  }

  function selectExample(ex: (typeof EXAMPLES)[number]) {
    setLat(String(ex.lat));
    setLng(String(ex.lng));
    setGeoError(null);
    setCoordinate({ lat: ex.lat, lng: ex.lng }, `${ex.label} · ${ex.note}`);
  }

  function locateMe() {
    setGeoError(null);
    if (!("geolocation" in navigator)) {
      setGeoError("Geolocation is not available in this browser.");
      return;
    }
    navigator.geolocation.getCurrentPosition(
      (pos) => {
        const la = Number(pos.coords.latitude.toFixed(5));
        const ln = Number(pos.coords.longitude.toFixed(5));
        setLat(String(la));
        setLng(String(ln));
        setCoordinate({ lat: la, lng: ln }, "My location");
      },
      () => setGeoError("Could not read your location. Enter coordinates manually."),
      { enableHighAccuracy: true, timeout: 8000 },
    );
  }

  return (
    <div className={cn("space-y-3", className)}>
      <div className="grid grid-cols-2 gap-3">
        <div className="space-y-1.5">
          <Label htmlFor="lat">Latitude</Label>
          <Input
            id="lat"
            inputMode="decimal"
            placeholder="17.385"
            value={lat}
            aria-invalid={lat !== "" && !latValid}
            onChange={(e) => {
              setLat(e.target.value);
              setGeoError(null);
              commit(e.target.value, lng);
            }}
          />
          {lat !== "" && !latValid && (
            <p className="text-xs text-danger">Latitude must be between −90 and 90.</p>
          )}
        </div>
        <div className="space-y-1.5">
          <Label htmlFor="lng">Longitude</Label>
          <Input
            id="lng"
            inputMode="decimal"
            placeholder="78.486"
            value={lng}
            aria-invalid={lng !== "" && !lngValid}
            onChange={(e) => {
              setLng(e.target.value);
              setGeoError(null);
              commit(lat, e.target.value);
            }}
          />
          {lng !== "" && !lngValid && (
            <p className="text-xs text-danger">Longitude must be between −180 and 180.</p>
          )}
        </div>
      </div>

      <div className="flex flex-wrap items-center gap-2">
        <Button type="button" variant="outline" size="sm" onClick={locateMe}>
          <LocateFixed className="h-3.5 w-3.5" /> Use my location
        </Button>
        {coordinateLabel && (
          <span className="inline-flex items-center gap-1 text-xs text-muted-foreground">
            <MapPin className="h-3.5 w-3.5 text-brand" /> {coordinateLabel}
          </span>
        )}
      </div>
      {geoError && <p className="text-xs text-warning">{geoError}</p>}

      <div>
        <p className="mb-1.5 text-xs font-medium text-muted-foreground">Example locations</p>
        <div className="flex flex-wrap gap-1.5">
          {EXAMPLES.map((ex) => {
            const active = coordinate?.lat === ex.lat && coordinate?.lng === ex.lng;
            return (
              <button
                key={ex.label}
                type="button"
                onClick={() => selectExample(ex)}
                className={cn(
                  "rounded-full border px-2.5 py-1 text-xs transition-colors",
                  active
                    ? "border-brand/50 bg-brand/10 text-foreground"
                    : "border-border bg-card/50 text-muted-foreground hover:border-brand/40 hover:text-foreground",
                )}
              >
                <span className="font-medium">{ex.label}</span>
                <span className="ml-1 opacity-60">{ex.note}</span>
              </button>
            );
          })}
        </div>
      </div>
    </div>
  );
}
