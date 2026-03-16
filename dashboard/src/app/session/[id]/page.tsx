'use client';

import { useState } from 'react';
import { SessionDetails } from '@/components/session-details';
import { RunStatusSummary } from '@/components/run-status-summary';
import { SessionReport } from '@/components/session-report';
import useDashboardStore from '@/hooks/useDashboard';
import { useWebSocket } from '@/lib/websocket';
import type { ResearchRunStatus } from '@/types/telemetry';

export default function SessionPage({ params }: { params: { id: string } }) {
  const sessionId = params.id;
  const { connected, events } = useWebSocket(sessionId);
  const viewMode = useDashboardStore((state) => state.viewMode);
  const selectedEvent = useDashboardStore((state) => state.selectedEvent);
  const [runStatus, setRunStatus] = useState<ResearchRunStatus>('queued');

  return (
    <div className="space-y-6">
      <RunStatusSummary
        runId={sessionId}
        onStatusChange={(status) => setRunStatus(status)}
      />
      <div className="grid grid-cols-1 xl:grid-cols-2 gap-6">
        <SessionReport sessionId={sessionId} runStatus={runStatus} />
        <SessionDetails
          sessionId={sessionId}
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
