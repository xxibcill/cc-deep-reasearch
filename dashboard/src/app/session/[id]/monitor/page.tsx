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
      <Card className="border-slate-200/80 shadow-sm">
        <CardContent className="flex min-h-[260px] items-center justify-center">
          <div className="space-y-2 text-center">
            <div className="mx-auto h-8 w-8 animate-spin rounded-full border-2 border-slate-300 border-t-slate-700" />
            <p className="text-sm text-muted-foreground">Loading telemetry monitor…</p>
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
      description="Live telemetry, workflow graphs, event tables, and execution traces stay isolated on the monitor route."
    >
      {({ sessionId, runStatus, sessionSummary }) => (
        <SessionTelemetryWorkspace sessionId={sessionId} runStatus={runStatus} sessionSummary={sessionSummary} />
      )}
    </SessionPageFrame>
  );
}
