'use client';

import { useEffect, useState } from 'react';
import {
  AlertCircle,
  Ban,
  CheckCircle,
  Clock,
  Loader2,
  Square,
  XCircle,
} from 'lucide-react';

import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import {
  getApiErrorMessage,
  getResearchRunStatus,
  stopResearchRun,
} from '@/lib/api';
import type { ResearchRunStatus, ResearchRunStatusResponse } from '@/types/telemetry';

interface RunStatusSummaryProps {
  runId: string;
  onSessionIdResolved?: (sessionId: string) => void;
  onStatusChange?: (status: ResearchRunStatus) => void;
  onStatusLoaded?: (status: ResearchRunStatusResponse) => void;
}

function statusIcon(status: ResearchRunStatus) {
  switch (status) {
    case 'queued':
      return <Clock className="h-5 w-5 text-muted-foreground" />;
    case 'running':
      return <Loader2 className="h-5 w-5 animate-spin text-primary" />;
    case 'completed':
      return <CheckCircle className="h-5 w-5 text-success" />;
    case 'failed':
      return <XCircle className="h-5 w-5 text-error" />;
    case 'cancelled':
      return <Ban className="h-5 w-5 text-warning" />;
    default:
      return <AlertCircle className="h-5 w-5 text-muted-foreground" />;
  }
}

function statusBadgeVariant(
  status: ResearchRunStatus
): 'default' | 'secondary' | 'success' | 'destructive' | 'warning' {
  switch (status) {
    case 'queued':
      return 'secondary';
    case 'running':
      return 'default';
    case 'completed':
      return 'success';
    case 'failed':
      return 'destructive';
    case 'cancelled':
      return 'warning';
    default:
      return 'secondary';
  }
}

function formatTimestamp(isoString: string | undefined): string {
  if (!isoString) {
    return '-';
  }
  const date = new Date(isoString);
  return date.toLocaleTimeString();
}

function formatDuration(start?: string, end?: string): string {
  if (!start) {
    return '-';
  }
  const startTime = new Date(start).getTime();
  const endTime = end ? new Date(end).getTime() : Date.now();
  const durationMs = endTime - startTime;

  if (durationMs < 1000) {
    return `${durationMs}ms`;
  }
  if (durationMs < 60000) {
    return `${Math.round(durationMs / 1000)}s`;
  }
  return `${Math.round(durationMs / 60000)}m`;
}

function isActiveStatus(status: ResearchRunStatus): boolean {
  return status === 'queued' || status === 'running';
}

function DetailItem({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-xl border border-border/70 bg-muted/20 px-3 py-2">
      <p className="text-[11px] font-semibold uppercase tracking-[0.2em] text-muted-foreground">
        {label}
      </p>
      <p className="mt-1 text-sm font-medium text-foreground">{value}</p>
    </div>
  );
}

