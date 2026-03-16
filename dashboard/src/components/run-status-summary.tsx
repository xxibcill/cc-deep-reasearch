'use client';

import { useEffect, useState } from 'react';
import { AlertCircle, CheckCircle, Clock, Loader2, XCircle } from 'lucide-react';

import { Badge } from '@/components/ui/badge';
import { Card, CardContent } from '@/components/ui/card';
import { getResearchRunStatus } from '@/lib/api';
import type { ResearchRunStatusResponse, ResearchRunStatus } from '@/types/telemetry';

interface RunStatusSummaryProps {
  runId: string;
  onSessionIdResolved?: (sessionId: string) => void;
  onStatusChange?: (status: ResearchRunStatus) => void;
}

function statusIcon(status: ResearchRunStatus) {
  switch (status) {
    case 'queued':
      return <Clock className="h-5 w-5 text-gray-500" />;
    case 'running':
      return <Loader2 className="h-5 w-5 text-blue-500 animate-spin" />;
    case 'completed':
      return <CheckCircle className="h-5 w-5 text-green-500" />;
    case 'failed':
      return <XCircle className="h-5 w-5 text-red-500" />;
    default:
      return <AlertCircle className="h-5 w-5 text-gray-500" />;
  }
}

function statusBadgeVariant(status: ResearchRunStatus): 'default' | 'secondary' | 'success' | 'destructive' {
  switch (status) {
    case 'queued':
      return 'secondary';
    case 'running':
      return 'default';
    case 'completed':
      return 'success';
    case 'failed':
      return 'destructive';
    default:
      return 'secondary';
  }
}

function formatTimestamp(isoString: string | undefined): string {
  if (!isoString) return '-';
  const date = new Date(isoString);
  return date.toLocaleTimeString();
}

function formatDuration(start?: string, end?: string): string {
  if (!start) return '-';
  const startTime = new Date(start).getTime();
  const endTime = end ? new Date(end).getTime() : Date.now();
  const durationMs = endTime - startTime;

  if (durationMs < 1000) return `${durationMs}ms`;
  if (durationMs < 60000) return `${Math.round(durationMs / 1000)}s`;
  return `${Math.round(durationMs / 60000)}m`;
}

export function RunStatusSummary({ runId, onSessionIdResolved, onStatusChange }: RunStatusSummaryProps) {
  const [status, setStatus] = useState<ResearchRunStatusResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let mounted = true;
    let intervalId: NodeJS.Timeout | null = null;

    const fetchStatus = async () => {
      try {
        const response = await getResearchRunStatus(runId);
        if (!mounted) return;
        setStatus(response);
        setError(null);

        // Notify parent of status changes
        if (onStatusChange) {
          onStatusChange(response.status);
        }

        // Notify parent when session ID is resolved
        if (response.session_id && onSessionIdResolved) {
          onSessionIdResolved(response.session_id);
        }

        // Stop polling if run is no longer active
        if (response.status !== 'queued' && response.status !== 'running') {
          if (intervalId) clearInterval(intervalId);
        }
      } catch (err) {
        if (!mounted) return;
        setError(err instanceof Error ? err.message : 'Failed to fetch status');
      }
    };

    void fetchStatus();

    // Poll every 2 seconds while run is active
    intervalId = setInterval(fetchStatus, 2000);

    return () => {
      mounted = false;
      if (intervalId) clearInterval(intervalId);
    };
  }, [runId, onSessionIdResolved, onStatusChange]);

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

  return (
    <Card>
      <CardContent className="p-4">
        <div className="flex items-center justify-between">
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

          <div className="text-right text-sm">
            {status.session_id && (
              <p>
                <span className="text-muted-foreground">Session: </span>
                <code className="text-xs">{status.session_id}</code>
              </p>
            )}
            {status.started_at && (
              <p>
                <span className="text-muted-foreground">Duration: </span>
                {formatDuration(status.started_at, status.completed_at)}
              </p>
            )}
            {status.completed_at && (
              <p>
                <span className="text-muted-foreground">Completed: </span>
                {formatTimestamp(status.completed_at)}
              </p>
            )}
          </div>
        </div>

        {status.error && (
          <div className="mt-4 rounded-md bg-red-50 border border-red-200 p-3">
            <p className="text-sm font-medium text-red-800">Error</p>
            <p className="text-sm text-red-600">{status.error}</p>
          </div>
        )}

        {status.result && (
          <div className="mt-4 rounded-md bg-green-50 border border-green-200 p-3">
            <p className="text-sm font-medium text-green-800">Result</p>
            <p className="text-sm text-green-600">
              Session ID: {status.result.session_id}
            </p>
            <p className="text-sm text-green-600">
              Report: {status.result.report_path ?? 'Generated in memory'}
            </p>
          </div>
        )}
      </CardContent>
    </Card>
  );
}
