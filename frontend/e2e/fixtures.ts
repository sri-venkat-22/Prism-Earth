// Deterministic API fixtures for the Playwright E2E suite (SRS §30.2, §36.1).
//
// The specs run the real Next.js UI but intercept the backend REST API at the
// network layer, so the core browser flows are proven end-to-end without a live
// database, GEE, or LLM. The payloads mirror the SRS §13 response shapes exactly.

import type { Page, Route } from "@playwright/test";

const NOW = "2026-06-26T10:30:00Z";

export const fieldsFixture = {
  count: 2,
  fields: [
    {
      id: "elevation",
      name: "elevation",
      description: "Height above mean sea level.",
      layer: "terrain",
      lifecycle: "stable",
      available: true,
      availability: "nationwide",
      nullable: true,
      null_meaning: null,
      source: "Copernicus DEM GLO-30",
      source_url: "https://dataspace.copernicus.eu",
      unit: "m",
      datatype: "float",
      ttl: "P30D",
      interpretation_hint: "Higher values indicate elevated terrain.",
      connector: "terrain_connector",
      presets: ["terrain"],
    },
    {
      id: "district_name",
      name: "district_name",
      description: "Administrative district.",
      layer: "administrative",
      lifecycle: "stable",
      available: true,
      availability: "region_gated",
      nullable: true,
      null_meaning: "outside_coverage",
      source: "Telangana Admin Boundaries",
      source_url: "https://telangana.gov.in",
      unit: null,
      datatype: "string",
      ttl: "P365D",
      interpretation_hint: "The district containing the point.",
      connector: "administrative_connector",
      presets: ["administrative"],
    },
  ],
};

export const layersFixture = {
  count: 2,
  layers: [
    {
      id: "terrain",
      name: "Terrain",
      purpose: "Elevation, slope, soils, groundwater",
      connector: "terrain_connector",
      field_count: 3,
    },
    {
      id: "administrative",
      name: "Administrative",
      purpose: "State, district, taluk, ULB",
      connector: "administrative_connector",
      field_count: 5,
    },
  ],
};

export const presetsFixture = {
  count: 1,
  presets: [
    {
      id: "terrain",
      name: "Terrain",
      description: "Core terrain fields for a coordinate.",
      fields: ["elevation", "slope", "aspect"],
      layers: ["terrain"],
      supported_states: ["telangana"],
    },
  ],
};

export const statesFixture = {
  count: 1,
  states: [
    {
      slug: "telangana",
      code: "TG",
      name: "Telangana",
      registered: true,
      lifecycle: "active",
      supported_datasets: ["Copernicus DEM GLO-30"],
      enabled_fields: ["elevation", "district_name"],
    },
  ],
};

export const healthFixture = {
  status: "ok",
  service: "Prism Earth",
  version: "0.1.0",
  environment: "development",
  timestamp: NOW,
  components: {
    api: { status: "ok" },
    database: { status: "ok" },
    redis: { status: "ok" },
    earth_engine: { status: "ok" },
    connectors: { status: "ok" },
  },
};

export const connectorsHealthFixture = {
  status: "ok",
  timestamp: NOW,
  count: 2,
  connectors: [
    { name: "terrain_connector", layer: "terrain", status: "ok", servable_fields: 3 },
    {
      name: "administrative_connector",
      layer: "administrative",
      status: "ok",
      servable_fields: 5,
    },
  ],
};

