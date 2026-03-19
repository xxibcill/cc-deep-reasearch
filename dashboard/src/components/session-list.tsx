'use client';

import { useState } from 'react';
import Link from 'next/link';
import {
  Activity,
  AlertCircle,
  Cpu,
  Filter,
  Network,
  Play,
  Search,
  Trash2,
} from 'lucide-react';

import { Session } from '@/types/telemetry';
import { AlertDialog } from '@/components/ui/alert-dialog';
import { Button } from '@/components/ui/button';
import { Select } from '@/components/ui/select';
import useDashboardStore from '@/hooks/useDashboard';
import { deleteSession } from '@/lib/api';

const sessionStatusOptions = ['completed', 'failed', 'interrupted', 'running', 'unknown'];

interface SessionListProps {
  error?: string | null;
  loading: boolean;
  loadingMore: boolean;
  loadMoreError?: string | null;
  nextCursor: string | null;
  onLoadMore?: () => void;
  onRetry?: () => void;
  sessions: Session[];
  total: number;
}

interface DeleteDialogState {
  session: Session | null;
  deleting: boolean;
}

interface SessionCardProps {
  session: Session;
  onDelete: (session: Session) => void;
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

function SessionCard({ session, onDelete }: SessionCardProps) {
  const timeLabel = session.completedAt ? 'Completed' : 'Last event';
  const timeValue = session.completedAt ?? session.lastEventAt;
  const showsQuery = session.query && session.query !== session.label;

  return (
    <article className="flex h-full flex-col rounded-lg border p-5">
      <div className="flex items-start justify-between gap-3">
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
        {session.active ? (
          <span className="rounded-full bg-green-100 px-2 py-1 text-xs font-medium text-green-800">
            Live
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
        <Button
          variant="outline"
          onClick={() => onDelete(session)}
          disabled={session.active}
          title={session.active ? 'Stop the active run before deleting this session.' : 'Delete session'}
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
        {filtered ? 'Try broadening the search or filters.' : 'Start a research session to begin monitoring.'}
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
  sessions,
  total,
}: SessionListProps) {
  const [deleteDialog, setDeleteDialog] = useState<DeleteDialogState>({
    session: null,
    deleting: false,
  });
  const [deleteError, setDeleteError] = useState<string | null>(null);
  const query = useDashboardStore((state) => state.sessionListQuery);
  const removeSession = useDashboardStore((state) => state.removeSession);
  const setSessionListQuery = useDashboardStore((state) => state.setSessionListQuery);
  const filtered =
    query.search.trim().length > 0 || query.status.length > 0 || query.activeOnly;

  const handleDeleteClick = (session: Session) => {
    setDeleteDialog({ session, deleting: false });
    setDeleteError(null);
  };

  const handleDeleteConfirm = async () => {
    if (!deleteDialog.session) {
      return;
    }

    setDeleteDialog((previous) => ({ ...previous, deleting: true }));
    setDeleteError(null);

    const result = await deleteSession(deleteDialog.session.sessionId);

    if (result.success) {
      removeSession(deleteDialog.session.sessionId);
      setDeleteDialog({ session: null, deleting: false });
      return;
    }

    setDeleteError(result.error || 'Failed to delete session');
    setDeleteDialog((previous) => ({ ...previous, deleting: false }));
  };

  const handleDialogClose = (open: boolean) => {
    if (open) {
      return;
    }
    setDeleteDialog({ session: null, deleting: false });
    setDeleteError(null);
  };

  return (
    <>
      <div className="space-y-4">
        <div className="flex flex-col gap-2 sm:flex-row sm:items-end sm:justify-between">
          <div>
            <h2 className="text-2xl font-semibold">Research Sessions</h2>
            <p className="text-sm text-muted-foreground">
              Showing {sessions.length} of {total} matching sessions
            </p>
          </div>
        </div>

        <SessionFilters />

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
                  onDelete={handleDeleteClick}
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
        open={deleteDialog.session !== null}
        onOpenChange={handleDialogClose}
        title="Delete Session"
        description={
          deleteError ||
          'This will permanently delete this session and all associated telemetry, report, and analytics history. This action cannot be undone.'
        }
        confirmLabel="Delete"
        destructive
        onConfirm={handleDeleteConfirm}
        loading={deleteDialog.deleting}
      />
    </>
  );
}
