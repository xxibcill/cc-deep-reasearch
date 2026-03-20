import { test, expect } from "@playwright/test";

test("homepage has title and loads correctly", async ({ page }) => {
  await page.goto("/");

  await expect(page).toHaveTitle(/CC Deep Research/);
});

test("navigation works", async ({ page }) => {
  await page.goto("/");

  // Check main layout loads
  await expect(page.locator("body")).toBeVisible();
});
