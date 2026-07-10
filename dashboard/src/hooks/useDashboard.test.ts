import { describe, it, expect, beforeEach } from 'vitest';
import useDashboardStore, {
  DEFAULT_EVENT_FILTERS,
  DEFAULT_LIVE_STREAM_STATUS,
  MAX_BUFFERED_EVENTS,
} from './useDashboard';
import type { TelemetryEvent } from '@/types/telemetry';

function buildEvent(sequenceNumber: number, eventId?: string): TelemetryEvent {
  return {
    eventId: eventId ?? `event-${sequenceNumber}`,
    parentEventId: null,
    sequenceNumber,
    timestamp: new Date(Date.UTC(2026, 3, 7, 0, 0, sequenceNumber)).toISOString(),
    sessionId: 'session-123',
    eventType: 'tool.search',
    category: 'tool',
    name: 'search_web',
    status: 'completed',
    durationMs: 1000,
    agentId: 'analyzer',
    metadata: {},
  };
}

function resetStore() {
  useDashboardStore.setState({
    sessionId: null,
    events: [],
    eventIdSet: new Set<string>(),
    filters: DEFAULT_EVENT_FILTERS,
    viewMode: 'graph',
    selectedEvent: null,
    connected: false,
    liveStreamStatus: DEFAULT_LIVE_STREAM_STATUS,
  });
}

beforeEach(() => {
  resetStore();
});

describe('eventIdSet deduplication', () => {
  it('appendEvent skips duplicate event IDs', () => {
    const store = useDashboardStore.getState();
    const event = buildEvent(1);

    store.appendEvent(event);
    expect(useDashboardStore.getState().events).toHaveLength(1);
    expect(useDashboardStore.getState().eventIdSet.size).toBe(1);

    // Append same event again
    store.appendEvent(event);
    expect(useDashboardStore.getState().events).toHaveLength(1);
    expect(useDashboardStore.getState().eventIdSet.size).toBe(1);
  });

  it('appendEvents skips duplicate event IDs', () => {
    const store = useDashboardStore.getState();
    const events = [
      buildEvent(1, 'event-a'),
      buildEvent(2, 'event-b'),
      buildEvent(3, 'event-a'), // duplicate
      buildEvent(4, 'event-c'),
      buildEvent(5, 'event-b'), // duplicate
    ];

    store.appendEvents(events);

    expect(useDashboardStore.getState().events).toHaveLength(3);
    const ids = useDashboardStore.getState().events.map((e) => e.eventId);
    expect(ids).toEqual(['event-a', 'event-b', 'event-c']);
  });

  it('eventIdSet stays in sync after replaceEvents', () => {
    const store = useDashboardStore.getState();
    const events = [buildEvent(1), buildEvent(2), buildEvent(3)];
    store.replaceEvents(events);

    const state = useDashboardStore.getState();
    expect(state.eventIdSet.size).toBe(3);
    expect(state.events.map((e) => e.eventId)).toEqual(['event-1', 'event-2', 'event-3']);
  });

  it('eventIdSet stays in sync after appendBufferedEvents trim', () => {
    const store = useDashboardStore.getState();
    // First add events up to MAX
    const initialEvents = Array.from({ length: MAX_BUFFERED_EVENTS }, (_, i) =>
      buildEvent(i + 1)
    );
    store.appendBufferedEvents(initialEvents);
    expect(useDashboardStore.getState().eventIdSet.size).toBe(MAX_BUFFERED_EVENTS);

    // Now add more events that exceed the buffer
    const newEvents = Array.from({ length: 100 }, (_, i) =>
      buildEvent(MAX_BUFFERED_EVENTS + i + 1)
    );
    store.appendBufferedEvents(newEvents);

    // Buffer should be trimmed and eventIdSet should match
    expect(useDashboardStore.getState().events).toHaveLength(MAX_BUFFERED_EVENTS);
    expect(useDashboardStore.getState().eventIdSet.size).toBe(MAX_BUFFERED_EVENTS);
  });

  it('appendEvent trims oldest events when exceeding MAX_BUFFERED_EVENTS', () => {
    const store = useDashboardStore.getState();
    // Fill to MAX - 2
    const initial = Array.from({ length: MAX_BUFFERED_EVENTS - 2 }, (_, i) =>
      buildEvent(i + 1)
    );
    store.replaceEvents(initial);

    // Add 5 new events - oldest 3 should be dropped (3998 + 5 = 4003 > 4000)
    for (let i = 0; i < 5; i++) {
      store.appendEvent(buildEvent(MAX_BUFFERED_EVENTS - 2 + i + 1));
    }

    const events = useDashboardStore.getState().events;
    expect(events).toHaveLength(MAX_BUFFERED_EVENTS);
    expect(events[0].eventId).toBe(`event-4`); // event-1, event-2, event-3 were trimmed
    expect(events.at(-1)?.eventId).toBe(`event-${MAX_BUFFERED_EVENTS + 3}`);
  });

  it('appendBufferedEvents keeps monotonic live batches in order', () => {
    const store = useDashboardStore.getState();
    store.replaceEvents([buildEvent(1), buildEvent(2)]);

    store.appendBufferedEvents([buildEvent(3), buildEvent(4), buildEvent(5)]);

    expect(useDashboardStore.getState().events.map((event) => event.sequenceNumber)).toEqual([
      1, 2, 3, 4, 5,
    ]);
  });

  it('appendBufferedEvents still sorts out-of-order batches', () => {
    const store = useDashboardStore.getState();
    store.replaceEvents([buildEvent(1), buildEvent(4)]);

    store.appendBufferedEvents([buildEvent(3), buildEvent(2)]);

    expect(useDashboardStore.getState().events.map((event) => event.sequenceNumber)).toEqual([
      1, 2, 3, 4,
    ]);
  });

  it('appendBufferedEvents handles 4,000 monotonic events in batches quickly', () => {
    const store = useDashboardStore.getState();
    const batches = Array.from({ length: 40 }, (_, batchIndex) =>
      Array.from({ length: 100 }, (_value, eventIndex) =>
        buildEvent(batchIndex * 100 + eventIndex + 1)
      )
    );

    const startedAt = performance.now();
    for (const batch of batches) {
      store.appendBufferedEvents(batch);
    }
    const elapsedMs = performance.now() - startedAt;

    expect(useDashboardStore.getState().events).toHaveLength(MAX_BUFFERED_EVENTS);
    expect(elapsedMs).toBeLessThan(250);
  });
});
