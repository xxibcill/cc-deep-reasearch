import type { BacklogItem, BacklogItemStatus, BacklogProductionStatus } from '@/types/content-gen'

export const STATUS_OPTIONS: BacklogItemStatus[] = [
  'captured',
  'backlog',
  'selected',
  'archived',
]

export function formatProductionStatus(status?: string | null) {
  if (!status || status === 'idle') {
    return ''
  }
  return status.replaceAll('_', ' ')
}

export function formatTimestamp(value?: string) {
  if (!value) {
    return '—'
  }

  const date = new Date(value)
  if (Number.isNaN(date.getTime())) {
    return value
  }
  return date.toLocaleString()
}

export function statusBadgeVariant(status: string): 'success' | 'warning' | 'info' | 'secondary' | 'outline' {
  if (status === 'captured') return 'secondary'
  if (status === 'selected') return 'success'
  if (status === 'archived') return 'secondary'
  return 'outline'
}

export function productionStatusBadgeVariant(
  status?: string | null,
): 'success' | 'warning' | 'info' | 'secondary' | 'outline' {
  if (status === 'in_production') return 'warning'
  if (status === 'ready_to_publish') return 'info'
  return 'secondary'
}

export function hasActiveProductionStatus(
  status?: BacklogProductionStatus | string | null,
): status is Exclude<BacklogProductionStatus, 'idle'> {
  return status === 'in_production' || status === 'ready_to_publish'
}

export function recommendationBadgeVariant(
  recommendation?: string,
): 'success' | 'destructive' | 'secondary' | 'outline' {
  if (recommendation === 'produce_now') return 'success'
  if (recommendation === 'kill') return 'destructive'
  if (recommendation === 'hold') return 'secondary'
  return 'outline'
}

export function backlogTitle(item: { title?: string; idea?: string; raw_idea?: string | null }): string {
  return item.title?.trim() || item.idea?.trim() || item.raw_idea?.trim() || 'Untitled idea'
}

export function backlogSummary(item: { one_line_summary?: string; idea?: string; raw_idea?: string | null }): string {
  return item.one_line_summary?.trim() || item.raw_idea?.trim() || item.idea?.trim() || 'No summary yet.'
}

export function backlogHook(item: Pick<BacklogItem, 'hook' | 'potential_hook'>): string {
  return item.hook?.trim() || item.potential_hook?.trim() || ''
}
