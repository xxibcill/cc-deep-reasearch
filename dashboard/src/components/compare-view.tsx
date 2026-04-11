'use client'

import { useEffect, useMemo, useState } from 'react'
import Link from 'next/link'
import {
  AlertCircle,
  ArrowLeft,
  ArrowRight,
  ArrowUpRight,
  Compass,
  GitCompare,
  Sparkles,
} from 'lucide-react'

import { getSession, getSessions, getSessionPromptMetadata } from '@/lib/api'
import {
  buildCompareNarrative,
  computeCompareDeltas,
  describeBaselineFit,
  formatCountDelta,
  formatDurationDelta,
  getDeltaColor,
  suggestBaselineSessions,
  type BaselineSuggestion,
  type BaselineFit,
  type SessionPair,
} from '@/lib/compare-utils'
import { Session, SessionPromptMetadata } from '@/types/telemetry'
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'
import { Badge } from '@/components/ui/badge'
import { Button, buttonVariants } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { HelpCallout } from '@/components/ui/help-callout'
import { PromptDiffCard } from './compare-prompt-diff'

interface MetricValueProps {
  label: string
  value: string | number | null
  delta?: number | null
  formatter?: (value: number | null) => string
  tone?: 'default' | 'positive' | 'negative' | 'neutral'
}

function MetricValue({ label, value, delta, formatter, tone = 'default' }: MetricValueProps) {
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

function SessionCard({ session, title }: { session: Session | null; title: string }) {
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
            value={
              session.depth ? session.depth.charAt(0).toUpperCase() + session.depth.slice(1) : 'N/A'
            }
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
      </CardContent>
    </Card>
  )
}

function ComparisonContext({
  sessionB,
  baselineFit,
  suggestions,
}: {
  sessionB: Session | null
  baselineFit: BaselineFit
  suggestions: BaselineSuggestion[]
}) {
  const toneClasses: Record<BaselineFit['tone'], string> = {
    positive: 'border-success/25 bg-success-muted/18',
    negative: 'border-warning/25 bg-warning-muted/22',
    neutral: 'border-border/70 bg-surface/68',
  }

  return (
    <Card className="overflow-hidden">
      <CardHeader className="border-b border-border/70">
        <div className="space-y-2">
          <div className="flex items-center gap-2 text-sm text-primary">
            <Compass className="h-4 w-4" />
            <span className="font-display text-[0.86rem] uppercase tracking-[0.14em]">
              Comparison context
            </span>
          </div>
          <CardTitle className="text-[1.2rem]">{baselineFit.label}</CardTitle>
          <p className="text-sm leading-6 text-muted-foreground">{baselineFit.summary}</p>
        </div>
      </CardHeader>
      <CardContent className="space-y-4 pt-6">
        <div className={`rounded-[1rem] border p-4 ${toneClasses[baselineFit.tone]}`}>
          <p className="text-xs uppercase tracking-[0.16em] text-muted-foreground">
            Baseline check
          </p>
          <p className="mt-2 text-sm leading-6 text-foreground">
            The suggestions below only use explicit heuristics from recent sessions: same query,
            similar label, or the most recent successful run.
          </p>
        </div>

        {sessionB && suggestions.length > 0 ? (
          <div className="space-y-3">
            <p className="text-xs uppercase tracking-[0.16em] text-muted-foreground">
              Suggested baselines for Session B
            </p>
            <div className="space-y-3">
              {suggestions.map((suggestion) => (
                <div
                  key={suggestion.session.sessionId}
                  className="rounded-[1rem] border border-border/70 bg-surface/58 p-4"
                >
                  <div className="flex flex-wrap items-start justify-between gap-3">
                    <div className="space-y-2">
                      <div className="flex flex-wrap items-center gap-2">
                        <Badge variant="outline">{suggestion.badge}</Badge>
                        <Badge
                          variant={
                            suggestion.confidence === 'high'
                              ? 'success'
                              : suggestion.confidence === 'medium'
                                ? 'info'
                                : 'outline'
                          }
                        >
                          {suggestion.confidence} confidence
                        </Badge>
                      </div>
                      <p className="text-sm font-semibold text-foreground">
                        {suggestion.session.label}
                      </p>
                      <p className="text-sm leading-6 text-muted-foreground">
                        {suggestion.reason} {suggestion.detail}
                      </p>
                    </div>
                    <Link
                      href={`/compare?a=${suggestion.session.sessionId}&b=${sessionB.sessionId}`}
                      className="inline-flex"
                    >
                      <Button size="sm" variant="outline">
                        Use as baseline
                      </Button>
                    </Link>
                  </div>
                </div>
              ))}
            </div>
          </div>
        ) : (
          <div className="rounded-[0.95rem] border border-border/70 bg-surface/55 px-4 py-3 text-sm text-muted-foreground">
            No stronger baseline suggestion was found in the recent session list.
          </div>
        )}
      </CardContent>
    </Card>
  )
}

