'use client';

import Link from 'next/link';
import { ArrowRight, Archive, CheckCircle2, Clock3, Database, FileText, Home, Radar, Search, XCircle } from 'lucide-react';

import { Badge } from '@/components/ui/badge';
import { Button, buttonVariants } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import type { ResearchRunStatus, Session } from '@/types/telemetry';

interface SessionOverviewProps {
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
    return 'Standard';
  }

  return depth.charAt(0).toUpperCase() + depth.slice(1);
}

function StatusIndicator({ status }: { status: ResearchRunStatus | null }) {
  const statusConfig: Record<string, { icon: typeof CheckCircle2; label: string; description: string }> = {
    running: {
      icon: Radar,
      label: 'Running',
      description: 'Research is actively collecting sources and analyzing findings.',
    },
    completed: {
      icon: CheckCircle2,
      label: 'Completed',
      description: 'Research finished successfully. A report is available.',
    },
    failed: {
      icon: XCircle,
      label: 'Failed',
      description: 'Research encountered an error and could not complete.',
    },
    cancelled: {
      icon: XCircle,
      label: 'Cancelled',
      description: 'Research was stopped before completion.',
    },
    queued: {
      icon: Clock3,
      label: 'Queued',
      description: 'Research is waiting to start.',
    },
  };

  const config = statusConfig[status ?? ''];
  const Icon = config?.icon ?? Clock3;

  return (
    <div className="flex items-start gap-3 rounded-2xl border border-border bg-surface-raised p-4">
      <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-background">
        <Icon className="h-5 w-5 text-foreground" />
      </div>
      <div className="space-y-1">
        <p className="font-medium text-foreground">{config?.label ?? 'Loading...'}</p>
        <p className="text-sm text-muted-foreground">{config?.description ?? 'Loading session status...'}</p>
      </div>
    </div>
  );
}

function QueryDisplay({ query }: { query: string | null }) {
  if (!query) {
    return (
      <div className="rounded-2xl border border-dashed border-border p-6 text-center">
        <p className="text-sm text-muted-foreground">No query was captured for this session.</p>
      </div>
    );
  }

  const displayQuery = query.length > 500 ? query.slice(0, 500) + '...' : query;
  const isTruncated = query.length > 500;

  return (
    <div className="space-y-2">
      <p className="text-xs uppercase tracking-wide text-muted-foreground">Research query</p>
      <div className="rounded-2xl border border-border bg-surface-raised p-4">
        <p className="whitespace-pre-wrap text-sm leading-relaxed text-foreground">{displayQuery}</p>
        {isTruncated && (
          <p className="mt-2 text-xs text-muted-foreground">
            Query truncated. View full query in technical details below.
          </p>
        )}
      </div>
    </div>
  );
}

function SessionIdentity({
  label,
  sessionId,
}: {
  label: string | null;
  sessionId: string;
}) {
  return (
    <div className="space-y-3 rounded-2xl border border-border bg-surface-raised p-5">
      <div className="flex flex-wrap items-center gap-2">
        <Badge variant="outline">Session brief</Badge>
        <span className="font-mono text-[0.72rem] uppercase tracking-[0.14em] text-muted-foreground">
          {sessionId.slice(0, 8)}
        </span>
      </div>
      <div className="space-y-1">
        <p className="text-[1.2rem] font-semibold leading-tight text-foreground">
          {label ?? 'Untitled session'}
        </p>
        <p className="text-sm leading-6 text-muted-foreground">
          Primary operator summary for this run before drilling into telemetry, artifacts, or
          technical details.
        </p>
      </div>
    </div>
  );
}

function ActivitySnapshot({ session }: { session: Session | null }) {
  return (
    <div className="grid gap-3 md:grid-cols-3">
      <div className="rounded-2xl border border-border bg-surface-raised p-4">
        <div className="flex items-center gap-2">
          <Search className="h-4 w-4 text-muted-foreground" />
          <p className="text-xs uppercase tracking-wide text-muted-foreground">Sources</p>
        </div>
        <p className="mt-2 text-2xl font-semibold tabular-nums text-foreground">{session?.totalSources ?? 0}</p>
      </div>

      <div className="rounded-2xl border border-border bg-surface-raised p-4">
        <div className="flex items-center gap-2">
          <Clock3 className="h-4 w-4 text-muted-foreground" />
          <p className="text-xs uppercase tracking-wide text-muted-foreground">Events</p>
        </div>
        <p className="mt-2 text-2xl font-semibold tabular-nums text-foreground">{session?.eventCount ?? 0}</p>
      </div>

      <div className="rounded-2xl border border-border bg-surface-raised p-4">
        <div className="flex items-center gap-2">
          <Clock3 className="h-4 w-4 text-muted-foreground" />
          <p className="text-xs uppercase tracking-wide text-muted-foreground">Duration</p>
        </div>
        <p className="mt-2 text-2xl font-semibold tabular-nums text-foreground">
          {formatDuration(session?.totalTimeMs ?? null)}
        </p>
      </div>
    </div>
  );
}

