import { Session } from '@/types/telemetry'

export interface CompareDeltas {
  durationDelta: number | null
  sourceCountDelta: number | null
  eventCountDelta: number | null
  routeDelta: Record<string, number> | null
  degradedReasonDelta: string[] | null
  failureCountDelta: number | null
}

export interface SessionPair {
  sessionA: Session | null
  sessionB: Session | null
}

export interface CompareInsight {
  title: string
  summary: string
  detail: string
  tone: 'positive' | 'negative' | 'neutral'
}

export interface CompareNextStep {
  title: string
  detail: string
  href: string
}

export interface CompareNarrative {
  assessment: 'improved' | 'regressed' | 'mixed' | 'stable' | 'inconclusive'
  assessmentLabel: string
  headline: string
  summary: string
  changes: string[]
  insights: CompareInsight[]
  nextSteps: CompareNextStep[]
}

export interface BaselineSuggestion {
  session: Session
  score: number
  confidence: 'high' | 'medium' | 'low'
  category: 'same_query' | 'similar_label' | 'recent_success'
  badge: string
  reason: string
  detail: string
}

export interface BaselineFit {
  tone: 'positive' | 'negative' | 'neutral'
  label: string
  summary: string
}

function formatDelta(value: number): string {
  const sign = value > 0 ? '+' : ''
  return `${sign}${value}`
}

function formatDepthLabel(depth: string | null): string {
  if (!depth) {
    return 'Unknown'
  }
  return depth.charAt(0).toUpperCase() + depth.slice(1)
}

function formatDurationAbs(ms: number): string {
  const absMs = Math.abs(ms)
  if (absMs < 1000) {
    return `${absMs} ms`
  }
  if (absMs < 60000) {
    return `${(absMs / 1000).toFixed(absMs >= 10000 ? 0 : 1)} s`
  }
  return `${(absMs / 60000).toFixed(absMs >= 600000 ? 0 : 1)} min`
}

function normalizeText(value: string | null | undefined): string {
  return (value ?? '')
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, ' ')
    .trim()
    .replace(/\s+/g, ' ')
}

function tokenize(value: string | null | undefined): string[] {
  return normalizeText(value)
    .split(' ')
    .map((token) => token.trim())
    .filter((token) => token.length >= 4)
}

function tokenOverlap(left: string | null | undefined, right: string | null | undefined): number {
  const leftTokens = new Set(tokenize(left))
  const rightTokens = new Set(tokenize(right))

  if (leftTokens.size === 0 || rightTokens.size === 0) {
    return 0
  }

  let overlap = 0
  for (const token of leftTokens) {
    if (rightTokens.has(token)) {
      overlap += 1
    }
  }

  return overlap / Math.max(leftTokens.size, rightTokens.size)
}

function isSuccessfulSession(session: Session): boolean {
  return !session.active && session.status === 'completed'
}

function getSessionTimestamp(session: Session): number {
  const rawValue = session.completedAt ?? session.lastEventAt ?? session.createdAt
  if (!rawValue) {
    return 0
  }

  const timestamp = Date.parse(rawValue)
  return Number.isFinite(timestamp) ? timestamp : 0
}

function getAssessment(pair: SessionPair, deltas: CompareDeltas): CompareNarrative['assessment'] {
  const { sessionA, sessionB } = pair

  if (!sessionA || !sessionB) {
    return 'inconclusive'
  }

  const outcomeImproved =
    (sessionA.status === 'failed' || sessionA.status === 'interrupted') &&
    sessionB.status === 'completed'
  const outcomeRegressed =
    sessionA.status === 'completed' &&
    (sessionB.status === 'failed' || sessionB.status === 'interrupted')

  if (outcomeImproved) {
    return 'improved'
  }
  if (outcomeRegressed || (deltas.failureCountDelta != null && deltas.failureCountDelta > 0)) {
    return 'regressed'
  }

  const faster = deltas.durationDelta != null && deltas.durationDelta < 0
  const slower = deltas.durationDelta != null && deltas.durationDelta > 0
  const broader = deltas.sourceCountDelta != null && deltas.sourceCountDelta > 0
  const narrower = deltas.sourceCountDelta != null && deltas.sourceCountDelta < 0

  if ((faster && broader) || (faster && sessionB.hasReport && !sessionA.hasReport)) {
    return 'improved'
  }
  if ((slower && narrower) || (!sessionB.hasReport && sessionA.hasReport)) {
    return 'regressed'
  }
  if (faster || slower || broader || narrower || sessionA.depth !== sessionB.depth) {
    return 'mixed'
  }

  return 'stable'
}

