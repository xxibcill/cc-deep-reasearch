import path from "node:path";
import type { Page } from "@playwright/test";

type MockSession = {
  session_id: string;
  label: string;
  created_at: string;
  total_time_ms: number | null;
  total_sources: number;
  status: string;
  active: boolean;
  event_count: number;
  last_event_at: string;
  query: string;
  depth: "quick" | "standard" | "deep";
  completed_at: string | null;
  has_session_payload: boolean;
  has_report: boolean;
  archived: boolean;
};

export const mockSessions: MockSession[] = [
  {
    session_id: "research-running-001",
    label: "Live NVIDIA Supply Chain Watch",
    created_at: "2026-04-06T01:00:00Z",
    total_time_ms: null,
    total_sources: 6,
    status: "running",
    active: true,
    event_count: 24,
    last_event_at: "2026-04-06T01:12:00Z",
    query: "Track current supply-chain constraints affecting NVIDIA GPU shipments.",
    depth: "standard",
    completed_at: null,
    has_session_payload: true,
    has_report: false,
    archived: false,
  },
  {
    session_id: "research-failed-002",
    label: "Broken Reuters Fact Check",
    created_at: "2026-04-05T19:00:00Z",
    total_time_ms: 18400,
    total_sources: 5,
    status: "failed",
    active: false,
    event_count: 31,
    last_event_at: "2026-04-05T19:00:18Z",
    query: "Validate whether Reuters published a correction on the earnings leak.",
    depth: "quick",
    completed_at: "2026-04-05T19:00:18Z",
    has_session_payload: true,
    has_report: false,
    archived: false,
  },
  {
    session_id: "research-report-003",
    label: "Stablecoin Banking Landscape",
    created_at: "2026-04-05T08:10:00Z",
    total_time_ms: 48600,
    total_sources: 12,
    status: "completed",
    active: false,
    event_count: 64,
    last_event_at: "2026-04-05T08:10:48Z",
    query: "Summarize the current banking-access landscape for major stablecoin issuers.",
    depth: "standard",
    completed_at: "2026-04-05T08:10:48Z",
    has_session_payload: true,
    has_report: true,
    archived: false,
  },
  {
    session_id: "research-deep-004",
    label: "Energy Grid Contagion Deep Dive",
    created_at: "2026-04-04T22:15:00Z",
    total_time_ms: 81200,
    total_sources: 19,
    status: "completed",
    active: false,
    event_count: 92,
    last_event_at: "2026-04-04T22:16:21Z",
    query: "Investigate how regional grid instability could spill into European energy pricing.",
    depth: "deep",
    completed_at: "2026-04-04T22:16:21Z",
    has_session_payload: true,
    has_report: true,
    archived: false,
  },
  {
    session_id: "research-archive-005",
    label: "Archived Policy Backfill",
    created_at: "2026-04-03T14:30:00Z",
    total_time_ms: 45200,
    total_sources: 10,
    status: "completed",
    active: false,
    event_count: 54,
    last_event_at: "2026-04-03T14:31:05Z",
    query: "Backfill the policy memo archive with the latest municipal zoning changes.",
    depth: "standard",
    completed_at: "2026-04-03T14:31:05Z",
    has_session_payload: true,
    has_report: true,
    archived: true,
  },
  {
    session_id: "research-history-006",
    label: "Telemetry Dry Run",
    created_at: "2026-04-02T10:15:00Z",
    total_time_ms: 22800,
    total_sources: 7,
    status: "completed",
    active: false,
    event_count: 36,
    last_event_at: "2026-04-02T10:15:22Z",
    query: "Run a telemetry-only smoke test without generating a final report artifact.",
    depth: "quick",
    completed_at: "2026-04-02T10:15:22Z",
    has_session_payload: true,
    has_report: false,
    archived: false,
  },
];

type MockOptions = {
  sessions?: MockSession[];
};

function getSession(sessionId: string, sessions: MockSession[]): MockSession {
  const session = sessions.find((item) => item.session_id === sessionId);
  if (!session) {
    throw new Error(`Unknown mock session: ${sessionId}`);
  }
  return session;
}

