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

import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card, CardContent } from '@/components/ui/card';
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
      return <Clock className="h-5 w-5 text-gray-500" />;
    case 'running':
      return <Loader2 className="h-5 w-5 animate-spin text-blue-500" />;
    case 'completed':
      return <CheckCircle className="h-5 w-5 text-green-500" />;
    case 'failed':
      return <XCircle className="h-5 w-5 text-red-500" />;
    case 'cancelled':
      return <Ban className="h-5 w-5 text-amber-500" />;
    default:
      return <AlertCircle className="h-5 w-5 text-gray-500" />;
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
      <Card className="border-red-200 bg-red-50">
        <CardContent className="p-4">
          <div className="flex items-center gap-3">
            <AlertCircle className="h-5 w-5 text-red-500" />
            <div>
              <p className="font-medium text-red-800">Failed to load run status</p>
              <p className="text-sm text-red-600">{error}</p>
            </div>
          </div>
        </CardContent>
      </Card>
    );
  }

  if (!status) {
    return (
      <Card>
        <CardContent className="p-4">
          <div className="flex items-center gap-3">
            <Loader2 className="h-5 w-5 animate-spin text-gray-400" />
            <span className="text-muted-foreground">Loading run status...</span>
          </div>
        </CardContent>
      </Card>
    );
  }

  const stopRequested = status.stop_requested === true;
  const showStopAction = isActiveStatus(status.status);

  return (
    <Card>
      <CardContent className="space-y-4 p-4">
        <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
          <div className="flex items-center gap-3">
            {statusIcon(status.status)}
            <div>
              <div className="flex items-center gap-2">
                <span className="font-medium capitalize">{status.status}</span>
                <Badge variant={statusBadgeVariant(status.status)}>{status.status}</Badge>
              </div>
              <p className="text-sm text-muted-foreground">
                Run ID: <code className="text-xs">{status.run_id}</code>
              </p>
            </div>
          </div>

          <div className="flex flex-col gap-3 lg:items-end">
            <div className="text-sm lg:text-right">
              {status.session_id ? (
                <p>
                  <span className="text-muted-foreground">Session: </span>
                  <code className="text-xs">{status.session_id}</code>
                </p>
              ) : null}
              {status.started_at ? (
                <p>
                  <span className="text-muted-foreground">Duration: </span>
                  {formatDuration(status.started_at, status.completed_at)}
                </p>
              ) : null}
              {status.completed_at ? (
                <p>
                  <span className="text-muted-foreground">Completed: </span>
                  {formatTimestamp(status.completed_at)}
                </p>
              ) : null}
            </div>

            {showStopAction ? (
              <Button type="button" variant="outline" onClick={handleStop} disabled={stopping || stopRequested}>
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

        {stopRequested && isActiveStatus(status.status) ? (
          <div className="rounded-md border border-amber-200 bg-amber-50 p-3">
            <p className="text-sm font-medium text-amber-800">Stop requested</p>
            <p className="text-sm text-amber-700">
              Waiting for the backend to confirm cancellation and close the session cleanly.
            </p>
          </div>
        ) : null}

        {stopError ? (
          <div className="rounded-md border border-red-200 bg-red-50 p-3">
            <p className="text-sm font-medium text-red-800">Stop failed</p>
            <p className="text-sm text-red-600">{stopError}</p>
          </div>
        ) : null}

        {status.error && status.status !== 'cancelled' ? (
          <div className="rounded-md border border-red-200 bg-red-50 p-3">
            <p className="text-sm font-medium text-red-800">Error</p>
            <p className="text-sm text-red-600">{status.error}</p>
          </div>
        ) : null}

        {status.status === 'cancelled' ? (
          <div className="rounded-md border border-amber-200 bg-amber-50 p-3">
            <p className="text-sm font-medium text-amber-800">Run cancelled</p>
            <p className="text-sm text-amber-700">
              {status.error ||
                'The in-progress run was stopped. Historical session artifacts remain available for follow-on actions.'}
            </p>
          </div>
        ) : null}

        {status.result ? (
          <div className="rounded-md border border-green-200 bg-green-50 p-3">
            <p className="text-sm font-medium text-green-800">Result</p>
            <p className="text-sm text-green-600">Session ID: {status.result.session_id}</p>
            <p className="text-sm text-green-600">
              Report: {status.result.report_path ?? 'Generated in memory'}
            </p>
          </div>
        ) : null}
      </CardContent>
    </Card>
  );
}
