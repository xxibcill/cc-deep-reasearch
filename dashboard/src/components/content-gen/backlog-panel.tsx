'use client'

import { useState } from 'react'
import { useRouter } from 'next/navigation'
import { Archive, CheckCircle2, LayoutGrid, List, Plus, Trash2 } from 'lucide-react'

import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Alert, AlertDescription } from '@/components/ui/alert'
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogBody, DialogFooter } from '@/components/ui/dialog'
import { NativeSelect } from '@/components/ui/native-select'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { BacklogItemForm } from '@/components/content-gen/backlog-item-form'
import { formatTimestamp, statusBadgeVariant, recommendationBadgeVariant, STATUS_OPTIONS } from '@/components/content-gen/backlog-shared'
import { cn } from '@/lib/utils'
import type { BacklogItem } from '@/types/content-gen'

interface BacklogPanelProps {
  items: BacklogItem[]
  backlogPath?: string | null
  loading?: boolean
  onUpdateStatus?: (ideaId: string, patch: Record<string, unknown>) => Promise<void>
  onEdit?: (ideaId: string, patch: Record<string, unknown>) => Promise<void>
  onSelect?: (ideaId: string) => Promise<void>
  onArchive?: (ideaId: string) => Promise<void>
  onDelete?: (ideaId: string) => Promise<void>
  onCreate?: (data: Record<string, unknown>) => Promise<void>
}

type BacklogViewMode = 'grid' | 'list'