function buildSessionDetail(session: MockSession) {
  return {
    session,
    summary: null,
    events_page: {
      events: [
        {
          event_id: `${session.session_id}-1`,
          parent_event_id: null,
          sequence_number: 1,
          timestamp: session.created_at,
          session_id: session.session_id,
          event_type: "research.started",
          category: "agent",
          name: "research-started",
          status: "started",
          duration_ms: null,
          agent_id: "analyzer",
          metadata: { phase: "intake" },
        },
        {
          event_id: `${session.session_id}-2`,
          parent_event_id: `${session.session_id}-1`,
          sequence_number: 2,
          timestamp: session.last_event_at,
          session_id: session.session_id,
          event_type: "source.collected",
          category: "tool",
          name: "source-collected",
          status: "completed",
          duration_ms: 1200,
          agent_id: "analyzer",
          metadata: { provider: "tavily", count: session.total_sources },
        },
        {
          event_id: `${session.session_id}-3`,
          parent_event_id: `${session.session_id}-1`,
          sequence_number: 3,
          timestamp: session.last_event_at,
          session_id: session.session_id,
          event_type: "report.generated",
          category: "llm",
          name: "report-generated",
          status: session.status === "failed" ? "failed" : "completed",
          duration_ms: session.total_time_ms,
          agent_id: "reporter",
          metadata: { report_ready: session.has_report },
        },
      ],
      total: 3,
      has_more: false,
      next_cursor: null,
      prev_cursor: null,
    },
    event_tail: [],
    agent_timeline: [],
    active_phase: session.active ? "analysis" : null,
    narrative: [],
    critical_path: {
      path: [],
      total_duration_ms: session.total_time_ms ?? 0,
      bottleneck_event: null,
      phase_durations: [],
    },
    state_changes: [],
    decisions: [],
    degradations: [],
    failures:
      session.status === "failed"
        ? [
            {
              event_id: `${session.session_id}-3`,
              sequence_number: 3,
              timestamp: session.last_event_at,
              event_type: "report.generated",
              category: "llm",
              name: "report-generated",
              status: "failed",
              severity: "error",
              reason_code: "mock_failure",
              error_message: "Mock failure for regression coverage",
              phase: "reporting",
              actor_id: "reporter",
              duration_ms: 1200,
              recoverable: false,
              stack_trace: null,
            },
          ]
        : [],
    decision_graph: {
      nodes: [],
      edges: [],
      summary: {
        node_count: 0,
        edge_count: 0,
        explicit_edge_count: 0,
        inferred_edge_count: 0,
      },
    },
    prompt_metadata: {
      overrides_applied: false,
      effective_overrides: {},
      default_prompts_used: ["analyzer", "deep_analyzer", "report_quality_evaluator"],
    },
  };
}

function buildReport(session: MockSession) {
  return {
    session_id: session.session_id,
    format: "markdown",
    media_type: "text/markdown",
    content: `# ${session.label}\n\n## Query\n\n${session.query}\n\n## Status\n\n${session.status}\n`,
  };
}

export async function mockDashboardApis(page: Page, options: MockOptions = {}) {
  const sessions = options.sessions ?? mockSessions;

  await page.route("**/api/sessions**", async (route) => {
    const url = new URL(route.request().url());
    const pathName = url.pathname;

    if (pathName.endsWith("/api/sessions")) {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          sessions,
          total: sessions.length,
          next_cursor: null,
        }),
      });
      return;
    }

    const reportMatch = pathName.match(/\/api\/sessions\/([^/]+)\/report$/);
    if (reportMatch) {
      const session = getSession(reportMatch[1], sessions);
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(buildReport(session)),
      });
      return;
    }

    const sessionMatch = pathName.match(/\/api\/sessions\/([^/]+)$/);
    if (sessionMatch) {
      const session = getSession(sessionMatch[1], sessions);
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(
          url.searchParams.get("include_derived") === "true"
            ? buildSessionDetail(session)
            : { session }
        ),
      });
      return;
    }

    await route.fallback();
  });
}

export async function mockResearchRunApi(page: Page, runId = "research-report-003") {
  await page.route("**/api/research-runs", async (route) => {
    if (route.request().method() !== "POST") {
      await route.fallback();
      return;
    }

    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        run_id: runId,
        status: "running",
      }),
    });
  });
}

export function screenshotPath(fileName: string) {
  return path.join(process.cwd(), "playwright-screenshots", "2026-04-06", fileName);
}