export function computeCompareDeltas(pair: SessionPair): CompareDeltas {
  const { sessionA, sessionB } = pair

  if (!sessionA || !sessionB) {
    return {
      durationDelta: null,
      sourceCountDelta: null,
      eventCountDelta: null,
      routeDelta: null,
      degradedReasonDelta: null,
      failureCountDelta: null,
    }
  }

  const durationDelta =
    sessionA.totalTimeMs != null && sessionB.totalTimeMs != null
      ? sessionB.totalTimeMs - sessionA.totalTimeMs
      : null
  const sourceCountDelta = sessionB.totalSources - sessionA.totalSources
  const eventCountDelta =
    sessionA.eventCount != null && sessionB.eventCount != null
      ? sessionB.eventCount - sessionA.eventCount
      : null

  const routeDelta: Record<string, number> = {}
  if (sessionA.depth !== sessionB.depth) {
    routeDelta.depth_change =
      (sessionB.depth === 'deep' ? 1 : sessionB.depth === 'standard' ? 0 : -1) -
      (sessionA.depth === 'deep' ? 1 : sessionA.depth === 'standard' ? 0 : -1)
  }

  const degradedReasonDelta: string[] = []
  if (
    sessionA.status !== sessionB.status &&
    (sessionB.status === 'failed' || sessionB.status === 'interrupted')
  ) {
    degradedReasonDelta.push(`Status changed to ${sessionB.status}`)
  }

  const failureCountDelta =
    (sessionB.status === 'failed' ? 1 : 0) - (sessionA.status === 'failed' ? 1 : 0)

  return {
    durationDelta,
    sourceCountDelta,
    eventCountDelta,
    routeDelta: Object.keys(routeDelta).length > 0 ? routeDelta : null,
    degradedReasonDelta: degradedReasonDelta.length > 0 ? degradedReasonDelta : null,
    failureCountDelta,
  }
}

export function formatDurationDelta(ms: number | null): string {
  if (ms === null) return 'N/A'
  const sign = ms > 0 ? '+' : ''
  const seconds = (ms / 1000).toFixed(2)
  return `${sign}${seconds}s`
}

export function formatCountDelta(count: number | null): string {
  if (count === null) return 'N/A'
  return formatDelta(count)
}

export function getDeltaColor(value: number | null): string {
  if (value === null) return 'text-gray-600'
  if (value > 0) return 'text-red-600'
  if (value < 0) return 'text-green-600'
  return 'text-gray-600'
}

function buildNextSteps(pair: SessionPair, deltas: CompareDeltas): CompareNextStep[] {
  const { sessionA, sessionB } = pair

  if (!sessionA || !sessionB) {
    return []
  }

  const nextSteps: CompareNextStep[] = []

  if (sessionB.status === 'failed' || sessionB.status === 'interrupted') {
    nextSteps.push({
      title: 'Inspect Session B monitor',
      detail: 'Start with the live or historical monitor to pinpoint the failure phase and last successful handoff.',
      href: `/session/${sessionB.sessionId}/monitor`,
    })
  }

  if (sessionA.hasReport || sessionB.hasReport) {
    nextSteps.push({
      title: 'Compare report outputs',
      detail: 'Check whether the operator-facing result changed, not just the telemetry around it.',
      href: `/session/${sessionB.hasReport ? sessionB.sessionId : sessionA.sessionId}/report`,
    })
  }

  if (sessionA.depth !== sessionB.depth) {
    nextSteps.push({
      title: 'Review plan and depth changes',
      detail: `Depth shifted from ${formatDepthLabel(sessionA.depth)} to ${formatDepthLabel(sessionB.depth)}, so route and evidence differences may be intentional.`,
      href: `/session/${sessionB.sessionId}`,
    })
  }

  if (deltas.sourceCountDelta != null && deltas.sourceCountDelta < 0) {
    nextSteps.push({
      title: 'Check evidence collection gaps',
      detail: 'Session B finished with fewer sources. Verify whether provider failures, tighter filters, or earlier stop conditions reduced coverage.',
      href: `/session/${sessionB.sessionId}/monitor`,
    })
  }

  if (deltas.durationDelta != null && deltas.durationDelta > 0) {
    nextSteps.push({
      title: 'Trace the slower segments',
      detail: 'Use Session B telemetry to find where extra run time accumulated before drawing conclusions from the final status alone.',
      href: `/session/${sessionB.sessionId}/monitor`,
    })
  }

  if (nextSteps.length === 0) {
    nextSteps.push({
      title: 'Open both session overviews',
      detail: 'The delta profile is small, so verify prompts, report availability, and metadata before escalating.',
      href: `/session/${sessionB.sessionId}`,
    })
  }

  return nextSteps.slice(0, 3)
}

