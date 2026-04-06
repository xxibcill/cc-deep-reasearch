'use client'

import { useEffect, useState } from 'react'
import Link from 'next/link'
import { AlertCircle, ArrowLeft, ArrowRight, ArrowUpRight, GitCompare } from 'lucide-react'

import { getSession } from '@/lib/api'
import {
  buildCompareNarrative,
  computeCompareDeltas,
  formatCountDelta,
  formatDurationDelta,
  getDeltaColor,
  type SessionPair,
} from '@/lib/compare-utils'
import { Session } from '@/types/telemetry'
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'

interface MetricValueProps {
  label: string
  value: string | number | null
  delta?: number | null
  formatter?: (value: number | null) => string
  tone?: 'default' | 'positive' | 'negative' | 'neutral'
}

function MetricValue({
  label,
  value,
  delta,
  formatter,
  tone = 'default',
}: MetricValueProps) {
  const displayValue = value == null ? 'N/A' : value
  const displayDelta = delta == null ? null : formatter ? formatter(delta) : formatCountDelta(delta)
  const deltaColor =
    tone === 'positive'
      ? 'text-success'
      : tone === 'negative'
        ? 'text-warning'
        : delta == null
          ? ''
          : getDeltaColor(delta)

  return (
    <div className="space-y-1 rounded-[1rem] border border-border/70 bg-surface/68 p-4">
      <p className="text-xs uppercase tracking-wide text-muted-foreground">{label}</p>
      <p className="text-base font-semibold text-foreground">{displayValue}</p>
      {displayDelta != null ? <p className={`text-sm ${deltaColor}`}>{displayDelta}</p> : null}
    </div>
  )
}

function SessionCard({
  session,
  title,
}: {
  session: Session | null
  title: string
}) {
  if (!session) {
    return (
      <Card className="border-dashed">
        <CardHeader>
          <CardTitle className="text-[1.1rem]">{title}</CardTitle>
        </CardHeader>
        <CardContent className="flex min-h-48 items-center justify-center text-muted-foreground">
          <div className="text-center">
            <AlertCircle className="mx-auto mb-2 h-8 w-8" />
            <p>No session selected</p>
          </div>
        </CardContent>
      </Card>
    )
  }

  const statusVariant =
    session.status === 'failed' || session.status === 'interrupted'
      ? 'warning'
      : session.active
        ? 'info'
        : session.hasReport
          ? 'success'
          : 'outline'

  return (
    <Card className="overflow-hidden">
      <CardHeader className="border-b border-border/70">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <CardTitle className="text-[1.1rem]">{title}</CardTitle>
          <Badge variant={statusVariant}>{session.active ? 'Active' : session.status}</Badge>
        </div>
      </CardHeader>
      <CardContent className="space-y-4 pt-6">
        <div>
          <Link
            href={`/session/${session.sessionId}`}
            className="inline-flex items-center gap-2 text-base font-semibold text-primary hover:underline"
          >
            {session.label}
            <ArrowUpRight className="h-3.5 w-3.5" />
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
          <MetricValue label="Status" value={session.status} />
          <MetricValue
            label="Depth"
            value={session.depth ? session.depth.charAt(0).toUpperCase() + session.depth.slice(1) : 'N/A'}
          />
          <MetricValue label="Sources" value={session.totalSources} />
          <MetricValue
            label="Duration"
            value={session.totalTimeMs ? `${(session.totalTimeMs / 1000).toFixed(2)}s` : null}
          />
          <MetricValue label="Events" value={session.eventCount} />
          <MetricValue
            label="Last Event"
            value={session.lastEventAt ? new Date(session.lastEventAt).toLocaleString() : null}
          />
        </div>

        <div className="flex flex-wrap gap-1.5 text-xs">
          <span
            className={`rounded-full px-2 py-0.5 ${
              session.active
                ? 'border border-success/30 bg-success-muted/30 text-success'
                : 'border border-border bg-surface-raised text-muted-foreground'
            }`}
          >
            {session.active ? 'Active' : 'Inactive'}
          </span>
          <span
            className={`rounded-full px-2 py-0.5 ${
              session.hasSessionPayload
                ? 'border border-success/30 bg-success-muted/30 text-success'
                : 'border border-border bg-surface-raised text-muted-foreground'
            }`}
          >
            Payload {session.hasSessionPayload ? 'Available' : 'Missing'}
          </span>
          <span
            className={`rounded-full px-2 py-0.5 ${
              session.hasReport
                ? 'border border-success/30 bg-success-muted/30 text-success'
                : 'border border-border bg-surface-raised text-muted-foreground'
            }`}
          >
            Report {session.hasReport ? 'Available' : 'Unavailable'}
          </span>
        </div>
      </CardContent>
    </Card>
  )
}

