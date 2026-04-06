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

export interface CompareNarrative {
  headline: string
  summary: string
  changes: string[]
  insights: CompareInsight[]
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
  if (sessionA.status !== sessionB.status && (sessionB.status === 'failed' || sessionB.status === 'interrupted')) {
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

export function buildCompareNarrative(pair: SessionPair): CompareNarrative {
  const { sessionA, sessionB } = pair
  const deltas = computeCompareDeltas(pair)

  if (!sessionA || !sessionB) {
    return {
      headline: 'Comparison data is incomplete',
      summary: 'Both sessions must load before the operator summary can be calculated.',
      changes: [],
      insights: [],
    }
  }

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
              detail: 'The comparison session reached a terminal state sooner than the baseline.',
              tone: 'positive',
            }
          : {
              title: 'Run time',
              summary: `Session B took ${formatDurationAbs(deltas.durationDelta)} longer.`,
              detail: 'The comparison session spent more time completing the workflow than the baseline.',
              tone: 'negative',
            }

  const sourceInsight: CompareInsight =
    deltas.sourceCountDelta === null
      ? {
          title: 'Evidence breadth',
          summary: 'Source-count data is unavailable.',
          detail: 'At least one session is missing source totals, so evidence breadth cannot be compared.',
          tone: 'neutral',
        }
      : deltas.sourceCountDelta === 0
      ? {
          title: 'Evidence breadth',
          summary: 'Both runs collected the same number of sources.',
          detail: 'Coverage stayed flat across the two sessions.',
          tone: 'neutral',
        }
      : deltas.sourceCountDelta > 0
        ? {
            title: 'Evidence breadth',
            summary: `Session B pulled in ${deltas.sourceCountDelta} more sources.`,
            detail: 'The comparison run cast a wider evidence net than the baseline.',
            tone: 'positive',
          }
        : {
            title: 'Evidence breadth',
            summary: `Session B used ${Math.abs(deltas.sourceCountDelta)} fewer sources.`,
            detail: 'The comparison run finished with a narrower evidence base than the baseline.',
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
            summary: 'Operator-visible activity was effectively unchanged.',
            detail: 'Both sessions emitted a similar amount of telemetry.',
            tone: 'neutral',
          }
        : deltas.eventCountDelta > 0
          ? {
              title: 'Telemetry footprint',
              summary: `Session B emitted ${deltas.eventCountDelta} more events.`,
              detail: 'Expect a denser trace and more operator detail in the comparison run.',
              tone: 'neutral',
            }
          : {
              title: 'Telemetry footprint',
              summary: `Session B emitted ${Math.abs(deltas.eventCountDelta)} fewer events.`,
              detail: 'The comparison run left behind a lighter telemetry trail.',
              tone: 'neutral',
            }

  let outcomeInsight: CompareInsight
  if (outcomeImproved) {
    outcomeInsight = {
      title: 'Outcome',
      summary: `Outcome improved from ${sessionA.status} to ${sessionB.status}.`,
      detail: 'The second session resolved a failure state and finished successfully.',
      tone: 'positive',
    }
  } else if (outcomeRegressed) {
    outcomeInsight = {
      title: 'Outcome',
      summary: `Outcome regressed from ${sessionA.status} to ${sessionB.status}.`,
      detail: 'The second session failed where the baseline had completed.',
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
    changes.push(sessionB.hasReport ? 'Session B finished report-ready.' : 'Session B no longer has a rendered report.')
  }
  if (sessionA.archived !== sessionB.archived) {
    changes.push(sessionB.archived ? 'Session B is archived while Session A remains in the active working set.' : 'Session B returned to the active working set.')
  }
  if (deltas.degradedReasonDelta?.length) {
    changes.push(...deltas.degradedReasonDelta)
  }

  let headline = 'Session B meaningfully changed the operator picture.'
  if (outcomeImproved) {
    headline = 'Session B improved the final outcome.'
  } else if (outcomeRegressed) {
    headline = 'Session B regressed compared with the baseline.'
  } else if (
    deltas.durationDelta != null &&
    deltas.durationDelta < 0 &&
    deltas.sourceCountDelta != null &&
    deltas.sourceCountDelta >= 0
  ) {
    headline = 'Session B was faster without shrinking evidence coverage.'
  } else if (
    deltas.durationDelta != null &&
    deltas.durationDelta > 0 &&
    deltas.sourceCountDelta != null &&
    deltas.sourceCountDelta > 0
  ) {
    headline = 'Session B traded more time for broader evidence coverage.'
  }

  return {
    headline,
    summary: `Baseline: ${sessionA.label}. Comparison: ${sessionB.label}. Read the signals below before drilling into either workspace.`,
    changes,
    insights: [timingInsight, sourceInsight, activityInsight, outcomeInsight],
  }
}
