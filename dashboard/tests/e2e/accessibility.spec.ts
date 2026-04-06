import { test, expect } from "./fixtures";
import { mockDashboardApis } from "./dashboard-mocks";

test.describe("Contrast checks with fixtures", () => {
  test("page meets WCAG AA contrast standards", async ({ page, checkPageContrast }) => {
    await mockDashboardApis(page);
    await page.goto("/");
    await page.waitForLoadState("networkidle");

    await checkPageContrast("body");
  });

  test("headings meet contrast standards", async ({ page, checkPageContrast }) => {
    await mockDashboardApis(page);
    await page.goto("/");
    await page.waitForLoadState("networkidle");

    await checkPageContrast("h1, h2, h3, h4, h5, h6");
  });

  test("interactive elements meet contrast standards", async ({ page, checkPageContrast }) => {
    await mockDashboardApis(page);
    await page.goto("/");
    await page.waitForLoadState("networkidle");

    await checkPageContrast("button, a, [role='button'], input, label");
  });

  test("navigation meets AAA contrast (strict)", async ({ page, checkPageContrast }) => {
    await mockDashboardApis(page);
    await page.goto("/");
    await page.waitForLoadState("networkidle");

    await checkPageContrast("nav, [role='navigation']", { level: "aaa" });
  });

  test("compare workflow summary remains readable", async ({ page, checkPageContrast }) => {
    await mockDashboardApis(page);
    await page.goto("/compare?a=research-report-003&b=research-deep-004");
    await page.waitForLoadState("networkidle");

    await expect(page.getByRole("heading", { name: "Session Comparison" })).toBeVisible();
    await checkPageContrast("main, h1, h2, h3, button, a");
  });
});
