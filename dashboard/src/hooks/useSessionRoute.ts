'use client';

import { useCallback, useEffect, useState } from 'react';

import useDashboardStore from '@/hooks/useDashboard';
import { getApiErrorMessage, getSession } from '@/lib/api';
import {
  isRunRouteId,
  isTerminalStatus,
  mergeRunStatus,
  toRunStatus,
} from '@/lib/session-route';
import type { ResearchRunStatus, ResearchRunStatusResponse, Session } from '@/types/telemetry';

interface SessionRouteState {
  isRunRoute: boolean;
  resolvedSessionId: string | null;
  runStatus: ResearchRunStatus | null;
  sessionSummary: Session | null;
  sessionError: string | null;
  setResolvedSessionId: (sessionId: string) => void;
  setRunStatus: (status: ResearchRunStatus) => void;
  handleRunStatusLoaded: (status: ResearchRunStatusResponse) => void;
}

export function useSessionRoute(routeId: string): SessionRouteState {
  const isRunRoute = isRunRouteId(routeId);
  const [resolvedSessionId, setResolvedSessionId] = useState<string | null>(
    isRunRoute ? null : routeId
  );
  const [runStatus, setRunStatus] = useState<ResearchRunStatus | null>(
    isRunRoute ? 'queued' : null
  );
  const [sessionSummary, setSessionSummary] = useState<Session | null>(null);
  const [sessionError, setSessionError] = useState<string | null>(null);
  const reconcileSession = useDashboardStore((state) => state.reconcileSession);

  const sessionId = isRunRoute ? resolvedSessionId : routeId;

  useEffect(() => {
    setResolvedSessionId(isRunRoute ? null : routeId);
    setRunStatus(isRunRoute ? 'queued' : null);
    setSessionSummary(null);
    setSessionError(null);
  }, [isRunRoute, routeId]);

  useEffect(() => {
    if (!sessionId) {
      return;
    }

    let mounted = true;
    let intervalId: NodeJS.Timeout | null = null;

    const loadSessionSummary = async () => {
      try {
        const response = await getSession(sessionId);
        if (!mounted) {
          return;
        }

        setSessionSummary(response.session);
        setSessionError(null);
        setRunStatus((current) => mergeRunStatus(current, toRunStatus(response.session)));

        if (isTerminalStatus(toRunStatus(response.session)) && intervalId) {
          clearInterval(intervalId);
          intervalId = null;
        }
      } catch (requestError) {
        if (!mounted) {
          return;
        }

        setSessionError(getApiErrorMessage(requestError, 'Failed to load session status.'));
      }
    };

    void loadSessionSummary();
    intervalId = setInterval(loadSessionSummary, 4000);

    return () => {
      mounted = false;
      if (intervalId) {
        clearInterval(intervalId);
      }
    };
  }, [sessionId]);

  const handleRunStatusLoaded = useCallback(
    (status: ResearchRunStatusResponse) => {
      if (!status.session_id) {
        return;
      }

      if (status.status === 'running') {
        reconcileSession(status.session_id, { active: true, status: 'running' });
        return;
      }

      if (status.status === 'completed') {
        reconcileSession(status.session_id, { active: false, status: 'completed' });
        return;
      }

      if (status.status === 'failed') {
        reconcileSession(status.session_id, { active: false, status: 'failed' });
        return;
      }

      if (status.status === 'cancelled') {
        reconcileSession(status.session_id, { active: false, status: 'interrupted' });
      }
    },
    [reconcileSession]
  );

  return {
    isRunRoute,
    resolvedSessionId,
    runStatus,
    sessionSummary,
    sessionError,
    setResolvedSessionId,
    setRunStatus,
    handleRunStatusLoaded,
  };
}
