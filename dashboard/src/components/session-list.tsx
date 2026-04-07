'use client';

import { useState, useEffect } from 'react';
import Link from 'next/link';
import {
  Activity,
  AlertCircle,
  Archive,
  ArchiveRestore,
  ArrowUpRight,
  GitCompare,
  Cpu,
  Filter,
  Network,
  Play,
  Search,
  Trash2,
  CheckCircle2,
  ShieldAlert,
  Sparkles,
} from 'lucide-react';

import { BulkSessionDeleteResponse, Session, SessionListQueryState } from '@/types/telemetry';
import { AlertDialog } from '@/components/ui/alert-dialog';
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card, CardContent } from '@/components/ui/card';
import { EmptyState } from '@/components/ui/empty-state';
import { SkeletonSessionCard } from '@/components/ui/skeleton';
import { getErrorGuidance } from '@/lib/error-messages';
import { Checkbox } from '@/components/ui/checkbox';
import { Input } from '@/components/ui/input';
import { useNotifications } from '@/components/ui/notification-center';
import { Select } from '@/components/ui/select';
import { SavedViewControls } from '@/components/saved-view-controls';
import { ResearchContentActions } from '@/components/research-content-actions';
import useDashboardStore, { DEFAULT_SESSION_LIST_QUERY } from '@/hooks/useDashboard';
import {
  archiveSession,
  bulkDeleteSessions,
  deleteSession,
  getApiErrorMessage,
  getSessionPurgeSummary,
  purgeArchivedSessions,
  restoreSession,
} from '@/lib/api';
import { buildResearchContentBridgePayloadFromSession } from '@/lib/research-content-bridge';
import { suggestBaselineSessions } from '@/lib/compare-utils';
import {
  areSessionListQueriesEqual,
  sanitizeSessionListQuery,
} from '@/lib/saved-views';

const sessionStatusOptions = ['completed', 'failed', 'interrupted', 'running', 'unknown'];
const SESSION_LIST_VIEW_STORAGE_KEY = 'ccdr.dashboard.saved-session-list-views';

function sanitizeSessionListSavedView(value: unknown): SessionListQueryState {
  return sanitizeSessionListQuery(value, sessionStatusOptions);
}

interface SessionListProps {
  error?: string | null;
  loading: boolean;
  loadingMore: boolean;
  loadMoreError?: string | null;
  nextCursor: string | null;
  onLoadMore?: () => void;
  onRetry?: () => void;
  onRefresh?: () => void;
  sessions: Session[];
  total: number;
}

interface DeleteDialogState {
  mode: 'single' | 'bulk' | null;
  sessions: Session[];
  deleting: boolean;
  forceDelete: boolean;
}

interface SessionCardProps {
  session: Session;
  selected: boolean;
  compareMode: boolean;
  compareSelected: boolean;
  compareSlot: 'A' | 'B' | null;
  compareLocked: boolean;
  onDelete: (session: Session) => void;
  onToggleSelection: (sessionId: string) => void;
  onToggleCompare: (sessionId: string) => void;
  onArchive?: (session: Session) => void;
  onRestore?: (session: Session) => void;
}

function formatTimestamp(value: string | null): string {
  if (!value) {
    return 'Unknown';
  }

  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? value : date.toLocaleString();
}

function formatDepth(value: string | null): string {
  if (!value) {
    return 'Unknown depth';
  }
  return value.charAt(0).toUpperCase() + value.slice(1);
}

function pluralize(count: number, noun: string): string {
  return `${count} ${noun}${count === 1 ? '' : 's'}`;
}

function buildFilterSummary(query: SessionListQueryState): string {
  const parts: string[] = [];

  if (query.search.trim()) {
    parts.push(`search "${query.search.trim()}"`);
  }
  if (query.status) {
    parts.push(`status ${query.status}`);
  }
  if (query.activeOnly) {
    parts.push('active-only view');
  }

  return parts.length > 0 ? parts.join(' • ') : 'all visible sessions';
}

function matchesVisibleSession(session: Session, query: SessionListQueryState): boolean {
  if (query.activeOnly && !session.active) {
    return false;
  }
  if (query.archivedOnly && !session.archived) {
    return false;
  }
  if (query.status && session.status !== query.status) {
    return false;
  }

  const search = query.search.trim().toLowerCase();
  if (!search) {
    return true;
  }

  return [session.sessionId, session.label, session.query ?? ''].some((value) =>
    value.toLowerCase().includes(search)
  );
}

function buildBulkFailureSummary(
  failedCount: number,
  activeConflictCount: number,
  partialFailureCount: number
): string {
  const parts: string[] = [];

  if (activeConflictCount > 0) {
    parts.push(pluralize(activeConflictCount, 'active conflict'));
  }
  if (partialFailureCount > 0) {
    parts.push(pluralize(partialFailureCount, 'partial failure'));
  }
  if (failedCount > 0) {
    parts.push(pluralize(failedCount, 'failed delete'));
  }

  return parts.join(', ');
}

function shouldPromptBulkForceDelete(
  response: BulkSessionDeleteResponse,
  forceDelete: boolean
): boolean {
  return !forceDelete && response.summary.active_conflict_count > 0;
}

function buildBulkDeleteAttentionMessage(
  response: BulkSessionDeleteResponse,
  remainingCount: number,
  deletedCount: number,
  forceRetryAvailable: boolean
): string {
  const failureSummary = buildBulkFailureSummary(
    response.summary.failed_count,
    response.summary.active_conflict_count,
    response.summary.partial_failure_count
  );
  const deletedSummary =
    deletedCount > 0 ? `Deleted ${pluralize(deletedCount, 'session')}. ` : '';
  const attentionSummary = `${deletedSummary}${pluralize(remainingCount, 'session')} still require attention: ${failureSummary}.`;

  if (!forceRetryAvailable) {
    return attentionSummary;
  }

  const retrySummary =
    response.summary.active_conflict_count === remainingCount
      ? 'Review and confirm force delete to stop the running processes.'
      : 'Review and confirm force delete to stop any still-running sessions.';

  return `${attentionSummary} ${retrySummary}`;
}

interface SessionGroup {
  title: string;
  description: string;
  icon: React.ElementType;
  sessions: Session[];
  variant: 'default' | 'warning' | 'success';
}

interface SessionTriageMeta {
  label: string;
  summary: string;
  badgeVariant: 'info' | 'warning' | 'success' | 'outline';
}

