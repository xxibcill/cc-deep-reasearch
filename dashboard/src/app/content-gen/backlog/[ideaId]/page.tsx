'use client'

import { useEffect, useState } from 'react'
import { useParams, useRouter } from 'next/navigation'
import Link from 'next/link'
import { ArrowLeft, Archive, CheckCircle2, Play, Trash2 } from 'lucide-react'

import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'
import { Badge } from '@/components/ui/badge'
import { buttonVariants } from '@/components/ui/button'
import { Button } from '@/components/ui/button'
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogBody, DialogFooter } from '@/components/ui/dialog'
import { EmptyState } from '@/components/ui/empty-state'
import { NativeSelect } from '@/components/ui/native-select'
import { formatTimestamp, statusBadgeVariant, recommendationBadgeVariant, STATUS_OPTIONS } from '@/components/content-gen/backlog-shared'
import { BacklogItemForm } from '@/components/content-gen/backlog-item-form'
import { NextActionCard } from '@/components/content-gen/next-action-card'
import { ExecutionBriefPanel } from '@/components/content-gen/execution-brief-panel'
import useContentGen from '@/hooks/useContentGen'

function DetailSection({
  title,
  children,
}: {
  title: string
  children: React.ReactNode
}) {
  return (
    <section className="rounded-[1.15rem] border border-border/75 bg-card/70 p-5">
      <h2 className="mb-4 text-[11px] font-mono uppercase tracking-[0.18em] text-muted-foreground">
        {title}
      </h2>
      {children}
    </section>
  )
}

function FieldRow({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div className="grid gap-1.5 sm:grid-cols-[14rem_1fr]">
      <p className="text-xs font-medium uppercase tracking-[0.12em] text-muted-foreground/80">{label}</p>
      <div className="text-sm text-foreground/88">{value}</div>
    </div>
  )
}

function EmptyField({ children = 'Not captured yet' }: { children?: React.ReactNode }) {
  return (
    <span className="text-sm text-muted-foreground/60 italic">{children}</span>
  )
}

