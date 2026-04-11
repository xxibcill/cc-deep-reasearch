import type { MockSession } from "./dashboard-mocks";

export interface ScenarioDefinition {
  name: string;
  description: string;
  sessions: MockSession[];
  tags: string[];
}

export const SCENARIOS = {
  healthyCompletedRun: {
    name: "healthyCompletedRun",
    description: "A completed research session with a full report, all telemetry, and no errors",
    sessions: [
      {
        session_id: "scenario-healthy-001",
        label: "Completed Research Task",
        created_at: "2026-04-07T10:00:00Z",
        total_time_ms: 120000,
        total_sources: 15,
        status: "completed",
        active: false,
        event_count: 45,
        last_event_at: "2026-04-07T10:02:00Z",
        query: "What are the latest developments in quantum computing?",
        depth: "standard",
        completed_at: "2026-04-07T10:02:00Z",
        has_session_payload: true,
        has_report: true,
        archived: false,
      },
    ],
    tags: ["completed", "healthy", "report"],
  } as ScenarioDefinition,

  liveActiveRun: {
    name: "liveActiveRun",
    description: "An actively running research session receiving live events",
    sessions: [
      {
        session_id: "scenario-live-001",
        label: "Live Research Analysis",
        created_at: "2026-04-07T10:30:00Z",
        total_time_ms: null,
        total_sources: 8,
        status: "running",
        active: true,
        event_count: 22,
        last_event_at: "2026-04-07T10:35:00Z",
        query: "Analyze the current state of AI chip supply chain",
        depth: "deep",
        completed_at: null,
        has_session_payload: true,
        has_report: false,
        archived: false,
      },
    ],
    tags: ["running", "live", "active"],
  } as ScenarioDefinition,

  failedRunWithPartialTelemetry: {
    name: "failedRunWithPartialTelemetry",
    description: "A failed session with some telemetry collected before failure",
    sessions: [
      {
        session_id: "scenario-failed-001",
        label: "Failed Analysis Task",
        created_at: "2026-04-07T09:00:00Z",
        total_time_ms: 35000,
        total_sources: 6,
        status: "failed",
        active: false,
        event_count: 18,
        last_event_at: "2026-04-07T09:00:35Z",
        query: "Verify breaking news story authenticity",
        depth: "quick",
        completed_at: "2026-04-07T09:00:35Z",
        has_session_payload: true,
        has_report: false,
        archived: false,
      },
    ],
    tags: ["failed", "partial", "error"],
  } as ScenarioDefinition,

  completedRunWithoutReport: {
    name: "completedRunWithoutReport",
    description: "A completed session that collected data but did not generate a report",
    sessions: [
      {
        session_id: "scenario-no-report-001",
        label: "Telemetry Only Run",
        created_at: "2026-04-07T08:00:00Z",
        total_time_ms: 45000,
        total_sources: 10,
        status: "completed",
        active: false,
        event_count: 32,
        last_event_at: "2026-04-07T08:00:45Z",
        query: "Quick data collection test",
        depth: "quick",
        completed_at: "2026-04-07T08:00:45Z",
        has_session_payload: true,
        has_report: false,
        archived: false,
      },
    ],
    tags: ["completed", "no-report", "telemetry"],
  } as ScenarioDefinition,

  sessionWithPromptOverrides: {
    name: "sessionWithPromptOverrides",
    description: "A session where prompt templates were overridden",
    sessions: [
      {
        session_id: "scenario-overrides-001",
        label: "Custom Prompt Research",
        created_at: "2026-04-07T07:00:00Z",
        total_time_ms: 95000,
        total_sources: 12,
        status: "completed",
        active: false,
        event_count: 38,
        last_event_at: "2026-04-07T07:01:35Z",
        query: "Deep technical analysis with custom prompts",
        depth: "deep",
        completed_at: "2026-04-07T07:01:35Z",
        has_session_payload: true,
        has_report: true,
        archived: false,
      },
    ],
    tags: ["completed", "prompts", "overrides"],
  } as ScenarioDefinition,

  sessionWithLargeEventVolume: {
    name: "sessionWithLargeEventVolume",
    description: "A session with high event count for stress testing",
    sessions: [
      {
        session_id: "scenario-large-001",
        label: "High Volume Research",
        created_at: "2026-04-06T20:00:00Z",
        total_time_ms: 300000,
        total_sources: 25,
        status: "completed",
        active: false,
        event_count: 150,
        last_event_at: "2026-04-06T20:05:00Z",
        query: "Comprehensive analysis across multiple domains",
        depth: "deep",
        completed_at: "2026-04-06T20:05:00Z",
        has_session_payload: true,
        has_report: true,
        archived: false,
      },
    ],
    tags: ["completed", "high-volume", "stress"],
  } as ScenarioDefinition,

  mixedStateDashboard: {
    name: "mixedStateDashboard",
    description: "Dashboard with multiple sessions in various states for list view testing",
    sessions: [
      {
        session_id: "scenario-mixed-001",
        label: "Active Research",
        created_at: "2026-04-07T10:30:00Z",
        total_time_ms: null,
        total_sources: 5,
        status: "running",
        active: true,
        event_count: 12,
        last_event_at: "2026-04-07T10:35:00Z",
        query: "Running query 1",
        depth: "standard",
        completed_at: null,
        has_session_payload: true,
        has_report: false,
        archived: false,
      },
      {
        session_id: "scenario-mixed-002",
        label: "Completed Task",
        created_at: "2026-04-07T09:00:00Z",
        total_time_ms: 60000,
        total_sources: 10,
        status: "completed",
        active: false,
        event_count: 30,
        last_event_at: "2026-04-07T09:01:00Z",
        query: "Completed query",
        depth: "standard",
        completed_at: "2026-04-07T09:01:00Z",
        has_session_payload: true,
        has_report: true,
        archived: false,
      },
      {
        session_id: "scenario-mixed-003",
        label: "Failed Task",
        created_at: "2026-04-07T08:00:00Z",
        total_time_ms: 15000,
        total_sources: 3,
        status: "failed",
        active: false,
        event_count: 8,
        last_event_at: "2026-04-07T08:00:15Z",
        query: "Failed query",
        depth: "quick",
        completed_at: "2026-04-07T08:00:15Z",
        has_session_payload: true,
        has_report: false,
        archived: false,
      },
      {
        session_id: "scenario-mixed-004",
        label: "Archived Task",
        created_at: "2026-04-05T10:00:00Z",
        total_time_ms: 80000,
        total_sources: 18,
        status: "completed",
        active: false,
        event_count: 55,
        last_event_at: "2026-04-05T10:01:20Z",
        query: "Old archived query",
        depth: "deep",
        completed_at: "2026-04-05T10:01:20Z",
        has_session_payload: true,
        has_report: true,
        archived: true,
      },
    ],
    tags: ["mixed", "dashboard", "list"],
  } as ScenarioDefinition,
} as const;

export type ScenarioName = keyof typeof SCENARIOS;

export function getScenario(name: ScenarioName) {
  return SCENARIOS[name];
}

export function getAllScenarios(): ScenarioDefinition[] {
  return Object.values(SCENARIOS);
}

export function getScenariosByTag(tag: string): ScenarioDefinition[] {
  return getAllScenarios().filter((s) => s.tags.includes(tag));
}

export function getScenarioSessionIds(scenario: ScenarioDefinition): string[] {
  return scenario.sessions.map((s) => s.session_id);
}