export function BacklogPanel({
  items,
  backlogPath,
  loading,
  onUpdateStatus,
  onEdit,
  onSelect,
  onArchive,
  onDelete,
  onCreate,
}: BacklogPanelProps) {
  const router = useRouter()
  const [statusFilter, setStatusFilter] = useState('')
  const [categoryFilter, setCategoryFilter] = useState('')
  const [viewMode, setViewMode] = useState<BacklogViewMode>('grid')
  const [busyKey, setBusyKey] = useState<string | null>(null)
  const [actionError, setActionError] = useState<string | null>(null)
  const [deleteConfirm, setDeleteConfirm] = useState<{ ideaId: string; idea: string } | null>(null)

  const navigateToDetail = (ideaId: string, e: React.MouseEvent) => {
    e.stopPropagation()
    router.push(`/content-gen/backlog/${ideaId}`)
  }

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

  const renderItemActions = (item: BacklogItem) => {
    const rowKey = item.idea_id

    return (
      <>
        {onEdit && <BacklogItemForm item={item} onSubmitEdit={onEdit} />}
        <Button
          type="button"
          variant="ghost"
          size="icon"
          onClick={() => {
            if (onSelect) {
              void runAction(`${rowKey}-select`, () => onSelect(item.idea_id))
            }
          }}
          disabled={!onSelect || busyKey === `${rowKey}-select`}
          className="h-8 w-8 text-muted-foreground/60 transition-all duration-200 hover:-translate-y-0.5 hover:text-success motion-reduce:transform-none"
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
          className="h-8 w-8 text-muted-foreground/60 transition-all duration-200 hover:-translate-y-0.5 hover:text-warning motion-reduce:transform-none"
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
              setDeleteConfirm({ ideaId: item.idea_id, idea: item.idea })
            }
          }}
          disabled={!onDelete || busyKey === `${rowKey}-delete`}
          className="h-8 w-8 text-muted-foreground/60 transition-all duration-200 hover:-translate-y-0.5 hover:text-error motion-reduce:transform-none"
          title="Delete item"
        >
          <Trash2 className="h-3.5 w-3.5" />
        </Button>
      </>
    )
  }

  return (
    <div className="space-y-4">
      {actionError && (
        <Alert variant="destructive">
          <AlertDescription>{actionError}</AlertDescription>
        </Alert>
      )}
      <div className="rounded-[1.15rem] border border-border/75 bg-surface/62 p-4 shadow-[inset_0_1px_0_rgba(255,255,255,0.04)]">
        <div className="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
          <div className="space-y-3">
            <div className="space-y-1">
              <p className="text-sm font-medium text-foreground">Persistent backlog</p>
              <p className="text-xs text-muted-foreground">
                {items.length} item{items.length === 1 ? '' : 's'}
                {backlogPath ? ` stored at ${backlogPath}` : ''}
              </p>
            </div>
            <div className="flex flex-wrap gap-2">
              <Badge variant="outline" className="bg-background/45">
                {filteredItems.length} visible
              </Badge>
              <Badge variant="success" className="bg-success/10 text-success">
                {items.filter((item) => item.status === 'selected').length} selected
              </Badge>
              <Badge variant="secondary" className="bg-secondary/50">
                {items.filter((item) => item.status === 'archived').length} archived
              </Badge>
            </div>
          </div>
          <div className="flex flex-col gap-3 xl:items-end">
            <div className="flex flex-col gap-3 sm:flex-row sm:flex-wrap sm:items-end xl:justify-end">
              {onCreate && (
                <div className="flex items-end">
                  <BacklogItemForm
                    onSubmitCreate={onCreate}
                    trigger={
                      <Button type="button" className="h-10 gap-2">
                        <Plus className="h-4 w-4" />
                        New item
                      </Button>
                    }
                  />
                </div>
              )}
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
            <div className="flex justify-start xl:justify-end">
              <div
                className="relative grid grid-cols-2 rounded-[0.95rem] border border-border/70 bg-background/40 p-1 shadow-[inset_0_1px_0_rgba(255,255,255,0.03)]"
                role="group"
                aria-label="Backlog view"
              >
                <div
                  aria-hidden="true"
                  className={cn(
                    'pointer-events-none absolute inset-y-1 left-1 w-[calc(50%-0.25rem)] rounded-[0.72rem] bg-card shadow-[0_12px_30px_rgba(0,0,0,0.22)] transition-transform duration-200 ease-[cubic-bezier(0.22,1,0.36,1)] motion-reduce:transition-none',
                    viewMode === 'grid' ? 'translate-x-0' : 'translate-x-full'
                  )}
                />
                {[
                  { value: 'grid' as const, label: 'Grid', icon: LayoutGrid },
                  { value: 'list' as const, label: 'List', icon: List },
                ].map(({ value, label, icon: Icon }) => (
                  <button
                    key={value}
                    type="button"
                    aria-pressed={viewMode === value}
                    onClick={() => setViewMode(value)}
                    className={cn(
                      'relative z-10 flex min-w-[7rem] items-center justify-center gap-2 rounded-[0.72rem] px-3 py-2 text-[0.76rem] font-semibold uppercase tracking-[0.16em] transition-colors duration-200 motion-reduce:transition-none',
                      viewMode === value ? 'text-foreground' : 'text-muted-foreground hover:text-foreground'
                    )}
                  >
                    <Icon className="h-4 w-4" />
                    <span>{label}</span>
                  </button>
                ))}
              </div>
            </div>
          </div>
        </div>
      </div>

      {!filteredItems.length ? (
        <div className="rounded-xl border border-dashed border-border bg-card/70 py-12 text-center">
          <p className="text-sm text-muted-foreground">No backlog items match the current filters.</p>
        </div>
      ) : (
        <div
          key={viewMode}
          className="animate-in fade-in-0 slide-in-from-bottom-2 duration-200 motion-reduce:animate-none"
        >
          {viewMode === 'grid' ? (
            <div className="grid gap-4 xl:grid-cols-2 2xl:grid-cols-3">
              {filteredItems.map((item) => {
                const rowKey = item.idea_id

                return (
                  <article
                    key={rowKey}
                    onClick={(e) => navigateToDetail(item.idea_id, e)}
                    className="group relative cursor-pointer overflow-hidden rounded-[1.15rem] border border-border/75 bg-card/95 p-4 shadow-[0_18px_48px_rgba(0,0,0,0.18)] transition-all duration-200 hover:-translate-y-1 hover:border-primary/35 hover:shadow-[0_22px_60px_rgba(12,18,30,0.28)] motion-reduce:transform-none motion-reduce:transition-none"
                  >
                    <div className="absolute inset-x-0 top-0 h-px bg-gradient-to-r from-transparent via-primary/45 to-transparent opacity-60" />
                    <div className="flex items-start justify-between gap-3">
                      <div className="space-y-3">
                        <div className="flex flex-wrap gap-2">
                          <Badge variant={statusBadgeVariant(item.status)}>{item.status}</Badge>
                          <Badge variant="outline">{item.category || 'uncategorized'}</Badge>
                          <Badge variant={recommendationBadgeVariant(item.latest_recommendation)}>
                            {item.latest_recommendation || 'unscored'}
                          </Badge>
                        </div>
                        <div className="space-y-2">
                          <h3 className="text-base font-semibold leading-tight text-foreground">
                            {item.idea}
                          </h3>
                          <div className="flex flex-wrap items-center gap-x-3 gap-y-1 text-[11px] uppercase tracking-[0.16em] text-muted-foreground">
                            <span className="font-mono">{item.idea_id.slice(0, 8)}</span>
                            <span>{formatTimestamp(item.updated_at || item.created_at)}</span>
                          </div>
                        </div>
                      </div>
                      <div className="min-w-[5.75rem] rounded-[0.95rem] border border-border/70 bg-background/45 px-3 py-2 text-right shadow-[inset_0_1px_0_rgba(255,255,255,0.04)]">
                        <p className="text-[10px] font-mono uppercase tracking-[0.18em] text-muted-foreground">
                          Score
                        </p>
                        <p className="mt-1 font-mono text-lg tabular-nums text-foreground">
                          {item.latest_score ?? item.priority_score ?? '—'}
                        </p>
                      </div>
                    </div>

                    <div className="mt-4 grid gap-3 sm:grid-cols-2">
                      <div className="rounded-[0.95rem] border border-border/65 bg-background/35 p-3">
                        <p className="text-[10px] font-mono uppercase tracking-[0.18em] text-muted-foreground">
                          Audience
                        </p>
                        <p className="mt-2 text-sm text-foreground/88">
                          {item.audience || 'No audience noted yet.'}
                        </p>
                      </div>
                      <div className="rounded-[0.95rem] border border-border/65 bg-background/35 p-3">
                        <p className="text-[10px] font-mono uppercase tracking-[0.18em] text-muted-foreground">
                          Theme
                        </p>
                        <p className="mt-2 text-sm text-foreground/88">
                          {item.source_theme || 'No source theme assigned.'}
                        </p>
                      </div>
                    </div>

                    <div className="mt-3 space-y-3 rounded-[0.95rem] border border-border/65 bg-background/30 p-3">
                      <div>
                        <p className="text-[10px] font-mono uppercase tracking-[0.18em] text-muted-foreground">
                          Problem
                        </p>
                        <p className="mt-2 text-sm text-foreground/84">
                          {item.problem || item.why_now || 'No operator note yet.'}
                        </p>
                      </div>
                      {item.selection_reasoning && (
                        <div className="border-t border-border/60 pt-3">
                          <p className="text-[10px] font-mono uppercase tracking-[0.18em] text-muted-foreground">
                            Selection signal
                          </p>
                          <p className="mt-2 text-sm text-foreground/78">
                            {item.selection_reasoning}
                          </p>
                        </div>
                      )}
                    </div>

                    <div className="mt-4 flex flex-col gap-3 border-t border-border/70 pt-4">
                      <div className="flex flex-wrap items-center gap-2 text-xs text-muted-foreground">
                        {item.source_theme ? <span>Theme: {item.source_theme}</span> : null}
                        {item.evidence ? <span>Evidence attached</span> : null}
                        {item.potential_hook ? <span>Hook ready</span> : null}
                      </div>
                      <div className="flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
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
                          className="h-9 min-w-[11rem] rounded-[0.8rem] bg-background/60"
                        >
                          {STATUS_OPTIONS.map((status) => (
                            <option key={status} value={status}>
                              {status}
                            </option>
                          ))}
                        </NativeSelect>
                        <div className="flex items-center justify-end gap-1">
                          {renderItemActions(item)}
                        </div>
                      </div>
                    </div>
                  </article>
                )
              })}
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
                      <TableRow
                        key={rowKey}
                        onClick={(e) => navigateToDetail(item.idea_id, e)}
                        className="cursor-pointer hover:bg-surface/50"
                      >
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
                            {renderItemActions(item)}
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
      )}

      {deleteConfirm && (
        <Dialog open={true} onOpenChange={(open) => !open && setDeleteConfirm(null)}>
          <DialogContent>
            <DialogHeader>
              <DialogTitle>Delete backlog item?</DialogTitle>
              <DialogDescription>
                This will permanently remove &ldquo;{deleteConfirm.idea}&rdquo; from the backlog. This action cannot be undone.
              </DialogDescription>
            </DialogHeader>
            <DialogBody>
              <p className="text-sm text-muted-foreground">
                If this item was generated by a pipeline, its source data may still be available in that pipeline&apos;s output.
              </p>
            </DialogBody>
            <DialogFooter>
              <Button
                type="button"
                variant="outline"
                onClick={() => setDeleteConfirm(null)}
                disabled={busyKey === `${deleteConfirm.ideaId}-delete`}
              >
                Cancel
              </Button>
              <Button
                type="button"
                variant="destructive"
                onClick={() => {
                  void runAction(`${deleteConfirm.ideaId}-delete`, async () => {
                    if (onDelete) {
                      await onDelete(deleteConfirm.ideaId)
                    }
                  })
                  setDeleteConfirm(null)
                }}
                disabled={busyKey === `${deleteConfirm.ideaId}-delete`}
              >
                {busyKey === `${deleteConfirm.ideaId}-delete` ? 'Deleting...' : 'Delete item'}
              </Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>
      )}
    </div>
  )
}
