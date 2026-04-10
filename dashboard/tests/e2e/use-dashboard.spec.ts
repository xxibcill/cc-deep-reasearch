import { expect, test } from "@playwright/test";

import useDashboardStore, {
  DEFAULT_EVENT_FILTERS,
  MAX_BUFFERED_EVENTS,
} from "@/hooks/useDashboard";
import type { TelemetryEvent } from "@/types/telemetry";

function buildEvent(sequenceNumber: number): TelemetryEvent {
  return {
    eventId: `event-${sequenceNumber}`,
    parentEventId: null,
    sequenceNumber,
    timestamp: new Date(Date.UTC(2026, 3, 7, 0, 0, sequenceNumber)).toISOString(),
    sessionId: "session-123",
    eventType: "tool.search",
    category: "tool",
    name: "search_web",
    status: "completed",
    durationMs: 1000,
    agentId: "analyzer",
    metadata: {},
  };
}

function resetStore() {
  useDashboardStore.setState({
    events: [],
    filters: DEFAULT_EVENT_FILTERS,
    viewMode: "graph",
    selectedEvent: null,
    connected: false,
  });
}

test.beforeEach(() => {
  resetStore();
});

test.afterEach(() => {
  resetStore();
});

test("appendEvents preserves full historical loads", async () => {
  const events = Array.from({ length: MAX_BUFFERED_EVENTS + 25 }, (_, index) =>
    buildEvent(index + 1)
  );

  useDashboardStore.getState().appendEvents(events);

  expect(useDashboardStore.getState().events).toHaveLength(events.length);
  expect(useDashboardStore.getState().events[0]?.eventId).toBe("event-1");
  expect(useDashboardStore.getState().events.at(-1)?.eventId).toBe(
    `event-${MAX_BUFFERED_EVENTS + 25}`
  );
});

test("appendBufferedEvents keeps live buffers bounded to the most recent events", async () => {
  const events = Array.from({ length: MAX_BUFFERED_EVENTS + 25 }, (_, index) =>
    buildEvent(index + 1)
  );

  useDashboardStore.getState().appendBufferedEvents(events);

  expect(useDashboardStore.getState().events).toHaveLength(MAX_BUFFERED_EVENTS);
  expect(useDashboardStore.getState().events[0]?.eventId).toBe("event-26");
  expect(useDashboardStore.getState().events.at(-1)?.eventId).toBe(
    `event-${MAX_BUFFERED_EVENTS + 25}`
  );
});