function DeltaColumn({ pair }: { pair: SessionPair }) {
  const deltas = computeCompareDeltas(pair)
  const narrative = buildCompareNarrative(pair)
  const toneClasses: Record<'positive' | 'negative' | 'neutral', string> = {
    positive: 'border-success/25 bg-success-muted/20',
    negative: 'border-warning/25 bg-warning-muted/25',
    neutral: 'border-border/70 bg-surface/68',
  }

  return (
    <Card className="overflow-hidden">
      <CardHeader className="border-b border-border/70">
        <div className="space-y-2">
          <div className="flex items-center gap-2 text-sm text-primary">
            <GitCompare className="h-4 w-4" />
            <span className="font-display text-[0.86rem] uppercase tracking-[0.14em]">
              Operator summary
            </span>
          </div>
          <CardTitle className="text-[1.2rem]">{narrative.headline}</CardTitle>
          <p className="text-sm leading-6 text-muted-foreground">{narrative.summary}</p>
        </div>
      </CardHeader>
      <CardContent className="space-y-5 pt-6">
        <div className="grid gap-3">
          {narrative.insights.map((insight) => (
            <div
              key={insight.title}
              className={`rounded-[1rem] border p-4 ${toneClasses[insight.tone]}`}
            >
              <p className="text-xs uppercase tracking-[0.16em] text-muted-foreground">
                {insight.title}
              </p>
              <p className="mt-2 text-sm font-medium text-foreground">{insight.summary}</p>
              <p className="mt-1 text-sm leading-6 text-muted-foreground">{insight.detail}</p>
            </div>
          ))}
        </div>

        <div className="space-y-3">
          <p className="text-xs uppercase tracking-[0.16em] text-muted-foreground">
            Raw deltas (B - A)
          </p>
          <div className="grid gap-3 sm:grid-cols-2">
            <MetricValue
              label="Duration"
              value={null}
              delta={deltas.durationDelta}
              formatter={formatDurationDelta}
              tone={
                deltas.durationDelta != null && deltas.durationDelta < 0
                  ? 'positive'
                  : deltas.durationDelta != null && deltas.durationDelta > 0
                    ? 'negative'
                    : 'neutral'
              }
            />
            <MetricValue
              label="Sources"
              value={null}
              delta={deltas.sourceCountDelta}
              tone={
                deltas.sourceCountDelta != null && deltas.sourceCountDelta > 0
                  ? 'positive'
                  : deltas.sourceCountDelta != null && deltas.sourceCountDelta < 0
                    ? 'negative'
                    : 'neutral'
              }
            />
            <MetricValue label="Events" value={null} delta={deltas.eventCountDelta} />
            <MetricValue
              label="Failures"
              value={null}
              delta={deltas.failureCountDelta}
              tone={
                deltas.failureCountDelta != null && deltas.failureCountDelta > 0
                  ? 'negative'
                  : deltas.failureCountDelta != null && deltas.failureCountDelta < 0
                    ? 'positive'
                    : 'neutral'
              }
            />
          </div>
        </div>

        {narrative.changes.length > 0 ? (
          <div className="space-y-2 border-t border-border/70 pt-4">
            <p className="text-xs uppercase tracking-[0.16em] text-muted-foreground">
              Material changes
            </p>
            <ul className="space-y-2 text-sm text-foreground">
              {narrative.changes.map((reason, idx) => (
                <li
                  key={`${reason}-${idx}`}
                  className="rounded-[0.9rem] border border-border/70 bg-surface/55 px-3 py-2"
                >
                  {reason}
                </li>
              ))}
            </ul>
          </div>
        ) : (
          <div className="rounded-[0.95rem] border border-border/70 bg-surface/55 px-4 py-3 text-sm text-muted-foreground">
            No material status or artifact changes were detected beyond the numeric deltas above.
          </div>
        )}
      </CardContent>
    </Card>
  )
}

