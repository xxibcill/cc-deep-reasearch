import type { MockSession } from './dashboard-mocks';

/**
 * Scenario name type for test fixtures.
 */
export type ScenarioName =
  | 'healthyCompletedRun'
  | 'liveActiveRun'
  | 'failedRunWithPartialTelemetry'
  | 'mixedStateDashboard';

interface Scenario {
  name: string;
  sessions: MockSession[];
}

/**
 * Predefined test scenarios.
 * This is a stub implementation with minimal data.
 */
export const SCENARIOS: Record<ScenarioName, Scenario> = {
  healthyCompletedRun: {
    name: 'Healthy Completed Run',
    sessions: [
      {
        session_id: 'research-report-003',
        label: 'Completed Research Run',
        created_at: '2026-04-01T10:00:00Z',
        total_time_ms: 120000,
        total_sources: 15,
        status: 'completed',
        active: false,
        event_count: 100,
        last_event_at: '2026-04-01T10:02:00Z',
        query: 'Sample research query',
        depth: 'deep',
        completed_at: '2026-04-01T10:02:00Z',
        has_session_payload: true,
        has_report: true,
      },
    ],
  },
  liveActiveRun: {
    name: 'Live Active Run',
    sessions: [
      {
        session_id: 'active-run-001',
        label: 'Active Research Run',
        created_at: '2026-04-10T09:00:00Z',
        total_time_ms: 30000,
        total_sources: 5,
        status: 'running',
        active: true,
        event_count: 25,
        last_event_at: '2026-04-10T09:00:30Z',
        query: 'Running research',
        depth: 'deep',
      },
    ],
  },
  failedRunWithPartialTelemetry: {
    name: 'Failed Run',
    sessions: [
      {
        session_id: 'failed-run-001',
        label: 'Failed Research Run',
        created_at: '2026-04-09T15:00:00Z',
        total_time_ms: 45000,
        total_sources: 3,
        status: 'failed',
        active: false,
        event_count: 15,
        last_event_at: '2026-04-09T15:00:45Z',
        query: 'Failed research query',
        depth: 'standard',
        has_session_payload: true,
        has_report: false,
      },
    ],
  },
  mixedStateDashboard: {
    name: 'Mixed State Dashboard',
    sessions: [
      {
        session_id: 'research-report-003',
        label: 'Completed Research',
        created_at: '2026-04-01T10:00:00Z',
        total_time_ms: 120000,
        total_sources: 15,
        status: 'completed',
        active: false,
        event_count: 100,
        last_event_at: '2026-04-01T10:02:00Z',
        query: 'Research query 1',
        depth: 'deep',
        completed_at: '2026-04-01T10:02:00Z',
        has_session_payload: true,
        has_report: true,
      },
      {
        session_id: 'active-run-001',
        label: 'Running Research',
        created_at: '2026-04-10T09:00:00Z',
        total_time_ms: 30000,
        total_sources: 5,
        status: 'running',
        active: true,
        event_count: 25,
        last_event_at: '2026-04-10T09:00:30Z',
        query: 'Research query 2',
        depth: 'deep',
      },
    ],
  },
};

/**
 * Get a scenario by name.
 */
export function getScenario(name: ScenarioName): Scenario {
  return SCENARIOS[name];
}