export function buildCompareNarrative(pair: SessionPair): CompareNarrative {
  const { sessionA, sessionB } = pair
  const deltas = computeCompareDeltas(pair)

  if (!sessionA || !sessionB) {
    return {
      assessment: 'inconclusive',
      assessmentLabel: 'Incomplete',
      headline: 'Comparison data is incomplete',
      summary: 'Both sessions must load before the operator summary can be calculated.',
      changes: [],
      insights: [],
      nextSteps: [],
    }
  }

  const assessment = getAssessment(pair, deltas)
  const outcomeImproved =
    (sessionA.status === 'failed' || sessionA.status === 'interrupted') &&
    sessionB.status === 'completed'
  const outcomeRegressed =
    sessionA.status === 'completed' &&
    (sessionB.status === 'failed' || sessionB.status === 'interrupted')

  const timingInsight: CompareInsight =
    deltas.durationDelta == null
      ? {
          title: 'Run time',
          summary: 'Timing data is incomplete.',
          detail: 'At least one session is missing total duration, so speed cannot be compared yet.',
          tone: 'neutral',
        }
      : deltas.durationDelta === 0
        ? {
            title: 'Run time',
            summary: 'Both runs finished in roughly the same time.',
            detail: 'Neither session created a meaningful speed difference.',
            tone: 'neutral',
          }
        : deltas.durationDelta < 0
          ? {
              title: 'Run time',
              summary: `Session B finished ${formatDurationAbs(deltas.durationDelta)} faster.`,
              detail: 'Faster completion is a positive signal only if evidence coverage and artifacts stayed intact.',
              tone: 'positive',
            }
          : {
              title: 'Run time',
              summary: `Session B took ${formatDurationAbs(deltas.durationDelta)} longer.`,
              detail: 'The comparison session spent more time completing the workflow than the baseline.',
              tone: 'negative',
            }

  const sourceInsight: CompareInsight =
    deltas.sourceCountDelta == null
      ? {
          title: 'Evidence breadth',
          summary: 'Source coverage is unavailable.',
          detail: 'At least one session is missing source-count data, so breadth could not be compared.',
          tone: 'neutral',
        }
      : deltas.sourceCountDelta === 0
      ? {
          title: 'Evidence breadth',
          summary: 'Source coverage stayed flat.',
          detail: 'Both runs collected the same number of sources, so any outcome shift came from something other than raw breadth.',
          tone: 'neutral',
        }
      : deltas.sourceCountDelta > 0
        ? {
            title: 'Evidence breadth',
            summary: `Session B pulled in ${deltas.sourceCountDelta} more sources.`,
            detail: 'Broader evidence can be an improvement, but only if the extra collection produced a better result instead of extra noise.',
            tone: 'positive',
          }
        : {
            title: 'Evidence breadth',
            summary: `Session B used ${Math.abs(deltas.sourceCountDelta)} fewer sources.`,
            detail: 'A narrower evidence set can indicate better focus or a regression in coverage. Inspect provider activity next.',
            tone: 'negative',
          }

  const activityInsight: CompareInsight =
    deltas.eventCountDelta == null
      ? {
          title: 'Telemetry footprint',
          summary: 'Event volume is unavailable.',
          detail: 'At least one session is missing event-count data.',
          tone: 'neutral',
        }
      : deltas.eventCountDelta === 0
        ? {
            title: 'Telemetry footprint',
            summary: 'Operator-visible activity stayed roughly flat.',
            detail: 'Both sessions emitted a similar amount of telemetry.',
            tone: 'neutral',
          }
        : deltas.eventCountDelta > 0
          ? {
              title: 'Telemetry footprint',
              summary: `Session B emitted ${deltas.eventCountDelta} more events.`,
              detail: 'Expect a denser trace. This is often worth inspecting when Session B also slowed down or changed depth.',
              tone: 'neutral',
            }
          : {
              title: 'Telemetry footprint',
              summary: `Session B emitted ${Math.abs(deltas.eventCountDelta)} fewer events.`,
              detail: 'The comparison run left behind a lighter telemetry trail. Confirm that the lighter trace was intentional.',
              tone: 'neutral',
            }

  let outcomeInsight: CompareInsight
  if (outcomeImproved) {
    outcomeInsight = {
      title: 'Outcome',
      summary: `Outcome improved from ${sessionA.status} to ${sessionB.status}.`,
      detail: 'The second session resolved a prior failure state and finished successfully.',
      tone: 'positive',
    }
  } else if (outcomeRegressed) {
    outcomeInsight = {
      title: 'Outcome',
      summary: `Outcome regressed from ${sessionA.status} to ${sessionB.status}.`,
      detail: 'Session B failed where the baseline had completed. Inspect the failing path before trusting any numeric gains.',
      tone: 'negative',
    }
  } else if (sessionA.hasReport !== sessionB.hasReport) {
    outcomeInsight = {
      title: 'Outcome',
      summary: sessionB.hasReport
        ? 'Session B produced a report artifact.'
        : 'Session B lost report readiness.',
      detail: sessionB.hasReport
        ? 'The comparison session ended with a reviewable report while the baseline did not.'
        : 'The baseline had a report-ready artifact that the comparison session did not preserve.',
      tone: sessionB.hasReport ? 'positive' : 'negative',
    }
  } else {
    outcomeInsight = {
      title: 'Outcome',
      summary: `Both runs ended in a ${sessionB.status} workflow state.`,
      detail: 'There was no major shift in terminal status or report availability.',
      tone: 'neutral',
    }
  }

  const changes: string[] = []
  if (sessionA.depth !== sessionB.depth) {
    changes.push(`Depth shifted from ${formatDepthLabel(sessionA.depth)} to ${formatDepthLabel(sessionB.depth)}.`)
  }
  if (sessionA.status !== sessionB.status) {
    changes.push(`Status moved from ${sessionA.status} to ${sessionB.status}.`)
  }
  if (sessionA.hasReport !== sessionB.hasReport) {
    changes.push(
      sessionB.hasReport
        ? 'Session B finished report-ready.'
        : 'Session B no longer has a rendered report.'
    )
  }
  if (sessionA.archived !== sessionB.archived) {
    changes.push(
      sessionB.archived
        ? 'Session B is archived while Session A remains in the active working set.'
        : 'Session B returned to the active working set.'
    )
  }
  if (deltas.degradedReasonDelta?.length) {
    changes.push(...deltas.degradedReasonDelta)
  }

  let headline = 'Session B changed the operator picture.'
  let assessmentLabel = 'Mixed'

  if (assessment === 'improved') {
    headline = 'Session B likely improved on the baseline.'
    assessmentLabel = 'Likely improved'
  } else if (assessment === 'regressed') {
    headline = 'Session B likely regressed against the baseline.'
    assessmentLabel = 'Likely regressed'
  } else if (assessment === 'stable') {
    headline = 'Session B looks materially similar to the baseline.'
    assessmentLabel = 'Mostly stable'
  } else if (assessment === 'inconclusive') {
    headline = 'The comparison is inconclusive.'
    assessmentLabel = 'Inconclusive'
  }

  return {
    assessment,
    assessmentLabel,
    headline,
    summary: `Baseline: ${sessionA.label}. Comparison: ${sessionB.label}. Use the signals below to decide whether Session B improved, regressed, or simply changed shape.`,
    changes,
    insights: [timingInsight, sourceInsight, activityInsight, outcomeInsight],
    nextSteps: buildNextSteps(pair, deltas),
  }
}