function DeltaColumn({
  pair,
  baselineFit,
  suggestions,
}: {
  pair: SessionPair
  baselineFit: BaselineFit
  suggestions: BaselineSuggestion[]
}) {
  const deltas = computeCompareDeltas(pair)
  const narrative = buildCompareNarrative(pair)
  const toneClasses: Record<'positive' | 'negative' | 'neutral', string> = {
    positive: 'border-success/25 bg-success-muted/20',
    negative: 'border-warning/25 bg-warning-muted/25',
    neutral: 'border-border/70 bg-surface/68',
  }
  const assessmentVariant =
    narrative.assessment === 'improved'
      ? 'success'
      : narrative.assessment === 'regressed'
        ? 'warning'
        : narrative.assessment === 'stable'
          ? 'outline'
          : 'info'
  const baselineVariant =
    baselineFit.tone === 'positive'
      ? 'success'
      : baselineFit.tone === 'negative'
        ? 'warning'
        : 'outline'

  return (
    <div className="space-y-5">
      <Card className="overflow-hidden">
        <CardHeader className="border-b border-border/70">
          <div className="space-y-3">
            <div className="flex flex-wrap items-center gap-2 text-sm text-primary">
              <GitCompare className="h-4 w-4" />
              <span className="font-display text-[0.86rem] uppercase tracking-[0.14em]">
                Operator summary
              </span>
            </div>
            <div className="flex flex-wrap gap-2">
              <Badge variant={assessmentVariant}>{narrative.assessmentLabel}</Badge>
              <Badge variant={baselineVariant}>{baselineFit.label}</Badge>
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

          <div className="space-y-2 border-t border-border/70 pt-4">
            <p className="text-xs uppercase tracking-[0.16em] text-muted-foreground">
              Inspect next
            </p>
            <div className="space-y-3">
              {narrative.nextSteps.map((step) => (
                <div
                  key={`${step.title}-${step.href}`}
                  className="rounded-[0.95rem] border border-border/70 bg-surface/55 px-4 py-3"
                >
                  <div className="flex flex-wrap items-center justify-between gap-3">
                    <div>
                      <p className="text-sm font-medium text-foreground">{step.title}</p>
                      <p className="mt-1 text-sm leading-6 text-muted-foreground">{step.detail}</p>
                    </div>
                    <Link
                      href={step.href}
                      className={buttonVariants({ size: 'sm', variant: 'outline' })}
                    >
                      Open
                    </Link>
                  </div>
                </div>
              ))}
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

      <ComparisonContext
        sessionB={pair.sessionB}
        baselineFit={baselineFit}
        suggestions={suggestions}
      />
    </div>
  )
}

interface CompareViewProps {
  sessionIdA: string
  sessionIdB: string
}

