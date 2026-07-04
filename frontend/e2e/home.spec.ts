import { expect, test } from "@playwright/test";

import { mockApi } from "./fixtures";

test.beforeEach(async ({ page }) => {
  await mockApi(page);
});

test("Home loads and navigation reaches the Ask flow", async ({ page }) => {
  await page.goto("/");

  // Primary navigation is present.
  const nav = page.getByRole("navigation", { name: "Primary" });
  await expect(nav.getByRole("link", { name: "Ask" })).toBeVisible();

  // Clicking through reaches the Ask page.
  await nav.getByRole("link", { name: "Ask" }).click();
  await expect(page).toHaveURL(/\/ask$/);
  await expect(page.getByRole("heading", { name: "Ask about any point in India." })).toBeVisible();
});
