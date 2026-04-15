import type { BriefLifecycleState } from '@/types/content-gen'

export const LIFECYCLE_STATE_OPTIONS: BriefLifecycleState[] = [
  'draft',
  'approved',
  'superseded',
  'archived',
]

export function lifecycleStateLabel(state: string): string {
  return state.charAt(0).toUpperCase() + state.slice(1)
}

export function lifecycleStateBadgeVariant(
  state: string,
): 'success' | 'warning' | 'secondary' | 'destructive' | 'outline' {
  if (state === 'approved') return 'success'
  if (state === 'draft') return 'warning'
  if (state === 'superseded') return 'secondary'
  if (state === 'archived') return 'outline'
  return 'outline'
}

export function provenanceLabel(provenance: string): string {
  const labels: Record<string, string> = {
    generated: 'AI Generated',
    operator_created: 'Operator Created',
    operator_edited: 'Operator Edited',
    cloned: 'Cloned',
  }
  return labels[provenance] || provenance
}

export function formatBriefTimestamp(value?: string) {
  if (!value) return '—'
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return value
  return date.toLocaleString()
}

export function briefTitle(brief: { title?: string; brief_id?: string }): string {
  return brief.title?.trim() || brief.brief_id?.trim() || 'Untitled brief'
}

export function briefRevisionSummary(revision: {
  version?: number
  theme?: string
  revision_notes?: string
  created_at?: string
}): string {
  const parts: string[] = []
  if (revision.version) parts.push(`v${revision.version}`)
  if (revision.theme) parts.push(revision.theme)
  if (revision.revision_notes) parts.push(revision.revision_notes)
  return parts.join(' · ') || 'No summary'
}