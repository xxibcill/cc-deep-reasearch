'use client';

import { useCallback, useEffect, useRef, useState } from 'react';

import useDashboardStore from '@/hooks/useDashboard';
import { getApiErrorMessage, getResearchRunBySession, getSession } from '@/lib/api';
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
  controlRunId: string | null;
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
  const [controlRunId, setControlRunId] = useState<string | null>(
    isRunRoute ? routeId : null
  );
  const [sessionSummary, setSessionSummary] = useState<Session | null>(null);
  const [sessionError, setSessionError] = useState<string | null>(null);
  const runLookupAttemptedRef = useRef<string | null>(null);
  const activeControlRunIdRef = useRef<string | null>(isRunRoute ? routeId : null);
  const reconcileSession = useDashboardStore((state) => state.reconcileSession);

  const sessionId = isRunRoute ? resolvedSessionId : routeId;

  useEffect(() => {
    setResolvedSessionId(isRunRoute ? null : routeId);
    setRunStatus(isRunRoute ? 'queued' : null);
    setControlRunId(isRunRoute ? routeId : null);
    setSessionSummary(null);
    setSessionError(null);
    runLookupAttemptedRef.current = null;
    activeControlRunIdRef.current = isRunRoute ? routeId : null;
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

        const sessionStatus = toRunStatus(response.session);

        setSessionSummary(response.session);
        setSessionError(null);

        if (!isRunRoute) {
          if (runLookupAttemptedRef.current !== sessionId) {
            runLookupAttemptedRef.current = sessionId;
            try {
              const lookup = await getResearchRunBySession(sessionId);
              if (!mounted) {
                return;
              }

              if (lookup && (lookup.status === 'queued' || lookup.status === 'running')) {
                activeControlRunIdRef.current = lookup.run_id;
                setControlRunId(lookup.run_id);
                setRunStatus(lookup.status);
              } else {
                activeControlRunIdRef.current = null;
                setControlRunId(null);
                setRunStatus((current) =>
                  mergeRunStatus(current, lookup?.status ?? sessionStatus)
                );
              }
            } catch {
              runLookupAttemptedRef.current = null;
              if (!activeControlRunIdRef.current) {
                setRunStatus((current) => mergeRunStatus(current, sessionStatus));
              }
            }
          } else if (!activeControlRunIdRef.current) {
            setRunStatus((current) => mergeRunStatus(current, sessionStatus));
          }
        } else {
          setRunStatus((current) => mergeRunStatus(current, sessionStatus));
        }

        if (
          isTerminalStatus(sessionStatus) &&
          (!isRunRoute ? !activeControlRunIdRef.current : true) &&
          intervalId
        ) {
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
  }, [isRunRoute, sessionId]);

  const handleRunStatusLoaded = useCallback(
    (status: ResearchRunStatusResponse) => {
      if (isTerminalStatus(status.status)) {
        activeControlRunIdRef.current = null;
        setControlRunId(null);
      }

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
    controlRunId,
    runStatus,
    sessionSummary,
    sessionError,
    setResolvedSessionId,
    setRunStatus,
    handleRunStatusLoaded,
  };
}
