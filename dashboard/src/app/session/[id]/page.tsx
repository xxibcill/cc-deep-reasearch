'use client';

import { SessionPageFrame } from '@/components/session-page-frame';
import { SessionStaticDetails } from '@/components/session-static-details';

export default function SessionPage({ params }: { params: { id: string } }) {
  return (
    <SessionPageFrame
      routeId={params.id}
      view="details"
      title="Session Overview"
      description="View static metadata, artifact availability, and run facts for this session."
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
