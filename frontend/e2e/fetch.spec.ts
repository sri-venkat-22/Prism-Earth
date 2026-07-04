import { expect, test } from "@playwright/test";

import { mockApi, seedLocation } from "./fixtures";

test.beforeEach(async ({ page }) => {
  await seedLocation(page);
  await mockApi(page);
});

test("Fetch flow: coordinate → field values with provenance (SRS §36.1)", async ({ page }) => {
  await page.goto("/fetch");

  // The deterministic fetch workbench renders.
  await expect(page.getByRole("heading", { name: "Fetch", exact: true })).toBeVisible();

  // Run a preset fetch (a default preset is auto-selected from /meta/presets).
  await page.getByRole("button", { name: /^Fetch$/ }).click();

  // The summary tiles reflect the mocked response (2 requested, 2 resolved).
  await expect(page.getByText("Resolved")).toBeVisible();

  // A field value is displayed with its unit.
  await expect(page.getByText(/542/).first()).toBeVisible();

  // Provenance / citations are available for the returned fields.
  await page.getByRole("tab", { name: /Provenance/ }).click();
  await expect(page.getByText("Copernicus DEM GLO-30").first()).toBeVisible();
});
