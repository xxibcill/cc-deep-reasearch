'use client';

import { useState } from 'react';
import Link from 'next/link';
import { Activity, AlertCircle, Cpu, Network, Play, Trash2 } from 'lucide-react';

import { Session } from '@/types/telemetry';
import { Button } from '@/components/ui/button';
import { AlertDialog } from '@/components/ui/alert-dialog';
import { deleteSession } from '@/lib/api';
import useDashboardStore from '@/hooks/useDashboard';

interface SessionListProps {
  error?: string | null;
  loading: boolean;
  onRetry?: () => void;
  sessions: Session[];
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

interface DeleteDialogState {
  session: Session | null;
  deleting: boolean;
}

interface SessionCardProps {
  session: Session;
  onDelete: (session: Session) => void;
}

function SessionCard({ session, onDelete }: SessionCardProps) {
  const handleDeleteClick = (e: React.MouseEvent) => {
    e.preventDefault();
    e.stopPropagation();
    onDelete(session);
  };

  const timeLabel = session.completedAt ? 'Completed' : 'Last event';
  const timeValue = session.completedAt ?? session.lastEventAt;
  const showsQuery = session.query && session.query !== session.label;

  return (
    <div className="border rounded-lg p-6 hover:bg-accent transition-colors">
      <div className="flex items-start justify-between mb-4">
        <Link href={`/session/${session.sessionId}`} className="flex-1">
          <h3 className="font-semibold text-lg leading-snug">{session.label}</h3>
          <p className="mt-1 text-xs font-mono text-muted-foreground">{session.sessionId}</p>
        </Link>
        <div className="flex items-center gap-2">
          {session.active && (
            <span className="bg-green-100 text-green-800 text-xs px-2 py-1 rounded-full">Live</span>
          )}
          <Button
            variant="ghost"
            size="icon"
            onClick={handleDeleteClick}
            disabled={session.active}
            title={session.active ? 'Cannot delete active session' : 'Delete session'}
            className="text-muted-foreground hover:text-red-600 hover:bg-red-50"
          >
            <Trash2 className="h-4 w-4" />
          </Button>
        </div>
      </div>

      <Link href={`/session/${session.sessionId}`} className="block">
        {showsQuery ? <p className="mb-4 text-sm text-muted-foreground">{session.query}</p> : null}

        <div className="mb-4 flex flex-wrap gap-2 text-xs">
          <span className="rounded-full bg-slate-100 px-2 py-1 text-slate-700">{formatDepth(session.depth)}</span>
          <span className="rounded-full bg-slate-100 px-2 py-1 text-slate-700">
            Payload {session.hasSessionPayload ? 'available' : 'missing'}
          </span>
          <span className="rounded-full bg-slate-100 px-2 py-1 text-slate-700">
            Report {session.hasReport ? 'available' : 'unavailable'}
          </span>
        </div>

        <div className="space-y-2 text-sm">
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

        <div className="mt-4 pt-4 border-t">
          <span className="inline-flex items-center gap-2 text-blue-600 hover:text-blue-700 font-medium">
            <Play className="h-4 w-4" />
            View Details
          </span>
        </div>
      </Link>
    </div>
  );
}

function LoadingState() {
  return (
    <div className="flex min-h-48 items-center justify-center">
      <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600"></div>
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
            <p className="font-medium text-red-800">Failed to load recent sessions</p>
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

function EmptyState() {
  return (
    <div className="text-center py-12">
      <Network className="mx-auto h-16 w-16 mb-4 text-muted-foreground" />
      <p className="text-xl text-muted-foreground mb-4">No sessions available</p>
      <p className="text-muted-foreground">Start a research session to begin monitoring</p>
    </div>
  );
}

export function SessionList({ error, loading, onRetry, sessions }: SessionListProps) {
  const [deleteDialog, setDeleteDialog] = useState<DeleteDialogState>({ session: null, deleting: false });
  const [deleteError, setDeleteError] = useState<string | null>(null);
  const removeSession = useDashboardStore((state) => state.removeSession);

  const handleDeleteClick = (session: Session) => {
    setDeleteDialog({ session, deleting: false });
    setDeleteError(null);
  };

  const handleDeleteConfirm = async () => {
    if (!deleteDialog.session) return;

    setDeleteDialog((prev) => ({ ...prev, deleting: true }));
    setDeleteError(null);

    const result = await deleteSession(deleteDialog.session.sessionId);

    if (result.success) {
      removeSession(deleteDialog.session.sessionId);
      setDeleteDialog({ session: null, deleting: false });
    } else {
      setDeleteError(result.error || 'Failed to delete session');
      setDeleteDialog((prev) => ({ ...prev, deleting: false }));
    }
  };

  const handleDialogClose = (open: boolean) => {
    if (!open) {
      setDeleteDialog({ session: null, deleting: false });
      setDeleteError(null);
    }
  };

  return (
    <>
      {loading ? (
        <LoadingState />
      ) : error ? (
        <ErrorState error={error} onRetry={onRetry} />
      ) : sessions.length === 0 ? (
        <EmptyState />
      ) : (
        <div className="space-y-4">
          <h2 className="text-2xl font-semibold mb-4">Research Sessions</h2>
          <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
            {sessions.map((session) => (
              <SessionCard key={session.sessionId} session={session} onDelete={handleDeleteClick} />
            ))}
          </div>
        </div>
      )}

      <AlertDialog
        open={deleteDialog.session !== null}
        onOpenChange={handleDialogClose}
        title="Delete Session"
        description={
          deleteError ||
          `This will permanently delete this session and all associated telemetry, report, and analytics history. This action cannot be undone.`
        }
        confirmLabel="Delete"
        destructive
        onConfirm={handleDeleteConfirm}
        loading={deleteDialog.deleting}
      />
    </>
  );
}