interface CompareViewProps {
  sessionIdA: string
  sessionIdB: string
}

export function CompareView({ sessionIdA, sessionIdB }: CompareViewProps) {
  const [sessionA, setSessionA] = useState<Session | null>(null)
  const [sessionB, setSessionB] = useState<Session | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    async function loadSessions() {
      setLoading(true)
      setError(null)
      try {
        const [resultA, resultB] = await Promise.all([getSession(sessionIdA), getSession(sessionIdB)])
        setSessionA(resultA.session)
        setSessionB(resultB.session)
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Failed to load sessions')
      } finally {
        setLoading(false)
      }
    }
    void loadSessions()
  }, [sessionIdA, sessionIdB])

  const pair: SessionPair = { sessionA, sessionB }

  if (loading) {
    return (
      <div className="flex min-h-96 items-center justify-center">
        <div className="h-12 w-12 animate-spin rounded-full border-b-2 border-primary" />
      </div>
    )
  }

  if (error) {
    return (
      <Alert variant="destructive" className="rounded-[1.2rem]">
        <div className="flex items-start gap-3">
          <AlertCircle className="mt-0.5 h-5 w-5 text-destructive" />
          <div>
            <AlertTitle>Failed to load sessions</AlertTitle>
            <AlertDescription>{error}</AlertDescription>
          </div>
        </div>
      </Alert>
    )
  }

  return (
    <div className="space-y-5">
      <Card className="overflow-hidden">
        <CardHeader className="gap-4 border-b border-border/70">
          <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
            <div className="space-y-3">
              <div className="flex flex-wrap items-center gap-2">
                <Badge variant="info">Compare route</Badge>
                <Badge variant="outline">B minus A deltas</Badge>
              </div>
              <div>
                <CardTitle className="text-[1.75rem]">Session Comparison</CardTitle>
                <p className="mt-2 max-w-3xl text-sm leading-6 text-muted-foreground">
                  Compare a baseline session against a second run without decoding raw telemetry by
                  hand first. The middle column summarizes operator-relevant changes before you open
                  either workspace.
                </p>
              </div>
            </div>
            <Link href="/">
              <Button variant="outline" size="sm">
                <ArrowLeft className="mr-1.5 h-3.5 w-3.5" />
                Back to Sessions
              </Button>
            </Link>
          </div>
        </CardHeader>
        <CardContent className="flex flex-wrap items-center gap-2 pt-6">
          <Badge variant="outline">A: {sessionA?.label || 'Unknown'}</Badge>
          <Badge variant="outline">B: {sessionB?.label || 'Unknown'}</Badge>
        </CardContent>
      </Card>

      <div className="grid grid-cols-1 gap-5 xl:grid-cols-[minmax(0,1fr)_minmax(22rem,0.95fr)_minmax(0,1fr)]">
        <SessionCard session={sessionA} title="Session A · Baseline" />
        <DeltaColumn pair={pair} />
        <SessionCard session={sessionB} title="Session B · Comparison" />
      </div>

      <footer className="flex flex-wrap justify-center gap-3 border-t border-border/70 pt-4">
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
  )
}
