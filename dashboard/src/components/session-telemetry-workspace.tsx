'use client';

import { useEffect, useRef, useState } from 'react';
import { AlertCircle, Loader2, Radar, RefreshCcw, Waves } from 'lucide-react';

import useDashboardStore from '@/hooks/useDashboard';
import { getApiErrorMessage, getSessionDetail, type SessionDetailResult } from '@/lib/api';
import { isTerminalStatus } from '@/lib/session-route';
import { useWebSocket } from '@/lib/websocket';
import { HelpCallout } from '@/components/ui/help-callout';
import { SessionDetails } from '@/components/session-details';
import { getStatusBadgeMeta } from '@/components/telemetry/telemetry-header';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { useNotifications } from '@/components/ui/notification-center';
import { SkeletonCard } from '@/components/ui/skeleton';
import { getErrorGuidance } from '@/lib/error-messages';
import type {
  ResearchRunStatus,
  Session,
  SessionPromptMetadata,
} from '@/types/telemetry';

function formatTimestamp(value: string | null | undefined): string | null {
  if (!value) {
    return null;
  }

  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return null;
  }

  return date.toLocaleTimeString();
}

function formatRetryCountdown(nextRetryAt: string | null, nowMs: number): string | null {
  if (!nextRetryAt) {
    return null;
  }

  const retryAtMs = Date.parse(nextRetryAt);
  if (!Number.isFinite(retryAtMs)) {
    return null;
  }

  const seconds = Math.max(1, Math.ceil((retryAtMs - nowMs) / 1000));
  return `${seconds}s`;
}

interface SessionTelemetryWorkspaceProps {
  sessionId: string;
  runStatus: ResearchRunStatus | null;
  sessionSummary: Session | null;
}

