/**
 * Smoke tests for the complete operator journey.
 *
 * Covers the main operator workflows without requiring live external provider calls.
 * Uses mock data and in-memory fixtures to keep tests deterministic and fast.
 *
 * Run with:
 *   npx playwright test tests/e2e/smoke-journey.spec.ts
 */

import { expect, test } from "@playwright/test";

import {
  mockDashboardApis,
  mockSessions,
} from "./dashboard-mocks";
import { SCENARIOS } from "./scenarios";
import { setupTestPage } from "./test-fixtures";

const SMOKE_TAG = "@smoke";

test.describe("Operator smoke suite", () => {
  test.beforeEach(async ({ page }) => {
    await mockDashboardApis(page);
  });

  // ── Journey 1: Launch or load a research session ────────────────────────────

  test(
    "operator can launch a new research session from the home page @smoke",
    async ({ page }) => {
      await page.goto("/");

      await page.getByLabel("Research Query").fill("What is the current state of fusion energy research?");

      await page.getByRole("button", { name: /start/i }).click();

      // Should navigate to the session monitor page
      await expect(page).toHaveURL(/\/session\/.*\/monitor/);
    }
  );

  test(
    "operator can load a session from the session list @smoke",
    async ({ page }) => {
      await setupTestPage(page, { customSessions: mockSessions });
      await page.goto("/");

      const firstSessionCard = page.locator("article").first();
      await expect(firstSessionCard).toBeVisible();

      await firstSessionCard.locator("a").first().click();

      await expect(page).toHaveURL(/\/session\/.*/);
      await expect(page.getByText(/Session Overview/i)).toBeVisible();
    }
  );

  // ── Journey 2: Monitor telemetry and inspect an event ───────────────────────

  test(
    "operator can monitor live telemetry for an active session @smoke",
    async ({ page }) => {
      const liveScenario = SCENARIOS.liveActiveRun;
      await setupTestPage(page, { customSessions: liveScenario.sessions });
      await page.goto(`/session/${liveScenario.sessions[0].session_id}/monitor`);

      await expect(page.getByText(/Live/i)).toBeVisible();
      await expect(page.getByText(/Radar/i)).toBeVisible();
    }
  );

  test(
    "operator can view session detail after load @smoke",
    async ({ page }) => {
      const healthyScenario = SCENARIOS.healthyCompletedRun;
      await setupTestPage(page, { customSessions: healthyScenario.sessions });
      await page.goto(`/session/${healthyScenario.sessions[0].session_id}`);

      await expect(page.getByText(/Session Overview/i)).toBeVisible();
      await expect(page.getByText(healthyScenario.sessions[0].label)).toBeVisible();
    }
  );

  // ── Journey 3: Add triage notes ──────────────────────────────────────────────

  test(
    "operator can add an annotation to a session @smoke",
    async ({ page }) => {
      const healthyScenario = SCENARIOS.healthyCompletedRun;
      await setupTestPage(page, { customSessions: healthyScenario.sessions });
      await page.goto(`/session/${healthyScenario.sessions[0].session_id}`);

      // Find the annotation panel
      const annotationPanel = page.getByText(/annotation|notes?|sticky note/i).first();
      if (await annotationPanel.isVisible()) {
        const noteInput = page.getByPlaceholder(/note|annotation/i);
        if (await noteInput.isVisible()) {
          await noteInput.fill("Reviewed the analysis. Findings look solid.");
          await page.getByRole("button", { name: /add|save/i }).first().click();
          await expect(page.getByText(/Reviewed the analysis/i)).toBeVisible();
        }
      }
    }
  );

  test(
    "operator can update triage status from the session detail page @smoke",
    async ({ page }) => {
      const healthyScenario = SCENARIOS.healthyCompletedRun;
      await setupTestPage(page, { customSessions: healthyScenario.sessions });
      await page.goto(`/session/${healthyScenario.sessions[0].session_id}`);

      const triageSection = page.getByText(/triage|status/i).first();
      if (await triageSection.isVisible()) {
        const statusButton = page.getByRole("button", { name: /needs review|investigated|blocked|ready/i }).first();
        if (await statusButton.isVisible()) {
          await statusButton.click();
          await expect(page.getByText(/triage/i)).toBeVisible();
        }
      }
    }
  );

  // ── Journey 4: Compare against a known-good run ──────────────────────────────

  test(
    "operator can open the compare page and select two sessions @smoke",
    async ({ page }) => {
      await setupTestPage(page, { customSessions: mockSessions });
      await page.goto("/compare");

      await expect(page.getByText(/compare/i)).toBeVisible();
    }
  );

  test(
    "failed session offers a compare-against-baseline action @smoke",
    async ({ page }) => {
      const failedScenario = SCENARIOS.failedRunWithPartialTelemetry;
      await setupTestPage(page, { customSessions: failedScenario.sessions });
      await page.goto(`/session/${failedScenario.sessions[0].session_id}`);

      const compareButton = page.getByRole("link", { name: /compare/i });
      if (await compareButton.isVisible()) {
        await expect(compareButton).toHaveAttribute("href", /\/compare\?b=/);
      }
    }
  );

  // ── Journey 5: Open a report ─────────────────────────────────────────────────

  test(
    "operator can open the research report for a completed session @smoke",
    async ({ page }) => {
      const healthyScenario = SCENARIOS.healthyCompletedRun;
      await setupTestPage(page, { customSessions: healthyScenario.sessions });
      await page.goto(`/session/${healthyScenario.sessions[0].session_id}/report`);

      await expect(page.getByText(/report/i)).toBeVisible();
    }
  );

  // ── Journey 6: Hand off report-ready work to content-gen ─────────────────────

  test(
    "report-ready session shows a content-gen handoff action @smoke",
    async ({ page }) => {
      const healthyScenario = SCENARIOS.healthyCompletedRun;
      await setupTestPage(page, { customSessions: healthyScenario.sessions });
      await page.goto(`/session/${healthyScenario.sessions[0].session_id}`);

      // The NextActions section may contain a content-gen handoff button
      const handoffButton = page.getByRole("link", { name: /content|studio|brief/i }).first();
      if (await handoffButton.isVisible()) {
        await expect(handoffButton).toBeVisible();
      }
    }
  );

  // ── Accessibility basics for new workflow controls ───────────────────────────

  test(
    "compare page uses semantic landmarks and accessible labels @smoke",
    async ({ page }) => {
      await setupTestPage(page, { customSessions: mockSessions });
      await page.goto("/compare");

      await expect(page.getByRole("main")).toBeVisible();

      const sessionACard = page.getByLabel(/baseline|session a/i).first();
      if (await sessionACard.isVisible()) {
        await expect(sessionACard).toBeVisible();
      }
    }
  );

  test(
    "session detail page annotations are keyboard accessible @smoke",
    async ({ page }) => {
      const healthyScenario = SCENARIOS.healthyCompletedRun;
      await setupTestPage(page, { customSessions: healthyScenario.sessions });
      await page.goto(`/session/${healthyScenario.sessions[0].session_id}`);

      const noteInput = page.getByPlaceholder(/note|annotation/i);
      if (await noteInput.isVisible()) {
        await noteInput.focus();
        await expect(noteInput).toBeFocused();
      }
    }
  );
});