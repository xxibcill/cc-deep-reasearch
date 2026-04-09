'use client';

import { SessionTelemetryWorkspace } from '@/components/session-telemetry-workspace';
import { SessionPageFrame } from '@/components/session-page-frame';

export default function SessionMonitorPage({ params }: { params: { id: string } }) {
  return (
    <SessionPageFrame
      routeId={id}
      view="monitor"
      title="Telemetry Monitor"
      description="Live telemetry, workflow graphs, event tables, and execution traces."
    >
      {({ sessionId, runStatus, sessionSummary }) => (
        <SessionTelemetryWorkspace
          sessionId={sessionId}
          runStatus={runStatus}
          sessionSummary={sessionSummary}
        />
      )}
    </SessionPageFrame>
  );
}
