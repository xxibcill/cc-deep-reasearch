'use client'

import { useEffect, useState } from 'react'
import { useRouter } from 'next/navigation'
import { Archive, CheckCircle2, Plus, Play, Trash2 } from 'lucide-react'

import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Alert, AlertDescription } from '@/components/ui/alert'
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogBody, DialogFooter } from '@/components/ui/dialog'
import { NativeSelect } from '@/components/ui/native-select'
import { BacklogItemForm } from '@/components/content-gen/backlog-item-form'
import {
  backlogHook,
  backlogSummary,
  backlogTitle,
  formatTimestamp,
  formatProductionStatus,
  hasActiveProductionStatus,
  productionStatusBadgeVariant,
  statusBadgeVariant,
  recommendationBadgeVariant,
  STATUS_OPTIONS,
} from '@/components/content-gen/backlog-shared'
import { ItemsView, ItemsViewHeader, ItemsViewLoading, ItemsViewEmpty, ItemsViewToggle, type ItemsViewMode } from '@/components/content-gen/items-view'
import { DataTable, type DataTableColumn } from '@/components/content-gen/data-table'
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
  onStartProduction?: (ideaId: string) => Promise<string | null>
}

type BacklogViewMode = ItemsViewMode

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
  onStartProduction,
}: BacklogPanelProps) {
  const router = useRouter()
  const [statusFilter, setStatusFilter] = useState('')
  const [categoryFilter, setCategoryFilter] = useState('')
  const [viewMode, setViewMode] = useState<BacklogViewMode>('grid')
  const [busyKey, setBusyKey] = useState<string | null>(null)
  const [actionError, setActionError] = useState<string | null>(null)
  const [deleteConfirm, setDeleteConfirm] = useState<{ ideaId: string; title: string } | null>(null)
  const [startConfirm, setStartConfirm] = useState<{ ideaId: string; title: string } | null>(null)
  const [selectedIdeaIds, setSelectedIdeaIds] = useState<Set<string>>(new Set())
  const [bulkDeleteConfirm, setBulkDeleteConfirm] = useState<Set<string> | null>(null)

  const toggleSelect = (ideaId: string) => {
    setSelectedIdeaIds((prev) => {
      const next = new Set(prev)
      if (next.has(ideaId)) {
        next.delete(ideaId)
      } else {
        next.add(ideaId)
      }
      return next
    })
  }

  const toggleSelectAll = () => {
    if (selectedIdeaIds.size === filteredItems.length) {
      setSelectedIdeaIds(new Set())
    } else {
      setSelectedIdeaIds(new Set(filteredItems.map((i) => i.idea_id)))
    }
  }

  const clearSelection = () => {
    setSelectedIdeaIds(new Set())
  }

  const navigateToDetail = (ideaId: string, e: React.MouseEvent) => {
    e.stopPropagation()
    router.push(`/content-gen/backlog/${ideaId}`)
  }

  const categories = [...new Set(items.map((item) => item.category).filter(Boolean))].sort()
  const filteredItems = items
    .filter((item) => (statusFilter ? item.status === statusFilter : true))
    .filter((item) => (categoryFilter ? item.category === categoryFilter : true))
    .sort((left, right) => {
      const leftPriority =
        left.status === 'selected' ? 0 : left.status === 'backlog' ? 1 : left.status === 'captured' ? 2 : 3
      const rightPriority =
        right.status === 'selected' ? 0 : right.status === 'backlog' ? 1 : right.status === 'captured' ? 2 : 3
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
    return <ItemsViewLoading label="backlog" />
  }

  const renderItemActions = (item: BacklogItem) => {
    const rowKey = item.idea_id

    return (
      <>
        {onEdit && <BacklogItemForm item={item} onSubmitEdit={onEdit} />}
        {onStartProduction && (
          <Button
            type="button"
            variant="ghost"
            size="icon"
            onClick={() => setStartConfirm({ ideaId: item.idea_id, title: backlogTitle(item) })}
            disabled={!onStartProduction || busyKey === `${rowKey}-start`}
            className="h-8 w-8 text-primary/70 transition-all duration-200 hover:-translate-y-0.5 hover:text-primary motion-reduce:transition-none"
            title="Start Production"
          >
            <Play className="h-3.5 w-3.5" />
          </Button>
        )}
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
          className="h-8 w-8 text-muted-foreground/60 transition-all duration-200 hover:-translate-y-0.5 hover:text-success motion-reduce:transition-none"
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
          className="h-8 w-8 text-muted-foreground/60 transition-all duration-200 hover:-translate-y-0.5 hover:text-warning motion-reduce:transition-none"
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
              setDeleteConfirm({ ideaId: item.idea_id, title: backlogTitle(item) })
            }
          }}
          disabled={!onDelete || busyKey === `${rowKey}-delete`}
          className="h-8 w-8 text-muted-foreground/60 transition-all duration-200 hover:-translate-y-0.5 hover:text-error motion-reduce:transition-none"
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
      <ItemsViewHeader
        title="Persistent backlog"
        totalCount={items.length}
        visibleCount={filteredItems.length}
        stats={
          <div className="flex flex-wrap gap-2">
            <Badge variant="outline" className="bg-background/45">
              {filteredItems.length} visible
            </Badge>
            <Badge variant="success" className="bg-success/10 text-success">
              {items.filter((item) => item.status === 'selected').length} selected
            </Badge>
            <Badge variant="secondary" className="bg-secondary/50">
              {items.filter((item) => item.status === 'captured').length} captured
            </Badge>
            <Badge variant="secondary" className="bg-secondary/50">
              {items.filter((item) => item.status === 'archived').length} archived
            </Badge>
            <Badge variant="warning" className="bg-warning/10 text-warning">
              {items.filter((item) => item.production_status === 'in_production').length} in production
            </Badge>
            <Badge variant="info" className="bg-info/10 text-info">
              {items.filter((item) => item.production_status === 'ready_to_publish').length} ready to publish
            </Badge>
          </div>
        }
        controls={
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
            <ItemsViewToggle value={viewMode} onChange={setViewMode} label="Backlog" />
          </div>
        }
      />

      {!filteredItems.length ? (
        <div className="rounded-xl border border-dashed border-border bg-card/70 py-12 text-center">
          <p className="text-sm text-muted-foreground">No backlog items match the current filters.</p>
        </div>
      ) : selectedIdeaIds.size > 0 ? (
        <div className="flex items-center justify-between rounded-xl border border-border bg-surface/80 px-4 py-3 shadow-sm">
          <div className="flex items-center gap-3">
            <span className="text-sm font-medium text-foreground">
              {selectedIdeaIds.size} selected
            </span>
            <Button
              type="button"
              variant="ghost"
              size="sm"
              onClick={toggleSelectAll}
              className="h-8 text-xs"
            >
              {selectedIdeaIds.size === filteredItems.length ? 'Deselect all' : 'Select all'}
            </Button>
            <Button
              type="button"
              variant="ghost"
              size="sm"
              onClick={clearSelection}
              className="h-8 text-xs"
            >
              Clear
            </Button>
          </div>
          <Button
            type="button"
            variant="destructive"
            size="sm"
            onClick={() => setBulkDeleteConfirm(new Set(selectedIdeaIds))}
            className="h-8 gap-2"
          >
            <Trash2 className="h-3.5 w-3.5" />
            Delete selected
          </Button>
        </div>
      ) : viewMode === 'grid' ? (
        <>
          {filteredItems.map((item) => {
            const rowKey = item.idea_id

            return (
              <article
                key={rowKey}
                role="button"
                tabIndex={0}
                onClick={(e) => navigateToDetail(item.idea_id, e)}
                onKeyDown={(e) => {
                  if (e.key === 'Enter' || e.key === ' ') {
                    e.preventDefault()
                    router.push(`/content-gen/backlog/${item.idea_id}`)
                  }
                }}
                className="group relative cursor-pointer overflow-hidden rounded-[0.95rem] border border-border/75 bg-card/95 p-4 shadow-[0_18px_48px_rgba(0,0,0,0.18)] transition-all duration-200 hover:-translate-y-1 hover:border-primary/35 hover:shadow-[0_22px_60px_rgba(12,18,30,0.28)] motion-reduce:transform-none motion-reduce:transition-none"
              >
                <div className="absolute inset-x-0 top-0 h-px bg-gradient-to-r from-transparent via-primary/45 to-transparent opacity-60" />
                <div className="flex items-start justify-between gap-3">
                  <div className="space-y-3">
                    <div className="flex flex-wrap gap-2">
                      <Badge variant={statusBadgeVariant(item.status)}>{item.status}</Badge>
                      {hasActiveProductionStatus(item.production_status) ? (
                        <Badge variant={productionStatusBadgeVariant(item.production_status)}>
                          {formatProductionStatus(item.production_status)}
                        </Badge>
                      ) : null}
                      <Badge variant="outline">{item.category || 'uncategorized'}</Badge>
                      <Badge variant={recommendationBadgeVariant(item.latest_recommendation)}>
                        {item.latest_recommendation || 'unscored'}
                      </Badge>
                    </div>
                    <div className="space-y-2">
                      <h3 className="text-base font-semibold leading-tight text-foreground">
                        {backlogTitle(item)}
                      </h3>
                      <p className="text-sm text-foreground/72">{backlogSummary(item)}</p>
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
                      {item.latest_score !== undefined || item.priority_score !== undefined ? (
                        <span className="font-mono tabular-nums">{item.latest_score ?? item.priority_score}</span>
                      ) : (
                        <span className="text-foreground/30">—</span>
                      )}
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
                    {item.source_theme && <span>Theme: {item.source_theme}</span>}
                    {item.evidence && <span>Evidence attached</span>}
                    {backlogHook(item) && <span>Hook ready</span>}
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
        </>
      ) : (
        <DataTable
          columns={[
            {
              id: 'idea',
              header: 'Idea',
              render: (item) => (
                <div className="space-y-1">
                  <p className="text-sm font-medium text-foreground">{backlogTitle(item)}</p>
                  <p className="text-xs text-muted-foreground">{backlogSummary(item)}</p>
                  <div className="flex flex-wrap items-center gap-2 text-xs text-muted-foreground">
                    <span className="font-mono">{item.idea_id.slice(0, 8)}</span>
                    {item.selection_reasoning ? (
                      <span className="truncate">Reason: {item.selection_reasoning}</span>
                    ) : null}
                  </div>
                </div>
              ),
              className: 'min-w-[22rem]',
            },
            {
              id: 'status',
              header: 'Backlog status',
              render: (item) => (
                <div className="space-y-2">
                  <Badge variant={statusBadgeVariant(item.status)}>{item.status}</Badge>
                  <NativeSelect
                    value={item.status}
                    onChange={(event) => {
                      if (onUpdateStatus) {
                        void runAction(`${item.idea_id}-status`, async () =>
                          onUpdateStatus(item.idea_id, { status: event.target.value }),
                        )
                      }
                    }}
                    disabled={!onUpdateStatus || busyKey === `${item.idea_id}-status`}
                    className="h-9 min-w-[10rem] rounded-md"
                  >
                    {STATUS_OPTIONS.map((status) => (
                      <option key={status} value={status}>
                        {status}
                      </option>
                    ))}
                  </NativeSelect>
                </div>
              ),
            },
            {
              id: 'pipeline',
              header: 'Pipeline',
              render: (item) =>
                hasActiveProductionStatus(item.production_status) ? (
                  <Badge variant={productionStatusBadgeVariant(item.production_status)}>
                    {formatProductionStatus(item.production_status)}
                  </Badge>
                ) : (
                  <span className="text-xs text-muted-foreground">idle</span>
                ),
            },
            {
              id: 'category',
              header: 'Category',
              render: (item) => <span className="text-foreground/80">{item.category || '—'}</span>,
            },
            {
              id: 'score',
              header: 'Score',
              render: (item) => (
                <span className="font-mono text-xs tabular-nums text-muted-foreground">
                  {item.latest_score ?? '—'}
                </span>
              ),
            },
            {
              id: 'recommendation',
              header: 'Recommendation',
              render: (item) => (
                <Badge variant={recommendationBadgeVariant(item.latest_recommendation)}>
                  {item.latest_recommendation || 'unscored'}
                </Badge>
              ),
            },
            {
              id: 'theme',
              header: 'Theme',
              render: (item) => (
                <span className="max-w-[12rem] truncate text-xs text-muted-foreground">
                  {item.source_theme || '—'}
                </span>
              ),
            },
            {
              id: 'updated',
              header: 'Updated',
              render: (item) => (
                <span className="max-w-[12rem] text-xs text-muted-foreground">
                  {formatTimestamp(item.updated_at || item.created_at)}
                </span>
              ),
            },
            {
              id: 'actions',
              header: '',
              render: (item) => (
                <div className="flex items-center justify-end gap-1">
                  {renderItemActions(item)}
                </div>
              ),
              className: 'text-right',
            },
          ]}
          data={filteredItems}
          keyField="idea_id"
          onRowClick={(item, e) => navigateToDetail(item.idea_id, e)}
          selection={{
            selectedIds: selectedIdeaIds,
            onToggle: toggleSelect,
            onToggleAll: toggleSelectAll,
          }}
          bulkActions={
            selectedIdeaIds.size > 0 ? (
              <div className="flex items-center justify-between rounded-xl border border-border bg-surface/80 px-4 py-3 shadow-sm">
                <div className="flex items-center gap-3">
                  <span className="text-sm font-medium text-foreground">
                    {selectedIdeaIds.size} selected
                  </span>
                  <Button
                    type="button"
                    variant="ghost"
                    size="sm"
                    onClick={toggleSelectAll}
                    className="h-8 text-xs"
                  >
                    {selectedIdeaIds.size === filteredItems.length ? 'Deselect all' : 'Select all'}
                  </Button>
                  <Button
                    type="button"
                    variant="ghost"
                    size="sm"
                    onClick={clearSelection}
                    className="h-8 text-xs"
                  >
                    Clear
                  </Button>
                </div>
                <Button
                  type="button"
                  variant="destructive"
                  size="sm"
                  onClick={() => setBulkDeleteConfirm(new Set(selectedIdeaIds))}
                  className="h-8 gap-2"
                >
                  <Trash2 className="h-3.5 w-3.5" />
                  Delete selected
                </Button>
              </div>
            ) : undefined
          }
        />
      )}

      {deleteConfirm && (
        <Dialog open={true} onOpenChange={(open) => !open && setDeleteConfirm(null)}>
          <DialogContent>
            <DialogHeader>
              <DialogTitle>Delete backlog item?</DialogTitle>
              <DialogDescription>
                This will permanently remove &ldquo;{deleteConfirm.title}&rdquo; from the backlog. This action cannot be undone.
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

      {startConfirm && (
        <Dialog open={true} onOpenChange={(open) => !open && setStartConfirm(null)}>
          <DialogContent>
            <DialogHeader>
              <DialogTitle>Start production?</DialogTitle>
              <DialogDescription>
                This will launch the pipeline for &ldquo;{startConfirm.title}&rdquo;. The item will move to the production pipeline.
              </DialogDescription>
            </DialogHeader>
            <DialogFooter>
              <Button
                type="button"
                variant="outline"
                onClick={() => setStartConfirm(null)}
                disabled={busyKey === `${startConfirm.ideaId}-start`}
              >
                Cancel
              </Button>
              <Button
                type="button"
                variant="default"
                onClick={() => {
                  void runAction(`${startConfirm.ideaId}-start`, async () => {
                    if (onStartProduction) {
                      const pipelineId = await onStartProduction(startConfirm.ideaId)
                      if (pipelineId) {
                        setStartConfirm(null)
                        router.push(`/content-gen/pipeline/${pipelineId}`)
                      }
                    }
                  })
                }}
                disabled={busyKey === `${startConfirm.ideaId}-start`}
              >
                {busyKey === `${startConfirm.ideaId}-start` ? 'Starting...' : 'Start Production'}
              </Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>
      )}

      {bulkDeleteConfirm && (
        <Dialog open={true} onOpenChange={(open) => !open && setBulkDeleteConfirm(null)}>
          <DialogContent>
            <DialogHeader>
              <DialogTitle>Delete {bulkDeleteConfirm.size} backlog items?</DialogTitle>
              <DialogDescription>
                This will permanently remove {bulkDeleteConfirm.size} item{bulkDeleteConfirm.size === 1 ? '' : 's'} from the backlog. This action cannot be undone.
              </DialogDescription>
            </DialogHeader>
            <DialogFooter>
              <Button
                type="button"
                variant="outline"
                onClick={() => setBulkDeleteConfirm(null)}
              >
                Cancel
              </Button>
              <Button
                type="button"
                variant="destructive"
                onClick={() => {
                  const ids = Array.from(bulkDeleteConfirm)
                  void runAction('bulk-delete', async () => {
                    if (onDelete) {
                      await Promise.all(ids.map((id) => onDelete(id)))
                    }
                  })
                  setBulkDeleteConfirm(null)
                  clearSelection()
                }}
              >
                Delete {bulkDeleteConfirm.size} item{bulkDeleteConfirm.size === 1 ? '' : 's'}
              </Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>
      )}
    </div>
  )
}
