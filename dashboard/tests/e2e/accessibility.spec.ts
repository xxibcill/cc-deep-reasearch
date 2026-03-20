import { test, expect } from "./fixtures";

test.describe("Contrast checks with fixtures", () => {
  test("page meets WCAG AA contrast standards", async ({ page, checkPageContrast }) => {
    await page.goto("/");
    await page.waitForLoadState("networkidle");

    await checkPageContrast("body");
  });

  test("headings meet contrast standards", async ({ page, checkPageContrast }) => {
    await page.goto("/");
    await page.waitForLoadState("networkidle");

    await checkPageContrast("h1, h2, h3, h4, h5, h6");
  });

  test("interactive elements meet contrast standards", async ({ page, checkPageContrast }) => {
    await page.goto("/");
    await page.waitForLoadState("networkidle");

    await checkPageContrast("button, a, [role='button'], input, label");
  });

  test("navigation meets AAA contrast (strict)", async ({ page, checkPageContrast }) => {
    await page.goto("/");
    await page.waitForLoadState("networkidle");

    await checkPageContrast("nav, [role='navigation']", { level: "aaa" });
  });
});
