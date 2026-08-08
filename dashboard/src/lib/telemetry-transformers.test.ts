import { describe, expect, it } from 'vitest';

import { normalizeServerMessage, normalizeSessionDetail } from './telemetry-transformers';
import type { ApiSession, ApiTelemetryEvent } from '@/types/telemetry';

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

describe('normalizeSessionDetail', () => {
  it('merges persisted summary metadata into a sparse historical session response', () => {
    const session = {
      session_id: 'research-report-003',
      created_at: '2026-04-05T15:00:00Z',
      total_time_ms: 9000,
      total_sources: 12,
      status: 'completed',
      active: false,
      event_count: 24,
      last_event_at: '2026-04-05T15:10:48Z',
    } as ApiSession;

    const normalized = normalizeSessionDetail(session, {
      query: 'Summarize the banking-access landscape for stablecoin issuers.',
      depth: 'standard',
      completed_at: '2026-04-05T15:10:48Z',
      sources: Array.from({ length: 12 }, (_, index) => ({ id: index })),
      metadata: { analysis: { findings: ['Finding'] } },
    });

    expect(normalized).toMatchObject({
      sessionId: 'research-report-003',
      label: 'Summarize the banking-access landscape for stablecoin issuers.',
      query: 'Summarize the banking-access landscape for stablecoin issuers.',
      depth: 'standard',
      completedAt: '2026-04-05T15:10:48Z',
      hasSessionPayload: true,
      hasReport: true,
    });
  });
});
