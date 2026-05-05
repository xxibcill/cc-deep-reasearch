'use client';

import Link from 'next/link';
import { useEffect, useState } from 'react';
import {
  AlertCircle,
  Archive,
  ArrowRight,
  CheckCircle2,
  Clock3,
  Database,
  FileText,
  GitCompare,
  Home,
  Pencil,
  Plus,
  Radar,
  Search,
  StickyNote,
  Trash2,
  XCircle,
} from 'lucide-react';

import {
  addSessionAnnotation,
  deleteSessionAnnotation,
  getSessionAnnotations,
  getSessionTriage,
  type SessionAnnotation as SessionAnnotationType,
  updateSessionTriage,
} from '@/lib/api';
import { ArtifactExplorer } from '@/components/artifact-explorer';
import { ResearchContentActions } from '@/components/research-content-actions';
import { Badge } from '@/components/ui/badge';
import { Button, buttonVariants } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { MetricCard } from '@/components/ui/metric-card';
import { Textarea } from '@/components/ui/textarea';
import { buildResearchContentBridgePayloadFromSession } from '@/lib/research-content-bridge';
import { useNotifications } from '@/components/ui/notification-center';
import type { ResearchRunStatus, Session, TriageStatus } from '@/types/telemetry';

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
      <MetricCard compact icon={Search} label="Sources" value={session?.totalSources ?? 0} />
      <MetricCard compact icon={Clock3} label="Events" value={session?.eventCount ?? 0} />
      <MetricCard
        compact
        icon={Clock3}
        label="Duration"
        value={formatDuration(session?.totalTimeMs ?? null)}
      />
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
  const isFailedOrInterrupted = runStatus === 'failed' || runStatus === 'cancelled' || runStatus === 'interrupted';

  return (
    <div className="space-y-3">
      <p className="text-xs uppercase tracking-wide text-muted-foreground">What to do next</p>
      <div className="flex flex-col gap-2">
        {isActive && (
          <Link
            href={`/session/${sessionId}/monitor`}
            className={buttonVariants({ variant: 'outline', size: 'sm', className: 'w-full justify-start' })}
          >
            <Radar className="mr-2 h-4 w-4" />
            Inspect live telemetry
            <ArrowRight className="ml-auto h-3 w-3" />
          </Link>
        )}

        {isFailedOrInterrupted && (
          <Link
            href={`/compare?b=${sessionId}`}
            className={buttonVariants({ variant: 'outline', size: 'sm', className: 'w-full justify-start' })}
          >
            <GitCompare className="mr-2 h-4 w-4" />
            Compare as target against baseline
            <ArrowRight className="ml-auto h-3 w-3" />
          </Link>
        )}

        {hasReport && (
          <Link
            href={`/session/${sessionId}/report`}
            className={buttonVariants({ variant: 'outline', size: 'sm', className: 'w-full justify-start' })}
          >
            <FileText className="mr-2 h-4 w-4" />
            Open research report
            <ArrowRight className="ml-auto h-3 w-3" />
          </Link>
        )}

        {isTerminal && !isArchived && (
          <Link
            href="/"
            className={buttonVariants({ variant: 'default', size: 'sm', className: 'w-full justify-start' })}
          >
            <Home className="mr-2 h-4 w-4" />
            Return to control room
            <ArrowRight className="ml-auto h-3 w-3" />
          </Link>
        )}
      </div>
    </div>
  );
}

function ContentStudioHandoff({
  sessionId,
  runStatus,
  session,
}: {
  sessionId: string;
  runStatus: ResearchRunStatus | null;
  session: Session | null;
}) {
  const bridgePayload = buildResearchContentBridgePayloadFromSession(
    sessionId,
    session,
    'session-overview'
  );
  const readyForContent = runStatus === 'completed' && Boolean(session?.hasReport);

  return (
    <Card className="xl:rounded-2xl">
      <CardHeader className="pb-3">
        <CardTitle className="text-base">Content Studio Handoff</CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="space-y-2">
          <div className="flex flex-wrap items-center gap-2">
            <Badge variant={readyForContent ? 'success' : 'secondary'}>
              {readyForContent ? 'Report-ready source' : 'Research still upstream'}
            </Badge>
            <Badge variant="outline" className="font-mono text-[0.7rem]">
              {sessionId.slice(0, 8)}
            </Badge>
          </div>
          <p className="text-sm leading-6 text-muted-foreground">
            {readyForContent
              ? 'Carry this session into a pipeline or quick script without losing the research context.'
              : 'Finish the research run and generate a report before sending it into downstream content workflows.'}
          </p>
        </div>

        {readyForContent ? (
          <ResearchContentActions
            payload={bridgePayload}
            className="w-full"
            orientation="column"
            primaryIntent="pipeline"
          />
        ) : null}
      </CardContent>
    </Card>
  );
}

