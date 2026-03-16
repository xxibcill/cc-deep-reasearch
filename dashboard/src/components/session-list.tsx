import Link from 'next/link';
import { Activity, Cpu, Network, Play } from 'lucide-react';

import { Session } from '@/types/telemetry';

interface SessionListProps {
  loading: boolean;
  sessions: Session[];
}

function formatTimestamp(value: string | null): string {
  if (!value) {
    return 'Unknown';
  }

  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? value : date.toLocaleString();
}

function SessionCard({ session }: { session: Session }) {
  return (
    <Link href={`/session/${session.sessionId}`} className="block">
      <div className="border rounded-lg p-6 hover:bg-accent transition-colors cursor-pointer">
        <div className="flex items-start justify-between mb-4">
          <h3 className="font-semibold text-lg">{session.sessionId.slice(0, 8)}</h3>
          {session.active && (
            <span className="bg-green-100 text-green-800 text-xs px-2 py-1 rounded-full">Live</span>
          )}
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
            <span className="text-muted-foreground">Last event:</span>
            <span className="font-medium">{formatTimestamp(session.lastEventAt)}</span>
          </div>
        </div>

        <div className="mt-4 pt-4 border-t">
          <span className="inline-flex items-center gap-2 text-blue-600 hover:text-blue-700 font-medium">
            <Play className="h-4 w-4" />
            View Details
          </span>
        </div>
      </div>
    </Link>
  );
}

function LoadingState() {
  return (
    <div className="flex items-center justify-center min-h-screen">
      <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600"></div>
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

export function SessionList({ loading, sessions }: SessionListProps) {
  if (loading) {
    return <LoadingState />;
  }

  if (sessions.length === 0) {
    return <EmptyState />;
  }

  return (
    <div className="space-y-4">
      <h2 className="text-2xl font-semibold mb-4">Research Sessions</h2>
      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
        {sessions.map((session) => (
          <SessionCard key={session.sessionId} session={session} />
        ))}
      </div>
    </div>
  );
}