export function SessionTelemetryWorkspace({
  sessionId,
  runStatus,
  sessionSummary,
}: SessionTelemetryWorkspaceProps) {
  const { notify } = useNotifications();
  const selectedEvent = useDashboardStore((state) => state.selectedEvent);
  const viewMode = useDashboardStore((state) => state.viewMode);
  const setSelectedEvent = useDashboardStore((state) => state.setSelectedEvent);
  const setViewMode = useDashboardStore((state) => state.setViewMode);
  const appendEvents = useDashboardStore((state) => state.appendEvents);
  const liveStreamDisabled = sessionSummary?.active === false || isTerminalStatus(runStatus);
  const { events, liveStreamStatus, reconnect } = useWebSocket(sessionId, {
    enabled: !liveStreamDisabled,
    historical: liveStreamDisabled,
  });
  const [derivedOutputs, setDerivedOutputs] = useState<SessionDetailResult['derivedOutputs'] | null>(
    null
  );
  const [promptMetadata, setPromptMetadata] = useState<SessionPromptMetadata | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [reloadNonce, setReloadNonce] = useState(0);
  const [nowMs, setNowMs] = useState(() => Date.now());
  const previousPhaseRef = useRef(liveStreamStatus.phase);

  useEffect(() => {
    if (liveStreamStatus.phase !== 'reconnecting' || !liveStreamStatus.nextRetryAt) {
      return;
    }

    const intervalId = window.setInterval(() => {
      setNowMs(Date.now());
    }, 1000);

    return () => {
      window.clearInterval(intervalId);
    };
  }, [liveStreamStatus.nextRetryAt, liveStreamStatus.phase]);

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

  useEffect(() => {
    const previousPhase = previousPhaseRef.current;
    previousPhaseRef.current = liveStreamStatus.phase;

    if (liveStreamStatus.phase !== 'failed' || previousPhase === 'failed') {
      return;
    }

    notify({
      variant: 'warning',
      persistent: true,
      title: 'Live stream dropped',
      description:
        liveStreamStatus.failureReason ??
        'The monitor kept buffered history, but live telemetry needs operator attention.',
      actions: liveStreamStatus.canReconnect
        ? [
            {
              label: 'Retry stream',
              onClick: reconnect,
            },
          ]
        : undefined,
    });
  }, [liveStreamStatus.canReconnect, liveStreamStatus.failureReason, liveStreamStatus.phase, notify, reconnect]);

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
  const badge = getStatusBadgeMeta(liveStreamStatus, events.length);
  const retryCountdown = formatRetryCountdown(liveStreamStatus.nextRetryAt, nowMs);
  const lastMessageLabel = formatTimestamp(liveStreamStatus.lastMessageAt);
  const lastEventLabel = formatTimestamp(liveStreamStatus.lastEventAt);
  const canRetryLiveStream = liveStreamStatus.canReconnect && liveStreamStatus.phase !== 'historical';
  const refreshWorkspace = () => setReloadNonce((value) => value + 1);

  if (!hasEvents) {
    const emptyStateDescription =
      liveStreamStatus.phase === 'historical'
        ? 'This session is no longer active, so the monitor can only show stored telemetry history.'
        : liveStreamStatus.phase === 'live'
          ? 'Events will appear here as the research session progresses. Connected and listening for activity.'
          : liveStreamStatus.phase === 'failed'
            ? 'The live stream could not be restored. Refresh the snapshot or retry the stream if the run is still active.'
            : liveStreamStatus.phase === 'reconnecting'
              ? `Events will appear here as the research session progresses. Reconnecting${
                  retryCountdown ? ` in ${retryCountdown}` : ''
                }.`
              : 'Waiting for the telemetry stream to begin.';

    return (
      <div className="space-y-4">
        <Card className="overflow-hidden">
          <CardHeader className="border-b border-border/60 bg-surface-raised/45">
            <div className="flex items-center justify-between">
              <div className="space-y-2">
                <CardTitle className="flex items-center gap-2">
                  <Radar className="h-5 w-5 text-primary" />
                  Telemetry Explorer
                </CardTitle>
                <p className="text-sm text-muted-foreground">
                  Session <span className="font-mono text-xs text-foreground">{sessionId}</span>{' '}
                  {liveStreamStatus.phase === 'historical'
                    ? 'has no active live stream.'
                    : 'is preparing the live telemetry feed.'}
                </p>
              </div>
              <Badge variant={badge.variant}>{badge.label}</Badge>
            </div>
          </CardHeader>
          <CardContent className="flex min-h-[320px] flex-col items-center justify-center gap-4 bg-surface/52">
            <Waves className="h-10 w-10 text-muted-foreground" />
            <div className="space-y-1 text-center">
              <p className="text-lg font-medium text-foreground">No telemetry events yet</p>
              <p className="max-w-xl text-sm text-muted-foreground">{emptyStateDescription}</p>
              {liveStreamStatus.failureReason ? (
                <p className="max-w-xl text-xs text-muted-foreground">
                  Last connection issue: {liveStreamStatus.failureReason}
                </p>
              ) : null}
            </div>
            <div className="flex flex-wrap items-center justify-center gap-3">
              <Button onClick={refreshWorkspace} type="button" variant="outline">
                <RefreshCcw className="mr-2 h-4 w-4" />
                Refresh history
              </Button>
              {canRetryLiveStream ? (
                <Button onClick={reconnect} type="button" variant="outline">
                  Retry live stream
                </Button>
              ) : null}
            </div>
          </CardContent>
        </Card>

        {(derivedOutputs || promptMetadata) ? (
          <SessionDetails
            sessionId={sessionId}
            liveStreamStatus={liveStreamStatus}
            events={events}
            selectedEvent={selectedEvent}
            viewMode={viewMode}
            onSelectEvent={setSelectedEvent}
            onViewModeChange={setViewMode}
            derivedOutputs={derivedOutputs ?? undefined}
            promptMetadata={promptMetadata ?? undefined}
          />
        ) : null}
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <HelpCallout
        id="telemetry-monitor"
        title="Telemetry monitor"
        content="Watch live events as they happen: agent calls, tool executions, reasoning traces, and derived outputs. Click any event to inspect the payload."
      />
      {liveStreamStatus.phase !== 'live' ? (
        <Card
          className={
            liveStreamStatus.phase === 'failed'
              ? 'border-error/25 bg-error-muted/18'
              : liveStreamStatus.phase === 'reconnecting'
                ? 'border-warning/25 bg-warning-muted/22'
                : 'border-border/70 bg-muted/20'
          }
        >
          <CardContent className="flex flex-col gap-4 p-4 lg:flex-row lg:items-start lg:justify-between">
            <div className="space-y-1.5">
              <p className="text-sm font-medium text-foreground">
                {liveStreamStatus.phase === 'historical'
                  ? 'Viewing historical telemetry only'
                  : liveStreamStatus.phase === 'failed'
                    ? 'Live stream unavailable'
                    : liveStreamStatus.phase === 'reconnecting'
                      ? 'Live stream interrupted'
                      : 'Connecting to live stream'}
              </p>
              <p className="text-sm text-muted-foreground">
                {liveStreamStatus.phase === 'historical'
                  ? 'This session is not active, so the monitor is showing stored telemetry history instead of a live feed.'
                  : liveStreamStatus.phase === 'failed'
                    ? `Automatic reconnect stopped after ${liveStreamStatus.reconnectAttempt} attempt${
                        liveStreamStatus.reconnectAttempt === 1 ? '' : 's'
                      }. The workspace remains usable with buffered history.`
                    : liveStreamStatus.phase === 'reconnecting'
                      ? `Buffered events remain visible while the dashboard retries the live stream${
                          retryCountdown ? ` in ${retryCountdown}` : ''
                        }.`
                      : 'The dashboard is establishing the live stream for this active session.'}
              </p>
              <p className="text-xs text-muted-foreground">
                {lastEventLabel ? `Last live event ${lastEventLabel}. ` : ''}
                {lastMessageLabel ? `Last stream message ${lastMessageLabel}. ` : ''}
                {liveStreamStatus.failureReason ? `Reason: ${liveStreamStatus.failureReason}` : ''}
              </p>
            </div>
            <div className="flex flex-wrap items-center gap-3">
              <Button onClick={refreshWorkspace} type="button" variant="outline">
                <RefreshCcw className="mr-2 h-4 w-4" />
                Refresh history
              </Button>
              {canRetryLiveStream ? (
                <Button onClick={reconnect} type="button" variant="outline">
                  Retry live stream
                </Button>
              ) : null}
            </div>
          </CardContent>
        </Card>
      ) : null}

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
        liveStreamStatus={liveStreamStatus}
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
