'use client';

import * as React from 'react';
import { SessionPageFrame } from '@/components/session-page-frame';
import { SessionReport } from '@/components/session-report';

export default function SessionReportPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = React.use(params);
  return (
    <SessionPageFrame
      routeId={id}
      view="report"
      title="Session Report"
      description="Final research artifacts and generated output."
    >
      {({ sessionId, runStatus, sessionSummary }) => (
        <SessionReport
          sessionId={sessionId}
          runStatus={runStatus}
          sessionSummary={sessionSummary}
          hasReport={sessionSummary?.hasReport}
        />
      )}
    </SessionPageFrame>
  );
}
