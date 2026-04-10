import type { ReadonlyURLSearchParams } from 'next/navigation'

import type { QuickScriptFields } from '@/lib/quick-script'
import type { ResearchOutputFormat, Session } from '@/types/telemetry'

export type ResearchContentBridgeSource = 'home' | 'session-overview' | 'session-report'
export type ContentStudioIntent = 'pipeline' | 'quick-script'

export interface ResearchContentBridgePayload {
  sessionId: string
  sessionLabel: string
  researchQuery: string
  hasReport: boolean
  source: ResearchContentBridgeSource
  createdAt: string | null
  completedAt: string | null
  reportFormat?: ResearchOutputFormat
  reportContent?: string
}

const RESEARCH_CONTENT_BRIDGE_STORAGE_KEY = 'ccdr.research-content-bridge'
const REPORT_TRANSFER_LIMIT = 12000

function trimText(value: string | null | undefined): string {
  return value?.trim() ?? ''
}

function truncateTransferredText(value: string, maxChars: number): string {
  if (value.length <= maxChars) {
    return value
  }

  return `${value.slice(0, maxChars).trimEnd()}\n\n[Report excerpt truncated for studio handoff.]`
}

function defaultSessionLabel(sessionId: string): string {
  return `Session ${sessionId.slice(0, 8)}`
}

function resolveSessionLabel(sessionId: string, label: string | null | undefined): string {
  const normalizedLabel = trimText(label)

  if (!normalizedLabel || normalizedLabel.toLowerCase() === 'untitled session') {
    return defaultSessionLabel(sessionId)
  }

  return normalizedLabel
}

function resolveSource(value: string | null | undefined): ResearchContentBridgeSource {
  if (value === 'session-overview' || value === 'session-report' || value === 'home') {
    return value
  }

  return 'home'
}

function isResearchContentBridgePayload(
  value: unknown,
): value is ResearchContentBridgePayload {
  if (!value || typeof value !== 'object') {
    return false
  }

  const candidate = value as Partial<ResearchContentBridgePayload>

  return (
    typeof candidate.sessionId === 'string'
    && typeof candidate.sessionLabel === 'string'
    && typeof candidate.researchQuery === 'string'
    && typeof candidate.hasReport === 'boolean'
    && typeof candidate.source === 'string'
  )
}

export function buildResearchContentBridgePayloadFromSession(
  sessionId: string,
  session: Session | null,
  source: ResearchContentBridgeSource,
): ResearchContentBridgePayload {
  return {
    sessionId,
    sessionLabel: resolveSessionLabel(sessionId, session?.label),
    researchQuery: trimText(session?.query),
    hasReport: Boolean(session?.hasReport),
    source,
    createdAt: session?.createdAt ?? null,
    completedAt: session?.completedAt ?? null,
  }
}

export function withResearchReportContent(
  payload: ResearchContentBridgePayload,
  report: {
    format: ResearchOutputFormat
    content: string
  } | null,
): ResearchContentBridgePayload {
  if (!report?.content.trim()) {
    return payload
  }

  return {
    ...payload,
    hasReport: true,
    reportFormat: report.format,
    reportContent: truncateTransferredText(report.content.trim(), REPORT_TRANSFER_LIMIT),
  }
}

export function storeResearchContentBridge(payload: ResearchContentBridgePayload): void {
  if (typeof window === 'undefined') {
    return
  }

  window.sessionStorage.setItem(
    RESEARCH_CONTENT_BRIDGE_STORAGE_KEY,
    JSON.stringify(payload),
  )
}

export function readResearchContentBridge(
  expectedSessionId?: string | null,
): ResearchContentBridgePayload | null {
  if (typeof window === 'undefined') {
    return null
  }

  const raw = window.sessionStorage.getItem(RESEARCH_CONTENT_BRIDGE_STORAGE_KEY)

  if (!raw) {
    return null
  }

  try {
    const parsed: unknown = JSON.parse(raw)

    if (!isResearchContentBridgePayload(parsed)) {
      return null
    }

    if (expectedSessionId && parsed.sessionId !== expectedSessionId) {
      return null
    }

    return parsed
  } catch {
    return null
  }
}

export function clearResearchContentBridge(): void {
  if (typeof window === 'undefined') {
    return
  }

  window.sessionStorage.removeItem(RESEARCH_CONTENT_BRIDGE_STORAGE_KEY)
}

export function buildContentStudioHref(
  payload: ResearchContentBridgePayload,
  intent: ContentStudioIntent,
): string {
  const params = new URLSearchParams()

  params.set('sourceSession', payload.sessionId)
  params.set('sourceLabel', payload.sessionLabel)
  params.set('source', payload.source)
  params.set('reportReady', payload.hasReport ? '1' : '0')
  params.set('intent', intent)

  return `/content-gen?${params.toString()}`
}

export function parseContentStudioIntent(value: string | null): ContentStudioIntent | null {
  if (value === 'pipeline' || value === 'quick-script') {
    return value
  }

  return null
}

export function buildResearchContentBridgeFromSearchParams(
  searchParams: URLSearchParams | ReadonlyURLSearchParams,
): ResearchContentBridgePayload | null {
  const sessionId = trimText(searchParams.get('sourceSession'))

  if (!sessionId) {
    return null
  }

  return {
    sessionId,
    sessionLabel: resolveSessionLabel(sessionId, searchParams.get('sourceLabel')),
    researchQuery: '',
    hasReport: searchParams.get('reportReady') === '1',
    source: resolveSource(searchParams.get('source')),
    createdAt: null,
    completedAt: null,
  }
}

export function formatResearchBridgeSource(source: ResearchContentBridgeSource): string {
  switch (source) {
    case 'session-overview':
      return 'Session overview'
    case 'session-report':
      return 'Session report'
    default:
      return 'Research home'
  }
}

export function buildPipelineThemeFromResearch(
  payload: ResearchContentBridgePayload,
): string {
  const label = trimText(payload.sessionLabel)

  if (label && label !== defaultSessionLabel(payload.sessionId)) {
    return label
  }

  const query = trimText(payload.researchQuery).replace(/\s+/g, ' ')

  if (!query) {
    return label || defaultSessionLabel(payload.sessionId)
  }

  return query.length > 120 ? `${query.slice(0, 117).trimEnd()}...` : query
}

export function buildQuickScriptFieldsFromResearch(
  payload: ResearchContentBridgePayload,
): Partial<QuickScriptFields> {
  const rawIdea = buildPipelineThemeFromResearch(payload)
  const sections: string[] = [
    `Research session: ${payload.sessionLabel} (${payload.sessionId})`,
  ]

  if (payload.researchQuery.trim()) {
    sections.push(`Research query:\n${payload.researchQuery.trim()}`)
  }

  if (payload.reportContent?.trim()) {
    sections.push(
      `Research report${payload.reportFormat ? ` (${payload.reportFormat})` : ''}:\n${payload.reportContent.trim()}`,
    )
  }

  return {
    raw_idea: rawIdea,
    source_material: sections.join('\n\n'),
  }
}
