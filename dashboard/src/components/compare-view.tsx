'use client';

import { useEffect, useState } from 'react';
import Link from 'next/link';
import {
  Activity,
  AlertCircle,
  ArrowLeft,
  ArrowRight,
  Cpu,
  Network,
} from 'lucide-react';

import { Session } from '@/types/telemetry';
import { Button } from '@/components/ui/button';
import { getSession } from '@/lib/api';
import {
  computeCompareDeltas,
  formatCountDelta,
  formatDurationDelta,
  getDeltaColor,
  type SessionPair,
} from '@/lib/compare-utils';

interface MetricValueProps {
  label: string;
  value: string | number | null;
  delta?: number | null;
  formatter?: (value: number | null) => string;
}

function MetricValue({ label, value, delta, formatter }: MetricValueProps) {
  const displayValue = value == null ? 'N/A' : value;
  const displayDelta = delta == null ? null : formatter ? formatter(delta) : formatCountDelta(delta);
  const deltaColor = delta == null ? '' : getDeltaColor(delta);

  return (
    <div className="space-y-0.5">
      <p className="text-xs uppercase tracking-wide text-muted-foreground">{label}</p>
      <p className="text-base font-semibold">{displayValue}</p>
      {displayDelta != null ? (
        <p className={`text-sm ${deltaColor}`}>{displayDelta}</p>
      ) : null}
    </div>
  );
}

