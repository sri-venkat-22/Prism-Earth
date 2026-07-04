import { expect, test } from "@playwright/test";

import { mockApi } from "./fixtures";

test.beforeEach(async ({ page }) => {
  await mockApi(page);
});

test("Explore renders the metadata catalog from /meta/* (SRS §36.1)", async ({ page }) => {
  const fieldsRequested = page.waitForRequest("**/meta/fields**");

  await page.goto("/explore");

  await expect(page.getByRole("heading", { name: "Explore" })).toBeVisible();
  await expect(page.getByRole("tab", { name: /Presets/ })).toBeVisible();

  // The datasets tab pulls the field catalog from the API.
  await fieldsRequested;

  // The Presets tab lists a preset from the mocked catalog.
  await page.getByRole("tab", { name: /Presets/ }).click();
  await expect(page.getByText(/Terrain/i).first()).toBeVisible();
});