function getSessionTriageMeta(session: Session): SessionTriageMeta {
  if (session.active) {
    return {
      label: 'Active',
      summary: 'Live session. Best candidate for monitor-first triage or an in-flight compare baseline.',
      badgeVariant: 'info',
    };
  }

  if (session.status === 'failed' || session.status === 'interrupted') {
    return {
      label: 'Needs attention',
      summary: 'Failure-state session. Prioritize review, compare, or archive only after investigation.',
      badgeVariant: 'warning',
    };
  }

  if (session.archived) {
    return {
      label: 'Archived',
      summary: 'Kept for record or retrospective comparison, but removed from the active working set.',
      badgeVariant: 'outline',
    };
  }

  if (session.hasReport) {
    return {
      label: 'Report ready',
      summary: 'Finished cleanly with artifacts available. Good candidate for compare or downstream review.',
      badgeVariant: 'success',
    };
  }

  return {
    label: 'Recent history',
    summary: 'Completed session without a report artifact. Keep it for trace review or lightweight reference.',
    badgeVariant: 'outline',
  };
}

function categorizeSessions(sessions: Session[]): SessionGroup[] {
  const activeSessions = sessions.filter((s) => s.active);
  const attentionSessions = sessions.filter(
    (s) => !s.active && (s.status === 'failed' || s.status === 'interrupted')
  );
  const reportReadySessions = sessions.filter(
    (s) => !s.active && !s.archived && s.hasReport && s.status !== 'failed' && s.status !== 'interrupted'
  );
  const archivedSessions = sessions.filter(
    (s) => !s.active && Boolean(s.archived)
  );
  const historySessions = sessions.filter(
    (s) =>
      !s.active &&
      s.status !== 'failed' &&
      s.status !== 'interrupted' &&
      !s.archived &&
      !s.hasReport
  );

  const groups: SessionGroup[] = [];

  if (activeSessions.length > 0) {
    groups.push({
      title: 'Running',
      description: 'Sessions currently in progress',
      icon: Play,
      sessions: activeSessions,
      variant: 'default',
    });
  }

  if (attentionSessions.length > 0) {
    groups.push({
      title: 'Needs Attention',
      description: 'Failed or interrupted sessions',
      icon: AlertCircle,
      sessions: attentionSessions,
      variant: 'warning',
    });
  }

  if (reportReadySessions.length > 0) {
    groups.push({
      title: 'Report Ready',
      description: 'Completed sessions with reviewable report artifacts',
      icon: CheckCircle2,
      sessions: reportReadySessions,
      variant: 'success',
    });
  }

  if (archivedSessions.length > 0) {
    groups.push({
      title: 'Archived',
      description: 'Historical sessions retained for later reference or comparison',
      icon: Archive,
      sessions: archivedSessions,
      variant: 'default',
    });
  }

  if (historySessions.length > 0) {
    groups.push({
      title: 'Recent History',
      description: 'Completed sessions that are neither urgent nor report-ready',
      icon: Activity,
      sessions: historySessions,
      variant: 'default',
    });
  }

  return groups;
}

