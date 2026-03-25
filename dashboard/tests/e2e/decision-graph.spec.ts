import { test, expect } from "@playwright/test";

function buildSessionDetailPayload(decisionGraph: Record<string, unknown>) {
  return {
    session: {
      session_id: "decision-graph-session",
      label: "Decision Graph Session",
      created_at: "2026-03-20T00:00:00Z",
      total_time_ms: 1200,
      total_sources: 4,
      status: "completed",
      active: false,
      event_count: 2,
      last_event_at: "2026-03-20T00:00:02Z",
      query: "route choice",
      depth: "standard",
      completed_at: "2026-03-20T00:00:03Z",
      has_session_payload: true,
      has_report: false,
      archived: false,
    },
    summary: null,
    events_page: {
      events: [
        {
          event_id: "route-request",
          parent_event_id: null,
          sequence_number: 1,
          timestamp: "2026-03-20T00:00:01Z",
          session_id: "decision-graph-session",
          event_type: "llm.route_request",
          category: "llm",
          name: "route-request",
          status: "started",
          duration_ms: null,
          agent_id: "analyzer",
          metadata: { operation: "analysis" },
        },
        {
          event_id: "route-decision",
          parent_event_id: null,
          sequence_number: 2,
          timestamp: "2026-03-20T00:00:02Z",
          session_id: "decision-graph-session",
          event_type: "decision.made",
          category: "decision",
          name: "routing",
          status: "decided",
          duration_ms: null,
          agent_id: "analyzer",
          metadata: {
            decision_type: "routing",
            chosen_option: "openrouter_api",
            rejected_options: ["anthropic_api"],
            inputs: { operation: "analysis" },
          },
        },
      ],
      total: 2,
      has_more: false,
      next_cursor: null,
      prev_cursor: null,
    },
    event_tail: [],
    agent_timeline: [],
    active_phase: null,
    narrative: [],
    critical_path: {
      path: [],
      total_duration_ms: 0,
      bottleneck_event: null,
      phase_durations: [],
    },
    state_changes: [],
    decisions: [
      {
        event_id: "route-decision",
        sequence_number: 2,
        timestamp: "2026-03-20T00:00:02Z",
        decision_type: "routing",
        reason_code: "route_selected",
        chosen_option: "openrouter_api",
        inputs: { operation: "analysis" },
        rejected_options: ["anthropic_api"],
        confidence: 0.81,
        cause_event_ids: ["route-request"],
        actor_id: "analyzer",
      },
    ],
    degradations: [],
    failures: [],
    decision_graph: decisionGraph,
  };
}

test("decision graph renders and routes node selection into the inspector", async ({ page }) => {
  await page.route("http://localhost:8000/api/sessions/decision-graph-session**", async (route) => {
    await route.fulfill({
      contentType: "application/json",
      body: JSON.stringify(
        buildSessionDetailPayload({
          nodes: [
            {
              id: "event:route-request",
              kind: "event",
              label: "route-request",
              event_id: "route-request",
              sequence_number: 1,
              timestamp: "2026-03-20T00:00:01Z",
              event_type: "llm.route_request",
              actor_id: "analyzer",
              status: "started",
              severity: "info",
              inferred: false,
              metadata: { operation: "analysis" },
            },
            {
              id: "decision:route-decision",
              kind: "decision",
              label: "routing: openrouter_api",
              event_id: "route-decision",
              sequence_number: 2,
              timestamp: "2026-03-20T00:00:02Z",
              event_type: "decision.made",
              actor_id: "analyzer",
              status: "decided",
              severity: "info",
              inferred: false,
              metadata: { decision_type: "routing", chosen_option: "openrouter_api" },
            },
            {
              id: "outcome:route-decision:chosen",
              kind: "outcome",
              label: "openrouter_api",
              event_id: "route-decision",
              sequence_number: 2,
              timestamp: "2026-03-20T00:00:02Z",
              event_type: "decision.made",
              actor_id: "analyzer",
              status: "decided",
              severity: "info",
              inferred: false,
              metadata: { outcome: "chosen" },
            },
          ],
          edges: [
            {
              id: "caused_by:decision:route-decision:event:route-request:explicit",
              source: "decision:route-decision",
              target: "event:route-request",
              kind: "caused_by",
              inferred: false,
            },
            {
              id: "produced:decision:route-decision:outcome:route-decision:chosen:explicit",
              source: "decision:route-decision",
              target: "outcome:route-decision:chosen",
              kind: "produced",
              inferred: false,
            },
            {
              id: "led_to:event:route-request:decision:route-decision:inferred",
              source: "event:route-request",
              target: "decision:route-decision",
              kind: "led_to",
              inferred: true,
            },
          ],
          summary: {
            node_count: 3,
            edge_count: 3,
            explicit_edge_count: 2,
            inferred_edge_count: 1,
          },
        })
      ),
    });
  });

  await page.goto("/session/decision-graph-session/monitor");

  await expect(page.getByText("Telemetry Explorer")).toBeVisible();
  await page.getByLabel("Decision Graph").click();

  await expect(page.getByText("Decision Graph")).toBeVisible();
  await expect(page.locator('[data-edge-inferred="true"]')).toHaveCount(1);

  await page.getByTestId("decision-graph-node-decision-route-decision").click();

  await expect(page.locator("pre").last()).toContainText('"eventId": "route-decision"');
  await expect(page.locator("pre").last()).toContainText('"decision_type": "routing"');
});

test("decision graph view shows an empty state when no nodes are available", async ({ page }) => {
  await page.route("http://localhost:8000/api/sessions/decision-graph-session**", async (route) => {
    await route.fulfill({
      contentType: "application/json",
      body: JSON.stringify(
        buildSessionDetailPayload({
          nodes: [],
          edges: [],
          summary: {
            node_count: 0,
            edge_count: 0,
            explicit_edge_count: 0,
            inferred_edge_count: 0,
          },
        })
      ),
    });
  });

  await page.goto("/session/decision-graph-session/monitor");

  await expect(page.getByText("Telemetry Explorer")).toBeVisible();
  await page.getByLabel("Decision Graph").click();

  await expect(page.getByText("No decision graph nodes matched the current filters.")).toBeVisible();
});
