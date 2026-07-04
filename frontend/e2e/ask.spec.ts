import { expect, test } from "@playwright/test";

import { mockApi, seedLocation } from "./fixtures";

test.beforeEach(async ({ page }) => {
  await seedLocation(page);
  await mockApi(page);
});

test("Ask flow: question → cited answer + execution trace (SRS §36.1)", async ({ page }) => {
  await page.goto("/ask");

  // Hero renders in the initial state.
  await expect(page.getByRole("heading", { name: "Ask about any point in India." })).toBeVisible();

  // Ask a question and submit.
  await page.getByLabel("Your question").fill("Is this area suitable for a solar farm?");
  await page.getByRole("button", { name: "Ask", exact: true }).click();

  // The synthesized answer appears...
  await expect(page.getByText(/broadly suitable for solar development/i)).toBeVisible();

  // ...with its citation sourced from the mocked response.
  await expect(page.getByText("Copernicus DEM GLO-30").first()).toBeVisible();

  // The execution trace (planner intent) is shown.
  await expect(page.getByText(/Solar Suitability/i).first()).toBeVisible();
});

test("Ask surfaces a clear error when the API fails", async ({ page }) => {
  // Override the /ask route with a 503 (LLM unavailable, SRS §38.8).
  await page.route("**/api/v1/ask", (route) =>
    route.fulfill({
      status: 503,
      contentType: "application/json",
      body: JSON.stringify({
        error: {
          code: "LLM_UNAVAILABLE",
          message: "The language model is not configured.",
          correlation_id: "REQ-ERR",
          timestamp: "2026-06-26T10:30:00Z",
        },
      }),
    }),
  );

  await page.goto("/ask");
  await page.getByLabel("Your question").fill("Anything?");
  await page.getByRole("button", { name: "Ask", exact: true }).click();

  await expect(page.getByText(/could not be answered/i)).toBeVisible();
});