function SessionCard({
  session,
  selected,
  compareMode,
  compareSelected,
  compareSlot,
  compareLocked,
  onDelete,
  onToggleSelection,
  onToggleCompare,
  onArchive,
  onRestore,
}: SessionCardProps) {
  const timeLabel = session.completedAt ? 'Completed' : 'Last event';
  const timeValue = session.completedAt ?? session.lastEventAt;
  const showsQuery = session.query && session.query !== session.label;
  const isArchived = session.archived;
  const [expanded, setExpanded] = useState(false);
  const triage = getSessionTriageMeta(session);
  const compareSelectionLabel =
    compareSlot === 'A'
      ? 'Baseline'
      : compareSlot === 'B'
        ? 'Comparison'
        : compareLocked
          ? 'Selection full'
          : 'Compare';
  const compareSelectionTitle = compareSelected
    ? `Remove ${session.label} from comparison`
    : compareLocked
      ? 'Two sessions are already selected. Deselect one to change the pair.'
      : 'Select for comparison';

  return (
    <article className="group relative overflow-hidden rounded-[1.2rem] border border-border/80 bg-[linear-gradient(180deg,rgba(19,34,38,0.9),rgba(16,27,31,0.94))] p-4 shadow-card transition-all duration-200 hover:-translate-y-px hover:shadow-card-raised">
      <div className="absolute inset-y-0 left-0 w-px bg-gradient-to-b from-primary via-primary/40 to-transparent" />

      <div className="grid gap-4 xl:grid-cols-[minmax(0,1.25fr)_minmax(18rem,0.9fr)_auto]">
        <div className="min-w-0 space-y-4">
          <div className="flex items-start gap-3">
            <div className="pt-1">
              {!compareMode ? (
                <label
                  className="flex min-h-[44px] min-w-[44px] items-center justify-center rounded-full"
                  title={
                    session.active
                      ? 'Stop the active run before selecting this session for deletion.'
                      : 'Select session'
                  }
                >
                  <Checkbox
                    checked={selected}
                    disabled={session.active}
                    onCheckedChange={() => onToggleSelection(session.sessionId)}
                    aria-label={`Select session ${session.label}`}
                  />
                </label>
              ) : (
                <div className="flex flex-col items-center gap-2 pt-0.5">
                  <label
                    className="flex min-h-[44px] min-w-[44px] items-center justify-center rounded-full"
                    title={compareSelectionTitle}
                  >
                    <Checkbox
                      checked={compareSelected}
                      disabled={compareLocked && !compareSelected}
                      onCheckedChange={() => onToggleCompare(session.sessionId)}
                      aria-label={`Compare session ${session.label}`}
                    />
                  </label>
                  <Badge variant={compareSelected ? 'info' : 'outline'} className="px-2">
                    {compareSelectionLabel}
                  </Badge>
                </div>
              )}
            </div>

            <div className="min-w-0 flex-1">
              <div className="flex flex-wrap items-center gap-2">
                <Badge variant="secondary">{formatDepth(session.depth)}</Badge>
                <Badge variant={session.active ? 'info' : isArchived ? 'warning' : 'outline'}>
                  {session.active ? 'Live' : isArchived ? 'Archived' : session.status}
                </Badge>
                <Badge variant={triage.badgeVariant}>{triage.label}</Badge>
                {session.hasReport ? <Badge variant="success">Report ready</Badge> : null}
              </div>

              <Link href={`/session/${session.sessionId}`} className="mt-3 block">
                <h3 className="truncate font-display text-[2rem] font-semibold uppercase tracking-[0.02em] text-foreground transition-colors group-hover:text-primary">
                  {session.label}
                </h3>
              </Link>
              <p className="mt-1 truncate font-mono text-[0.74rem] uppercase tracking-[0.14em] text-muted-foreground">
                {session.sessionId}
              </p>

              <p className="mt-3 max-w-3xl text-sm leading-6 text-muted-foreground">
                {showsQuery ? session.query : 'Research session with telemetry, routing, and output history available for inspection.'}
              </p>
              <p className="mt-2 text-sm leading-6 text-foreground/86">
                {triage.summary}
              </p>
            </div>
          </div>

          <div className="flex flex-wrap items-center gap-2">
            <Badge variant="outline">
              Payload {session.hasSessionPayload ? 'available' : 'missing'}
            </Badge>
            <Badge variant="outline">
              Report {session.hasReport ? 'available' : 'unavailable'}
            </Badge>
            <button
              type="button"
              onClick={() => setExpanded((prev) => !prev)}
              className="ml-auto font-mono text-[0.72rem] uppercase tracking-[0.16em] text-muted-foreground transition-colors hover:text-foreground"
            >
              {expanded ? 'Hide detail' : 'Expand detail'}
            </button>
          </div>
        </div>

        <dl className="grid gap-3 rounded-[1rem] border border-border/70 bg-surface/68 p-4 sm:grid-cols-2 xl:grid-cols-1">
          <div className="space-y-1">
            <dt className="eyebrow">Status</dt>
            <dd className="flex items-center gap-2 text-sm text-foreground">
              <Activity className="h-4 w-4 text-primary" />
              <span className="font-medium capitalize">{session.status}</span>
            </dd>
          </div>
          <div className="space-y-1">
            <dt className="eyebrow">Sources</dt>
            <dd className="flex items-center gap-2 text-sm text-foreground">
              <Network className="h-4 w-4 text-primary" />
              <span className="font-medium tabular-nums">{session.totalSources}</span>
            </dd>
          </div>
          <div className="space-y-1 sm:col-span-2 xl:col-span-1">
            <dt className="eyebrow">{timeLabel}</dt>
            <dd className="flex items-start gap-2 text-sm text-foreground">
              <Cpu className="mt-0.5 h-4 w-4 shrink-0 text-primary" />
              <span className="leading-6">{formatTimestamp(timeValue)}</span>
            </dd>
          </div>
        </dl>

        <div className="flex flex-col gap-2 xl:min-w-[12rem]">
          <Link
            href={`/session/${session.sessionId}`}
            className="inline-flex h-11 items-center justify-center gap-2 rounded-[0.9rem] border border-primary/40 bg-primary px-4 font-display text-[0.82rem] font-semibold uppercase tracking-[0.16em] text-primary-foreground transition-all duration-200 hover:-translate-y-px hover:bg-primary/92"
          >
            <Play className="h-3.5 w-3.5" />
            View details
          </Link>
          <Link
            href={`/session/${session.sessionId}`}
            className="inline-flex h-10 items-center justify-center gap-2 rounded-[0.9rem] border border-border/80 bg-surface/72 px-4 font-display text-[0.8rem] font-semibold uppercase tracking-[0.14em] text-foreground transition-all duration-200 hover:-translate-y-px hover:border-primary/35 hover:bg-surface-raised"
          >
            <ArrowUpRight className="h-3.5 w-3.5" />
            Open workspace
          </Link>
          {session.hasReport && !session.active && !isArchived ? (
            <ResearchContentActions
              payload={buildResearchContentBridgePayloadFromSession(
                session.sessionId,
                session,
                'home'
              )}
              orientation="column"
              primaryIntent="pipeline"
            />
          ) : null}
          {!session.active && !isArchived && onArchive ? (
            <Button
              variant="outline"
              size="sm"
              onClick={() => onArchive(session)}
              title="Archive session"
            >
              <Archive className="h-3.5 w-3.5" />
              Archive
            </Button>
          ) : null}
          {!session.active && isArchived && onRestore ? (
            <Button
              variant="outline"
              size="sm"
              onClick={() => onRestore(session)}
              title="Restore archived session"
            >
              <ArchiveRestore className="h-3.5 w-3.5" />
              Restore
            </Button>
          ) : null}
          <Button
            variant="outline"
            size="sm"
            onClick={() => onDelete(session)}
            disabled={session.active}
            title={
              session.active
                ? 'Stop the active run before deleting this session.'
                : 'Delete session'
            }
          >
            <Trash2 className="h-3.5 w-3.5" />
            Delete
          </Button>
        </div>
      </div>

      {expanded ? (
        <div className="mt-4 grid gap-3 border-t border-border/70 pt-4 text-sm text-muted-foreground animate-fade-in md:grid-cols-3">
          <div className="rounded-[0.95rem] border border-border/65 bg-surface/55 p-4">
            <p className="eyebrow">Query context</p>
            <p className="mt-3 leading-6 text-foreground/88">
              {session.query || 'No explicit query text recorded for this session.'}
            </p>
          </div>
          <div className="rounded-[0.95rem] border border-border/65 bg-surface/55 p-4">
            <p className="eyebrow">Retention state</p>
            <div className="mt-3 space-y-2">
              <div className="flex items-center justify-between gap-4">
                <span>Telemetry payload</span>
                <span className="font-mono text-xs uppercase tracking-[0.16em] text-foreground">
                  {session.hasSessionPayload ? 'Stored' : 'Missing'}
                </span>
              </div>
              <div className="flex items-center justify-between gap-4">
                <span>Report artifact</span>
                <span className="font-mono text-xs uppercase tracking-[0.16em] text-foreground">
                  {session.hasReport ? 'Stored' : 'Missing'}
                </span>
              </div>
            </div>
          </div>
          <div className="rounded-[0.95rem] border border-border/65 bg-surface/55 p-4">
            <p className="eyebrow">Triage guidance</p>
            <p className="mt-3 leading-6 text-foreground/88">{triage.summary}</p>
          </div>
        </div>
      ) : null}
    </article>
  );
}

