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
import { Button } from '@/components/ui/button';
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
    <article className="flex h-full flex-col rounded-lg border p-5">
      <div className="flex items-start justify-between gap-3">
        <div className="flex min-w-0 flex-1 items-start gap-3">
          <div className="mt-1 flex gap-2">
            {!compareMode ? (
              <label
                className="flex items-center"
                title={
                  session.active
                    ? 'Stop the active run before selecting this session for deletion.'
                    : 'Select session'
                }
              >
                <input
                  type="checkbox"
                  checked={selected}
                  disabled={session.active}
                  onChange={() => onToggleSelection(session.sessionId)}
                  className="h-4 w-4 rounded border-slate-300 text-red-600 focus:ring-red-500"
                  aria-label={`Select session ${session.label}`}
                />
              </label>
            ) : (
              <label className="flex items-center" title="Select for comparison">
                <input
                  type="checkbox"
                  checked={compareSelected}
                  onChange={() => onToggleCompare(session.sessionId)}
                  className="h-4 w-4 rounded border-blue-300 text-blue-600 focus:ring-blue-500"
                  aria-label={`Compare session ${session.label}`}
                />
              </label>
            )}
          </div>
          <div className="min-w-0 flex-1">
            <Link href={`/session/${session.sessionId}`} className="block">
              <h3 className="text-lg font-semibold leading-snug hover:text-blue-700">
                {session.label}
              </h3>
            </Link>
            <p className="mt-1 truncate text-xs font-mono text-muted-foreground">
              {session.sessionId}
            </p>
          </div>
        </div>
        {session.active ? (
          <span className="rounded-full bg-green-100 px-2 py-1 text-xs font-medium text-green-800">
            Live
          </span>
        ) : isArchived ? (
          <span className="rounded-full bg-amber-100 px-2 py-1 text-xs font-medium text-amber-800">
            Archived
          </span>
        ) : null}
      </div>

      {showsQuery ? (
        <p className="mt-4 text-sm text-muted-foreground">{session.query}</p>
      ) : null}

      <div className="mt-4 flex flex-wrap gap-2 text-xs">
        <span className="rounded-full bg-slate-100 px-2 py-1 text-slate-700">
          {formatDepth(session.depth)}
        </span>
        <span className="rounded-full bg-slate-100 px-2 py-1 text-slate-700">
          Payload {session.hasSessionPayload ? 'available' : 'missing'}
        </span>
        <span className="rounded-full bg-slate-100 px-2 py-1 text-slate-700">
          Report {session.hasReport ? 'available' : 'unavailable'}
        </span>
      </div>

      <div className="mt-4 space-y-2 text-sm">
        <div className="flex items-center gap-2">
          <Activity className="h-4 w-4" />
          <span className="text-muted-foreground">Status:</span>
          <span className="font-medium">{session.status}</span>
        </div>

        <div className="flex items-center gap-2">
          <Network className="h-4 w-4" />
          <span className="text-muted-foreground">Sources:</span>
          <span className="font-medium">{session.totalSources}</span>
        </div>

        <div className="flex items-center gap-2">
          <Cpu className="h-4 w-4" />
          <span className="text-muted-foreground">{timeLabel}:</span>
          <span className="font-medium">{formatTimestamp(timeValue)}</span>
        </div>
      </div>

      <div className="mt-5 flex flex-col gap-2 border-t pt-4 sm:flex-row">
        <Link
          href={`/session/${session.sessionId}`}
          className="inline-flex h-10 items-center justify-center rounded-md bg-primary px-4 text-sm font-medium text-primary-foreground hover:opacity-90"
        >
          <Play className="mr-2 h-4 w-4" />
          View Details
        </Link>
        {!session.active && !isArchived && onArchive ? (
          <Button
            variant="outline"
            onClick={() => onArchive(session)}
            title="Archive session"
          >
            <Archive className="mr-2 h-4 w-4" />
            Archive
          </Button>
        ) : null}
        {!session.active && isArchived && onRestore ? (
          <Button
            variant="outline"
            onClick={() => onRestore(session)}
            title="Restore archived session"
          >
            <ArchiveRestore className="mr-2 h-4 w-4" />
            Restore
          </Button>
        ) : null}
        <Button
          variant="outline"
          onClick={() => onDelete(session)}
          disabled={session.active}
          title={
            session.active
              ? 'Stop the active run before deleting this session.'
              : 'Delete session'
          }
        >
          <Trash2 className="mr-2 h-4 w-4" />
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
    <div className="space-y-4 rounded-lg border bg-slate-50/60 p-4">
      <div className="flex items-center gap-2 text-sm font-medium text-slate-700">
        <Filter className="h-4 w-4" />
        Filter Sessions
      </div>
      <div className="flex flex-col gap-3 lg:flex-row lg:items-end">
        <label className="flex-1">
          <span className="mb-1 block text-xs font-medium uppercase tracking-wide text-muted-foreground">
            Search
          </span>
          <div className="flex h-10 items-center rounded-md border bg-background px-3">
            <Search className="mr-2 h-4 w-4 text-muted-foreground" />
            <input
              type="search"
              value={query.search}
              onChange={(event) => setSessionListQuery({ search: event.target.value })}
              placeholder="Query, label, or session ID"
              className="w-full bg-transparent text-sm outline-none"
            />
          </div>
        </label>
        <Select
          label="Status"
          value={query.status}
          options={sessionStatusOptions}
          onChange={(value) => setSessionListQuery({ status: value })}
        />
        <div className="flex min-w-[11rem] flex-col gap-2">
          <span className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
            Activity
          </span>
          <Button
            type="button"
            variant={query.activeOnly ? 'default' : 'outline'}
            onClick={() => setSessionListQuery({ activeOnly: !query.activeOnly })}
          >
            {query.activeOnly ? 'Active Only' : 'All Sessions'}
          </Button>
        </div>
        {hasFilters ? (
          <Button
            type="button"
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
    <div className="flex min-h-48 items-center justify-center">
      <div className="h-12 w-12 animate-spin rounded-full border-b-2 border-blue-600" />
    </div>
  );
}