export function suggestBaselineSessions(
  target: Session | null,
  sessions: Session[],
  options: { limit?: number } = {}
): BaselineSuggestion[] {
  if (!target) {
    return []
  }

  const limit = options.limit ?? 3
  const normalizedTargetQuery = normalizeText(target.query)
  const normalizedTargetLabel = normalizeText(target.label)

  const candidates = sessions
    .filter((session) => session.sessionId !== target.sessionId)
    .filter(isSuccessfulSession)
    .map((session): BaselineSuggestion => {
      const queryMatch =
        normalizedTargetQuery.length > 0 && normalizeText(session.query) === normalizedTargetQuery
      const labelExact = normalizeText(session.label) === normalizedTargetLabel
      const labelOverlap = tokenOverlap(session.label, target.label)
      const queryOverlap = tokenOverlap(session.query, target.query)
      const similarLabel = labelExact || Math.max(labelOverlap, queryOverlap) >= 0.45
      const recencyBonus = getSessionTimestamp(session) / 1_000_000_000_000

      let score = recencyBonus
      let category: BaselineSuggestion['category'] = 'recent_success'
      let badge = 'Recent successful run'
      let reason = 'Most recent completed session'
      let detail = 'Useful when no stronger same-query or same-label baseline is available.'

      if (queryMatch) {
        score += 200
        category = 'same_query'
        badge = 'Same query baseline'
        reason = 'Matches the same normalized query as Session B.'
        detail = 'This is the strongest explicit heuristic available in the current session list.'
      } else if (similarLabel) {
        score += 120 + Math.max(labelOverlap, queryOverlap) * 25
        category = 'similar_label'
        badge = 'Similar label baseline'
        reason = 'Shares a similar label or query shape with Session B.'
        detail = 'Use this when exact query reuse is missing but the run appears to cover the same investigation.'
      } else {
        score += 40
      }

      if (session.depth === target.depth) {
        score += 8
      }
      if (session.hasReport) {
        score += 8
      }

      return {
        session,
        score,
        confidence:
          queryMatch || labelExact ? 'high' : similarLabel ? 'medium' : 'low',
        category,
        badge,
        reason,
        detail,
      }
    })
    .sort((left, right) => {
      if (right.score !== left.score) {
        return right.score - left.score
      }
      return getSessionTimestamp(right.session) - getSessionTimestamp(left.session)
    })

  const uniqueSuggestions: BaselineSuggestion[] = []
  const seenIds = new Set<string>()

  for (const candidate of candidates) {
    if (seenIds.has(candidate.session.sessionId)) {
      continue
    }
    seenIds.add(candidate.session.sessionId)
    uniqueSuggestions.push(candidate)
    if (uniqueSuggestions.length >= limit) {
      break
    }
  }

  return uniqueSuggestions
}