function SessionFilters() {
  const query = useDashboardStore((state) => state.sessionListQuery);
  const setSessionListQuery = useDashboardStore((state) => state.setSessionListQuery);
  const normalizedQuery = sanitizeSessionListSavedView(query);
  const hasFilters =
    normalizedQuery.search.trim().length > 0
    || normalizedQuery.status.length > 0
    || normalizedQuery.activeOnly
    || normalizedQuery.archivedOnly;

  return (
    <div className="rounded-[1.2rem] border border-border/80 bg-surface/68 p-4 shadow-card">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-2 text-sm text-foreground">
          <Filter className="h-4 w-4 text-primary" />
          <span className="font-display text-[1.05rem] font-semibold uppercase tracking-[0.12em]">
            Session filters
          </span>
        </div>
        {hasFilters ? (
          <Button
            type="button"
            size="sm"
            variant="ghost"
            onClick={() => setSessionListQuery(DEFAULT_SESSION_LIST_QUERY)}
          >
            Clear
          </Button>
        ) : null}
      </div>
      <div className="mt-4">
        <SavedViewControls
          storageKey={SESSION_LIST_VIEW_STORAGE_KEY}
          title="Saved Views"
          description="Keep a few reusable session-list presets for repeated triage work."
          itemLabel="session view"
          testIdPrefix="session-view"
          selectLabel="Saved session view"
          inputLabel="View name"
          emptyState="No saved session views yet."
          currentValue={normalizedQuery}
          sanitizeStoredValue={sanitizeSessionListSavedView}
          sanitizeForSave={sanitizeSessionListSavedView}
          sanitizeForApply={sanitizeSessionListSavedView}
          isEqual={areSessionListQueriesEqual}
          onApply={(value) => setSessionListQuery(value)}
        />
      </div>
      <div className="mt-4 grid gap-3 xl:grid-cols-[minmax(0,1fr)_12rem_12rem_12rem]">
        <label className="min-w-0">
          <span className="mb-1.5 block text-xs font-medium uppercase tracking-[0.18em] text-muted-foreground">
            Search
          </span>
          <div className="relative">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground shrink-0" />
            <Input
              type="search"
              value={query.search}
              onChange={(event) => setSessionListQuery({ search: event.target.value })}
              placeholder="Query, label, or session ID"
              className="pl-9"
              aria-label="Search sessions"
            />
          </div>
        </label>
        <Select
          label="Status"
          value={query.status}
          options={sessionStatusOptions}
          onChange={(value) => setSessionListQuery({ status: value })}
          emptyLabel="All"
          className="h-11 bg-surface/72"
        />
        <div className="flex min-w-[11rem] flex-col gap-1.5">
          <span className="text-xs font-medium uppercase tracking-[0.18em] text-muted-foreground">
            Lifecycle
          </span>
          <div className="flex gap-1">
            <Button
              type="button"
              size="sm"
              variant={query.activeOnly ? 'default' : 'outline'}
              onClick={() => setSessionListQuery({ activeOnly: !query.activeOnly, archivedOnly: false })}
              title="Show only active sessions"
            >
              <Play className="h-3 w-3" />
            </Button>
            <Button
              type="button"
              size="sm"
              variant={query.archivedOnly ? 'default' : 'outline'}
              onClick={() => setSessionListQuery({ archivedOnly: !query.archivedOnly, activeOnly: false })}
              title="Show only archived sessions"
            >
              <Archive className="h-3 w-3" />
            </Button>
          </div>
        </div>
      </div>
    </div>
  );
}

function LoadingState() {
  return (
    <div className="space-y-3" role="status" aria-label="Loading sessions">
      {Array.from({ length: 4 }).map((_, i) => (
        <SkeletonSessionCard key={i} />
      ))}
    </div>
  );
}

function ErrorState({ error, onRetry }: { error: string; onRetry?: () => void }) {
  const { guidance } = getErrorGuidance(error);
  return (
    <Alert variant="destructive" className="rounded-[1.2rem]">
      <div className="flex items-start gap-3">
        <AlertCircle className="h-5 w-5 shrink-0 mt-0.5" />
        <div className="space-y-2">
          <AlertTitle>Failed to load sessions</AlertTitle>
          <AlertDescription>{error}</AlertDescription>
          {guidance && (
            <p className="text-xs text-muted-foreground">{guidance}</p>
          )}
          {onRetry ? (
            <Button onClick={onRetry} type="button" variant="outline" size="sm">
              Retry
            </Button>
          ) : null}
        </div>
      </div>
    </Alert>
  );
}

