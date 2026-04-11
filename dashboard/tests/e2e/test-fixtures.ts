import type { Page } from "@playwright/test";
import { mockDashboardApis, type MockSession } from "./dashboard-mocks";
import { getScenario, type ScenarioName, SCENARIOS } from "./scenarios";

export interface TestFixtureOptions {
  scenario?: ScenarioName;
  customSessions?: MockSession[];
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

export async function setupDashboardWithActiveRun(page: Page): Promise<void> {
  await setupTestPage(page, { scenario: "liveActiveRun" });
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