const TRIAGE_OPTIONS: { value: TriageStatus; label: string; variant: 'default' | 'outline' | 'destructive' | 'ghost' }[] = [
  { value: 'needs_review', label: 'Needs Review', variant: 'destructive' },
  { value: 'investigated', label: 'Investigated', variant: 'outline' },
  { value: 'blocked', label: 'Blocked', variant: 'destructive' },
  { value: 'ready', label: 'Ready', variant: 'default' },
  { value: 'archived', label: 'Archived', variant: 'ghost' },
];

function NextActionsPanel({
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
    <Card className="xl:rounded-2xl">
      <CardHeader className="pb-3">
        <CardTitle className="text-base">Next Actions</CardTitle>
      </CardHeader>
      <CardContent>
        <NextActions
          sessionId={sessionId}
          runStatus={runStatus}
          hasReport={hasReport}
          isArchived={isArchived}
        />
      </CardContent>
    </Card>
  );
}

function TriagePanel({ sessionId }: { sessionId: string }) {
  const [triageStatus, setTriageStatus] = useState<string | null>(null);
  const [triageOwner, setTriageOwner] = useState('');
  const [loading, setLoading] = useState(false);
  const [editingOwner, setEditingOwner] = useState(false);
  const { notify } = useNotifications();

  useEffect(() => {
    getSessionTriage(sessionId).then((result) => {
      setTriageStatus(result.triage_status);
      setTriageOwner(result.triage_owner ?? '');
    }).catch(() => {});
  }, [sessionId]);

  const handleTriageStatusChange = async (status: TriageStatus) => {
    setLoading(true);
    try {
      await updateSessionTriage(sessionId, { triage_status: status });
      setTriageStatus(status);
      notify({ variant: 'success', title: 'Triage status updated' });
    } catch {
      notify({ variant: 'destructive', title: 'Failed to update triage status' });
    } finally {
      setLoading(false);
    }
  };

  const handleOwnerSave = async () => {
    if (!triageOwner.trim()) return;
    setLoading(true);
    try {
      await updateSessionTriage(sessionId, { triage_owner: triageOwner.trim() });
      setEditingOwner(false);
      notify({ variant: 'success', title: 'Owner updated' });
    } catch {
      notify({ variant: 'destructive', title: 'Failed to update owner' });
    } finally {
      setLoading(false);
    }
  };

  return (
    <Card className="xl:rounded-2xl">
      <CardHeader className="pb-3">
        <CardTitle className="text-base flex items-center gap-2">
          <StickyNote className="h-4 w-4 text-primary" />
          Triage
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="space-y-2">
          <p className="text-xs uppercase tracking-wide text-muted-foreground">Status</p>
          <div className="flex flex-wrap gap-2">
            {TRIAGE_OPTIONS.map((option) => (
              <Button
                key={option.value}
                type="button"
                size="sm"
                variant={triageStatus === option.value ? option.variant : 'outline'}
                onClick={() => handleTriageStatusChange(option.value)}
                disabled={loading}
              >
                {option.label}
              </Button>
            ))}
          </div>
        </div>
        <div className="space-y-2">
          <p className="text-xs uppercase tracking-wide text-muted-foreground">Owner</p>
          {editingOwner ? (
            <div className="flex gap-2">
              <Input
                value={triageOwner}
                onChange={(e) => setTriageOwner(e.target.value)}
                placeholder="Operator name"
                className="h-9"
              />
              <Button size="sm" onClick={handleOwnerSave} disabled={loading}>Save</Button>
              <Button size="sm" variant="ghost" onClick={() => setEditingOwner(false)}>Cancel</Button>
            </div>
          ) : (
            <div className="flex items-center gap-2">
              <span className="text-sm text-foreground">{triageOwner || 'Unassigned'}</span>
              <Button size="sm" variant="ghost" onClick={() => setEditingOwner(true)}>
                <Pencil className="h-3 w-3" />
              </Button>
            </div>
          )}
        </div>
      </CardContent>
    </Card>
  );
}

