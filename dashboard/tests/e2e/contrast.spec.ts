import { test, expect } from "@playwright/test";
import { checkContrast, expectContrastToPass } from "./contrast-utils";

test.describe("Text Contrast Accessibility", () => {
  test("all text elements meet WCAG AA contrast ratio", async ({ page }) => {
    await page.goto("/");

    // Wait for page to fully load
    await page.waitForLoadState("networkidle");

    // Check all text elements
    const results = await checkContrast(page, "body *:has-text('')");

    // Filter out elements with no visible text
    const visibleResults = results.filter((r) => !r.element.includes('""'));

    // Assert all pass AA standard
    expectContrastToPass(visibleResults, "aa");
  });

  test("headings meet contrast requirements", async ({ page }) => {
    await page.goto("/");
    await page.waitForLoadState("networkidle");

    const results = await checkContrast(page, "h1, h2, h3, h4, h5, h6");
    expectContrastToPass(results, "aa");
  });

  test("buttons and interactive elements meet contrast", async ({ page }) => {
    await page.goto("/");
    await page.waitForLoadState("networkidle");

    const results = await checkContrast(page, "button, a, [role='button']");
    expectContrastToPass(results, "aa");
  });

  test("form inputs meet contrast requirements", async ({ page }) => {
    await page.goto("/");
    await page.waitForLoadState("networkidle");

    const results = await checkContrast(page, "input, textarea, select, label");
    expectContrastToPass(results, "aa");
  });

  test("report contrast metrics", async ({ page }) => {
    await page.goto("/");
    await page.waitForLoadState("networkidle");

    const results = await checkContrast(page, "body *:has-text('')");

    // Log contrast report
    console.log("\n=== Contrast Report ===");
    console.log(`Total elements checked: ${results.length}`);

    const passing = results.filter((r) => r.passes.aa);
    const failing = results.filter((r) => !r.passes.aa);

    console.log(`Passing AA: ${passing.length}`);
    console.log(`Failing AA: ${failing.length}`);

    if (failing.length > 0) {
      console.log("\nFailing elements:");
      failing.forEach((f) => {
        console.log(`  - ${f.element}`);
        console.log(`    Ratio: ${f.ratio}:1`);
      });
    }

    // This test always passes - it's just for reporting
    expect(true).toBe(true);
  });
});

test.describe("Specific Component Contrast", () => {
  test("sidebar navigation contrast", async ({ page }) => {
    await page.goto("/");
    await page.waitForLoadState("networkidle");

    // Check sidebar if it exists
    const sidebar = page.locator("nav, [role='navigation'], aside").first();
    if (await sidebar.isVisible()) {
      const results = await checkContrast(page, "nav *, [role='navigation'] *, aside *");
      expectContrastToPass(results, "aa");
    }
  });

  test("cards and panels contrast", async ({ page }) => {
    await page.goto("/");
    await page.waitForLoadState("networkidle");

    const results = await checkContrast(page, "[class*='card'], [class*='panel'], [class*='box']");
    // Soft assertion - only fail if there are elements and they fail
    if (results.length > 0) {
      expectContrastToPass(results, "aa");
    }
  });
});
