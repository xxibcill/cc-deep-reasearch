'use client'

import { useEffect, useState } from 'react'
import { useRouter } from 'next/navigation'
import { Archive, CheckCircle2, Copy, MoreHorizontal, Play, Trash2 } from 'lucide-react'

import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Alert, AlertDescription } from '@/components/ui/alert'
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogBody, DialogFooter } from '@/components/ui/dialog'
import { NativeSelect } from '@/components/ui/native-select'
import {
  lifecycleStateBadgeVariant,
  lifecycleStateLabel,
  provenanceLabel,
  formatBriefTimestamp,
  briefTitle,
  LIFECYCLE_STATE_OPTIONS,
} from '@/components/content-gen/brief-shared'
import { ItemsView, ItemsViewHeader, ItemsViewLoading, ItemsViewEmpty, ItemsViewToggle, type ItemsViewMode } from '@/components/content-gen/items-view'
import { DataTable, type DataTableColumn } from '@/components/content-gen/data-table'
import { useBriefs } from '@/hooks/useBriefs'
import type { ManagedOpportunityBrief } from '@/types/content-gen'

interface BriefIndexPanelProps {
  initialLifecycleState?: string
}

export function BriefIndexPanel({ initialLifecycleState }: BriefIndexPanelProps) {
  const router = useRouter()
  const briefs = useBriefs((s) => s.briefs)
  const loading = useBriefs((s) => s.briefsLoading)
  const loadBriefs = useBriefs((s) => s.loadBriefs)
  const archiveBrief = useBriefs((s) => s.archiveBrief)
  const cloneBrief = useBriefs((s) => s.cloneBrief)
  const approveBrief = useBriefs((s) => s.approveBrief)
  const error = useBriefs((s) => s.error)

  type BriefsViewMode = ItemsViewMode

  const [viewMode, setViewMode] = useState<BriefsViewMode>('list')
  const [lifecycleFilter, setLifecycleFilter] = useState(initialLifecycleState || '')
  const [busyKey, setBusyKey] = useState<string | null>(null)
  const [actionError, setActionError] = useState<string | null>(null)
  const [cloneConfirm, setCloneConfirm] = useState<{ briefId: string; title: string } | null>(null)

  useEffect(() => {
    void loadBriefs(lifecycleFilter || undefined)
  }, [lifecycleFilter, loadBriefs])

  const navigateToDetail = (briefId: string, e: React.MouseEvent) => {
    e.stopPropagation()
    router.push(`/content-gen/briefs/${briefId}`)
  }

  const filteredBriefs = briefs
    .filter((b) => (lifecycleFilter ? b.lifecycle_state === lifecycleFilter : true))
    .sort((left, right) => (right.updated_at || '').localeCompare(left.updated_at || ''))

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

  const columns: DataTableColumn<ManagedOpportunityBrief>[] = [
    {
      id: 'title',
      header: 'Title',
      render: (brief) => (
        <div className="space-y-1">
          <p className="text-sm font-medium text-foreground">{briefTitle(brief)}</p>
          <p className="text-xs font-mono text-muted-foreground">{brief.brief_id}</p>
        </div>
      ),
      className: 'min-w-[20rem]',
    },
    {
      id: 'lifecycle',
      header: 'Lifecycle',
      render: (brief) => (
        <Badge variant={lifecycleStateBadgeVariant(brief.lifecycle_state)}>
          {lifecycleStateLabel(brief.lifecycle_state)}
        </Badge>
      ),
    },
    {
      id: 'revisions',
      header: 'Revisions',
      render: (brief) => (
        <div className="flex items-center gap-2">
          <span className="font-mono text-sm text-foreground">{brief.revision_count}</span>
          {brief.current_revision_id !== brief.latest_revision_id && (
            <Badge variant="warning" className="text-[10px]">
              out of date
            </Badge>
          )}
        </div>
      ),
    },
    {
      id: 'provenance',
      header: 'Provenance',
      render: (brief) => (
        <span className="text-xs text-foreground/70">{provenanceLabel(brief.provenance)}</span>
      ),
    },
    {
      id: 'updated',
      header: 'Updated',
      render: (brief) => (
        <span className="text-xs text-muted-foreground">{formatBriefTimestamp(brief.updated_at)}</span>
      ),
    },
    {
      id: 'actions',
      header: 'Actions',
      render: (brief) => (
        <div className="flex items-center justify-end gap-1">
          <Button
            type="button"
            variant="ghost"
            size="icon"
            onClick={(e) => {
              e.stopPropagation()
              router.push(`/content-gen/briefs/${brief.brief_id}`)
            }}
            className="h-8 w-8 text-muted-foreground/60 transition-all duration-200 hover:-translate-y-0.5 hover:text-primary motion-reduce:transition-none"
            title="View brief"
          >
            <MoreHorizontal className="h-3.5 w-3.5" />
          </Button>
          {brief.lifecycle_state === 'draft' && (
            <Button
              type="button"
              variant="ghost"
              size="icon"
              onClick={(e) => {
                e.stopPropagation()
                void runAction(`${brief.brief_id}-approve`, () =>
                  approveBrief(brief.brief_id, brief.updated_at),
                )
              }}
              disabled={busyKey === `${brief.brief_id}-approve`}
              className="h-8 w-8 text-muted-foreground/60 transition-all duration-200 hover:-translate-y-0.5 hover:text-success motion-reduce:transition-none"
              title="Approve brief"
            >
              <CheckCircle2 className="h-3.5 w-3.5" />
            </Button>
          )}
          <Button
            type="button"
            variant="ghost"
            size="icon"
            onClick={(e) => {
              e.stopPropagation()
              setCloneConfirm({ briefId: brief.brief_id, title: briefTitle(brief) })
            }}
            disabled={busyKey === `${brief.brief_id}-clone`}
            className="h-8 w-8 text-muted-foreground/60 transition-all duration-200 hover:-translate-y-0.5 hover:text-warning motion-reduce:transition-none"
            title="Clone brief"
          >
            <Copy className="h-3.5 w-3.5" />
          </Button>
          <Button
            type="button"
            variant="ghost"
            size="icon"
            onClick={(e) => {
              e.stopPropagation()
              void runAction(`${brief.brief_id}-archive`, () =>
                archiveBrief(brief.brief_id, brief.updated_at),
              )
            }}
            disabled={busyKey === `${brief.brief_id}-archive`}
            className="h-8 w-8 text-muted-foreground/60 transition-all duration-200 hover:-translate-y-0.5 hover:text-error motion-reduce:transition-none"
            title="Archive brief"
          >
            <Archive className="h-3.5 w-3.5" />
          </Button>
        </div>
      ),
      className: 'text-right',
    },
  ]

  if (loading && briefs.length === 0) {
    return <ItemsViewLoading label="briefs" />
  }

  return (
    <div className="space-y-4">
      {actionError && (
        <Alert variant="destructive">
          <AlertDescription>{actionError}</AlertDescription>
        </Alert>
      )}

      <ItemsViewHeader
        title="Opportunity briefs"
        totalCount={briefs.length}
        visibleCount={filteredBriefs.length}
        stats={
          <div className="flex flex-wrap gap-2">
            <Badge variant="outline" className="bg-background/45">
              {filteredBriefs.length} visible
            </Badge>
            <Badge variant="success" className="bg-success/10 text-success">
              {briefs.filter((b) => b.lifecycle_state === 'approved').length} approved
            </Badge>
            <Badge variant="warning" className="bg-warning/10 text-warning">
              {briefs.filter((b) => b.lifecycle_state === 'draft').length} drafts
            </Badge>
            <Badge variant="secondary" className="bg-secondary/50">
              {briefs.filter((b) => b.lifecycle_state === 'superseded').length} superseded
            </Badge>
          </div>
        }
        controls={
          <div className="flex flex-col gap-3 sm:flex-row sm:items-end">
            <div className="space-y-1">
              <label className="text-[11px] font-mono uppercase tracking-[0.18em] text-muted-foreground">
                Lifecycle state
              </label>
              <NativeSelect
                value={lifecycleFilter}
                onChange={(event) => setLifecycleFilter(event.target.value)}
                className="h-10 min-w-[12rem]"
              >
                <option value="">All states</option>
                {LIFECYCLE_STATE_OPTIONS.map((state) => (
                  <option key={state} value={state}>
                    {lifecycleStateLabel(state)}
                  </option>
                ))}
              </NativeSelect>
            </div>
            <ItemsViewToggle value={viewMode} onChange={setViewMode} label="Briefs" />
          </div>
        }
      />

      {!filteredBriefs.length ? (
        <ItemsViewEmpty
          label="briefs"
          message="No briefs found."
          secondaryMessage={
            lifecycleFilter
              ? `No briefs in "${lifecycleStateLabel(lifecycleFilter)}" state.`
              : 'No briefs have been created yet.'
          }
        />
      ) : (
        <ItemsView mode={viewMode}>
          {viewMode === 'grid' ? (
            <>
              {filteredBriefs.map((brief) => (
                <article
                  key={brief.brief_id}
                  role="button"
                  tabIndex={0}
                  onClick={(e) => navigateToDetail(brief.brief_id, e)}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter' || e.key === ' ') {
                      e.preventDefault()
                      router.push(`/content-gen/briefs/${brief.brief_id}`)
                    }
                  }}
                  className="group relative cursor-pointer overflow-hidden rounded-[0.95rem] border border-border/75 bg-card/95 p-4 shadow-[0_18px_48px_rgba(0,0,0,0.18)] transition-all duration-200 hover:-translate-y-1 hover:border-primary/35 hover:shadow-[0_22px_60px_rgba(12,18,30,0.28)] motion-reduce:transform-none motion-reduce:transition-none"
                >
                  <div className="absolute inset-x-0 top-0 h-px bg-gradient-to-r from-transparent via-primary/45 to-transparent opacity-60" />
                  <div className="flex items-start justify-between gap-3">
                    <div className="space-y-3 flex-1 min-w-0">
                      <div className="flex flex-wrap gap-2">
                        <Badge variant={lifecycleStateBadgeVariant(brief.lifecycle_state)}>
                          {lifecycleStateLabel(brief.lifecycle_state)}
                        </Badge>
                        {brief.current_revision_id !== brief.latest_revision_id && (
                          <Badge variant="warning" className="text-[10px]">
                            out of date
                          </Badge>
                        )}
                      </div>
                      <div className="space-y-2">
                        <h3 className="text-base font-semibold leading-tight text-foreground truncate">
                          {briefTitle(brief)}
                        </h3>
                        <div className="flex flex-wrap items-center gap-x-3 gap-y-1 text-[11px] uppercase tracking-[0.16em] text-muted-foreground">
                          <span className="font-mono">{brief.brief_id.slice(0, 8)}</span>
                          <span>{formatBriefTimestamp(brief.updated_at)}</span>
                        </div>
                      </div>
                    </div>
                    <div className="min-w-[5.75rem] rounded-[0.95rem] border border-border/70 bg-background/45 px-3 py-2 text-right shadow-[inset_0_1px_0_rgba(255,255,255,0.04)]">
                      <p className="text-[10px] font-mono uppercase tracking-[0.18em] text-muted-foreground">
                        Rev
                      </p>
                      <p className="mt-1 font-mono text-lg tabular-nums text-foreground">
                        {brief.revision_count}
                      </p>
                    </div>
                  </div>
                  <div className="mt-4 flex flex-col gap-3 border-t border-border/70 pt-4">
                    <div className="flex flex-wrap items-center gap-2 text-xs text-muted-foreground">
                      <span>{provenanceLabel(brief.provenance)}</span>
                    </div>
                    <div className="flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
                      <span className="text-xs text-muted-foreground">Theme: {brief.lifecycle_state}</span>
                      <div className="flex items-center justify-end gap-1">
                        <Button
                          type="button"
                          variant="ghost"
                          size="icon"
                          onClick={(e) => {
                            e.stopPropagation()
                            router.push(`/content-gen/briefs/${brief.brief_id}`)
                          }}
                          className="h-8 w-8 text-muted-foreground/60 transition-all duration-200 hover:-translate-y-0.5 hover:text-primary motion-reduce:transition-none"
                          title="View brief"
                        >
                          <MoreHorizontal className="h-3.5 w-3.5" />
                        </Button>
                        {brief.lifecycle_state === 'draft' && (
                          <Button
                            type="button"
                            variant="ghost"
                            size="icon"
                            onClick={(e) => {
                              e.stopPropagation()
                              void runAction(`${brief.brief_id}-approve`, () =>
                                approveBrief(brief.brief_id, brief.updated_at),
                              )
                            }}
                            disabled={busyKey === `${brief.brief_id}-approve`}
                            className="h-8 w-8 text-muted-foreground/60 transition-all duration-200 hover:-translate-y-0.5 hover:text-success motion-reduce:transition-none"
                            title="Approve brief"
                          >
                            <CheckCircle2 className="h-3.5 w-3.5" />
                          </Button>
                        )}
                        <Button
                          type="button"
                          variant="ghost"
                          size="icon"
                          onClick={(e) => {
                            e.stopPropagation()
                            setCloneConfirm({ briefId: brief.brief_id, title: briefTitle(brief) })
                          }}
                          disabled={busyKey === `${brief.brief_id}-clone`}
                          className="h-8 w-8 text-muted-foreground/60 transition-all duration-200 hover:-translate-y-0.5 hover:text-warning motion-reduce:transition-none"
                          title="Clone brief"
                        >
                          <Copy className="h-3.5 w-3.5" />
                        </Button>
                        <Button
                          type="button"
                          variant="ghost"
                          size="icon"
                          onClick={(e) => {
                            e.stopPropagation()
                            void runAction(`${brief.brief_id}-archive`, () =>
                              archiveBrief(brief.brief_id, brief.updated_at),
                            )
                          }}
                          disabled={busyKey === `${brief.brief_id}-archive`}
                          className="h-8 w-8 text-muted-foreground/60 transition-all duration-200 hover:-translate-y-0.5 hover:text-error motion-reduce:transition-none"
                          title="Archive brief"
                        >
                          <Archive className="h-3.5 w-3.5" />
                        </Button>
                      </div>
                    </div>
                  </div>
                </article>
              ))}
            </>
          ) : (
            <DataTable
              columns={columns}
              data={filteredBriefs}
              keyField="brief_id"
              onRowClick={(brief, e) => navigateToDetail(brief.brief_id, e)}
            />
          )}
        </ItemsView>
      )}

      {cloneConfirm && (
        <Dialog open={true} onOpenChange={(open) => !open && setCloneConfirm(null)}>
          <DialogContent>
            <DialogHeader>
              <DialogTitle>Clone brief?</DialogTitle>
              <DialogDescription>
                This will create a new brief with the same content as &ldquo;{cloneConfirm.title}&rdquo;,
                starting in draft state.
              </DialogDescription>
            </DialogHeader>
            <DialogFooter>
              <Button
                type="button"
                variant="outline"
                onClick={() => setCloneConfirm(null)}
                disabled={busyKey === `${cloneConfirm.briefId}-clone`}
              >
                Cancel
              </Button>
              <Button
                type="button"
                variant="default"
                onClick={() => {
                  void runAction(`${cloneConfirm.briefId}-clone`, async () => {
                    const newId = await cloneBrief(cloneConfirm.briefId)
                    setCloneConfirm(null)
                    if (newId) {
                      router.push(`/content-gen/briefs/${newId}`)
                    }
                  })
                }}
                disabled={busyKey === `${cloneConfirm.briefId}-clone`}
              >
                {busyKey === `${cloneConfirm.briefId}-clone` ? 'Cloning...' : 'Clone brief'}
              </Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>
      )}
    </div>
  )
}