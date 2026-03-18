'use client';

import { useEffect, useState } from 'react';
import { SessionDetails } from '@/components/session-details';
import { RunStatusSummary } from '@/components/run-status-summary';
import { SessionReport } from '@/components/session-report';
import useDashboardStore from '@/hooks/useDashboard';
import { useWebSocket } from '@/lib/websocket';
import type { ResearchRunStatus } from '@/types/telemetry';

export default function SessionPage({ params }: { params: { id: string } }) {
  const routeId = params.id;
  const isRunRoute = routeId.startsWith('run-');
  const [resolvedSessionId, setResolvedSessionId] = useState<string | null>(
    isRunRoute ? null : routeId
  );
  const [runStatus, setRunStatus] = useState<ResearchRunStatus | null>(
    isRunRoute ? 'queued' : null
  );
  const telemetrySessionId = isRunRoute ? resolvedSessionId : routeId;
  const displaySessionId = resolvedSessionId ?? routeId;
  const { connected, events } = useWebSocket(telemetrySessionId);
  const viewMode = useDashboardStore((state) => state.viewMode);
  const selectedEvent = useDashboardStore((state) => state.selectedEvent);

  useEffect(() => {
    setResolvedSessionId(isRunRoute ? null : routeId);
    setRunStatus(isRunRoute ? 'queued' : null);
  }, [isRunRoute, routeId]);

  return (
    <div className="space-y-6">
      {isRunRoute ? (
        <RunStatusSummary
          runId={routeId}
          onSessionIdResolved={(sessionId) => setResolvedSessionId(sessionId)}
          onStatusChange={(status) => setRunStatus(status)}
        />
      ) : null}
      <div className="grid grid-cols-1 xl:grid-cols-2 gap-6">
        <SessionReport sessionId={displaySessionId} runStatus={runStatus} />
        <SessionDetails
          sessionId={displaySessionId}
          connected={connected}
          events={events}
          selectedEvent={selectedEvent}
          viewMode={viewMode}
          onSelectEvent={(event) => useDashboardStore.getState().setSelectedEvent(event)}
          onViewModeChange={(mode) => useDashboardStore.getState().setViewMode(mode)}
        />
      </div>
    </div>
  );
}
