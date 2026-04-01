'use client';

import { useState } from 'react';
import Link from 'next/link';
import {
  Activity,
  AlertCircle,
  Archive,
  ArchiveRestore,
  GitCompare,
  Cpu,
  Filter,
  Network,
  Play,
  Search,
  Trash2,
} from 'lucide-react';

import { BulkSessionDeleteResponse, Session, SessionListQueryState } from '@/types/telemetry';
import { AlertDialog } from '@/components/ui/alert-dialog';
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Checkbox } from '@/components/ui/checkbox';
import { Input } from '@/components/ui/input';
import { Select } from '@/components/ui/select';
import useDashboardStore from '@/hooks/useDashboard';
import {
  archiveSession,
  bulkDeleteSessions,
  deleteSession,
  getApiErrorMessage,
  restoreSession,
} from '@/lib/api';

const sessionStatusOptions = ['completed', 'failed', 'interrupted', 'running', 'unknown'];

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

function SessionCard({
  session,
  selected,
  compareMode,
  compareSelected,
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

  return (
    <article className="flex h-full flex-col rounded-lg border p-4">
      <div className="flex items-start justify-between gap-2">
        <div className="flex min-w-0 flex-1 items-start gap-2.5">
          <div className="pt-0.5">
            {!compareMode ? (
              <label
                className="flex items-center"
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
              <label className="flex items-center" title="Select for comparison">
                <Checkbox
                  checked={compareSelected}
                  onCheckedChange={() => onToggleCompare(session.sessionId)}
                  aria-label={`Compare session ${session.label}`}
                />
              </label>
            )}
          </div>
          <div className="min-w-0 flex-1">
            <Link href={`/session/${session.sessionId}`} className="block">
              <h3 className="text-base font-semibold leading-snug hover:text-blue-700 truncate">
                {session.label}
              </h3>
            </Link>
            <p className="mt-0.5 truncate text-xs font-mono text-muted-foreground">
              {session.sessionId}
            </p>
          </div>
        </div>
        {session.active ? (
          <Badge variant="success">Live</Badge>
        ) : isArchived ? (
          <Badge variant="warning">Archived</Badge>
        ) : null}
      </div>

      {showsQuery ? (
        <p className="mt-3 text-sm text-muted-foreground line-clamp-2">{session.query}</p>
      ) : null}

      <div className="mt-3 flex flex-wrap gap-1.5 text-xs">
        <Badge variant="secondary">{formatDepth(session.depth)}</Badge>
        <Badge variant="secondary">Payload {session.hasSessionPayload ? 'available' : 'missing'}</Badge>
        <Badge variant="secondary">Report {session.hasReport ? 'available' : 'unavailable'}</Badge>
      </div>

      <div className="mt-3 space-y-1.5 text-sm">
        <div className="flex items-center gap-2">
          <Activity className="h-3.5 w-3.5 text-muted-foreground shrink-0" />
          <span className="text-muted-foreground min-w-[60px]">Status:</span>
          <span className="font-medium">{session.status}</span>
        </div>

        <div className="flex items-center gap-2">
          <Network className="h-3.5 w-3.5 text-muted-foreground shrink-0" />
          <span className="text-muted-foreground min-w-[60px]">Sources:</span>
          <span className="font-medium">{session.totalSources}</span>
        </div>

        <div className="flex items-center gap-2">
          <Cpu className="h-3.5 w-3.5 text-muted-foreground shrink-0" />
          <span className="text-muted-foreground min-w-[60px]">{timeLabel}:</span>
          <span className="font-medium truncate">{formatTimestamp(timeValue)}</span>
        </div>
      </div>

      <div className="mt-auto pt-4 flex flex-wrap gap-2 border-t">
        <Link
          href={`/session/${session.sessionId}`}
          className="inline-flex h-8 items-center justify-center rounded-md bg-primary px-3 text-sm font-medium text-primary-foreground hover:opacity-90"
        >
          <Play className="mr-1.5 h-3.5 w-3.5" />
          View Details
        </Link>
        {!session.active && !isArchived && onArchive ? (
          <Button
            variant="outline"
            size="sm"
            onClick={() => onArchive(session)}
            title="Archive session"
          >
            <Archive className="mr-1.5 h-3.5 w-3.5" />
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
            <ArchiveRestore className="mr-1.5 h-3.5 w-3.5" />
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
          <Trash2 className="mr-1.5 h-3.5 w-3.5" />
          Delete
        </Button>
      </div>
    </article>
  );
}

function SessionFilters() {
  const query = useDashboardStore((state) => state.sessionListQuery);
  const setSessionListQuery = useDashboardStore((state) => state.setSessionListQuery);
  const hasFilters =
    query.search.trim().length > 0 || query.status.length > 0 || query.activeOnly;

  return (
    <div className="space-y-3 rounded-lg border bg-slate-50/60 p-4">
      <div className="flex items-center gap-2 text-sm font-medium text-slate-700">
        <Filter className="h-4 w-4" />
        Filter Sessions
      </div>
      <div className="flex flex-col gap-3 lg:flex-row lg:items-end">
        <label className="flex-1">
          <span className="mb-1.5 block text-xs font-medium uppercase tracking-wide text-muted-foreground">
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
            />
          </div>
        </label>
        <Select
          label="Status"
          value={query.status}
          options={sessionStatusOptions}
          onChange={(value) => setSessionListQuery({ status: value })}
        />
        <div className="flex min-w-[11rem] flex-col gap-1.5">
          <span className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
            Activity
          </span>
          <Button
            type="button"
            size="sm"
            variant={query.activeOnly ? 'default' : 'outline'}
            onClick={() => setSessionListQuery({ activeOnly: !query.activeOnly })}
          >
            {query.activeOnly ? 'Active Only' : 'All Sessions'}
          </Button>
        </div>
        {hasFilters ? (
          <Button
            type="button"
            size="sm"
            variant="ghost"
            onClick={() => setSessionListQuery({ search: '', status: '', activeOnly: false })}
          >
            Clear
          </Button>
        ) : null}
      </div>
    </div>
  );
}

function LoadingState() {
  return (
    <Card className="flex min-h-48 items-center justify-center">
      <CardContent className="flex items-center gap-3">
        <div className="h-12 w-12 animate-spin rounded-full border-b-2 border-primary" />
        <span className="text-muted-foreground">Loading sessions...</span>
      </CardContent>
    </Card>
  );
}

function ErrorState({ error, onRetry }: { error: string; onRetry?: () => void }) {
  return (
    <Alert variant="destructive">
      <div className="flex items-start gap-3">
        <AlertCircle className="h-5 w-5 shrink-0 mt-0.5" />
        <div className="space-y-2">
          <AlertTitle>Failed to load sessions</AlertTitle>
          <AlertDescription>{error}</AlertDescription>
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

function EmptyState({
  filtered,
  onClearFilters,
}: {
  filtered: boolean;
  onClearFilters: () => void;
}) {
  return (
    <Card className="py-12">
      <CardContent className="text-center">
        <Network className="mx-auto mb-4 h-16 w-16 text-muted-foreground" />
        <CardTitle className="text-xl text-muted-foreground">
          {filtered ? 'No sessions match the current filters' : 'No sessions available'}
        </CardTitle>
        <p className="mt-2 text-muted-foreground">
          {filtered
            ? 'Try broadening the search or filters.'
            : 'Start a research session to begin monitoring.'}
        </p>
        {filtered ? (
          <Button className="mt-4" type="button" variant="outline" onClick={onClearFilters}>
            Clear Filters
          </Button>
        ) : null}
      </CardContent>
    </Card>
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
  const [deleteDialog, setDeleteDialog] = useState<DeleteDialogState>({
    mode: null,
    sessions: [],
    deleting: false,
    forceDelete: false,
  });
  const [deleteError, setDeleteError] = useState<string | null>(null);
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
  const toggleCompareSessionId = useDashboardStore((state) => state.toggleCompareSessionId);
  const clearCompareSessionIds = useDashboardStore((state) => state.clearCompareSessionIds);
  const filtered =
    query.search.trim().length > 0 || query.status.length > 0 || query.activeOnly;

  // Compare mode state
  const compareSessionIdSet = new Set(compareSessionIds.filter(Boolean) as string[]);
  const canViewComparison = compareSessionIdSet.size === 2;
  const [sessionA, sessionB] = compareSessionIds;

  const selectedSessionIdSet = new Set(selectedSessionIds);
  const selectableSessions = sessions.filter((session) => !session.active);
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
      refreshSessions();
    }
  };

  const handleRestore = async (session: Session) => {
    const result = await restoreSession(session.sessionId);
    if (result.success) {
      refreshSessions();
    }
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
    } catch (requestError) {
      setDeleteError(
        getApiErrorMessage(requestError, 'Failed to delete the selected sessions')
      );
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
              <p className="rounded-md border border-amber-200 bg-amber-50 px-3 py-2 text-amber-700">
                This session is currently active. Force deleting will stop the running process.
              </p>
              <p>
                This will permanently delete <span className="font-medium">{session.label}</span> and
                all associated telemetry, report, and analytics history.
              </p>
              <p className="font-mono text-xs text-slate-600">{session.sessionId}</p>
            </>
          ) : (
            <>
              <p>
                This will permanently delete <span className="font-medium">{session.label}</span> and
                all associated telemetry, report, and analytics history.
              </p>
              <p className="font-mono text-xs text-slate-600">{session.sessionId}</p>
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
        <ul className="space-y-2 rounded-md border bg-slate-50 px-3 py-3 text-slate-700">
          {previewSessions.map((session) => (
            <li key={session.sessionId} className="flex flex-col gap-1">
              <span className="font-medium">{session.label}</span>
              <span className="font-mono text-xs text-slate-600">{session.sessionId}</span>
            </li>
          ))}
          {remainingCount > 0 ? (
            <li className="text-xs uppercase tracking-wide text-slate-600">
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

  return (
    <>
      <div className="space-y-4">
        <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <h2 className="text-xl font-semibold">
              {compareMode ? 'Select Sessions to Compare' : 'Research Sessions'}
            </h2>
            <p className="text-sm text-muted-foreground">
              {compareMode
                ? `Select up to 2 sessions (${compareSessionIdSet.size}/2 selected)`
                : `Showing ${sessions.length} of ${total} matching sessions`}
            </p>
          </div>
          <div className="flex gap-2">
            <Button
              type="button"
              size="sm"
              variant={compareMode ? 'default' : 'outline'}
              onClick={() => setCompareMode(!compareMode)}
            >
              <GitCompare className="mr-1.5 h-3.5 w-3.5" />
              Compare
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

        <SessionFilters />

        {compareMode && canViewComparison ? (
          <Alert variant="info" className="flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
            <div>
              <AlertTitle>
                2 sessions selected for comparison
              </AlertTitle>
              <AlertDescription>
                Ready to compare {sessions.find((s) => s.sessionId === sessionA)?.label || 'Session A'} vs {sessions.find((s) => s.sessionId === sessionB)?.label || 'Session B'}
              </AlertDescription>
            </div>
            <Link href={`/compare?a=${sessionA}&b=${sessionB}`} className="inline-flex">
              <Button type="button" variant="default">
                <GitCompare className="mr-2 h-4 w-4" />
                View Comparison
              </Button>
            </Link>
          </Alert>
        ) : null}

        {selectedSessions.length > 0 ? (
          <Alert variant="destructive" className="flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
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
        ) : sessions.length === 0 ? (
          <EmptyState
            filtered={filtered}
            onClearFilters={() =>
              setSessionListQuery({ search: '', status: '', activeOnly: false })
            }
          />
        ) : (
          <>
            <div className="grid gap-4 sm:grid-cols-2">
              {sessions.map((session) => (
                <SessionCard
                  key={session.sessionId}
                  session={session}
                  selected={selectedSessionIdSet.has(session.sessionId)}
                  compareMode={compareMode}
                  compareSelected={compareSessionIdSet.has(session.sessionId)}
                  onDelete={handleDeleteClick}
                  onToggleSelection={toggleSessionSelection}
                  onToggleCompare={toggleCompareSessionId}
                  onArchive={handleArchive}
                  onRestore={handleRestore}
                />
              ))}
            </div>

            {loadMoreError ? (
              <Alert variant="destructive" className="mt-4">
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
    </>
  );
}