export default function BacklogDetailPage() {
  const params = useParams()
  const router = useRouter()
  const ideaId = params.ideaId as string

  const backlog = useContentGen((s) => s.backlog)
  const backlogLoading = useContentGen((s) => s.backlogLoading)
  const error = useContentGen((s) => s.error)
  const loadBacklog = useContentGen((s) => s.loadBacklog)
  const updateBacklogItem = useContentGen((s) => s.updateBacklogItem)
  const selectBacklogItem = useContentGen((s) => s.selectBacklogItem)
  const archiveBacklogItem = useContentGen((s) => s.archiveBacklogItem)
  const deleteBacklogItem = useContentGen((s) => s.deleteBacklogItem)
  const startBacklogItem = useContentGen((s) => s.startBacklogItem)
  const strategy = useContentGen((s) => s.strategy)

  const [busy, setBusy] = useState(false)
  const [actionError, setActionError] = useState<string | null>(null)
  const [deleteConfirm, setDeleteConfirm] = useState(false)

  useEffect(() => {
    if (backlog.length === 0) {
      void loadBacklog()
    }
  }, [backlog.length, loadBacklog])

  const item = backlog.find((i) => i.idea_id === ideaId)

  const runAction = async (key: string, action: () => Promise<void>) => {
    try {
      setBusy(true)
      setActionError(null)
      await action()
    } catch (err) {
      const msg = err instanceof Error ? err.message : String(err)
      setActionError(msg)
    } finally {
      setBusy(false)
    }
  }

  const handleDelete = async () => {
    if (!item) return
    await deleteBacklogItem(item.idea_id)
    router.push('/content-gen/backlog')
  }

  if (backlogLoading) {
    return <div className="py-8 text-center text-sm text-muted-foreground">Loading backlog...</div>
  }

  if (error) {
    return (
      <Alert variant="destructive">
        <AlertTitle>Backlog load error</AlertTitle>
        <AlertDescription>{error}</AlertDescription>
      </Alert>
    )
  }

  if (!item) {
    return (
      <div className="py-8">
        <EmptyState
          icon={ArrowLeft}
          title="Backlog item not found"
          description={`No backlog item with ID "${ideaId}" was found in the persistent backlog. The item may have been deleted or the ID is incorrect.`}
          action={{ label: 'Back to backlog', href: '/content-gen/backlog' }}
        />
      </div>
    )
  }

  return (
    <div className="space-y-6">
      {actionError && (
        <Alert variant="destructive">
          <AlertDescription>{actionError}</AlertDescription>
        </Alert>
      )}

      {/* Breadcrumb + back */}
      <div className="flex flex-wrap items-center gap-3">
        <Link
          href="/content-gen/backlog"
          className={buttonVariants({ variant: 'ghost', size: 'sm', className: 'px-3' })}
        >
          <ArrowLeft className="h-4 w-4" />
          Back
        </Link>
        <nav className="flex items-center gap-1.5 text-xs text-muted-foreground">
          <Link href="/content-gen" className="hover:text-foreground transition-colors">Content Studio</Link>
          <span>/</span>
          <Link href="/content-gen/backlog" className="hover:text-foreground transition-colors">Backlog</Link>
          <span>/</span>
          <span className="text-foreground">{item.idea.slice(0, 40)}{item.idea.length > 40 ? '…' : ''}</span>
        </nav>
      </div>

      {/* Header */}
      <div className="rounded-[1.15rem] border border-border/75 bg-card/95 p-5 shadow-[0_18px_48px_rgba(0,0,0,0.18)]">
        <div className="flex flex-col gap-4 xl:flex-row xl:items-start xl:justify-between">
          <div className="space-y-3">
            <div className="flex flex-wrap gap-2">
              <Badge variant={statusBadgeVariant(item.status)}>{item.status}</Badge>
              <Badge variant="outline">{item.category || 'uncategorized'}</Badge>
              <Badge variant={recommendationBadgeVariant(item.latest_recommendation)}>
                {item.latest_recommendation || 'unscored'}
              </Badge>
              {item.risk_level ? (
                <Badge variant={item.risk_level === 'high' ? 'destructive' : item.risk_level === 'medium' ? 'warning' : 'secondary'}>
                  {item.risk_level} risk
                </Badge>
              ) : null}
            </div>
            <h1 className="max-w-2xl text-2xl font-semibold leading-tight text-foreground">{item.idea}</h1>
            <div className="flex flex-wrap items-center gap-x-4 gap-y-1 font-mono text-xs uppercase tracking-[0.14em] text-muted-foreground">
              <span>{item.idea_id}</span>
              <span>{item.content_type || 'No content type'}</span>
              <span>Updated {formatTimestamp(item.updated_at || item.created_at)}</span>
            </div>
          </div>

          {/* Score stack */}
          <div className="flex shrink-0 gap-4 xl:flex-col xl:items-end">
            <div className="rounded-[0.95rem] border border-border/70 bg-background/45 px-4 py-3 text-right shadow-[inset_0_1px_0_rgba(255,255,255,0.04)]">
              <p className="text-[10px] font-mono uppercase tracking-[0.18em] text-muted-foreground">Score</p>
              <p className="mt-1 font-mono text-2xl tabular-nums text-foreground">
                {item.latest_score !== undefined || item.priority_score !== undefined ? (
                  <span className="font-mono tabular-nums">{item.latest_score ?? item.priority_score}</span>
                ) : (
                  <span className="text-foreground/30">—</span>
                )}
              </p>
            </div>
            <div className="rounded-[0.95rem] border border-border/70 bg-background/45 px-4 py-3 text-right shadow-[inset_0_1px_0_rgba(255,255,255,0.04)]">
              <p className="text-[10px] font-mono uppercase tracking-[0.18em] text-muted-foreground">Priority</p>
              <p className="mt-1 font-mono text-2xl tabular-nums text-foreground">
                {item.priority_score ?? '—'}
              </p>
            </div>
          </div>
        </div>
      </div>

      {/* Sticky action rail */}
      <div className="sticky top-20 z-10 flex flex-wrap items-center gap-3 rounded-[1.15rem] border border-border/75 bg-surface/92 p-4 backdrop-blur-sm">
        <div className="flex flex-wrap items-center gap-2">
          <BacklogItemForm item={item} onSubmitEdit={updateBacklogItem} />

          <Button
            type="button"
            variant="ghost"
            size="sm"
            className="h-9 gap-2"
            onClick={() => {
              if (selectBacklogItem) {
                void runAction('select', () => selectBacklogItem(item.idea_id))
              }
            }}
            disabled={busy}
            title="Select item"
          >
            <CheckCircle2 className="h-4 w-4" />
            Select item
          </Button>

          <Button
            type="button"
            variant="default"
            size="sm"
            className="h-9 gap-2"
            onClick={() => {
              if (startBacklogItem) {
                void runAction('start-production', async () => {
                  const pipelineId = await startBacklogItem(item.idea_id)
                  if (pipelineId) {
                    router.push(`/content-gen/pipeline/${pipelineId}`)
                  }
                })
              }
            }}
            disabled={busy}
            title="Start Production"
          >
            <Play className="h-4 w-4" />
            {busy ? 'Starting...' : 'Start Production'}
          </Button>

          <NativeSelect
            value={item.status}
            onChange={(event) => {
              if (updateBacklogItem) {
                void runAction('status', () =>
                  updateBacklogItem(item.idea_id, { status: event.target.value }),
                )
              }
            }}
            disabled={busy}
            className="h-9 min-w-[11rem] rounded-[0.8rem]"
          >
            {STATUS_OPTIONS.map((status) => (
              <option key={status} value={status}>{status}</option>
            ))}
          </NativeSelect>
        </div>

        <div className="ml-auto flex items-center gap-2">
          <Button
            type="button"
            variant="ghost"
            size="sm"
            className="h-9 gap-2 text-warning hover:text-warning"
            onClick={() => {
              if (archiveBacklogItem) {
                void runAction('archive', () => archiveBacklogItem(item.idea_id))
              }
            }}
            disabled={busy}
            title="Archive item"
          >
            <Archive className="h-4 w-4" />
            Archive
          </Button>
          <Button
            type="button"
            variant="ghost"
            size="sm"
            className="h-9 gap-2 text-error hover:text-error"
            onClick={() => setDeleteConfirm(true)}
            disabled={busy}
            title="Delete item"
          >
            <Trash2 className="h-4 w-4" />
            Delete
          </Button>
        </div>
      </div>

      {/* Content sections */}
      <div className="grid gap-5 xl:grid-cols-[1fr_22rem]">
        <div className="space-y-5">
          <DetailSection title="Editorial summary">
            <div className="space-y-4">
              <FieldRow label="Idea" value={<span className="text-base font-medium">{item.idea}</span>} />
              <FieldRow label="Audience" value={item.audience ? <span>{item.audience}</span> : <EmptyField />} />
              <FieldRow label="Problem" value={item.problem ? <span>{item.problem}</span> : <EmptyField />} />
              <FieldRow label="Why now" value={item.why_now ? <span>{item.why_now}</span> : <EmptyField />} />
              <FieldRow label="Potential hook" value={item.potential_hook ? <span>{item.potential_hook}</span> : <EmptyField />} />
              <FieldRow label="Content type" value={item.content_type ? <span>{item.content_type}</span> : <EmptyField />} />
            </div>
          </DetailSection>

          <DetailSection title="Scoring and decisioning">
            <div className="space-y-4">
              <FieldRow label="Latest score" value={item.latest_score !== undefined ? <span className="font-mono">{item.latest_score}</span> : <EmptyField />} />
              <FieldRow label="Priority score" value={item.priority_score !== undefined ? <span className="font-mono">{item.priority_score}</span> : <EmptyField />} />
              <FieldRow label="Recommendation" value={item.latest_recommendation ? <Badge variant={recommendationBadgeVariant(item.latest_recommendation)}>{item.latest_recommendation}</Badge> : <EmptyField />} />
              <FieldRow label="Selection reasoning" value={item.selection_reasoning ? <span>{item.selection_reasoning}</span> : <EmptyField />} />
              <FieldRow label="Expertise reason" value={item.expertise_reason ? <span>{item.expertise_reason}</span> : <EmptyField />} />
              <FieldRow label="Genericity risk" value={item.genericity_risk ? <span>{item.genericity_risk}</span> : <EmptyField />} />
              <FieldRow label="Proof gap note" value={item.proof_gap_note ? <span>{item.proof_gap_note}</span> : <EmptyField />} />
              <FieldRow label="Last scored at" value={item.last_scored_at ? <span>{formatTimestamp(item.last_scored_at)}</span> : <EmptyField />} />
            </div>
          </DetailSection>
        </div>

        <div className="space-y-5">
          <DetailSection title="Evidence and provenance">
            <div className="space-y-4">
              <FieldRow label="Source theme" value={item.source_theme ? <span>{item.source_theme}</span> : <EmptyField />} />
              <FieldRow label="Source" value={item.source ? <span>{item.source}</span> : <EmptyField />} />
              <FieldRow label="Evidence" value={item.evidence ? <span>{item.evidence}</span> : <EmptyField />} />
              {item.source_pipeline_id ? (
                <FieldRow
                  label="Source pipeline"
                  value={
                    <Link
                      href={`/content-gen/pipeline/${item.source_pipeline_id}`}
                      className="text-primary hover:underline"
                    >
                      {item.source_pipeline_id}
                    </Link>
                  }
                />
              ) : (
                <FieldRow label="Source pipeline" value={<EmptyField />} />
              )}
            </div>
          </DetailSection>

          <DetailSection title="AI Recommendations">
            <div className="space-y-4">
              <NextActionCard
                ideaId={item.idea_id}
                strategy={strategy as unknown as Record<string, unknown> | null}
                onApplySuggestedFields={async (ideaId, fields) => {
                  if (updateBacklogItem) {
                    await updateBacklogItem(ideaId, fields)
                  }
                }}
              />
              <ExecutionBriefPanel
                ideaId={item.idea_id}
                strategy={strategy as unknown as Record<string, unknown> | null}
                onStartProduction={async (id) => {
                  if (startBacklogItem) {
                    const pipelineId = await startBacklogItem(id)
                    if (pipelineId) {
                      router.push(`/content-gen/pipeline/${pipelineId}`)
                    }
                  }
                  return null
                }}
              />
            </div>
          </DetailSection>

          <DetailSection title="Operational metadata">
            <div className="space-y-4">
              <FieldRow label="Status" value={<Badge variant={statusBadgeVariant(item.status)}>{item.status}</Badge>} />
              <FieldRow label="Category" value={item.category ? <Badge variant="outline">{item.category}</Badge> : <EmptyField />} />
              <FieldRow label="Risk level" value={item.risk_level ? <Badge variant={item.risk_level === 'high' ? 'destructive' : item.risk_level === 'medium' ? 'warning' : 'secondary'}>{item.risk_level}</Badge> : <EmptyField />} />
              <FieldRow label="Created at" value={item.created_at ? <span>{formatTimestamp(item.created_at)}</span> : <EmptyField />} />
              <FieldRow label="Updated at" value={item.updated_at ? <span>{formatTimestamp(item.updated_at)}</span> : <EmptyField />} />
            </div>
          </DetailSection>
        </div>
      </div>

      {/* Delete confirmation dialog */}
      {deleteConfirm && (
        <Dialog open={true} onOpenChange={(open) => !open && setDeleteConfirm(false)}>
          <DialogContent>
            <DialogHeader>
              <DialogTitle>Delete backlog item?</DialogTitle>
              <DialogDescription>
                This will permanently remove &ldquo;{item.idea}&rdquo; from the backlog. This action cannot be undone.
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
                onClick={() => setDeleteConfirm(false)}
                disabled={busy}
              >
                Cancel
              </Button>
              <Button
                type="button"
                variant="destructive"
                onClick={() => {
                  void runAction('delete', handleDelete)
                  setDeleteConfirm(false)
                }}
                disabled={busy}
              >
                {busy ? 'Deleting...' : 'Delete item'}
              </Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>
      )}
    </div>
  )
}
