import type { Page } from "@playwright/test";
import { mockDashboardApis, type MockSession } from "./dashboard-mocks";
import { getScenario, type ScenarioName, SCENARIOS } from "./scenarios";

export interface TestFixtureOptions {
  scenario?: ScenarioName;
  customSessions?: MockSession[];
}

export interface ActiveRunFixture {
  runId: string;
  session: MockSession;
}

export async function setupTestPage(
  page: Page,
  options: TestFixtureOptions = {}
): Promise<void> {
  const sessions = options.customSessions ?? (options.scenario
    ? getScenario(options.scenario).sessions
    : SCENARIOS.healthyCompletedRun.sessions);

  await mockDashboardApis(page, { sessions });
}

export async function openPrimaryNavigation(page: Page): Promise<void> {
  const menuButton = page.getByRole("button", { name: "Open main navigation" });
  await menuButton.focus();
  await menuButton.press("Enter");
}

export async function setupDashboardWithActiveRun(page: Page): Promise<ActiveRunFixture> {
  await setupTestPage(page, { scenario: "liveActiveRun" });
  const session = SCENARIOS.liveActiveRun.sessions[0];
  const runId = `run-${session.session_id}`;
  let stopRequested = false;

  await page.route(`**/api/research-runs/by-session/${session.session_id}`, async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        run_id: runId,
        status: stopRequested ? "cancelled" : "running",
        session_id: session.session_id,
        stop_requested: stopRequested,
      }),
    });
  });

  await page.route(`**/api/research-runs/${runId}/stop`, async (route) => {
    stopRequested = true;
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        run_id: runId,
        status: "running",
        session_id: session.session_id,
        stop_requested: true,
      }),
    });
  });

  await page.route(`**/api/research-runs/${runId}`, async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        run_id: runId,
        status: stopRequested ? "cancelled" : "running",
        created_at: session.created_at,
        started_at: session.created_at,
        completed_at: stopRequested ? session.last_event_at : undefined,
        session_id: session.session_id,
        stop_requested: stopRequested,
      }),
    });
  });

  return { runId, session };
}

export async function setupDashboardWithFailedRun(page: Page): Promise<void> {
  await setupTestPage(page, { scenario: "failedRunWithPartialTelemetry" });
}

export async function setupDashboardWithMixedState(page: Page): Promise<void> {
  await setupTestPage(page, { scenario: "mixedStateDashboard" });
}

export async function setupDashboardWithArchived(page: Page): Promise<void> {
  const archivedSession = {
    session_id: "archived-001",
    label: "Old Archived Research",
    created_at: "2026-03-01T10:00:00Z",
    total_time_ms: 90000,
    total_sources: 14,
    status: "completed" as const,
    active: false,
    event_count: 42,
    last_event_at: "2026-03-01T10:01:30Z",
    query: "Historical research task",
    depth: "standard" as const,
    completed_at: "2026-03-01T10:01:30Z",
    has_session_payload: true,
    has_report: true,
    archived: true,
  };
  await mockDashboardApis(page, { sessions: [archivedSession] });
}

export * from "./scenarios";