function AnnotationPanel({ sessionId }: { sessionId: string }) {
  const [annotations, setAnnotations] = useState<SessionAnnotationType[]>([]);
  const [newNote, setNewNote] = useState('');
  const [author, setAuthor] = useState('');
  const [loading, setLoading] = useState(false);
  const { notify } = useNotifications();

  useEffect(() => {
    getSessionAnnotations(sessionId).then((result) => {
      setAnnotations(result.annotations);
    }).catch(() => {});
  }, [sessionId]);

  const handleAddNote = async () => {
    if (!newNote.trim()) return;
    setLoading(true);
    try {
      const result = await addSessionAnnotation(sessionId, newNote.trim(), author.trim() || undefined);
      setAnnotations((prev) => [...prev, result.annotation]);
      setNewNote('');
      notify({ variant: 'success', title: 'Note added' });
    } catch {
      notify({ variant: 'destructive', title: 'Failed to add note' });
    } finally {
      setLoading(false);
    }
  };

  const handleDeleteNote = async (index: number) => {
    try {
      await deleteSessionAnnotation(sessionId, index);
      setAnnotations((prev) => prev.filter((_, i) => i !== index));
      notify({ variant: 'success', title: 'Note deleted' });
    } catch {
      notify({ variant: 'destructive', title: 'Failed to delete note' });
    }
  };

  return (
    <Card className="xl:rounded-2xl">
      <CardHeader className="pb-3">
        <CardTitle className="text-base flex items-center gap-2">
          <StickyNote className="h-4 w-4 text-primary" />
          Notes
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="space-y-2">
          <Textarea
            value={newNote}
            onChange={(e) => setNewNote(e.target.value)}
            placeholder="Add a note about this session..."
            className="min-h-[80px] resize-none"
          />
          <div className="flex gap-2">
            <Input
              value={author}
              onChange={(e) => setAuthor(e.target.value)}
              placeholder="Your name (optional)"
              className="h-9 flex-1"
            />
            <Button size="sm" onClick={handleAddNote} disabled={loading || !newNote.trim()}>
              <Plus className="h-3 w-3" />
              Add
            </Button>
          </div>
        </div>
        {annotations.length > 0 ? (
          <div className="space-y-3">
            {annotations.map((annotation, index) => (
              <div key={index} className="rounded-[0.8rem] border border-border/70 bg-surface-raised p-3">
                <div className="flex items-start justify-between gap-2">
                  <p className="text-sm text-foreground whitespace-pre-wrap">{annotation.note}</p>
                  <button
                    type="button"
                    onClick={() => handleDeleteNote(index)}
                    className="text-muted-foreground hover:text-destructive transition-colors"
                    title="Delete note"
                  >
                    <Trash2 className="h-3 w-3" />
                  </button>
                </div>
                <p className="mt-2 text-xs text-muted-foreground">
                  {annotation.author ? `${annotation.author} · ` : ''}
                  {new Date(annotation.created_at).toLocaleString()}
                </p>
              </div>
            ))}
          </div>
        ) : (
          <p className="text-xs text-muted-foreground">No notes yet.</p>
        )}
      </CardContent>
    </Card>
  );
}

export function SessionOverview({ sessionId, runStatus, sessionSummary }: SessionOverviewProps) {
  const [isExportDialogOpen, setIsExportDialogOpen] = useState(false);

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

        <ArtifactExplorer
          sessionId={sessionId}
          runStatus={runStatus}
          sessionSummary={sessionSummary}
          onOpenBundleExport={() => setIsExportDialogOpen(true)}
        />
      </div>

      <aside className="space-y-6 xl:sticky xl:top-6 xl:self-start">
        <NextActionsPanel
          sessionId={sessionId}
          runStatus={runStatus}
          hasReport={sessionSummary?.hasReport ?? false}
          isArchived={sessionSummary?.archived ?? false}
        />
        <ContentStudioHandoff
          session={sessionSummary}
          sessionId={sessionId}
          runStatus={runStatus}
        />
        <TriagePanel sessionId={sessionId} />
        <AnnotationPanel sessionId={sessionId} />
      </aside>
    </div>
  );
}
