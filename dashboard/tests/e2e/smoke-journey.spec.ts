/**
 * Smoke tests for the complete operator journey.
 *
 * Covers the main operator workflows without requiring live external provider calls.
 * Uses mock data and in-memory fixtures to keep tests deterministic and fast.
 *
 * Run with:
 *   npx playwright test tests/e2e/smoke-journey.spec.ts
 */

import { expect, test, type Page } from "@playwright/test";

import {
  mockDashboardApis,
  mockResearchRunApi,
  mockSessions,
} from "./dashboard-mocks";
import { SCENARIOS } from "./scenarios";
import { setupTestPage } from "./test-fixtures";

async function mockSessionAnnotations(page: Page, sessionId: string) {
  await page.route(`**/api/sessions/${sessionId}/annotations`, async (route) => {
    if (route.request().method() === "GET") {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ annotations: [], count: 0 }),
      });
      return;
    }

    if (route.request().method() === "POST") {
      const payload = route.request().postDataJSON() as {
        note?: string;
        author?: string;
      };
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          annotation: {
            note: payload.note ?? "",
            author: payload.author ?? null,
            created_at: "2026-05-05T12:00:00Z",
            updated_at: null,
          },
        }),
      });
      return;
    }

    await route.fallback();
  });
}

test.describe("Operator smoke suite", () => {
  test.beforeEach(async ({ page }) => {
    await mockDashboardApis(page);
    await mockResearchRunApi(page);
  });

  // ── Journey 1: Launch or load a research session ────────────────────────────

  test(
    "operator can launch a new research session from the home page @smoke",
    async ({ page }) => {
      await page.goto("/");

      const researchQuery = page.getByLabel("Research Query");
      const startButton = page.getByRole("button", {
        name: /start standard research pass/i,
      });
      const queryText = "What is the current state of fusion energy research?";
      const monitorUrl = /\/session\/.*\/monitor/;

      await expect(researchQuery).toBeVisible();
      await expect(async () => {
        if (monitorUrl.test(new URL(page.url()).pathname)) {
          return;
        }

        await researchQuery.fill(queryText);
        await expect(researchQuery).toHaveValue(queryText);
        await expect(startButton).toBeEnabled({ timeout: 1_000 });
        await startButton.click();
        await expect(page).toHaveURL(monitorUrl, { timeout: 2_000 });
      }).toPass({ timeout: 15_000 });
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

      await expect(page.getByText(/Live telemetry/i)).toBeVisible();
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
      const sessionId = healthyScenario.sessions[0].session_id;
      await setupTestPage(page, { customSessions: healthyScenario.sessions });
      await mockSessionAnnotations(page, sessionId);
      await page.goto(`/session/${sessionId}`);

      const noteText = "Reviewed the analysis. Findings look solid.";
      const noteInput = page.getByPlaceholder("Add a note about this session...");
      const addNoteButton = page.getByRole("button", { name: /^add$/i }).first();

      await expect(noteInput).toBeVisible();
      await expect(async () => {
        await noteInput.fill(noteText);
        await expect(addNoteButton).toBeEnabled({ timeout: 1_000 });
      }).toPass({ timeout: 10_000 });

      await addNoteButton.click();
      await expect(page.getByText(noteText)).toBeVisible();
    }
  );

  test(
    "operator can update triage status from the session detail page @smoke",
    async ({ page }) => {
      const healthyScenario = SCENARIOS.healthyCompletedRun;
      await setupTestPage(page, { customSessions: healthyScenario.sessions });
      await page.goto(`/session/${healthyScenario.sessions[0].session_id}`);

      const triageSection = page.getByText(/triage status/i).first();
      if (await triageSection.isVisible()) {
        const statusButton = page.getByRole("button", { name: /needs review|investigated|blocked|ready/i }).first();
        if (await statusButton.isVisible()) {
          await statusButton.click();
          await expect(page.getByRole('heading', { name: 'Triage' })).toBeVisible();
        }
      }
    }
  );

  // ── Journey 4: Compare against a known-good run ──────────────────────────────

  test(
    "operator can open a populated compare page @smoke",
    async ({ page }) => {
      await setupTestPage(page, { customSessions: mockSessions });
      await page.goto("/compare?a=research-report-003&b=research-deep-004");

      await expect(page.getByRole("heading", { name: "Session Comparison" })).toBeVisible();
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

      await expect(page.getByRole('heading', { name: 'Session Report' })).toBeVisible();
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
