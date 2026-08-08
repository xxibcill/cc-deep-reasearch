import { act, render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { RunStatusSummary } from '@/components/run-status-summary';
import { getResearchRunStatus } from '@/lib/api';
import type { ResearchRunStatusResponse } from '@/types/telemetry';

vi.mock('@/components/ui/notification-center', () => ({
  useNotifications: () => ({ notify: vi.fn() }),
}));

vi.mock('@/lib/api', () => ({
  getApiErrorMessage: (_error: unknown, fallback: string) => fallback,
  getResearchRunStatus: vi.fn(),
  stopResearchRun: vi.fn(),
}));

const getResearchRunStatusMock = vi.mocked(getResearchRunStatus);

function deferred<T>() {
  let resolve!: (value: T) => void;
  const promise = new Promise<T>((promiseResolve) => {
    resolve = promiseResolve;
  });
  return { promise, resolve };
}

function runStatus(
  runId: string,
  status: ResearchRunStatusResponse['status']
): ResearchRunStatusResponse {
  return {
    run_id: runId,
    status,
    created_at: '2026-08-08T00:00:00Z',
    completed_at: status === 'completed' ? '2026-08-08T00:00:10Z' : undefined,
    session_id: 'session-race',
  };
}

describe('RunStatusSummary polling', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('discards a delayed response from an obsolete status request', async () => {
    const delayedResponse = deferred<ResearchRunStatusResponse>();
    getResearchRunStatusMock.mockImplementation((runId) =>
      runId === 'run-old'
        ? delayedResponse.promise
        : Promise.resolve(runStatus('run-current', 'completed'))
    );
    const onStatusChange = vi.fn();

    const { rerender } = render(
      <RunStatusSummary runId="run-old" onStatusChange={onStatusChange} />
    );

    rerender(<RunStatusSummary runId="run-current" onStatusChange={onStatusChange} />);

    await waitFor(() => {
      expect(onStatusChange).toHaveBeenCalledWith('completed');
    });

    await act(async () => {
      delayedResponse.resolve(runStatus('run-old', 'running'));
      await delayedResponse.promise;
    });

    expect(onStatusChange.mock.calls.map(([status]) => status)).toEqual(['completed']);
    expect(screen.getAllByText('Completed').length).toBeGreaterThan(0);
    expect(screen.queryByRole('button', { name: 'Stop run' })).toBeNull();
  });

  it('clears active controls while a new run status is loading', async () => {
    const currentResponse = deferred<ResearchRunStatusResponse>();
    getResearchRunStatusMock.mockImplementation((runId) =>
      runId === 'run-old'
        ? Promise.resolve(runStatus('run-old', 'running'))
        : currentResponse.promise
    );

    const { rerender } = render(<RunStatusSummary runId="run-old" />);

    await screen.findByRole('button', { name: 'Stop run' });
    rerender(<RunStatusSummary runId="run-current" />);

    expect(screen.queryByRole('button', { name: 'Stop run' })).toBeNull();
    expect(screen.getByText('Loading run status...')).toBeTruthy();

    await act(async () => {
      currentResponse.resolve(runStatus('run-current', 'completed'));
      await currentResponse.promise;
    });
  });
});
