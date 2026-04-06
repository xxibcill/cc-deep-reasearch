'use client';

import { useEffect, useState } from 'react';
import { AlertCircle, Loader2, Radar, Waves } from 'lucide-react';

import useDashboardStore from '@/hooks/useDashboard';
import { getApiErrorMessage, getSessionDetail, type SessionDetailResult } from '@/lib/api';
import { useWebSocket } from '@/lib/websocket';
import { SessionDetails } from '@/components/session-details';
import { Badge } from '@/components/ui/badge';
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
      <Card className="overflow-hidden">
        <CardHeader className="border-b border-border/60 bg-surface-raised/45">
          <div className="space-y-2">
            <p className="eyebrow">Monitor summary</p>
            <CardTitle className="text-[1.25rem]">Preparing telemetry workspace</CardTitle>
            <p className="max-w-2xl text-sm leading-6 text-muted-foreground">
              Loading event history, derived outputs, and prompt metadata for this session.
            </p>
          </div>
        </CardHeader>
        <CardContent className="space-y-5 p-5">
          <div className="grid grid-cols-2 gap-3 xl:grid-cols-4">
            {Array.from({ length: 4 }).map((_, i) => (
              <SkeletonCard key={i} />
            ))}
          </div>
          <div className="flex h-[300px] items-center justify-center rounded-xl border border-border/70 bg-surface/58">
            <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
          </div>
        </CardContent>
      </Card>
    );
  }

  if (error && events.length === 0) {
    return (
      <Card className="overflow-hidden border-error/25">
        <CardHeader className="border-b border-border/60 bg-error-muted/18">
          <CardTitle className="flex items-center gap-2 text-[1.25rem] text-foreground">
            <AlertCircle className="h-5 w-5 text-error" />
            Telemetry Unavailable
          </CardTitle>
          <p className="max-w-2xl text-sm leading-6 text-muted-foreground">
            The workspace could not assemble the telemetry history for this session.
          </p>
        </CardHeader>
        <CardContent className="space-y-4">
          <p className="text-sm text-error">{error}</p>
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
      <Card className="overflow-hidden">
        <CardHeader className="border-b border-border/60 bg-surface-raised/45">
          <div className="flex items-center justify-between">
            <div className="space-y-2">
              <CardTitle className="flex items-center gap-2">
                <Radar className="h-5 w-5 text-primary" />
                Telemetry Explorer
              </CardTitle>
              <p className="text-sm text-muted-foreground">
                Session <span className="font-mono text-xs text-foreground">{sessionId}</span> is
                connected to the workspace shell, but no telemetry has been recorded yet.
              </p>
            </div>
            <Badge variant={isLive ? 'info' : 'secondary'}>{isLive ? 'Live' : 'Reconnecting'}</Badge>
          </div>
        </CardHeader>
        <CardContent className="flex min-h-[320px] flex-col items-center justify-center gap-4 bg-surface/52">
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
        <Card className="border-warning/25 bg-warning-muted/22">
          <CardContent className="flex items-start gap-3 p-4">
            <Radar className="mt-0.5 h-5 w-5 text-warning" />
            <div className="space-y-1">
              <p className="text-sm font-medium text-foreground">Partial telemetry data</p>
              <p className="text-sm text-muted-foreground">
                Historical event data loaded, but one or more supplemental monitor datasets failed
                to refresh. {error}
              </p>
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
