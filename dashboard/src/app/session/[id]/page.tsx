'use client';

import { useCallback, useEffect, useState } from 'react';

import { RunStatusSummary } from '@/components/run-status-summary';
import { SessionDetails } from '@/components/session-details';
import { SessionReport } from '@/components/session-report';
import { Card, CardContent } from '@/components/ui/card';
import useDashboardStore from '@/hooks/useDashboard';
import { getSessionDetail, type SessionDetailResult } from '@/lib/api';
import { useWebSocket } from '@/lib/websocket';
import type {
  ResearchRunStatus,
  ResearchRunStatusResponse,
  CriticalPath,
  StateChange,
  Decision,
  Degradation,
  Failure,
  ApiTelemetryEvent,
} from '@/types/telemetry';

export default function SessionPage({ params }: { params: { id: string } }) {
  const routeId = params.id;
  const isRunRoute = routeId.startsWith('run-');
  const [resolvedSessionId, setResolvedSessionId] = useState<string | null>(
    isRunRoute ? null : routeId
  );
  const [runStatus, setRunStatus] = useState<ResearchRunStatus | null>(
    isRunRoute ? 'queued' : null
  );
  const [derivedOutputs, setDerivedOutputs] = useState<{
    narrative: ApiTelemetryEvent[];
    criticalPath: CriticalPath;
    stateChanges: StateChange[];
    decisions: Decision[];
    degradations: Degradation[];
    failures: Failure[];
  } | null>(null);
  const setSelectedEvent = useDashboardStore((state) => state.setSelectedEvent);
  const selectedEvent = useDashboardStore((state) => state.selectedEvent);
  const viewMode = useDashboardStore((state) => state.viewMode);
  const setViewMode = useDashboardStore((state) => state.setViewMode);
  const reconcileSession = useDashboardStore((state) => state.reconcileSession);
  const telemetrySessionId = isRunRoute ? resolvedSessionId : routeId;
  const { connected, events } = useWebSocket(telemetrySessionId);

  // Fetch derived outputs for historical sessions
  useEffect(() => {
    if (!telemetrySessionId || isRunRoute) {
      setDerivedOutputs(null);
      return;
    }

    getSessionDetail(telemetrySessionId)
      .then((result: SessionDetailResult) => {
        setDerivedOutputs(result.derivedOutputs);
      })
      .catch((error) => {
        console.error('Failed to fetch derived outputs:', error);
        setDerivedOutputs(null);
      });
  }, [telemetrySessionId, isRunRoute]);

  useEffect(() => {
    setResolvedSessionId(isRunRoute ? null : routeId);
    setRunStatus(isRunRoute ? 'queued' : null);
  }, [isRunRoute, routeId]);

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

  return (
    <div className="space-y-5">
      {isRunRoute ? (
        <RunStatusSummary
          runId={routeId}
          onSessionIdResolved={setResolvedSessionId}
          onStatusChange={setRunStatus}
          onStatusLoaded={handleRunStatusLoaded}
        />
      ) : null}

      {!telemetrySessionId ? (
        <Card className="border-dashed">
          <CardContent className="py-8 text-center text-sm text-muted-foreground">
            Waiting for the backend to allocate a session ID before live telemetry can load.
          </CardContent>
        </Card>
      ) : (
        <div className="grid grid-cols-1 gap-5 xl:grid-cols-2">
          <SessionReport sessionId={telemetrySessionId} runStatus={runStatus} />
          <SessionDetails
            sessionId={telemetrySessionId}
            connected={connected}
            events={events}
            selectedEvent={selectedEvent}
            viewMode={viewMode}
            onSelectEvent={setSelectedEvent}
            onViewModeChange={setViewMode}
            derivedOutputs={derivedOutputs ?? undefined}
          />
        </div>
      )}
    </div>
  );
}