export function RunStatusSummary({
  runId,
  onSessionIdResolved,
  onStatusChange,
  onStatusLoaded,
}: RunStatusSummaryProps) {
  const [status, setStatus] = useState<ResearchRunStatusResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [stopError, setStopError] = useState<string | null>(null);
  const [stopping, setStopping] = useState(false);

  useEffect(() => {
    let mounted = true;
    let intervalId: NodeJS.Timeout | null = null;

    const fetchStatus = async () => {
      try {
        const response = await getResearchRunStatus(runId);
        if (!mounted) {
          return;
        }

        setStatus(response);
        setError(null);

        if (onStatusChange) {
          onStatusChange(response.status);
        }
        if (response.session_id && onSessionIdResolved) {
          onSessionIdResolved(response.session_id);
        }
        if (onStatusLoaded) {
          onStatusLoaded(response);
        }
        if (!isActiveStatus(response.status)) {
          setStopping(false);
        }
        if (!isActiveStatus(response.status) && intervalId) {
          clearInterval(intervalId);
        }
      } catch (requestError) {
        if (!mounted) {
          return;
        }
        setError(getApiErrorMessage(requestError, 'Failed to fetch status'));
      }
    };

    void fetchStatus();
    intervalId = setInterval(fetchStatus, 2000);

    return () => {
      mounted = false;
      if (intervalId) {
        clearInterval(intervalId);
      }
    };
  }, [runId, onSessionIdResolved, onStatusChange, onStatusLoaded]);

  const handleStop = async () => {
    setStopError(null);
    setStopping(true);

    try {
      const response = await stopResearchRun(runId);
      setStatus((current) =>
        current
          ? {
              ...current,
              status: response.status,
              stop_requested: response.stop_requested,
              session_id: response.session_id ?? current.session_id,
            }
          : null
      );
      if (response.status === 'cancelled') {
        setStopping(false);
      }
    } catch (requestError) {
      setStopError(getApiErrorMessage(requestError, 'Failed to stop run'));
      setStopping(false);
    }
  };

  if (error) {
    return (
      <Card className="shadow-sm">
        <CardContent className="p-4">
          <Alert className="flex items-start gap-3" variant="destructive">
            <AlertCircle className="mt-0.5 h-5 w-5 shrink-0" />
            <div className="space-y-1">
              <AlertTitle>Failed to load run status</AlertTitle>
              <AlertDescription>{error}</AlertDescription>
            </div>
          </Alert>
        </CardContent>
      </Card>
    );
  }

  if (!status) {
    return (
      <Card className="shadow-sm">
        <CardContent className="p-4">
          <Alert className="flex items-center gap-3" variant="default">
            <Loader2 className="h-5 w-5 animate-spin text-muted-foreground" />
            <AlertDescription>Loading run status...</AlertDescription>
          </Alert>
        </CardContent>
      </Card>
    );
  }

  const stopRequested = status.stop_requested === true;
  const showStopAction = isActiveStatus(status.status);

  return (
    <Card className="overflow-hidden border-slate-200/80 shadow-sm">
      <CardHeader className="gap-4 border-b bg-[linear-gradient(135deg,rgba(15,23,42,0.04),rgba(56,189,248,0.10))]">
        <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
          <div className="space-y-2">
            <div className="flex flex-wrap items-center gap-2">
              <CardTitle className="flex items-center gap-2">
                {statusIcon(status.status)}
                Run Status
              </CardTitle>
              <Badge variant={statusBadgeVariant(status.status)}>{status.status}</Badge>
              {stopRequested && isActiveStatus(status.status) ? (
                <Badge variant="warning">Stop Requested</Badge>
              ) : null}
            </div>
            <p className="text-sm text-muted-foreground">
              Run <span className="font-mono text-xs text-foreground">{status.run_id}</span>
              {status.session_id ? (
                <>
                  {' '}
                  is attached to session{' '}
                  <span className="font-mono text-xs text-foreground">{status.session_id}</span>.
                </>
              ) : (
                '. Waiting for session allocation.'
              )}
            </p>
          </div>

          <div className="flex flex-col gap-3 lg:items-end">
            {showStopAction ? (
              <Button
                type="button"
                variant="outline"
                onClick={handleStop}
                disabled={stopping || stopRequested}
              >
                {stopping || stopRequested ? (
                  <>
                    <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                    Stopping...
                  </>
                ) : (
                  <>
                    <Square className="mr-2 h-4 w-4" />
                    Stop Run
                  </>
                )}
              </Button>
            ) : null}
          </div>
        </div>
      </CardHeader>

      <CardContent className="space-y-4 p-5">
        <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-4">
          <DetailItem label="Run ID" value={status.run_id} />
          <DetailItem label="Session" value={status.session_id ?? 'Pending'} />
          <DetailItem
            label="Duration"
            value={status.started_at ? formatDuration(status.started_at, status.completed_at) : '-'}
          />
          <DetailItem
            label="Completed"
            value={status.completed_at ? formatTimestamp(status.completed_at) : 'In progress'}
          />
        </div>

        {stopRequested && isActiveStatus(status.status) ? (
          <Alert className="flex items-start gap-3" variant="warning">
            <Clock className="mt-0.5 h-5 w-5 shrink-0" />
            <div className="space-y-1">
              <AlertTitle>Stop requested</AlertTitle>
              <AlertDescription>
                Waiting for the backend to confirm cancellation and close the session cleanly.
              </AlertDescription>
            </div>
          </Alert>
        ) : null}

        {stopError ? (
          <Alert className="flex items-start gap-3" variant="destructive">
            <AlertCircle className="mt-0.5 h-5 w-5 shrink-0" />
            <div className="space-y-1">
              <AlertTitle>Stop failed</AlertTitle>
              <AlertDescription>{stopError}</AlertDescription>
            </div>
          </Alert>
        ) : null}

        {status.error && status.status !== 'cancelled' ? (
          <Alert className="flex items-start gap-3" variant="destructive">
            <AlertCircle className="mt-0.5 h-5 w-5 shrink-0" />
            <div className="space-y-1">
              <AlertTitle>Run error</AlertTitle>
              <AlertDescription>{status.error}</AlertDescription>
            </div>
          </Alert>
        ) : null}

        {status.status === 'cancelled' ? (
          <Alert className="flex items-start gap-3" variant="warning">
            <Ban className="mt-0.5 h-5 w-5 shrink-0" />
            <div className="space-y-1">
              <AlertTitle>Run cancelled</AlertTitle>
              <AlertDescription>
                {status.error ||
                  'The in-progress run was stopped. Historical session artifacts remain available for follow-on actions.'}
              </AlertDescription>
            </div>
          </Alert>
        ) : null}

        {status.result ? (
          <Alert className="flex items-start gap-3" variant="success">
            <CheckCircle className="mt-0.5 h-5 w-5 shrink-0" />
            <div className="space-y-1">
              <AlertTitle>Result available</AlertTitle>
              <AlertDescription>
                Session ID: {status.result.session_id}
                <br />
                Report: {status.result.report_path ?? 'Generated in memory'}
              </AlertDescription>
            </div>
          </Alert>
        ) : null}
      </CardContent>
    </Card>
  );
}
