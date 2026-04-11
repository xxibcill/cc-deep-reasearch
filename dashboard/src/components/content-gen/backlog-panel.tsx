'use client'

import { useState } from 'react'
import { Archive, CheckCircle2, Trash2 } from 'lucide-react'

import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Alert, AlertDescription } from '@/components/ui/alert'
import { NativeSelect } from '@/components/ui/native-select'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import type { BacklogItem, BacklogItemStatus } from '@/types/content-gen'

const STATUS_OPTIONS: BacklogItemStatus[] = [
  'backlog',
  'selected',
  'in_production',
  'published',
  'archived',
]

function formatTimestamp(value?: string) {
  if (!value) {
    return '—'
  }

  const date = new Date(value)
  if (Number.isNaN(date.getTime())) {
    return value
  }
  return date.toLocaleString()
}

function statusBadgeVariant(status: string): 'success' | 'warning' | 'info' | 'secondary' | 'outline' {
  if (status === 'selected') return 'success'
  if (status === 'in_production') return 'warning'
  if (status === 'published') return 'info'
  if (status === 'archived') return 'secondary'
  return 'outline'
}

function recommendationBadgeVariant(
  recommendation?: string,
): 'success' | 'destructive' | 'secondary' | 'outline' {
  if (recommendation === 'produce_now') return 'success'
  if (recommendation === 'kill') return 'destructive'
  if (recommendation === 'hold') return 'secondary'
  return 'outline'
}

interface BacklogPanelProps {
  items: BacklogItem[]
  backlogPath?: string | null
  loading?: boolean
  onUpdateStatus?: (ideaId: string, patch: Record<string, unknown>) => Promise<void>
  onSelect?: (ideaId: string) => Promise<void>
  onArchive?: (ideaId: string) => Promise<void>
  onDelete?: (ideaId: string) => Promise<void>
}

