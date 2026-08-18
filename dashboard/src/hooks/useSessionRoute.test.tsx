import { act, renderHook, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { useSessionRoute } from '@/hooks/useSessionRoute';
import { getSession } from '@/lib/api';
import type { Session } from '@/types/telemetry';

vi.mock('@/lib/api', () => ({
  getApiErrorMessage: (_error: unknown, fallback: string) => fallback,
  getSession: vi.fn(),
}));

const getSessionMock = vi.mocked(getSession);

const finalizedTelemetrySession: Session = {
  sessionId: 'research-finalizing',
  label: 'Finalizing research',
  createdAt: '2026-08-12T10:00:00Z',
  totalTimeMs: 1_000,
  totalSources: 4,
  status: 'completed',
  active: false,
  eventCount: 10,
  lastEventAt: '2026-08-12T10:01:00Z',
  query: 'Why is the report still finalizing?',
  depth: 'standard',
  completedAt: '2026-08-12T10:01:00Z',
  hasSessionPayload: true,
  hasReport: false,
};

describe('useSessionRoute run lifecycle', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    getSessionMock.mockResolvedValue({ session: finalizedTelemetrySession });
  });

  it('does not let early session telemetry complete an active research job', async () => {
    const { result } = renderHook(() => useSessionRoute('run-finalizing'));

    act(() => {
      result.current.setRunStatus('running');
      result.current.setResolvedSessionId('research-finalizing');
    });

    await waitFor(() => {
      expect(result.current.sessionSummary?.sessionId).toBe('research-finalizing');
    });

    expect(result.current.runStatus).toBe('running');
  });
});