export function SessionList({
  error,
  loading,
  loadingMore,
  loadMoreError,
  nextCursor,
  onLoadMore,
  onRetry,
  onRefresh,
  sessions,
  total,
}: SessionListProps) {
  const { notify } = useNotifications();
  const [deleteDialog, setDeleteDialog] = useState<DeleteDialogState>({
    mode: null,
    sessions: [],
    deleting: false,
    forceDelete: false,
  });
  const [deleteError, setDeleteError] = useState<string | null>(null);
  const [purgeSummary, setPurgeSummary] = useState<{
    archived_sessions_count: number;
    no_artifacts_count: number;
    active_count: number;
    recommendations: Array<{ category: string; description: string; action: string; count: number }>;
  } | null>(null);
  const [purgeLoading, setPurgeLoading] = useState(false);
  const [showPurgeDialog, setShowPurgeDialog] = useState(false);
  const [purgeDryRun, setPurgeDryRun] = useState(true);
  const query = useDashboardStore((state) => state.sessionListQuery);
  const selectedSessionIds = useDashboardStore((state) => state.selectedSessionIds);
  const toggleSessionSelection = useDashboardStore((state) => state.toggleSessionSelection);
  const setSelectedSessionIds = useDashboardStore((state) => state.setSelectedSessionIds);
  const clearSessionSelection = useDashboardStore((state) => state.clearSessionSelection);
  const removeSession = useDashboardStore((state) => state.removeSession);
  const removeSessions = useDashboardStore((state) => state.removeSessions);
  const setSessionListQuery = useDashboardStore((state) => state.setSessionListQuery);
  const compareMode = useDashboardStore((state) => state.compareMode);
  const setCompareMode = useDashboardStore((state) => state.setCompareMode);
  const compareSessionIds = useDashboardStore((state) => state.compareSessionIds);
  const setCompareSessionIds = useDashboardStore((state) => state.setCompareSessionIds);
  const toggleCompareSessionId = useDashboardStore((state) => state.toggleCompareSessionId);
  const clearCompareSessionIds = useDashboardStore((state) => state.clearCompareSessionIds);
  const filtered =
    query.search.trim().length > 0 || query.status.length > 0 || query.activeOnly || query.archivedOnly;

  useEffect(() => {
    async function loadPurgeSummary() {
      try {
        const summary = await getSessionPurgeSummary();
        setPurgeSummary(summary);
      } catch {
        setPurgeSummary(null);
      }
    }
    loadPurgeSummary();
  }, []);

  const handlePurgeClick = async (dryRun: boolean) => {
    setPurgeLoading(true);
    try {
      const result = await purgeArchivedSessions(dryRun, false);
      if (dryRun) {
        notify({
          variant: 'info',
          title: 'Purge Preview',
          description: result.message,
        });
      } else {
        notify({
          variant: 'success',
          title: 'Purge Complete',
          description: `Deleted ${result.deleted} archived session(s)`,
        });
        refreshSessions();
      }
    } catch (requestError) {
      notify({
        variant: 'destructive',
        persistent: true,
        title: 'Purge Failed',
        description: getApiErrorMessage(requestError, 'Failed to purge archived sessions'),
      });
    } finally {
      setPurgeLoading(false);
      setShowPurgeDialog(false);
    }
  };

  const compareSessionIdSet = new Set(compareSessionIds.filter(Boolean) as string[]);
  const canViewComparison = compareSessionIdSet.size === 2;
  const [sessionA, sessionB] = compareSessionIds;
  const compareBaseline = sessions.find((session) => session.sessionId === sessionA) ?? null;
  const compareCandidate = sessions.find((session) => session.sessionId === sessionB) ?? null;
  const compareAssistTarget = compareSessionIdSet.size === 1 ? compareBaseline : compareCandidate;
  const baselineSuggestions = compareMode
    ? suggestBaselineSessions(
        compareAssistTarget,
        sessions.filter((session) => session.sessionId !== sessionA),
        { limit: 3 }
      )
    : [];
  const suggestedBaseline = baselineSuggestions[0] ?? null;
  const shouldOfferSuggestedBaseline =
    compareMode &&
    compareSessionIdSet.size === 1 &&
    compareBaseline &&
    suggestedBaseline &&
    suggestedBaseline.session.sessionId !== compareBaseline.sessionId &&
    (
      compareBaseline.active
      || compareBaseline.status !== 'completed'
      || !compareBaseline.hasReport
      || suggestedBaseline.confidence === 'high'
    );
  const shouldOfferBaselineSwitch =
    compareMode &&
    compareSessionIdSet.size === 2 &&
    compareCandidate &&
    suggestedBaseline &&
    suggestedBaseline.session.sessionId !== sessionA &&
    suggestedBaseline.confidence !== 'low';

  const visibleSessions = sessions.filter((session) => matchesVisibleSession(session, query));
  const selectedSessionIdSet = new Set(selectedSessionIds);
  const selectableSessions = visibleSessions.filter((session) => !session.active);
  const selectedSessions = selectableSessions.filter((session) =>
    selectedSessionIdSet.has(session.sessionId)
  );
  const allSelectableSelected =
    selectableSessions.length > 0 && selectedSessions.length === selectableSessions.length;

  const handleDeleteClick = (session: Session) => {
    setDeleteDialog({ mode: 'single', sessions: [session], deleting: false, forceDelete: false });
    setDeleteError(null);
  };

  const handleBulkDeleteClick = () => {
    if (selectedSessions.length === 0) {
      return;
    }
    setDeleteDialog({ mode: 'bulk', sessions: selectedSessions, deleting: false, forceDelete: false });
    setDeleteError(null);
  };

  const handleArchive = async (session: Session) => {
    const result = await archiveSession(session.sessionId);
    if (result.success) {
      notify({
        variant: 'success',
        title: 'Session archived',
        description: `${session.label} moved out of the active working set.`,
        actions: [
          {
            label: 'Open session',
            href: `/session/${session.sessionId}`,
          },
        ],
      });
      refreshSessions();
      return;
    }

    notify({
      variant: 'destructive',
      persistent: true,
      title: 'Archive failed',
      description: result.error || 'Failed to archive session.',
      actions: [
        {
          label: 'Open session',
          href: `/session/${session.sessionId}`,
        },
      ],
    });
  };

  const handleRestore = async (session: Session) => {
    const result = await restoreSession(session.sessionId);
    if (result.success) {
      notify({
        variant: 'success',
        title: 'Session restored',
        description: `${session.label} is back in the active working set.`,
        actions: [
          {
            label: 'Open session',
            href: `/session/${session.sessionId}`,
          },
        ],
      });
      refreshSessions();
      return;
    }

    notify({
      variant: 'destructive',
      persistent: true,
      title: 'Restore failed',
      description: result.error || 'Failed to restore session.',
      actions: [
        {
          label: 'Open session',
          href: `/session/${session.sessionId}`,
        },
      ],
    });
  };

  const refreshSessions = () => {
    onRefresh?.();
  };

  const handleDeleteConfirm = async () => {
    if (deleteDialog.sessions.length === 0 || deleteDialog.mode === null) {
      return;
    }

    setDeleteDialog((previous) => ({ ...previous, deleting: true }));
    setDeleteError(null);

    if (deleteDialog.mode === 'single') {
      const session = deleteDialog.sessions[0];
      const result = await deleteSession(session.sessionId, deleteDialog.forceDelete);

      if (result.success) {
        removeSession(session.sessionId);
        setDeleteDialog({ mode: null, sessions: [], deleting: false, forceDelete: false });
        notify({
          variant: 'success',
          title: 'Session deleted',
          description: `${session.label} and its stored artifacts were removed.`,
        });
        refreshSessions();
        return;
      }

      if (result.activeConflict) {
        if (deleteDialog.forceDelete) {
          setDeleteError('Failed to force delete: session is still active');
          setDeleteDialog((previous) => ({ ...previous, deleting: false }));
          return;
        }
        setDeleteError(null);
        setDeleteDialog((previous) => ({ ...previous, deleting: false, forceDelete: true }));
        return;
      }

      setDeleteError(result.error || 'Failed to delete session');
      notify({
        variant: 'destructive',
        persistent: true,
        title: 'Delete failed',
        description: result.error || 'Failed to delete session.',
      });
      setDeleteDialog((previous) => ({ ...previous, deleting: false }));
      return;
    }

    try {
      const response = await bulkDeleteSessions(
        deleteDialog.sessions.map((session) => session.sessionId),
        deleteDialog.forceDelete
      );
      const removableIds = response.results
        .filter((result) => result.outcome === 'deleted' || result.outcome === 'not_found')
        .map((result) => result.session_id);
      const retainedIds = new Set(
        response.results
          .filter((result) => result.outcome !== 'deleted' && result.outcome !== 'not_found')
          .map((result) => result.session_id)
      );

      if (removableIds.length > 0) {
        removeSessions(removableIds);
        refreshSessions();
      }

      if (retainedIds.size === 0) {
        setDeleteDialog({ mode: null, sessions: [], deleting: false, forceDelete: false });
        notify({
          variant: 'success',
          title: 'Selected sessions deleted',
          description:
            removableIds.length > 0
              ? `Removed ${pluralize(removableIds.length, 'session')} from ${buildFilterSummary(query)}.`
              : 'The selected sessions were already gone.',
        });
        return;
      }

      const remainingSessions = deleteDialog.sessions.filter((session) =>
        retainedIds.has(session.sessionId)
      );
      const forceRetryAvailable = shouldPromptBulkForceDelete(response, deleteDialog.forceDelete);
      setSelectedSessionIds(remainingSessions.map((session) => session.sessionId));
      setDeleteDialog({
        mode: 'bulk',
        sessions: remainingSessions,
        deleting: false,
        forceDelete: forceRetryAvailable,
      });
      setDeleteError(
        buildBulkDeleteAttentionMessage(
          response,
          remainingSessions.length,
          removableIds.length,
          forceRetryAvailable
        )
      );
      notify({
        variant:
          response.summary.active_conflict_count > 0 || response.summary.partial_failure_count > 0
            ? 'warning'
            : 'destructive',
        persistent: true,
        title: 'Some sessions still need attention',
        description: buildBulkDeleteAttentionMessage(
          response,
          remainingSessions.length,
          removableIds.length,
          forceRetryAvailable
        ),
      });
    } catch (requestError) {
      const message = getApiErrorMessage(requestError, 'Failed to delete the selected sessions');
      setDeleteError(message);
      notify({
        variant: 'destructive',
        persistent: true,
        title: 'Bulk delete failed',
        description: message,
      });
      setDeleteDialog((previous) => ({ ...previous, deleting: false }));
    }
  };

  const handleDialogClose = (open: boolean) => {
    if (open) {
      return;
    }
    setDeleteDialog({ mode: null, sessions: [], deleting: false, forceDelete: false });
    setDeleteError(null);
  };

  const handleSelectVisible = () => {
    if (allSelectableSelected) {
      clearSessionSelection();
      return;
    }
    setSelectedSessionIds(selectableSessions.map((session) => session.sessionId));
  };

  const renderDeleteDescription = () => {
    const sessionCount = deleteDialog.sessions.length;
    const previewSessions = deleteDialog.sessions.slice(0, 5);
    const remainingCount = sessionCount - previewSessions.length;

    if (deleteDialog.mode === 'single') {
      const session = deleteDialog.sessions[0];
      return (
        <div className="space-y-3">
          {deleteDialog.forceDelete ? (
            <>
              <p className="rounded-[0.9rem] border border-warning/30 bg-warning-muted/30 px-3 py-2 text-warning">
                This session is currently active. Force deleting will stop the running process.
              </p>
              <p>
                This will permanently delete <span className="font-medium">{session.label}</span> and
                all associated telemetry, report, and analytics history.
              </p>
              <p className="font-mono text-xs text-muted-foreground">{session.sessionId}</p>
            </>
          ) : (
            <>
              <p>
                This will permanently delete <span className="font-medium">{session.label}</span> and
                all associated telemetry, report, and analytics history.
              </p>
              <p className="font-mono text-xs text-muted-foreground">{session.sessionId}</p>
              {deleteError ? (
                <Alert variant="destructive" className="mt-2">
                  <AlertDescription>{deleteError}</AlertDescription>
                </Alert>
              ) : (
                <p>This action cannot be undone.</p>
              )}
            </>
          )}
        </div>
      );
    }

    return (
      <div className="space-y-3">
        {deleteDialog.forceDelete ? (
          <Alert variant="warning" className="mt-2">
            <AlertDescription>
              Some selected sessions are currently active. Force deleting will stop any running
              processes before removing their telemetry, report, and analytics history.
            </AlertDescription>
          </Alert>
        ) : null}
        <p>
          This will permanently delete {pluralize(sessionCount, 'selected session')} from{' '}
          <span className="font-medium">{buildFilterSummary(query)}</span>.
        </p>
        <ul className="space-y-2 rounded-[0.95rem] border border-border/70 bg-surface/62 px-3 py-3 text-foreground">
          {previewSessions.map((session) => (
            <li key={session.sessionId} className="flex flex-col gap-1">
              <span className="font-medium">{session.label}</span>
              <span className="font-mono text-xs text-muted-foreground">{session.sessionId}</span>
            </li>
          ))}
          {remainingCount > 0 ? (
            <li className="font-mono text-xs uppercase tracking-[0.16em] text-muted-foreground">
              And {pluralize(remainingCount, 'more session')}
            </li>
          ) : null}
        </ul>
        {deleteError ? (
          <Alert variant="destructive" className="mt-2">
            <AlertDescription>{deleteError}</AlertDescription>
          </Alert>
        ) : (
          <p>This action cannot be undone.</p>
        )}
      </div>
    );
  };

  const sessionGroups = categorizeSessions(visibleSessions);

  return (
    <>
      <div className="space-y-4">
        <div className="panel-shell rounded-[1.4rem] p-5 sm:p-6">
          <div className="flex flex-col gap-4 xl:flex-row xl:items-end xl:justify-between">
            <div className="space-y-3">
              <p className="eyebrow">Research archive</p>
              <h2 className="font-display text-[2.6rem] font-semibold uppercase tracking-[0.02em] text-foreground">
                {compareMode ? 'Compare Sessions' : 'Research Sessions'}
              </h2>
              <p className="max-w-2xl text-sm leading-6 text-muted-foreground">
                {compareMode
                  ? 'Pick a baseline and one comparison session. The list locks after two selections.'
                  : `${visibleSessions.length} of ${total} sessions`}
              </p>
            </div>
            <div className="flex flex-wrap gap-2">
              {!compareMode && purgeSummary && (purgeSummary.archived_sessions_count > 0 || purgeSummary.no_artifacts_count > 0) ? (
                <Button
                  type="button"
                  size="sm"
                  variant="outline"
                  onClick={() => setShowPurgeDialog(true)}
                >
                  <Sparkles className="h-3.5 w-3.5" />
                  Lifecycle
                  {purgeSummary.archived_sessions_count > 0 && (
                    <Badge variant="warning" className="ml-1 px-1.5 py-0">
                      {purgeSummary.archived_sessions_count}
                    </Badge>
                  )}
                </Button>
              ) : null}
              <Button
                type="button"
                size="sm"
                variant={compareMode ? 'default' : 'outline'}
                onClick={() => setCompareMode(!compareMode)}
              >
                <GitCompare className="h-3.5 w-3.5" />
                {compareMode ? 'Exit Compare' : 'Start Compare'}
              </Button>
              {!compareMode && selectableSessions.length > 0 ? (
                <Button type="button" size="sm" variant="outline" onClick={handleSelectVisible}>
                  {allSelectableSelected ? 'Clear Selection' : 'Select Visible'}
                </Button>
              ) : null}
              {compareMode && compareSessionIdSet.size > 0 ? (
                <Button
                  type="button"
                  size="sm"
                  variant="ghost"
                  onClick={clearCompareSessionIds}
                >
                  Clear Selection
                </Button>
              ) : null}
            </div>
          </div>
        </div>

        <SessionFilters />

        {compareMode ? (
          <Alert variant="info" className="flex flex-col gap-4 rounded-[1.15rem] lg:flex-row lg:items-center lg:justify-between">
            <div className="space-y-2">
              <AlertTitle>
                {compareSessionIdSet.size === 0
                  ? 'Compare mode is active'
                  : compareSessionIdSet.size === 1
                    ? 'Baseline selected'
                    : 'Comparison ready'}
              </AlertTitle>
              <AlertDescription>
                {compareSessionIdSet.size === 0
                  ? 'Start with the session you trust as the baseline, then pick a second session to explain what changed.'
                  : compareSessionIdSet.size === 1
                    ? `Baseline locked: ${compareBaseline?.label || 'Session A'}. Choose one more session for the side-by-side summary.`
                    : `Ready to compare ${compareBaseline?.label || 'Session A'} against ${compareCandidate?.label || 'Session B'}.`}
              </AlertDescription>
              <div className="flex flex-wrap gap-2">
                <Badge variant={compareBaseline ? 'info' : 'outline'}>
                  A: {compareBaseline?.label || 'Choose baseline'}
                </Badge>
                <Badge variant={compareCandidate ? 'info' : 'outline'}>
                  B: {compareCandidate?.label || 'Choose comparison'}
                </Badge>
              </div>
              {shouldOfferSuggestedBaseline && compareBaseline && suggestedBaseline ? (
                <div className="rounded-[0.95rem] border border-primary/25 bg-surface/50 px-4 py-3">
                  <p className="text-sm font-medium text-foreground">
                    Suggested baseline: {suggestedBaseline.session.label}
                  </p>
                  <p className="mt-1 text-sm leading-6 text-muted-foreground">
                    If {compareBaseline.label} is the run you want to explain, start from{' '}
                    {suggestedBaseline.session.label}. {suggestedBaseline.reason}
                  </p>
                </div>
              ) : null}
              {shouldOfferBaselineSwitch && compareCandidate && suggestedBaseline ? (
                <div className="rounded-[0.95rem] border border-border/70 bg-surface/50 px-4 py-3">
                  <p className="text-sm font-medium text-foreground">
                    Alternative baseline available
                  </p>
                  <p className="mt-1 text-sm leading-6 text-muted-foreground">
                    {suggestedBaseline.session.label} is a stronger heuristic match for{' '}
                    {compareCandidate.label}. {suggestedBaseline.reason}
                  </p>
                </div>
              ) : null}
            </div>
            <div className="flex flex-wrap gap-2">
              {shouldOfferSuggestedBaseline && compareBaseline && suggestedBaseline ? (
                <Button
                  type="button"
                  variant="outline"
                  onClick={() =>
                    setCompareSessionIds([
                      suggestedBaseline.session.sessionId,
                      compareBaseline.sessionId,
                    ])
                  }
                >
                  Use Suggested Baseline
                </Button>
              ) : null}
              {shouldOfferBaselineSwitch && compareCandidate && suggestedBaseline ? (
                <Button
                  type="button"
                  variant="outline"
                  onClick={() =>
                    setCompareSessionIds([
                      suggestedBaseline.session.sessionId,
                      compareCandidate.sessionId,
                    ])
                  }
                >
                  Switch Baseline
                </Button>
              ) : null}
              {canViewComparison ? (
                <Button
                  type="button"
                  variant="default"
                  onClick={() => window.location.assign(`/compare?a=${sessionA}&b=${sessionB}`)}
                >
                  <GitCompare className="h-4 w-4" />
                  View Comparison
                </Button>
              ) : null}
              {compareSessionIdSet.size > 0 ? (
                <Button type="button" variant="outline" onClick={clearCompareSessionIds}>
                  Clear Compare Pair
                </Button>
              ) : null}
            </div>
          </Alert>
        ) : null}

        {selectedSessions.length > 0 ? (
          <Alert variant="destructive" className="flex flex-col gap-3 rounded-[1.15rem] lg:flex-row lg:items-center lg:justify-between">
            <div>
              <AlertTitle>
                {pluralize(selectedSessions.length, 'session')} selected for deletion
              </AlertTitle>
              <AlertDescription>
                Scope: {buildFilterSummary(query)}
              </AlertDescription>
            </div>
            <div className="flex flex-wrap gap-2">
              <Button type="button" variant="outline" onClick={clearSessionSelection}>
                Clear Selection
              </Button>
              <Button type="button" variant="destructive" onClick={handleBulkDeleteClick}>
                <Trash2 className="mr-2 h-4 w-4" />
                Delete Selected
              </Button>
            </div>
          </Alert>
        ) : null}

        {loading ? (
          <LoadingState />
        ) : error ? (
          <ErrorState error={error} onRetry={onRetry} />
        ) : visibleSessions.length === 0 ? (
          <EmptyState
            icon={Network}
            title={filtered ? 'No sessions match the current filters' : 'No sessions available'}
            description={
              filtered
                ? 'Try broadening the search or filters.'
                : 'Start a research session to begin monitoring.'
            }
            action={
              filtered ? (
                <Button
                  type="button"
                  variant="outline"
                  onClick={() => setSessionListQuery(DEFAULT_SESSION_LIST_QUERY)}
                >
                  Clear Filters
                </Button>
              ) : undefined
            }
          />
        ) : (
          <>
            <div className="space-y-6">
              {sessionGroups.map((group) => (
                <div key={group.title} className="space-y-3">
                  <div className="flex items-center gap-3">
                    <group.icon className="h-5 w-5 text-primary" />
                    <div>
                      <h3 className="font-display text-[1.4rem] font-semibold uppercase tracking-[0.02em] text-foreground">
                        {group.title}
                      </h3>
                      <p className="text-sm text-muted-foreground">{group.description}</p>
                    </div>
                    <Badge variant={group.variant === 'warning' ? 'warning' : group.variant === 'success' ? 'success' : 'outline'} className="ml-auto">
                      {group.sessions.length}
                    </Badge>
                  </div>
                  <div className="space-y-3">
                    {group.sessions.map((session) => (
                      <SessionCard
                        key={session.sessionId}
                        session={session}
                        selected={selectedSessionIdSet.has(session.sessionId)}
                        compareMode={compareMode}
                        compareSelected={compareSessionIdSet.has(session.sessionId)}
                        compareSlot={session.sessionId === sessionA ? 'A' : session.sessionId === sessionB ? 'B' : null}
                        compareLocked={compareSessionIdSet.size >= 2}
                        onDelete={handleDeleteClick}
                        onToggleSelection={toggleSessionSelection}
                        onToggleCompare={toggleCompareSessionId}
                        onArchive={handleArchive}
                        onRestore={handleRestore}
                      />
                    ))}
                  </div>
                </div>
              ))}
            </div>

            {loadMoreError ? (
              <Alert variant="destructive" className="mt-4 rounded-[1.15rem]">
                <AlertDescription>{loadMoreError}</AlertDescription>
              </Alert>
            ) : null}

            {nextCursor && onLoadMore ? (
              <div className="flex justify-center pt-2">
                <Button type="button" variant="outline" onClick={onLoadMore} disabled={loadingMore}>
                  {loadingMore ? 'Loading More...' : 'Load More Sessions'}
                </Button>
              </div>
            ) : null}
          </>
        )}
      </div>

      <AlertDialog
        open={deleteDialog.mode !== null}
        onOpenChange={handleDialogClose}
        title={deleteDialog.mode === 'bulk' ? 'Delete Selected Sessions' : 'Delete Session'}
        description={renderDeleteDescription()}
        confirmLabel={
          deleteDialog.forceDelete
            ? 'Force Delete'
            : deleteDialog.mode === 'bulk'
              ? 'Delete Sessions'
              : 'Delete Session'
        }
        destructive
        onConfirm={handleDeleteConfirm}
        loading={deleteDialog.deleting}
        loadingLabel={deleteDialog.mode === 'bulk' ? 'Deleting Sessions...' : 'Deleting Session...'}
      />

      <AlertDialog
        open={showPurgeDialog}
        onOpenChange={setShowPurgeDialog}
        title="Session Lifecycle"
        description={
          <div className="space-y-4">
            <p>Manage archived sessions and storage cleanup.</p>
            
            {purgeSummary && (
              <div className="space-y-3">
                <div className="rounded-[0.8rem] border border-border/70 bg-surface/50 p-4 space-y-3">
                  <div className="flex items-center justify-between">
                    <span className="flex items-center gap-2">
                      <ShieldAlert className="h-4 w-4 text-warning" />
                      <span className="text-sm font-medium">Active Sessions</span>
                    </span>
                    <Badge variant="info">{purgeSummary.active_count}</Badge>
                  </div>
                  <div className="flex items-center justify-between">
                    <span className="flex items-center gap-2">
                      <Archive className="h-4 w-4 text-muted-foreground" />
                      <span className="text-sm font-medium">Archived</span>
                    </span>
                    <Badge variant="warning">{purgeSummary.archived_sessions_count}</Badge>
                  </div>
                  <div className="flex items-center justify-between">
                    <span className="flex items-center gap-2">
                      <Activity className="h-4 w-4 text-muted-foreground" />
                      <span className="text-sm font-medium">No Artifacts</span>
                    </span>
                    <Badge variant="outline">{purgeSummary.no_artifacts_count}</Badge>
                  </div>
                </div>

                {purgeSummary.recommendations.length > 0 && (
                  <div className="rounded-[0.8rem] border border-primary/20 bg-surface/30 p-4">
                    <p className="text-xs font-medium uppercase tracking-[0.14em] text-muted-foreground mb-2">
                      Recommendations
                    </p>
                    <ul className="space-y-2">
                      {purgeSummary.recommendations.map((rec, idx) => (
                        <li key={idx} className="flex items-center gap-2 text-sm">
                          <Sparkles className="h-3.5 w-3.5 text-primary shrink-0" />
                          <span>{rec.description}</span>
                        </li>
                      ))}
                    </ul>
                  </div>
                )}
              </div>
            )}

            <div className="flex flex-col gap-3 pt-2">
              <Button
                type="button"
                variant="outline"
                onClick={() => handlePurgeClick(true)}
                disabled={purgeLoading || !purgeSummary?.archived_sessions_count}
              >
                Preview Purge
              </Button>
              <Button
                type="button"
                variant="destructive"
                onClick={() => handlePurgeClick(false)}
                disabled={purgeLoading || !purgeSummary?.archived_sessions_count}
              >
                {purgeLoading ? 'Purging...' : 'Purge All Archived'}
              </Button>
            </div>

            <p className="text-xs text-muted-foreground">
              Active sessions are always protected from purge. This action cannot be undone.
            </p>
          </div>
        }
        confirmLabel=""
        cancelLabel="Close"
        onConfirm={() => {}}
      />
    </>
  );
}
