'use client'

import { useEffect, useState } from 'react'
import { useRouter } from 'next/navigation'
import { Archive, CheckCircle2, Copy, MoreHorizontal, Play, Trash2 } from 'lucide-react'

import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Alert, AlertDescription } from '@/components/ui/alert'
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogBody, DialogFooter } from '@/components/ui/dialog'
import { NativeSelect } from '@/components/ui/native-select'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import {
  lifecycleStateBadgeVariant,
  lifecycleStateLabel,
  provenanceLabel,
  formatBriefTimestamp,
  briefTitle,
  LIFECYCLE_STATE_OPTIONS,
} from '@/components/content-gen/brief-shared'
import useContentGen from '@/hooks/useContentGen'
import type { ManagedOpportunityBrief } from '@/types/content-gen'

interface BriefIndexPanelProps {
  initialLifecycleState?: string
}

export function BriefIndexPanel({ initialLifecycleState }: BriefIndexPanelProps) {
  const router = useRouter()
  const briefs = useContentGen((s) => s.briefs)
  const loading = useContentGen((s) => s.briefsLoading)
  const loadBriefs = useContentGen((s) => s.loadBriefs)
  const archiveBrief = useContentGen((s) => s.archiveBrief)
  const cloneBrief = useContentGen((s) => s.cloneBrief)
  const approveBrief = useContentGen((s) => s.approveBrief)
  const error = useContentGen((s) => s.error)

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

  if (loading && briefs.length === 0) {
    return <div className="py-8 text-center text-sm text-muted-foreground">Loading briefs...</div>
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
          <div className="space-y-1">
            <p className="text-sm font-medium text-foreground">Opportunity briefs</p>
            <p className="text-xs text-muted-foreground">
              {briefs.length} brief{briefs.length === 1 ? '' : 's'} total
            </p>
          </div>
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
        </div>

        <div className="mt-4 flex flex-wrap items-end gap-3">
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
        </div>
      </div>

      {!filteredBriefs.length ? (
        <div className="rounded-xl border border-dashed border-border bg-card/70 py-16 text-center">
          <p className="text-sm text-muted-foreground">No briefs found.</p>
          <p className="mt-1 text-xs text-muted-foreground/60">
            {lifecycleFilter
              ? `No briefs in "${lifecycleStateLabel(lifecycleFilter)}" state.`
              : 'No briefs have been created yet.'}
          </p>
        </div>
      ) : (
        <div className="overflow-hidden rounded-xl border border-border bg-card/95 shadow-sm">
          <Table>
            <TableHeader className="bg-surface-raised/60">
              <TableRow className="hover:bg-transparent">
                <TableHead>Title</TableHead>
                <TableHead>Lifecycle</TableHead>
                <TableHead>Revisions</TableHead>
                <TableHead>Provenance</TableHead>
                <TableHead>Updated</TableHead>
                <TableHead className="text-right">Actions</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {filteredBriefs.map((brief) => {
                const rowKey = brief.brief_id
                return (
                  <TableRow
                    key={rowKey}
                    onClick={(e) => navigateToDetail(brief.brief_id, e)}
                    className="cursor-pointer hover:bg-surface/50"
                  >
                    <TableCell className="min-w-[20rem]">
                      <div className="space-y-1">
                        <p className="text-sm font-medium text-foreground">{briefTitle(brief)}</p>
                        <p className="text-xs font-mono text-muted-foreground">{brief.brief_id}</p>
                      </div>
                    </TableCell>
                    <TableCell>
                      <Badge variant={lifecycleStateBadgeVariant(brief.lifecycle_state)}>
                        {lifecycleStateLabel(brief.lifecycle_state)}
                      </Badge>
                    </TableCell>
                    <TableCell>
                      <div className="flex items-center gap-2">
                        <span className="font-mono text-sm text-foreground">{brief.revision_count}</span>
                        {brief.current_revision_id !== brief.latest_revision_id && (
                          <Badge variant="warning" className="text-[10px]">
                            out of date
                          </Badge>
                        )}
                      </div>
                    </TableCell>
                    <TableCell>
                      <span className="text-xs text-foreground/70">
                        {provenanceLabel(brief.provenance)}
                      </span>
                    </TableCell>
                    <TableCell className="text-xs text-muted-foreground">
                      {formatBriefTimestamp(brief.updated_at)}
                    </TableCell>
                    <TableCell className="text-right">
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
                              void runAction(`${rowKey}-approve`, () =>
                                approveBrief(brief.brief_id, brief.updated_at),
                              )
                            }}
                            disabled={busyKey === `${rowKey}-approve`}
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
                          disabled={busyKey === `${rowKey}-clone`}
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
                            void runAction(`${rowKey}-archive`, () =>
                              archiveBrief(brief.brief_id, brief.updated_at),
                            )
                          }}
                          disabled={busyKey === `${rowKey}-archive`}
                          className="h-8 w-8 text-muted-foreground/60 transition-all duration-200 hover:-translate-y-0.5 hover:text-error motion-reduce:transition-none"
                          title="Archive brief"
                        >
                          <Archive className="h-3.5 w-3.5" />
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