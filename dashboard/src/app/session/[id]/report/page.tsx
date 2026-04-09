'use client';

import { SessionPageFrame } from '@/components/session-page-frame';
import { SessionReport } from '@/components/session-report';

export default function SessionReportPage({ params }: { params: { id: string } }) {
  return (
    <SessionPageFrame
      routeId={params.id}
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