function ArtifactsSection({
  session,
  sessionId,
  runStatus,
}: {
  session: Session | null;
  sessionId: string;
  runStatus: ResearchRunStatus | null;
}) {
  const hasReport = session?.hasReport ?? false;
  const hasPayload = session?.hasSessionPayload ?? false;
  const isActive = session?.active ?? runStatus === 'running';
  const isArchived = session?.archived ?? false;

  return (
    <div className="space-y-3">
      <p className="text-xs uppercase tracking-wide text-muted-foreground">Artifacts</p>
      <div className="flex flex-wrap gap-2">
        {hasReport ? (
          <Link
            href={`/session/${sessionId}/report`}
            className={buttonVariants({
              variant: 'outline',
              size: 'sm',
            })}
          >
            <FileText className="mr-2 h-4 w-4" />
            View Report
            <ArrowRight className="ml-2 h-3 w-3" />
          </Link>
        ) : isActive ? (
          <Badge variant="secondary">Report pending</Badge>
        ) : (
          <Badge variant="outline">No report available</Badge>
        )}

        {hasPayload ? (
          <Badge variant="success">
            <Database className="mr-1 h-3 w-3" />
            Payload saved
          </Badge>
        ) : (
          <Badge variant="secondary">No payload</Badge>
        )}

        {isArchived ? (
          <Badge variant="warning">
            <Archive className="mr-1 h-3 w-3" />
            Archived
          </Badge>
        ) : null}
      </div>
    </div>
  );
}

function TechnicalFacts({
  sessionId,
  session,
}: {
  sessionId: string;
  session: Session | null;
}) {
  return (
    <div className="space-y-3">
      <p className="text-xs uppercase tracking-wide text-muted-foreground">Technical details</p>
      <dl className="grid gap-2 text-sm">
        <div className="flex justify-between">
          <dt className="text-muted-foreground">Session ID</dt>
          <dd className="font-mono text-foreground">{sessionId.slice(0, 8)}</dd>
        </div>
        <div className="flex justify-between">
          <dt className="text-muted-foreground">Depth</dt>
          <dd className="text-foreground">{formatDepth(session?.depth ?? null)}</dd>
        </div>
        <div className="flex justify-between">
          <dt className="text-muted-foreground">Created</dt>
          <dd className="text-foreground">{formatTimestamp(session?.createdAt ?? null)}</dd>
        </div>
        <div className="flex justify-between">
          <dt className="text-muted-foreground">Completed</dt>
          <dd className="text-foreground">{formatTimestamp(session?.completedAt ?? null)}</dd>
        </div>
        {session?.query && session.query.length > 500 && (
          <div className="mt-2 border-t border-border pt-2">
            <dt className="mb-1 text-muted-foreground">Full query</dt>
            <dd className="max-h-32 overflow-y-auto rounded-lg bg-surface-raised p-2 text-xs font-mono text-foreground">
              {session.query}
            </dd>
          </div>
        )}
      </dl>
    </div>
  );
}

function NextActions({
  sessionId,
  runStatus,
  hasReport,
  isArchived,
}: {
  sessionId: string;
  runStatus: ResearchRunStatus | null;
  hasReport: boolean;
  isArchived: boolean;
}) {
  const isActive = runStatus === 'running';
  const isTerminal = runStatus === 'completed' || runStatus === 'failed' || runStatus === 'cancelled';

  return (
    <div className="space-y-3">
      <p className="text-xs uppercase tracking-wide text-muted-foreground">What to do next</p>
      <div className="flex flex-col gap-2">
        {isActive && (
          <Link href={`/session/${sessionId}/monitor`}>
            <Button variant="outline" size="sm" className="w-full justify-start">
              <Radar className="mr-2 h-4 w-4" />
              Inspect live telemetry
              <ArrowRight className="ml-auto h-3 w-3" />
            </Button>
          </Link>
        )}

        {hasReport && (
          <Link href={`/session/${sessionId}/report`}>
            <Button variant="outline" size="sm" className="w-full justify-start">
              <FileText className="mr-2 h-4 w-4" />
              Open research report
              <ArrowRight className="ml-auto h-3 w-3" />
            </Button>
          </Link>
        )}

        {isTerminal && !isArchived && (
          <Link href="/">
            <Button variant="default" size="sm" className="w-full justify-start">
              <Home className="mr-2 h-4 w-4" />
              Return to control room
              <ArrowRight className="ml-auto h-3 w-3" />
            </Button>
          </Link>
        )}
      </div>
    </div>
  );
}

export function SessionOverview({ sessionId, runStatus, sessionSummary }: SessionOverviewProps) {
  return (
    <div className="grid gap-6 xl:grid-cols-[1fr_280px]">
      <div className="space-y-6">
        <StatusIndicator status={runStatus} />
        <SessionIdentity label={sessionSummary?.label ?? null} sessionId={sessionId} />

        <QueryDisplay query={sessionSummary?.query ?? null} />

        <ActivitySnapshot session={sessionSummary} />

        <div className="grid gap-6 md:grid-cols-2">
          <ArtifactsSection
            session={sessionSummary}
            sessionId={sessionId}
            runStatus={runStatus}
          />
          <TechnicalFacts sessionId={sessionId} session={sessionSummary} />
        </div>
      </div>

      <aside className="space-y-6 xl:sticky xl:top-6 xl:self-start">
        <Card className="xl:rounded-2xl">
          <CardHeader className="pb-3">
            <CardTitle className="text-base">Next Actions</CardTitle>
          </CardHeader>
          <CardContent>
            <NextActions
              sessionId={sessionId}
              runStatus={runStatus}
              hasReport={sessionSummary?.hasReport ?? false}
              isArchived={sessionSummary?.archived ?? false}
            />
          </CardContent>
        </Card>
      </aside>
    </div>
  );
}