export const fetchFixture = {
  request_id: "REQ-E2E-0001",
  timestamp: NOW,
  location: {
    lat: 17.385,
    lng: 78.486,
    in_pilot_region: true,
    state: "Telangana",
    district: "Hyderabad",
    taluk: null,
    village: null,
    municipality: null,
    ward: null,
  },
  fields: {
    elevation: {
      name: "elevation",
      value: 542.16,
      unit: "m",
      datatype: "float",
      confidence: "high",
      dataset: "Copernicus DEM GLO-30",
      dataset_version: "2023",
      retrieved_at: NOW,
      ttl: "P30D",
      layer: "terrain",
      null_meaning: null,
    },
    district_name: {
      name: "district_name",
      value: "Hyderabad",
      unit: null,
      datatype: "string",
      confidence: "high",
      dataset: "Telangana Admin Boundaries",
      dataset_version: "2024",
      retrieved_at: NOW,
      ttl: "P365D",
      layer: "administrative",
      null_meaning: null,
    },
  },
  provenance: {
    elevation: {
      field: "elevation",
      dataset: "Copernicus DEM GLO-30",
      dataset_version: "2023",
      source_url: "https://dataspace.copernicus.eu",
      retrieved_at: NOW,
      ttl: "P30D",
      confidence: "high",
      null_meaning: null,
      reason: null,
    },
    district_name: {
      field: "district_name",
      dataset: "Telangana Admin Boundaries",
      dataset_version: "2024",
      source_url: "https://telangana.gov.in",
      retrieved_at: NOW,
      ttl: "P365D",
      confidence: "high",
      null_meaning: null,
      reason: null,
    },
  },
  citations: [
    {
      citation_id: "CIT-001",
      dataset: "Copernicus DEM GLO-30",
      provider: "ESA Copernicus",
      source_url: "https://dataspace.copernicus.eu",
      dataset_version: "2023",
      retrieved_at: NOW,
      ttl: "P30D",
      license: "Copernicus",
      field_names: ["elevation"],
    },
  ],
  partial_failures: [],
  summary: {
    requested: 2,
    resolved: 2,
    null: 0,
    datasets_used: ["Copernicus DEM GLO-30", "Telangana Admin Boundaries"],
  },
};

export const askFixture = {
  request_id: "REQ-E2E-0002",
  timestamp: NOW,
  location: fetchFixture.location,
  answer:
    "This location in Hyderabad sits at roughly 542 m elevation with gentle slope, " +
    "making it broadly suitable for solar development, subject to land-use checks.",
  citations: fetchFixture.citations,
  trace: {
    planner: {
      intent: "Solar Suitability",
      presets: ["terrain"],
      fields: ["elevation", "district_name"],
      layers: ["terrain", "administrative"],
      connectors: ["terrain_connector", "administrative_connector"],
      planning_reason: "Solar suitability depends on terrain and administrative context.",
      warnings: [],
      model: "test-model",
      duration_ms: 120,
      prompt_tokens: 100,
      completion_tokens: 40,
    },
    fetch: {
      requested_fields: ["elevation", "district_name"],
      resolved_fields: ["elevation", "district_name"],
      null_fields: [],
      datasets_used: ["Copernicus DEM GLO-30", "Telangana Admin Boundaries"],
      connectors: [
        { connector: "terrain_connector", fields: ["elevation"], status: "ok", reason: null },
      ],
      partial_failures: [],
      duration_ms: 80,
    },
    synthesizer: {
      model: "test-model",
      unavailable_fields: [],
      citations_used: ["CIT-001"],
      duration_ms: 60,
      prompt_tokens: 200,
      completion_tokens: 90,
    },
    total_duration_ms: 260,
  },
  provenance: fetchFixture.provenance,
};

/**
 * Intercept every `/api/v1/**` request and fulfil it from the fixtures above,
 * so the specs never touch a real backend. Order matters — more specific paths
 * are matched first.
 */
export async function mockApi(page: Page): Promise<void> {
  await page.route("**/api/v1/**", async (route: Route) => {
    const url = new URL(route.request().url());
    const path = url.pathname;

    const json = (body: unknown) =>
      route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(body),
      });

    if (path.includes("/health/connectors")) return json(connectorsHealthFixture);
    if (path.includes("/health")) return json(healthFixture);
    if (path.includes("/meta/fields")) return json(fieldsFixture);
    if (path.includes("/meta/layers")) return json(layersFixture);
    if (path.includes("/meta/presets")) return json(presetsFixture);
    if (/\/meta\/states\/[^/]+$/.test(path)) {
      return json({
        query: "telangana",
        supported: true,
        state: statesFixture.states[0],
        message: "Supported pilot region.",
      });
    }
    if (path.includes("/meta/states")) return json(statesFixture);
    if (path.endsWith("/fetch")) return json(fetchFixture);
    if (path.endsWith("/ask")) return json(askFixture);

    return route.fulfill({ status: 404, body: "{}", contentType: "application/json" });
  });
}

/**
 * Seed the persisted Zustand location store so pages that require a working
 * coordinate (Fetch) are usable immediately.
 */
export async function seedLocation(page: Page): Promise<void> {
  await page.addInitScript(() => {
    window.localStorage.setItem(
      "prism-earth-location",
      JSON.stringify({
        state: {
          coordinate: { lat: 17.385, lng: 78.486 },
          coordinateLabel: "Hyderabad · pilot region",
          history: [],
        },
        version: 0,
      }),
    );
  });
}