export function BacklogPanel({
  items,
  backlogPath,
  loading,
  onUpdateStatus,
  onSelect,
  onArchive,
  onDelete,
}: BacklogPanelProps) {
  const [statusFilter, setStatusFilter] = useState('')
  const [categoryFilter, setCategoryFilter] = useState('')
  const [busyKey, setBusyKey] = useState<string | null>(null)
  const [actionError, setActionError] = useState<string | null>(null)

  const categories = [...new Set(items.map((item) => item.category).filter(Boolean))].sort()
  const filteredItems = items
    .filter((item) => (statusFilter ? item.status === statusFilter : true))
    .filter((item) => (categoryFilter ? item.category === categoryFilter : true))
    .sort((left, right) => {
      const leftPriority = left.status === 'selected' ? 0 : left.status === 'in_production' ? 1 : 2
      const rightPriority = right.status === 'selected' ? 0 : right.status === 'in_production' ? 1 : 2
      if (leftPriority !== rightPriority) {
        return leftPriority - rightPriority
      }
      return (right.updated_at || '').localeCompare(left.updated_at || '')
    })

  const runAction = async (key: string, action: () => Promise<void>) => {
    try {
      setBusyKey(key)
      setActionError(null)
      await action()
    } catch (err) {
      setActionError(err instanceof Error ? err.message : String(err))
    } finally {
      setBusyKey(null)
    }
  }

  if (loading) {
    return <div className="py-8 text-center text-sm text-muted-foreground">Loading backlog...</div>
  }

  return (
    <div className="space-y-4">
      {actionError && (
        <Alert variant="destructive">
          <AlertDescription>{actionError}</AlertDescription>
        </Alert>
      )}
      <div className="flex flex-col gap-3 rounded-[1rem] border border-border/75 bg-surface/62 p-4 lg:flex-row lg:items-end lg:justify-between">
        <div className="space-y-1">
          <p className="text-sm font-medium text-foreground">Persistent backlog</p>
          <p className="text-xs text-muted-foreground">
            {items.length} item{items.length === 1 ? '' : 's'}
            {backlogPath ? ` stored at ${backlogPath}` : ''}
          </p>
        </div>
        <div className="flex flex-col gap-3 sm:flex-row">
          <div className="space-y-1">
            <label className="text-[11px] font-mono uppercase tracking-[0.18em] text-muted-foreground">
              Status
            </label>
            <NativeSelect value={statusFilter} onChange={(event) => setStatusFilter(event.target.value)} className="h-10 min-w-[11rem]">
              <option value="">All statuses</option>
              {STATUS_OPTIONS.map((status) => (
                <option key={status} value={status}>
                  {status}
                </option>
              ))}
            </NativeSelect>
          </div>
          <div className="space-y-1">
            <label className="text-[11px] font-mono uppercase tracking-[0.18em] text-muted-foreground">
              Category
            </label>
            <NativeSelect value={categoryFilter} onChange={(event) => setCategoryFilter(event.target.value)} className="h-10 min-w-[12rem]">
              <option value="">All categories</option>
              {categories.map((category) => (
                <option key={category} value={category}>
                  {category}
                </option>
              ))}
            </NativeSelect>
          </div>
        </div>
      </div>

      {!filteredItems.length ? (
        <div className="rounded-xl border border-dashed border-border bg-card/70 py-12 text-center">
          <p className="text-sm text-muted-foreground">No backlog items match the current filters.</p>
        </div>
      ) : (
        <div className="overflow-hidden rounded-xl border border-border bg-card/95 shadow-sm">
          <Table>
            <TableHeader className="bg-surface-raised/60">
              <TableRow className="hover:bg-transparent">
                <TableHead>Idea</TableHead>
                <TableHead>Status</TableHead>
                <TableHead>Category</TableHead>
                <TableHead>Score</TableHead>
                <TableHead>Recommendation</TableHead>
                <TableHead>Theme</TableHead>
                <TableHead>Updated</TableHead>
                <TableHead className="text-right">&nbsp;</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {filteredItems.map((item) => {
                const rowKey = item.idea_id
                return (
                  <TableRow key={rowKey}>
                    <TableCell className="min-w-[22rem]">
                      <div className="space-y-1">
                        <p className="text-sm font-medium text-foreground">{item.idea}</p>
                        <div className="flex flex-wrap items-center gap-2 text-xs text-muted-foreground">
                          <span className="font-mono">{item.idea_id.slice(0, 8)}</span>
                          {item.selection_reasoning ? (
                            <span className="truncate">Reason: {item.selection_reasoning}</span>
                          ) : null}
                        </div>
                      </div>
                    </TableCell>
                    <TableCell>
                      <div className="space-y-2">
                        <Badge variant={statusBadgeVariant(item.status)}>{item.status}</Badge>
                        <NativeSelect
                          value={item.status}
                          onChange={(event) => {
                            if (onUpdateStatus) {
                              void runAction(`${rowKey}-status`, async () =>
                                onUpdateStatus(item.idea_id, { status: event.target.value }),
                              )
                            }
                          }}
                          disabled={!onUpdateStatus || busyKey === `${rowKey}-status`}
                          className="h-9 min-w-[10rem] rounded-md"
                        >
                          {STATUS_OPTIONS.map((status) => (
                            <option key={status} value={status}>
                              {status}
                            </option>
                          ))}
                        </NativeSelect>
                      </div>
                    </TableCell>
                    <TableCell className="text-foreground/80">{item.category || '—'}</TableCell>
                    <TableCell className="font-mono text-xs tabular-nums text-muted-foreground">
                      {item.latest_score ?? '—'}
                    </TableCell>
                    <TableCell>
                      <Badge variant={recommendationBadgeVariant(item.latest_recommendation)}>
                        {item.latest_recommendation || 'unscored'}
                      </Badge>
                    </TableCell>
                    <TableCell className="max-w-[12rem] truncate text-xs text-muted-foreground">
                      {item.source_theme || '—'}
                    </TableCell>
                    <TableCell className="max-w-[12rem] text-xs text-muted-foreground">
                      {formatTimestamp(item.updated_at || item.created_at)}
                    </TableCell>
                    <TableCell className="text-right">
                      <div className="flex items-center justify-end gap-1">
                        <Button
                          type="button"
                          variant="ghost"
                          size="icon"
                          onClick={() => {
                            if (onSelect) {
                              void runAction(`${rowKey}-select`, () => onSelect(item.idea_id))
                            }
                          }}
                          disabled={!onSelect || busyKey === `${rowKey}-select` || item.status === 'selected'}
                          className="h-8 w-8 text-muted-foreground/60 hover:text-success"
                          title="Select item"
                        >
                          <CheckCircle2 className="h-3.5 w-3.5" />
                        </Button>
                        <Button
                          type="button"
                          variant="ghost"
                          size="icon"
                          onClick={() => {
                            if (onArchive) {
                              void runAction(`${rowKey}-archive`, () => onArchive(item.idea_id))
                            }
                          }}
                          disabled={!onArchive || busyKey === `${rowKey}-archive`}
                          className="h-8 w-8 text-muted-foreground/60 hover:text-warning"
                          title="Archive item"
                        >
                          <Archive className="h-3.5 w-3.5" />
                        </Button>
                        <Button
                          type="button"
                          variant="ghost"
                          size="icon"
                          onClick={() => {
                            if (onDelete) {
                              void runAction(`${rowKey}-delete`, () => onDelete(item.idea_id))
                            }
                          }}
                          disabled={!onDelete || busyKey === `${rowKey}-delete`}
                          className="h-8 w-8 text-muted-foreground/60 hover:text-error"
                          title="Delete item"
                        >
                          <Trash2 className="h-3.5 w-3.5" />
                        </Button>
                      </div>
                    </TableCell>
                  </TableRow>
                )
              })}
            </TableBody>
          </Table>
        </div>
      )}
    </div>
  )
}
