import { act, render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { SessionTelemetryWorkspace } from '@/components/session-telemetry-workspace';
import {
  getSessionDerivedOutputs,
  getSessionEventsPage,
  getSessionPromptMetadata,
  getSessionSummary,
} from '@/lib/api';
import type { SessionDetailResult } from '@/lib/api';
import type { Session, SessionPromptMetadata } from '@/types/telemetry';

vi.mock('@/components/session-details', () => ({
  SessionDetails: ({ promptMetadata }: { promptMetadata?: SessionPromptMetadata }) => (
    <div data-testid="prompt-metadata">
      {promptMetadata?.effective_overrides.analyzer?.prompt_prefix}
    </div>
  ),
}));

vi.mock('@/components/ui/notification-center', () => ({
  useNotifications: () => ({ notify: vi.fn() }),
}));

vi.mock('@/hooks/useDebugExport', () => ({
  useDebugExport: () => ({ exportDebugBundle: vi.fn(), isExporting: false }),
}));

vi.mock('@/lib/websocket', () => ({
  useWebSocket: () => ({
    events: [],
    reconnect: vi.fn(),
    liveStreamStatus: {
      phase: 'historical',
      connected: false,
      reconnectAttempt: 0,
      maxReconnectAttempts: 5,
      nextRetryAt: null,
      lastMessageAt: null,
      lastEventAt: null,
      lastHistoryAt: null,
      lastDisconnectAt: null,
      lastSuccessAt: null,
      failureReason: null,
      canReconnect: false,
      reconnectHistory: [],
    },
  }),
}));

vi.mock('@/lib/api', () => ({
  getApiErrorMessage: (_error: unknown, fallback: string) => fallback,
  getSessionDerivedOutputs: vi.fn(),
  getSessionEventsPage: vi.fn(),
  getSessionPromptMetadata: vi.fn(),
  getSessionSummary: vi.fn(),
}));

const getSessionDerivedOutputsMock = vi.mocked(getSessionDerivedOutputs);
const getSessionEventsPageMock = vi.mocked(getSessionEventsPage);
const getSessionPromptMetadataMock = vi.mocked(getSessionPromptMetadata);
const getSessionSummaryMock = vi.mocked(getSessionSummary);

function deferred<T>() {
  let resolve!: (value: T) => void;
  let reject!: (reason?: unknown) => void;
  const promise = new Promise<T>((promiseResolve, promiseReject) => {
    resolve = promiseResolve;
    reject = promiseReject;
  });
  return { promise, resolve, reject };
}

function derivedOutputs(): SessionDetailResult['derivedOutputs'] {
  return {
    narrative: [],
    criticalPath: {
      path: [],
      total_duration_ms: 0,
      bottleneck_event: null,
      phase_durations: [],
    },
    stateChanges: [],
    decisions: [],
    degradations: [],
    failures: [],
    decisionGraph: {
      nodes: [],
      edges: [],
      summary: {
        node_count: 0,
        edge_count: 0,
        explicit_edge_count: 0,
        inferred_edge_count: 0,
      },
    },
  };
}

function promptMetadata(label: string): SessionPromptMetadata {
  return {
    overrides_applied: true,
    effective_overrides: {
      analyzer: { prompt_prefix: label, system_prompt: null },
    },
    default_prompts_used: [],
  };
}

describe('SessionTelemetryWorkspace derived output loading', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    getSessionSummaryMock.mockResolvedValue({ session: {} as Session });
    getSessionEventsPageMock.mockResolvedValue({
      events: [],
      count: 0,
      hasMore: false,
      nextCursor: null,
      prevCursor: null,
    });
  });

  it('clears previous output and ignores a late response after session navigation', async () => {
    const delayedDerived = deferred<SessionDetailResult['derivedOutputs']>();
    const delayedPrompts = deferred<SessionPromptMetadata>();
    getSessionDerivedOutputsMock.mockImplementation((sessionId) =>
      sessionId === 'session-middle'
        ? delayedDerived.promise
        : Promise.resolve(derivedOutputs())
    );
    getSessionPromptMetadataMock.mockImplementation((sessionId) =>
      sessionId === 'session-middle'
        ? delayedPrompts.promise
        : Promise.resolve(promptMetadata(sessionId))
    );

    const { rerender } = render(
      <SessionTelemetryWorkspace
        sessionId="session-old"
        runStatus="completed"
        sessionSummary={null}
      />
    );

    expect((await screen.findByTestId('prompt-metadata')).textContent).toBe('session-old');
    rerender(
      <SessionTelemetryWorkspace
        sessionId="session-middle"
        runStatus="completed"
        sessionSummary={null}
      />
    );

    expect(screen.queryByTestId('prompt-metadata')).toBeNull();
    await waitFor(() => {
      expect(getSessionPromptMetadataMock).toHaveBeenCalledWith('session-middle');
    });
    expect(screen.queryByTestId('prompt-metadata')).toBeNull();

    rerender(
      <SessionTelemetryWorkspace
        sessionId="session-current"
        runStatus="completed"
        sessionSummary={null}
      />
    );
    expect((await screen.findByTestId('prompt-metadata')).textContent).toBe('session-current');

    await act(async () => {
      delayedDerived.resolve(derivedOutputs());
      delayedPrompts.resolve(promptMetadata('session-middle'));
      await Promise.all([delayedDerived.promise, delayedPrompts.promise]);
    });

    expect(screen.getByTestId('prompt-metadata').textContent).toBe('session-current');
  });

  it('shows prompt metadata even when derived outputs fail', async () => {
    const delayedDerived = deferred<SessionDetailResult['derivedOutputs']>();
    getSessionDerivedOutputsMock.mockReturnValue(delayedDerived.promise);
    getSessionPromptMetadataMock.mockResolvedValue(promptMetadata('prompt-audit'));

    render(
      <SessionTelemetryWorkspace
        sessionId="prompt-audit"
        runStatus="completed"
        sessionSummary={null}
      />
    );

    expect((await screen.findByTestId('prompt-metadata')).textContent).toBe('prompt-audit');

    await act(async () => {
      delayedDerived.reject(new Error('derived output failure'));
      await delayedDerived.promise.catch(() => undefined);
    });

    expect(screen.getByTestId('prompt-metadata').textContent).toBe('prompt-audit');
  });
});
