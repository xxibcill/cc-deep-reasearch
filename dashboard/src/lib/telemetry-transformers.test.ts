import { describe, expect, it } from 'vitest';

import { normalizeServerMessage } from './telemetry-transformers';
import type { ApiTelemetryEvent } from '@/types/telemetry';

const apiEvent: ApiTelemetryEvent = {
  event_id: 'event-1',
  parent_event_id: null,
  sequence_number: 1,
  timestamp: '2026-06-10T00:00:00.000Z',
  session_id: 'session-123',
  event_type: 'phase.started',
  category: 'phase',
  name: 'source_collection',
  status: 'started',
  duration_ms: null,
  agent_id: null,
  metadata: {},
};

describe('normalizeServerMessage', () => {
  it('normalizes paginated history messages with cursor metadata', () => {
    const message = normalizeServerMessage({
      type: 'history_page',
      events: [apiEvent],
      total: 5,
      has_more: true,
      next_cursor: 7,
      prev_cursor: null,
    });

    expect(message).toMatchObject({
      type: 'history_page',
      total: 5,
      has_more: true,
      next_cursor: 7,
      prev_cursor: null,
    });
    expect(message?.events).toHaveLength(1);
    expect(message?.events?.[0]).toMatchObject({
      eventId: 'event-1',
      sequenceNumber: 1,
      sessionId: 'session-123',
    });
  });
});
