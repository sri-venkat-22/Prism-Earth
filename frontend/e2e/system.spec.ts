import { expect, test } from "@playwright/test";

import { mockApi } from "./fixtures";

test.beforeEach(async ({ page }) => {
  await mockApi(page);
});

test("System page reports connector health from /health/connectors", async ({ page }) => {
  const connectorsRequested = page.waitForRequest("**/health/connectors**");

  await page.goto("/system");

  await expect(page.getByRole("heading", { name: "System" })).toBeVisible();
  await connectorsRequested;

  // A connector from the mocked fleet is shown.
  await expect(page.getByText(/terrain/i).first()).toBeVisible();
});
