import AxeBuilder from "@axe-core/playwright";
import { test, expect } from "@playwright/test";

import { openOperatorSurface, operatorSurfaces } from "./a11y-surfaces";

test.describe("Dashboard accessibility baseline @a11y", () => {
  for (const surface of operatorSurfaces) {
    test(`${surface.name} exposes landmarks and one primary heading`, async ({ page }) => {
      await openOperatorSurface(page, surface);

      await expect(page.locator("header")).toBeVisible();
      await expect(page.locator("main")).toBeVisible();
      await expect(page.locator('nav[aria-label="Primary navigation"]')).toBeVisible();
      await expect(page.locator("main h1")).toHaveCount(1);
    });

    test(`${surface.name} has no baseline axe violations`, async ({ page }) => {
      await openOperatorSurface(page, surface);

      const results = await new AxeBuilder({ page })
        .include("main")
        .withTags(["wcag2a", "wcag2aa"])
        .disableRules(["color-contrast"])
        .analyze();

      expect(results.violations).toEqual([]);
    });
  }
});
