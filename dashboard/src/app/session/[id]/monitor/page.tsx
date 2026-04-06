'use client';

import dynamic from 'next/dynamic';

import { Card, CardContent } from '@/components/ui/card';
import { SessionPageFrame } from '@/components/session-page-frame';

const SessionTelemetryWorkspace = dynamic(
  () =>
    import('@/components/session-telemetry-workspace').then(
      (module) => module.SessionTelemetryWorkspace
    ),
  {
    ssr: false,
    loading: () => (
      <Card className="border-border/70 bg-surface/68">
        <CardContent className="flex min-h-[260px] items-center justify-center">
          <div className="space-y-2 text-center">
            <div className="mx-auto h-8 w-8 animate-spin rounded-full border-2 border-border border-t-primary" />
            <p className="text-sm text-muted-foreground">Loading monitor...</p>
          </div>
        </CardContent>
      </Card>
    ),
  }
);

export default function SessionMonitorPage({ params }: { params: { id: string } }) {
  return (
    <SessionPageFrame
      routeId={params.id}
      view="monitor"
      title="Telemetry Monitor"
      description="Live telemetry, workflow graphs, event tables, and execution traces."
    >
      {({ sessionId }) => <SessionTelemetryWorkspace sessionId={sessionId} />}
    </SessionPageFrame>
  );
}
