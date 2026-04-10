'use client';

import * as React from 'react';
import { SessionTelemetryWorkspace } from '@/components/session-telemetry-workspace';
import { SessionPageFrame } from '@/components/session-page-frame';

export default function SessionMonitorPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = React.use(params);
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