function ErrorState({ error, onRetry }: { error: string; onRetry?: () => void }) {
  return (
    <div className="rounded-lg border border-red-200 bg-red-50 p-6">
      <div className="flex items-start gap-3">
        <AlertCircle className="mt-0.5 h-5 w-5 text-red-600" />
        <div className="space-y-3">
          <div>
            <p className="font-medium text-red-800">Failed to load sessions</p>
            <p className="text-sm text-red-700">{error}</p>
          </div>
          {onRetry ? (
            <Button onClick={onRetry} type="button" variant="outline">
              Retry
            </Button>
          ) : null}
        </div>
      </div>
    </div>
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
    <div className="py-12 text-center">
      <Network className="mx-auto mb-4 h-16 w-16 text-muted-foreground" />
      <p className="mb-2 text-xl text-muted-foreground">
        {filtered ? 'No sessions match the current filters' : 'No sessions available'}
      </p>
      <p className="text-muted-foreground">
        {filtered
          ? 'Try broadening the search or filters.'
          : 'Start a research session to begin monitoring.'}
      </p>
      {filtered ? (
        <Button className="mt-4" type="button" variant="outline" onClick={onClearFilters}>
          Clear Filters
        </Button>
      ) : null}
    </div>
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
              <p className="font-mono text-xs text-slate-500">{session.sessionId}</p>
            </>
          ) : (
            <>
              <p>
                This will permanently delete <span className="font-medium">{session.label}</span> and
                all associated telemetry, report, and analytics history.
              </p>
              <p className="font-mono text-xs text-slate-500">{session.sessionId}</p>
              {deleteError ? (
                <p className="rounded-md border border-red-200 bg-red-50 px-3 py-2 text-red-700">
                  {deleteError}
                </p>
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
          <p className="rounded-md border border-amber-200 bg-amber-50 px-3 py-2 text-amber-700">
            Some selected sessions are currently active. Force deleting will stop any running
            processes before removing their telemetry, report, and analytics history.
          </p>
        ) : null}
        <p>
          This will permanently delete {pluralize(sessionCount, 'selected session')} from{' '}
          <span className="font-medium">{buildFilterSummary(query)}</span>.
        </p>
        <ul className="space-y-2 rounded-md border bg-slate-50 px-3 py-3 text-slate-700">
          {previewSessions.map((session) => (
            <li key={session.sessionId} className="flex flex-col gap-1">
              <span className="font-medium">{session.label}</span>
              <span className="font-mono text-xs text-slate-500">{session.sessionId}</span>
            </li>
          ))}
          {remainingCount > 0 ? (
            <li className="text-xs uppercase tracking-wide text-slate-500">
              And {pluralize(remainingCount, 'more session')}
            </li>
          ) : null}
        </ul>
        {deleteError ? (
          <p className="rounded-md border border-red-200 bg-red-50 px-3 py-2 text-red-700">
            {deleteError}
          </p>
        ) : (
          <p>This action cannot be undone.</p>
        )}
      </div>
    );
  };

  return (
    <>
      <div className="space-y-4">
        <div className="flex flex-col gap-2 sm:flex-row sm:items-end sm:justify-between">
          <div>
            <h2 className="text-2xl font-semibold">
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
              variant={compareMode ? 'default' : 'outline'}
              onClick={() => setCompareMode(!compareMode)}
            >
              <GitCompare className="mr-2 h-4 w-4" />
              Compare
            </Button>
            {!compareMode && selectableSessions.length > 0 ? (
              <Button type="button" variant="outline" onClick={handleSelectVisible}>
                {allSelectableSelected ? 'Clear Selection' : 'Select Visible'}
              </Button>
            ) : null}
            {compareMode && compareSessionIdSet.size > 0 ? (
              <Button
                type="button"
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
          <div className="flex flex-col gap-3 rounded-lg border border-blue-200 bg-blue-50/70 p-4 lg:flex-row lg:items-center lg:justify-between">
            <div>
              <p className="font-medium text-blue-900">
                2 sessions selected for comparison
              </p>
              <p className="text-sm text-blue-800">
                Ready to compare {sessions.find((s) => s.sessionId === sessionA)?.label || 'Session A'} vs {sessions.find((s) => s.sessionId === sessionB)?.label || 'Session B'}
              </p>
            </div>
            <Link href={`/compare?a=${sessionA}&b=${sessionB}`} className="inline-flex">
              <Button type="button" variant="default">
                <GitCompare className="mr-2 h-4 w-4" />
                View Comparison
              </Button>
            </Link>
          </div>
        ) : null}

        {selectedSessions.length > 0 ? (
          <div className="flex flex-col gap-3 rounded-lg border border-red-200 bg-red-50/70 p-4 lg:flex-row lg:items-center lg:justify-between">
            <div>
              <p className="font-medium text-red-900">
                {pluralize(selectedSessions.length, 'session')} selected for deletion
              </p>
              <p className="text-sm text-red-800">
                Scope: {buildFilterSummary(query)}
              </p>
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
          </div>
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
            <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
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
              <div className="rounded-md border border-red-200 bg-red-50 p-3 text-sm text-red-700">
                {loadMoreError}
              </div>
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