export function describeBaselineFit(
  baseline: Session | null,
  target: Session | null,
  suggestions: BaselineSuggestion[]
): BaselineFit {
  if (!baseline || !target) {
    return {
      tone: 'neutral',
      label: 'Baseline fit unknown',
      summary: 'Load both sessions before scoring the baseline context.',
    }
  }

  if (!isSuccessfulSession(baseline)) {
    return {
      tone: 'negative',
      label: 'Weak baseline',
      summary: 'The current baseline is not a completed successful run, so comparisons may blur regressions with baseline instability.',
    }
  }

  const topSuggestion = suggestions[0]
  if (!topSuggestion || topSuggestion.session.sessionId === baseline.sessionId) {
    return {
      tone: 'positive',
      label: 'Recommended baseline',
      summary: 'The current baseline lines up with the strongest available heuristic from recent sessions.',
    }
  }

  const normalizedBaselineQuery = normalizeText(baseline.query)
  const normalizedTargetQuery = normalizeText(target.query)
  const workable =
    (normalizedBaselineQuery.length > 0 && normalizedBaselineQuery === normalizedTargetQuery) ||
    tokenOverlap(baseline.label, target.label) >= 0.45 ||
    tokenOverlap(baseline.query, target.query) >= 0.45

  if (workable) {
    return {
      tone: 'neutral',
      label: 'Workable baseline',
      summary: `The current baseline is usable, but ${topSuggestion.session.label} is a slightly better heuristic match.`,
    }
  }

  return {
    tone: 'negative',
    label: 'Alternative baseline suggested',
    summary: `${topSuggestion.session.label} is a better same-query, same-label, or recent-success baseline for Session B.`,
  }
}
