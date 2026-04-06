import { expect, test } from "@playwright/test";

import { mockDashboardApis, mockSessions } from "./dashboard-mocks";

test("home page exposes the control-room structure and launch presets", async ({ page }) => {
  await mockDashboardApis(page);

  await page.goto("/");

  await expect(page).toHaveTitle(/CC Deep Research/);
  await expect(page.getByRole("heading", { name: "Operations overview" })).toBeVisible();
  await expect(page.getByText("Running now", { exact: true })).toBeVisible();
  await expect(page.getByText("Failed or interrupted", { exact: true })).toBeVisible();
  await expect(page.getByText("Reports ready", { exact: true })).toBeVisible();
  await expect(page.getByText("Fast verification for a claim, update, or short question.")).toBeVisible();
  await expect(page.getByText("Balanced coverage for most day-to-day research requests.")).toBeVisible();
  await expect(page.getByText("Broader collection and more synthesis room for complex topics.")).toBeVisible();
  await expect(page.getByRole("heading", { name: "Running" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Needs Attention" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Report Ready" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Archived" })).toBeVisible();
});

test("launch form submits preset-derived options and prompt overrides", async ({ page }) => {
  await mockDashboardApis(page);

  let requestBody: Record<string, unknown> | null = null;
  await page.route("**/api/research-runs", async (route) => {
    requestBody = route.request().postDataJSON() as Record<string, unknown>;
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        run_id: "research-report-003",
        status: "running",
      }),
    });
  });

  await page.goto("/");
  await page.getByRole("button", { name: /Quick factual check/i }).click();
  await page.getByLabel("Research Query").fill("Check whether the ECB changed its inflation forecast today.");
  await page.getByRole("button", { name: /Operator Prompt Overrides/i }).click();
  await page.getByLabel("Analyzer Prompt Prefix", { exact: true }).fill("Prioritize central-bank sources.");
  await page.getByRole("button", { name: /Start Quick factual check/i }).click();

  await expect(page).toHaveURL(/\/session\/research-report-003\/monitor$/);
  expect(requestBody).toMatchObject({
    depth: "quick",
    min_sources: 3,
    realtime_enabled: true,
    agent_prompt_overrides: {
      analyzer: {
        prompt_prefix: "Prioritize central-bank sources.",
      },
    },
  });
});

test("compare mode guides selection and opens the integrated compare route", async ({ page }) => {
  await mockDashboardApis(page);

  await page.goto("/");
  await page.getByRole("button", { name: "Start Compare" }).click();

  await expect(page.getByText("Compare mode is active")).toBeVisible();
  await page.getByLabel("Compare session Stablecoin Banking Landscape").click();
  await expect(page.getByText("Baseline locked: Stablecoin Banking Landscape.")).toBeVisible();
  await page.getByLabel("Compare session Energy Grid Contagion Deep Dive").click();

  await expect(page.getByText("Comparison ready")).toBeVisible();
  await page.getByRole("button", { name: "View Comparison" }).click();

  await expect(page).toHaveURL(/\/compare\?a=research-report-003&b=research-deep-004$/);
  await expect(page.getByRole("heading", { name: "Session Comparison" })).toBeVisible();
  await expect(page.getByText("Operator summary")).toBeVisible();
  await expect(page.getByText("Material changes")).toBeVisible();
});

test("session workspace navigation covers overview, monitor, and report views", async ({ page }) => {
  await mockDashboardApis(page);

  await page.goto("/session/research-report-003");

  await expect(page.getByRole("heading", { name: "Session Overview" })).toBeVisible();
  await expect(page.getByText("Stablecoin Banking Landscape")).toBeVisible();

  await page.getByRole("link", { name: "Monitor" }).click();
  await expect(page).toHaveURL(/\/session\/research-report-003\/monitor$/);
  await expect(page.getByRole("heading", { name: "Telemetry Monitor" })).toBeVisible();
  await expect(page.getByText("Telemetry Explorer")).toBeVisible();

  await page.getByRole("link", { name: "Report" }).click();
  await expect(page).toHaveURL(/\/session\/research-report-003\/report$/);
  await expect(page.getByRole("heading", { name: "Session Report" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Stablecoin Banking Landscape" })).toBeVisible();
});

test("home page shows the empty state when no sessions are available", async ({ page }) => {
  await mockDashboardApis(page, { sessions: [] });

  await page.goto("/");

  await expect(page.getByRole("heading", { name: "Ready to research" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "No sessions available" })).toBeVisible();
});

test("compare route shows a clear error state for invalid selections", async ({ page }) => {
  await mockDashboardApis(page, { sessions: mockSessions });

  await page.goto("/compare?a=research-report-003&b=research-report-003");

  await expect(page.getByRole("heading", { name: "Invalid comparison" })).toBeVisible();
  await expect(page.getByText("Pick two different sessions")).toBeVisible();
});
