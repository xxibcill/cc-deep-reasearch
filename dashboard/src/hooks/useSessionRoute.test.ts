import { renderHook, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { useSessionRoute } from '@/hooks/useSessionRoute';
import { getResearchRunBySession, getSession } from '@/lib/api';
import type { Session } from '@/types/telemetry';

vi.mock('@/lib/api', () => ({
  getApiErrorMessage: (_error: unknown, fallback: string) => fallback,
  getResearchRunBySession: vi.fn(),
  getSession: vi.fn(),
}));

const getResearchRunBySessionMock = vi.mocked(getResearchRunBySession);
const getSessionMock = vi.mocked(getSession);

const interruptedSession: Session = {
  sessionId: 'quiet-session',
  label: 'Quiet active session',
  createdAt: '2026-08-11T10:00:00Z',
  totalTimeMs: 900_000,
  totalSources: 2,
  status: 'interrupted',
  active: false,
  eventCount: 8,
  lastEventAt: '2026-08-11T10:15:00Z',
  query: 'Research a quiet long-running task',
  depth: 'deep',
  completedAt: null,
  hasSessionPayload: true,
  hasReport: false,
};

describe('useSessionRoute', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('keeps controls when the run registry is active but telemetry looks interrupted', async () => {
    getSessionMock.mockResolvedValue({ session: interruptedSession });
    getResearchRunBySessionMock.mockResolvedValue({
      run_id: 'run-quiet-session',
      status: 'running',
      stop_requested: false,
      session_id: interruptedSession.sessionId,
    });

    const { result, unmount } = renderHook(() => useSessionRoute(interruptedSession.sessionId));

    await waitFor(() => {
      expect(result.current.controlRunId).toBe('run-quiet-session');
    });

    expect(result.current.runStatus).toBe('running');
    expect(getResearchRunBySessionMock).toHaveBeenCalledWith(interruptedSession.sessionId);

    unmount();
  });
});
