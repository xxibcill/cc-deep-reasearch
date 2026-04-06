'use client';

import { SessionPageFrame } from '@/components/session-page-frame';
import { SessionReport } from '@/components/session-report';

export default function SessionReportPage({ params }: { params: { id: string } }) {
  return (
    <SessionPageFrame
      routeId={params.id}
      view="report"
      title="Session Report"
      description="View final research artifacts and generated output. Available when session completes."
    >
      {({ sessionId, runStatus, sessionSummary }) => (
        <SessionReport
          sessionId={sessionId}
          runStatus={runStatus}
          hasReport={sessionSummary?.hasReport}
        />
      )}
    </SessionPageFrame>
  );
}