export function CompareView({ sessionIdA, sessionIdB }: CompareViewProps) {
  const [sessionA, setSessionA] = useState<Session | null>(null)
  const [sessionB, setSessionB] = useState<Session | null>(null)
  const [sessionAPromptMetadata, setSessionAPromptMetadata] = useState<
    SessionPromptMetadata | undefined
  >()
  const [sessionBPromptMetadata, setSessionBPromptMetadata] = useState<
    SessionPromptMetadata | undefined
  >()
  const [recentSessions, setRecentSessions] = useState<Session[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    async function loadSessions() {
      setLoading(true)
      setError(null)

      try {
        const [resultA, resultB, recentResult] = await Promise.allSettled([
          getSession(sessionIdA),
          getSession(sessionIdB),
          getSessions({ limit: 50 }),
        ])

        if (resultA.status === 'rejected' || resultB.status === 'rejected') {
          throw new Error('Failed to load sessions')
        }

        setSessionA(resultA.value.session)
        setSessionB(resultB.value.session)

        const [promptA, promptB] = await Promise.allSettled([
          getSessionPromptMetadata(sessionIdA),
          getSessionPromptMetadata(sessionIdB),
        ])
        if (promptA.status === 'fulfilled') {
          setSessionAPromptMetadata(promptA.value)
        }
        if (promptB.status === 'fulfilled') {
          setSessionBPromptMetadata(promptB.value)
        }

        if (recentResult.status === 'fulfilled') {
          setRecentSessions(recentResult.value.sessions)
        } else {
          setRecentSessions([])
        }
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Failed to load sessions')
      } finally {
        setLoading(false)
      }
    }
    // eslint-disable-next-line @typescript-eslint/no-floating-promises
    void loadSessions() // intentionally discard promise - error handling is done inside the function
  }, [sessionIdA, sessionIdB])

  const pair: SessionPair = { sessionA, sessionB }
  const rankedBaselines = useMemo(
    () => suggestBaselineSessions(sessionB, recentSessions, { limit: 3 }),
    [recentSessions, sessionB],
  )
  const baselineSuggestions = useMemo(
    () =>
      rankedBaselines.filter((suggestion) => suggestion.session.sessionId !== sessionA?.sessionId),
    [rankedBaselines, sessionA?.sessionId],
  )
  const baselineFit = useMemo(
    () => describeBaselineFit(sessionA, sessionB, rankedBaselines),
    [rankedBaselines, sessionA, sessionB],
  )

  if (loading) {
    return (
      <Card className="overflow-hidden">
        <CardHeader className="gap-4 border-b border-border/70">
          <div className="flex flex-wrap items-center gap-2">
            <Badge variant="info">Compare route</Badge>
            <Badge variant="outline">Loading comparison</Badge>
          </div>
          <div>
            <CardTitle as="h1" className="text-[1.75rem]">
              Session Comparison
            </CardTitle>
            <p className="mt-2  text-sm leading-6 text-muted-foreground">
              Loading the baseline, comparison session, and recent-run context.
            </p>
          </div>
        </CardHeader>
        <CardContent className="flex min-h-72 items-center justify-center pt-6">
          <div className="w-full space-y-6">
            <div className="flex justify-center">
              <div className="h-12 w-12 animate-spin rounded-full border-b-2 border-primary" />
            </div>
            <div className="grid gap-4 xl:grid-cols-[minmax(0,1fr)_minmax(24rem,1.05fr)_minmax(0,1fr)]">
              <Card className="border-dashed border-border/60 bg-surface/45">
                <CardHeader>
                  <CardTitle className="text-base">Session A · Baseline</CardTitle>
                </CardHeader>
              </Card>
              <Card className="border-dashed border-border/60 bg-surface/45">
                <CardHeader>
                  <CardTitle className="text-base">Operator summary</CardTitle>
                  <p className="text-xs uppercase tracking-[0.16em] text-muted-foreground">
                    Material changes
                  </p>
                </CardHeader>
              </Card>
              <Card className="border-dashed border-border/60 bg-surface/45">
                <CardHeader>
                  <CardTitle className="text-base">Session B · Comparison</CardTitle>
                </CardHeader>
              </Card>
            </div>
          </div>
        </CardContent>
      </Card>
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
      <HelpCallout
        id="compare-mode"
        title="Compare mode"
        content="Select two sessions to see deltas in duration, sources, events, and failures. The baseline context panel suggests which past run to compare against."
      />
      <Card className="overflow-hidden">
        <CardHeader className="gap-4 border-b border-border/70">
          <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
            <div className="space-y-3">
              <div className="flex flex-wrap items-center gap-2">
                <Badge variant="info">Compare route</Badge>
                <Badge variant="outline">B minus A deltas</Badge>
                <Badge variant="outline">
                  <Sparkles className="mr-1.5 h-3.5 w-3.5" />
                  Baseline suggestions enabled
                </Badge>
              </div>
              <div>
                <CardTitle as="h1" className="text-[1.75rem]">
                  Session Comparison
                </CardTitle>
                <p className="mt-2  text-sm leading-6 text-muted-foreground">
                  Compare a baseline session against a second run without decoding raw telemetry by
                  hand first. This view now scores the baseline context, summarizes likely impact,
                  and points to the next inspection path.
                </p>
              </div>
            </div>
            <Link href="/" className={buttonVariants({ variant: 'outline', size: 'sm' })}>
              <ArrowLeft className="mr-1.5 h-3.5 w-3.5" />
              Back to Sessions
            </Link>
          </div>
        </CardHeader>
        <CardContent className="flex flex-wrap items-center gap-2 pt-6">
          <Badge variant="outline">A: {sessionA?.label || 'Unknown'}</Badge>
          <Badge variant="outline">B: {sessionB?.label || 'Unknown'}</Badge>
        </CardContent>
      </Card>

      <div className="grid grid-cols-1 gap-5 xl:grid-cols-[minmax(0,1fr)_minmax(24rem,1.05fr)_minmax(0,1fr)]">
        <SessionCard session={sessionA} title="Session A · Baseline" />
        <DeltaColumn pair={pair} baselineFit={baselineFit} suggestions={baselineSuggestions} />
        <SessionCard session={sessionB} title="Session B · Comparison" />
      </div>

      {(sessionAPromptMetadata || sessionBPromptMetadata) && (
        <PromptDiffCard
          sessionA={sessionAPromptMetadata}
          sessionB={sessionBPromptMetadata}
          sessionALabel={sessionA?.label || 'Session A'}
          sessionBLabel={sessionB?.label || 'Session B'}
        />
      )}

      <footer className="flex flex-wrap justify-center gap-3 border-t border-border/70 pt-4">
        <Link
          href={`/session/${sessionIdA}`}
          className={buttonVariants({ variant: 'outline', size: 'sm' })}
        >
          <ArrowLeft className="mr-1.5 h-3.5 w-3.5" />
          View Session A Details
        </Link>
        <Link
          href={`/session/${sessionIdB}`}
          className={buttonVariants({ variant: 'outline', size: 'sm' })}
        >
          View Session B Details
          <ArrowRight className="ml-1.5 h-3.5 w-3.5" />
        </Link>
      </footer>
    </div>
  )
}
