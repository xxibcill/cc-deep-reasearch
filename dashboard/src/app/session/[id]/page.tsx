'use client';

import { SessionPageFrame } from '@/components/session-page-frame';
import { SessionStaticDetails } from '@/components/session-static-details';

export default function SessionPage({ params }: { params: { id: string } }) {
  return (
    <SessionPageFrame
      routeId={params.id}
      view="details"
      title="Session Overview"
      description="What this session is about, whether it succeeded, and what to do next."
    >
      {({ sessionId, runStatus, sessionSummary }) => (
        <SessionStaticDetails
          sessionId={sessionId}
          runStatus={runStatus}
          sessionSummary={sessionSummary}
        />
      )}
    </SessionPageFrame>
  );
}
