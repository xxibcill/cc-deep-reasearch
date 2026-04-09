import { expect, test } from "@playwright/test";

import { deriveOperatorInsights, deriveTelemetryState } from "@/lib/telemetry-transformers";
import type { TelemetryEvent } from "@/types/telemetry";

function buildEvent(
  sequenceNumber: number,
  overrides: Partial<TelemetryEvent>
): TelemetryEvent {
  return {
    eventId: `event-${sequenceNumber}`,
    parentEventId: null,
    sequenceNumber,
    timestamp: new Date(Date.now() - (10 - sequenceNumber) * 1_000).toISOString(),
    sessionId: "session-123",
    eventType: "phase.started",
    category: "phase",
    name: "planning",
    status: "started",
    durationMs: null,
    agentId: null,
    metadata: {},
    ...overrides,
  };
}

test("deriveOperatorInsights reports completed runs with an available report", async () => {
  const events = [
    buildEvent(1, {
      eventType: "phase.started",
      name: "planning",
      status: "started",
    }),
    buildEvent(2, {
      eventType: "agent.started",
      category: "agent",
      name: "planning-agent",
      status: "started",
      agentId: "analyzer",
      metadata: { phase: "planning" },
    }),
    buildEvent(3, {
      eventType: "agent.completed",
      category: "agent",
      name: "planning-agent",
      status: "completed",
      durationMs: 15_000,
      agentId: "analyzer",
      metadata: { phase: "planning" },
    }),
    buildEvent(4, {
      eventType: "phase.completed",
      name: "planning",
      status: "completed",
      durationMs: 15_000,
    }),
  ];

  const derived = deriveTelemetryState(events);
  const insights = deriveOperatorInsights(events, derived, true);

  expect(insights).toContainEqual(
    expect.objectContaining({
      id: "insight-complete",
      status: "healthy",
      actions: [expect.objectContaining({ actionType: "open_report" })],
    })
  );
});

test("deriveOperatorInsights flags completed runs that are missing a report", async () => {
  const events = [
    buildEvent(1, {
      eventType: "phase.started",
      name: "analysis",
      status: "started",
    }),
    buildEvent(2, {
      eventType: "agent.started",
      category: "agent",
      name: "analysis-agent",
      status: "started",
      agentId: "analyzer",
      metadata: { phase: "analysis" },
    }),
    buildEvent(3, {
      eventType: "agent.completed",
      category: "agent",
      name: "analysis-agent",
      status: "completed",
      durationMs: 42_000,
      agentId: "analyzer",
      metadata: { phase: "analysis" },
    }),
    buildEvent(4, {
      eventType: "phase.completed",
      name: "analysis",
      status: "completed",
      durationMs: 42_000,
    }),
  ];

  const derived = deriveTelemetryState(events);
  const insights = deriveOperatorInsights(events, derived, false);

  expect(insights).toContainEqual(
    expect.objectContaining({
      id: "insight-complete-no-report",
      status: "warning",
      actions: expect.arrayContaining([
        expect.objectContaining({ actionType: "view_phases" }),
        expect.objectContaining({ actionType: "compare_runs" }),
      ]),
    })
  );
});

test("deriveOperatorInsights detects stalled active runs", async () => {
  const stalledTimestamp = new Date(Date.now() - 121_000).toISOString();
  const events = [
    buildEvent(1, {
      timestamp: stalledTimestamp,
      eventType: "phase.started",
      name: "synthesis",
      status: "started",
    }),
    buildEvent(2, {
      timestamp: stalledTimestamp,
      eventType: "agent.started",
      category: "agent",
      name: "synthesis-agent",
      status: "started",
      agentId: "analyzer",
      metadata: { phase: "synthesis" },
    }),
  ];

  const derived = deriveTelemetryState(events);
  const insights = deriveOperatorInsights(events, derived, false);

  expect(insights).toContainEqual(
    expect.objectContaining({
      id: "insight-stalled",
      status: "warning",
      actions: expect.arrayContaining([
        expect.objectContaining({ actionType: "view_phases" }),
        expect.objectContaining({ actionType: "review_llm_reasoning" }),
      ]),
    })
  );
});

test("deriveOperatorInsights points to tool failures with phase context", async () => {
  const events = [
    buildEvent(1, {
      eventType: "phase.started",
      name: "analysis",
      status: "started",
    }),
    buildEvent(2, {
      eventType: "agent.started",
      category: "agent",
      name: "analysis-agent",
      status: "started",
      agentId: "analyzer",
      metadata: { phase: "analysis" },
    }),
    buildEvent(3, {
      eventType: "tool.search",
      category: "tool",
      name: "search_web",
      status: "failed",
      durationMs: 5_000,
      agentId: "analyzer",
      metadata: {
        error: "upstream timeout",
      },
    }),
  ];

  const derived = deriveTelemetryState(events);
  const insights = deriveOperatorInsights(events, derived, false);
  const failureInsight = insights.find((insight) => insight.id === "insight-failures");

  expect(failureInsight).toEqual(
    expect.objectContaining({
      status: "error",
      phase: "analysis",
      description: expect.stringContaining("analysis"),
      actions: expect.arrayContaining([
        expect.objectContaining({ actionType: "inspect_tool_failures" }),
        expect.objectContaining({ actionType: "compare_runs" }),
      ]),
    })
  );
});

test("deriveOperatorInsights surfaces slow tools without treating them as failures", async () => {
  const events = [
    buildEvent(1, {
      eventType: "phase.started",
      name: "analysis",
      status: "started",
    }),
    buildEvent(2, {
      eventType: "agent.started",
      category: "agent",
      name: "analysis-agent",
      status: "running",
      agentId: "analyzer",
      metadata: { phase: "analysis" },
    }),
    buildEvent(3, {
      eventType: "tool.search",
      category: "tool",
      name: "search_web",
      status: "completed",
      durationMs: 45_000,
      agentId: "analyzer",
      metadata: {
        result_count: 12,
      },
    }),
  ];

  const derived = deriveTelemetryState(events);
  const insights = deriveOperatorInsights(events, derived, false);

  expect(insights).toContainEqual(
    expect.objectContaining({
      id: "insight-slow",
      status: "warning",
      actions: expect.arrayContaining([
        expect.objectContaining({ actionType: "inspect_tool_failures" }),
        expect.objectContaining({ actionType: "view_decisions" }),
      ]),
    })
  );
  expect(insights).toContainEqual(expect.objectContaining({ id: "insight-active", status: "healthy" }));
});
