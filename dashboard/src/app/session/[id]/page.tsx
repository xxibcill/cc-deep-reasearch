'use client';

import * as React from 'react';
import { SessionPageFrame } from '@/components/session-page-frame';
import { SessionOverview as SessionStaticDetails } from '@/components/session-static-details';

export default function SessionPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = React.use(params);
  return (
    <SessionPageFrame
      routeId={id}
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
