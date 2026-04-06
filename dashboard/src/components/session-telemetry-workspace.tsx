'use client';

import { useEffect, useState } from 'react';
import { AlertCircle, Loader2, Radar, Waves } from 'lucide-react';

import useDashboardStore from '@/hooks/useDashboard';
import { getApiErrorMessage, getSessionDetail, type SessionDetailResult } from '@/lib/api';
import { useWebSocket } from '@/lib/websocket';
import { SessionDetails } from '@/components/session-details';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { SkeletonCard } from '@/components/ui/skeleton';
import { getErrorGuidance } from '@/lib/error-messages';
import type { SessionPromptMetadata } from '@/types/telemetry';

export function SessionTelemetryWorkspace({ sessionId }: { sessionId: string }) {
  const selectedEvent = useDashboardStore((state) => state.selectedEvent);
  const viewMode = useDashboardStore((state) => state.viewMode);
  const setSelectedEvent = useDashboardStore((state) => state.setSelectedEvent);
  const setViewMode = useDashboardStore((state) => state.setViewMode);
  const appendEvents = useDashboardStore((state) => state.appendEvents);
  const { connected, events } = useWebSocket(sessionId);
  const [derivedOutputs, setDerivedOutputs] = useState<SessionDetailResult['derivedOutputs'] | null>(
    null
  );
  const [promptMetadata, setPromptMetadata] = useState<SessionPromptMetadata | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [reloadNonce, setReloadNonce] = useState(0);

  useEffect(() => {
    let mounted = true;

    setLoading(true);
    setError(null);
    setDerivedOutputs(null);
    setPromptMetadata(null);

    getSessionDetail(sessionId)
      .then((result) => {
        if (!mounted) {
          return;
        }
        appendEvents(result.events);
        setDerivedOutputs(result.derivedOutputs);
        setPromptMetadata(result.promptMetadata ?? null);
      })
      .catch((requestError) => {
        if (!mounted) {
          return;
        }
        setError(getApiErrorMessage(requestError, 'Failed to load telemetry workspace.'));
      })
      .finally(() => {
        if (mounted) {
          setLoading(false);
        }
      });

    return () => {
      mounted = false;
    };
  }, [appendEvents, reloadNonce, sessionId]);

  if (loading && events.length === 0) {
    return (
      <Card>
        <CardContent className="p-5 space-y-5">
          <div className="grid grid-cols-2 gap-3 xl:grid-cols-4">
            {Array.from({ length: 4 }).map((_, i) => (
              <SkeletonCard key={i} />
            ))}
          </div>
          <div className="h-[300px] rounded-xl border flex items-center justify-center">
            <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
          </div>
        </CardContent>
      </Card>
    );
  }

  if (error && events.length === 0) {
    return (
      <Card className="border-destructive">
        <CardHeader>
          <CardTitle className="flex items-center gap-2 text-destructive">
            <AlertCircle className="h-5 w-5" />
            Telemetry Unavailable
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <p className="text-sm text-destructive">{error}</p>
          {(() => {
            const { guidance } = getErrorGuidance(error);
            return guidance ? <p className="text-xs text-muted-foreground">{guidance}</p> : null;
          })()}
          <Button onClick={() => setReloadNonce((value) => value + 1)} variant="outline">
            Retry
          </Button>
        </CardContent>
      </Card>
    );
  }

  const hasEvents = events.length > 0;
  const isLive = connected;

  if (!hasEvents) {
    return (
      <Card>
        <CardHeader className="border-b bg-[linear-gradient(135deg,rgba(15,23,42,0.04),rgba(14,165,233,0.10))]">
          <div className="flex items-center justify-between">
            <div className="space-y-2">
              <CardTitle className="flex items-center gap-2">
                <Radar className="h-5 w-5 text-primary" />
                Telemetry Explorer
              </CardTitle>
              <p className="text-sm text-muted-foreground">
                Session <span className="font-mono text-xs text-foreground">{sessionId}</span> — waiting for events to arrive.
              </p>
            </div>
            <div className="flex items-center gap-2">
              <span className="inline-flex h-2.5 w-2.5 animate-pulse rounded-full bg-amber-500" />
              <span className="text-sm text-muted-foreground">Live</span>
            </div>
          </div>
        </CardHeader>
        <CardContent className="flex min-h-[320px] flex-col items-center justify-center gap-4">
          <Waves className="h-10 w-10 text-muted-foreground" />
          <div className="space-y-1 text-center">
            <p className="text-lg font-medium text-foreground">No telemetry events yet</p>
            <p className="text-sm text-muted-foreground">
              Events will appear here as the research session progresses.
              {isLive ? ' Connected and listening for activity.' : ' Reconnecting to live stream...'}
            </p>
          </div>
        </CardContent>
      </Card>
    );
  }

  return (
    <div className="space-y-4">
      {error ? (
        <Card className="border-warning/30 bg-warning-muted/30">
          <CardContent className="flex items-start gap-3 p-4">
            <Radar className="mt-0.5 h-5 w-5 text-warning" />
            <div className="space-y-1">
              <p className="text-sm font-medium text-foreground">Partial telemetry data</p>
              <p className="text-sm text-muted-foreground">{error}</p>
            </div>
          </CardContent>
        </Card>
      ) : null}

      <SessionDetails
        sessionId={sessionId}
        connected={connected}
        events={events}
        selectedEvent={selectedEvent}
        viewMode={viewMode}
        onSelectEvent={setSelectedEvent}
        onViewModeChange={setViewMode}
        derivedOutputs={derivedOutputs ?? undefined}
        promptMetadata={promptMetadata ?? undefined}
      />
    </div>
  );
}
