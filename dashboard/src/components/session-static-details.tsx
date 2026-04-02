'use client';

import { Activity, CalendarClock, Clock3, FileText, HardDrive, Search } from 'lucide-react';

import { Badge } from '@/components/ui/badge';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { runStatusBadgeVariant } from '@/lib/session-route';
import type { ResearchRunStatus, Session } from '@/types/telemetry';

interface SessionStaticDetailsProps {
  sessionId: string;
  runStatus: ResearchRunStatus | null;
  sessionSummary: Session | null;
}

function formatTimestamp(value: string | null): string {
  if (!value) {
    return 'Unknown';
  }

  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? value : date.toLocaleString();
}

function formatDuration(totalTimeMs: number | null): string {
  if (totalTimeMs == null) {
    return 'Unknown';
  }

  if (totalTimeMs < 1000) {
    return `${totalTimeMs} ms`;
  }

  if (totalTimeMs < 60000) {
    return `${(totalTimeMs / 1000).toFixed(1)} s`;
  }

  return `${(totalTimeMs / 60000).toFixed(1)} min`;
}

function formatDepth(depth: string | null): string {
  if (!depth) {
    return 'Unknown';
  }

  return depth.charAt(0).toUpperCase() + depth.slice(1);
}

function MetricCard({
  title,
  value,
  icon: Icon,
}: {
  title: string;
  value: string | number;
  icon: typeof Activity;
}) {
  return (
    <Card className="border-slate-200/80 shadow-sm">
      <CardContent className="flex items-center gap-3 p-4">
        <div className="rounded-xl bg-slate-100 p-2 text-slate-700">
          <Icon className="h-4 w-4" />
        </div>
        <div>
          <p className="text-xs uppercase tracking-wide text-muted-foreground">{title}</p>
          <p className="text-lg font-semibold text-slate-900">{value}</p>
        </div>
      </CardContent>
    </Card>
  );
}

function DetailRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-start justify-between gap-4 border-b border-slate-100 py-3 last:border-b-0 last:pb-0 first:pt-0">
      <span className="text-sm text-muted-foreground">{label}</span>
      <span className="text-right text-sm font-medium text-slate-900">{value}</span>
    </div>
  );
}

export function SessionStaticDetails({
  sessionId,
  runStatus,
  sessionSummary,
}: SessionStaticDetailsProps) {
  return (
    <div className="space-y-6">
      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
        <MetricCard
          title="Status"
          value={runStatus ?? sessionSummary?.status ?? 'loading'}
          icon={Activity}
        />
        <MetricCard
          title="Sources"
          value={sessionSummary?.totalSources ?? 0}
          icon={Search}
        />
        <MetricCard
          title="Events"
          value={sessionSummary?.eventCount ?? 0}
          icon={Clock3}
        />
        <MetricCard
          title="Duration"
          value={formatDuration(sessionSummary?.totalTimeMs ?? null)}
          icon={CalendarClock}
        />
      </div>

      <div className="grid gap-6 xl:grid-cols-[minmax(0,1.35fr)_360px]">
        <Card className="border-slate-200/80 shadow-sm">
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Search className="h-5 w-5 text-sky-700" />
              Session Summary
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="space-y-2">
              <div className="flex flex-wrap items-center gap-2">
                <h2 className="text-2xl font-semibold tracking-tight text-slate-900">
                  {sessionSummary?.label ?? sessionId}
                </h2>
                <Badge variant={runStatusBadgeVariant(runStatus)}>{runStatus ?? 'loading'}</Badge>
                {sessionSummary?.active ? <Badge variant="info">Live</Badge> : null}
                {sessionSummary?.archived ? <Badge variant="warning">Archived</Badge> : null}
              </div>
              <p className="text-xs font-mono text-muted-foreground">{sessionId}</p>
            </div>

            <div className="rounded-2xl border border-slate-200 bg-slate-50/80 p-4">
              <p className="text-xs uppercase tracking-wide text-muted-foreground">Query</p>
              <p className="mt-2 whitespace-pre-wrap text-sm leading-6 text-slate-900">
                {sessionSummary?.query ?? 'No query metadata was captured for this session.'}
              </p>
            </div>

            <div className="grid gap-4 md:grid-cols-2">
              <div className="rounded-2xl border border-slate-200 p-4">
                <p className="text-xs uppercase tracking-wide text-muted-foreground">Execution</p>
                <div className="mt-3 space-y-1.5 text-sm text-slate-900">
                  <p>Depth: {formatDepth(sessionSummary?.depth ?? null)}</p>
                  <p>Created: {formatTimestamp(sessionSummary?.createdAt ?? null)}</p>
                  <p>Last event: {formatTimestamp(sessionSummary?.lastEventAt ?? null)}</p>
                  <p>Completed: {formatTimestamp(sessionSummary?.completedAt ?? null)}</p>
                </div>
              </div>

              <div className="rounded-2xl border border-slate-200 p-4">
                <p className="text-xs uppercase tracking-wide text-muted-foreground">Artifacts</p>
                <div className="mt-3 flex flex-wrap gap-2">
                  <Badge variant={sessionSummary?.hasSessionPayload ? 'success' : 'secondary'}>
                    Payload {sessionSummary?.hasSessionPayload ? 'available' : 'missing'}
                  </Badge>
                  <Badge variant={sessionSummary?.hasReport ? 'success' : 'secondary'}>
                    Report {sessionSummary?.hasReport ? 'available' : 'unavailable'}
                  </Badge>
                </div>
              </div>
            </div>
          </CardContent>
        </Card>

        <Card className="border-slate-200/80 shadow-sm">
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <HardDrive className="h-5 w-5 text-slate-700" />
              Session Facts
            </CardTitle>
          </CardHeader>
          <CardContent>
            <DetailRow label="Session ID" value={sessionId} />
            <DetailRow label="Label" value={sessionSummary?.label ?? 'Unknown'} />
            <DetailRow label="Status" value={runStatus ?? sessionSummary?.status ?? 'loading'} />
            <DetailRow label="Sources" value={String(sessionSummary?.totalSources ?? 0)} />
            <DetailRow label="Events" value={String(sessionSummary?.eventCount ?? 0)} />
            <DetailRow
              label="Report"
              value={sessionSummary?.hasReport ? 'Available' : 'Unavailable'}
            />
            <DetailRow
              label="Payload"
              value={sessionSummary?.hasSessionPayload ? 'Available' : 'Missing'}
            />
            <DetailRow
              label="Runtime"
              value={formatDuration(sessionSummary?.totalTimeMs ?? null)}
            />
            <DetailRow
              label="Archived"
              value={sessionSummary?.archived ? 'Yes' : 'No'}
            />
          </CardContent>
        </Card>
      </div>

      {!sessionSummary?.hasReport ? (
        <Card className="border-dashed border-slate-300/90 shadow-sm">
          <CardContent className="flex items-start gap-3 p-5">
            <FileText className="mt-0.5 h-5 w-5 text-slate-500" />
            <div className="space-y-1">
              <p className="text-sm font-medium text-slate-900">Report route is conditional</p>
              <p className="text-sm text-muted-foreground">
                Open <span className="font-mono">/session/{sessionId}/report</span> after the run
                completes and a report artifact is available.
              </p>
            </div>
          </CardContent>
        </Card>
      ) : null}
    </div>
  );
}