function SessionCard({
  session,
  title,
  borderColor = 'border-slate-200',
}: {
  session: Session | null;
  title: string;
  borderColor?: string;
}) {
  if (!session) {
    return (
      <div className={`rounded-lg border ${borderColor} border-dashed bg-slate-50 p-5`}>
        <h3 className="mb-3 text-base font-semibold">{title}</h3>
        <div className="flex min-h-48 items-center justify-center text-muted-foreground">
          <div className="text-center">
            <AlertCircle className="mx-auto mb-2 h-8 w-8" />
            <p>No session selected</p>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className={`rounded-lg border ${borderColor} bg-white p-5`}>
      <h3 className="mb-3 text-base font-semibold">{title}</h3>
      <div className="space-y-3">
        <div>
          <Link
            href={`/session/${session.sessionId}`}
            className="text-base font-semibold text-blue-600 hover:underline"
          >
            {session.label}
          </Link>
          <p className="mt-0.5 text-xs font-mono text-muted-foreground">{session.sessionId}</p>
        </div>

        {session.query ? (
          <div>
            <p className="text-xs uppercase tracking-wide text-muted-foreground">Query</p>
            <p className="mt-0.5 text-sm line-clamp-2">{session.query}</p>
          </div>
        ) : null}

        <div className="grid grid-cols-2 gap-3">
          <MetricValue
            label="Status"
            value={session.status}
          />
          <MetricValue
            label="Depth"
            value={session.depth ? session.depth.charAt(0).toUpperCase() + session.depth.slice(1) : 'N/A'}
          />
          <MetricValue
            label="Sources"
            value={session.totalSources}
          />
          <MetricValue
            label="Duration"
            value={session.totalTimeMs ? `${(session.totalTimeMs / 1000).toFixed(2)}s` : null}
          />
          <MetricValue
            label="Events"
            value={session.eventCount}
          />
          <MetricValue
            label="Last Event"
            value={session.lastEventAt ? new Date(session.lastEventAt).toLocaleString() : null}
          />
        </div>

        <div className="flex flex-wrap gap-1.5 text-xs">
          <span className={`rounded-full px-2 py-0.5 ${
            session.active ? 'bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-100' : 'bg-slate-100 text-slate-700 dark:bg-slate-800 dark:text-slate-300'
          }`}>
            {session.active ? 'Active' : 'Inactive'}
          </span>
          <span className={`rounded-full px-2 py-0.5 ${
            session.hasSessionPayload ? 'bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-100' : 'bg-slate-100 text-slate-700 dark:bg-slate-800 dark:text-slate-300'
          }`}>
            Payload {session.hasSessionPayload ? 'Available' : 'Missing'}
          </span>
          <span className={`rounded-full px-2 py-0.5 ${
            session.hasReport ? 'bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-100' : 'bg-slate-100 text-slate-700 dark:bg-slate-800 dark:text-slate-300'
          }`}>
            Report {session.hasReport ? 'Available' : 'Unavailable'}
          </span>
        </div>
      </div>
    </div>
  );
}

function DeltaColumn({ pair }: { pair: SessionPair }) {
  const deltas = computeCompareDeltas(pair);

  return (
    <div className="flex min-h-[320px] items-center justify-center">
      <div className="w-full space-y-4 rounded-lg border border-slate-200 bg-slate-50 p-5">
        <h4 className="text-center text-sm font-semibold text-muted-foreground">Deltas (B - A)</h4>

        <div className="space-y-3">
          <MetricValue
            label="Duration"
            value={null}
            delta={deltas.durationDelta}
            formatter={formatDurationDelta}
          />
          <MetricValue
            label="Sources"
            value={null}
            delta={deltas.sourceCountDelta}
          />
          <MetricValue
            label="Events"
            value={null}
            delta={deltas.tokenDelta}
          />
          <MetricValue
            label="Failures"
            value={null}
            delta={deltas.failureCountDelta}
          />

          {deltas.degradedReasonDelta && deltas.degradedReasonDelta.length > 0 ? (
            <div>
              <p className="text-xs uppercase tracking-wide text-muted-foreground">Changes</p>
              <ul className="mt-1.5 space-y-1 text-sm">
                {deltas.degradedReasonDelta.map((reason, idx) => (
                  <li key={idx} className="text-amber-600">{reason}</li>
                ))}
              </ul>
            </div>
          ) : null}
        </div>

        <div className="pt-3 text-center border-t">
          <p className="text-xs text-muted-foreground">
            {deltas.durationDelta === null ? 'Complete data needed' : 'Comparison ready'}
          </p>
        </div>
      </div>
    </div>
  );
}

interface CompareViewProps {
  sessionIdA: string;
  sessionIdB: string;
}

export function CompareView({ sessionIdA, sessionIdB }: CompareViewProps) {
  const [sessionA, setSessionA] = useState<Session | null>(null);
  const [sessionB, setSessionB] = useState<Session | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    async function loadSessions() {
      setLoading(true);
      setError(null);
      try {
        const [resultA, resultB] = await Promise.all([
          getSession(sessionIdA),
          getSession(sessionIdB),
        ]);
        setSessionA(resultA.session);
        setSessionB(resultB.session);
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Failed to load sessions');
      } finally {
        setLoading(false);
      }
    }
    loadSessions();
  }, [sessionIdA, sessionIdB]);

  const pair: SessionPair = { sessionA, sessionB };

  if (loading) {
    return (
      <div className="flex min-h-96 items-center justify-center">
        <div className="h-12 w-12 animate-spin rounded-full border-b-2 border-blue-600" />
      </div>
    );
  }

  if (error) {
    return (
      <div className="rounded-lg border border-red-200 bg-red-50 p-6">
        <div className="flex items-start gap-3">
          <AlertCircle className="mt-0.5 h-5 w-5 text-red-600" />
          <div>
            <p className="font-medium text-red-800">Failed to load sessions</p>
            <p className="text-sm text-red-700">{error}</p>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-5">
      <header className="flex items-center gap-4 border-b pb-4">
        <Link href="/">
          <Button variant="outline" size="sm">
            <ArrowLeft className="mr-1.5 h-3.5 w-3.5" />
            Back to Sessions
          </Button>
        </Link>
        <div className="flex-1 min-w-0">
          <h1 className="text-xl font-semibold truncate">Session Comparison</h1>
          <p className="text-sm text-muted-foreground truncate">
            Comparing {sessionA?.label || 'Unknown'} vs {sessionB?.label || 'Unknown'}
          </p>
        </div>
      </header>

      <div className="grid grid-cols-1 gap-5 lg:grid-cols-3">
        <SessionCard session={sessionA} title="Session A" borderColor="border-blue-200" />
        <DeltaColumn pair={pair} />
        <SessionCard session={sessionB} title="Session B" borderColor="border-purple-200" />
      </div>

      <footer className="flex justify-center gap-3 border-t pt-4">
        <Link href={`/session/${sessionIdA}`}>
          <Button variant="outline" size="sm">
            <ArrowLeft className="mr-1.5 h-3.5 w-3.5" />
            View Session A Details
          </Button>
        </Link>
        <Link href={`/session/${sessionIdB}`}>
          <Button variant="outline" size="sm">
            View Session B Details
            <ArrowRight className="ml-1.5 h-3.5 w-3.5" />
          </Button>
        </Link>
      </footer>
    </div>
  );
}
