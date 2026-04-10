import { test, expect } from "@playwright/test";

import { openOperatorSurface, operatorSurfaces } from "./a11y-surfaces";
import { checkContrast, expectContrastToPass } from "./contrast-utils";

const CONTENT_SELECTOR =
  "main h1, main h2, main h3, main p, main li, main a, main button, main label, main input, main textarea, main select, main [role='button']";

test.describe("Dashboard contrast baseline @a11y", () => {
  for (const surface of operatorSurfaces) {
    test(`${surface.name} meets WCAG AA contrast for operator content`, async ({ page }) => {
      await openOperatorSurface(page, surface);

      const results = await checkContrast(page, CONTENT_SELECTOR);

      expect(results.length).toBeGreaterThan(0);
      expectContrastToPass(results, "aa");
    });
  }

  test("primary navigation remains readable", async ({ page }) => {
    await openOperatorSurface(page, operatorSurfaces[0]);

    const results = await checkContrast(page, 'nav[aria-label="Primary"] a');

    expect(results.length).toBeGreaterThan(0);
    expectContrastToPass(results, "aa");
  });
});
