import fs from "node:fs";
import path from "node:path";
import { test } from "@playwright/test";

import { mockDashboardApis, screenshotPath } from "./dashboard-mocks";

test.describe("dashboard screenshots", () => {
  test.skip(!process.env.CAPTURE_DASHBOARD_SCREENSHOTS, "Only used to refresh checked-in screenshots.");

  test("capture home control room", async ({ page }) => {
    await mockDashboardApis(page);
    await page.goto("/");
    await page.waitForLoadState("networkidle");

    const outputPath = screenshotPath("home-control-room.png");
    fs.mkdirSync(path.dirname(outputPath), { recursive: true });
    await page.screenshot({ path: outputPath, fullPage: true });
  });

  test("capture compare workflow", async ({ page }) => {
    await mockDashboardApis(page);
    await page.goto("/compare?a=research-report-003&b=research-deep-004");
    await page.waitForLoadState("networkidle");

    const outputPath = screenshotPath("compare-stablecoin-vs-grid.png");
    fs.mkdirSync(path.dirname(outputPath), { recursive: true });
    await page.screenshot({ path: outputPath, fullPage: true });
  });

  test("capture session workspace overview", async ({ page }) => {
    await mockDashboardApis(page);
    await page.goto("/session/research-report-003");
    await page.waitForLoadState("networkidle");

    const outputPath = screenshotPath("session-overview-stablecoin.png");
    fs.mkdirSync(path.dirname(outputPath), { recursive: true });
    await page.screenshot({ path: outputPath, fullPage: true });
  });
});
