import type { BacklogItemStatus } from '@/types/content-gen'

export const STATUS_OPTIONS: BacklogItemStatus[] = [
  'backlog',
  'selected',
  'in_production',
  'published',
  'archived',
]

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
  if (status === 'selected') return 'success'
  if (status === 'in_production') return 'warning'
  if (status === 'published') return 'info'
  if (status === 'archived') return 'secondary'
  return 'outline'
}

export function recommendationBadgeVariant(
  recommendation?: string,
): 'success' | 'destructive' | 'secondary' | 'outline' {
  if (recommendation === 'produce_now') return 'success'
  if (recommendation === 'kill') return 'destructive'
  if (recommendation === 'hold') return 'secondary'
  return 'outline'
}
