'use client';

import { SessionPageFrame } from '@/components/session-page-frame';
import { SessionStaticDetails } from '@/components/session-static-details';

export default function SessionPage({ params }: { params: { id: string } }) {
  return (
    <SessionPageFrame
      routeId={params.id}
      view="details"
      title="Session Details"
      description="Static metadata, artifact availability, and run facts live on the base session route."
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
