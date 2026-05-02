'use client'

import { useEffect, useState } from 'react'
import { useParams, useRouter } from 'next/navigation'
import Link from 'next/link'
import { Archive, ArrowLeft, CheckCircle2, Copy, Play, Trash2 } from 'lucide-react'

import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'
import { Badge } from '@/components/ui/badge'
import { buttonVariants } from '@/components/ui/button'
import { Button } from '@/components/ui/button'
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
  DialogBody,
  DialogFooter,
} from '@/components/ui/dialog'
import { EmptyState } from '@/components/ui/empty-state'
import { NativeSelect } from '@/components/ui/native-select'
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
import { BacklogDetailToolbar } from '@/components/content-gen/backlog-detail-toolbar'
import { BacklogItemForm } from '@/components/content-gen/backlog-item-form'
import { IdeaBacklogHeader } from '@/components/content-gen/idea-backlog-header'
import { NextActionCard } from '@/components/content-gen/next-action-card'
import { ExecutionBriefPanel } from '@/components/content-gen/execution-brief-panel'
import { useBacklog } from '@/hooks/useBacklog'
import { useStrategy } from '@/hooks/useStrategy'

function DetailSection({
  title,
  children,
  action,
}: {
  title: string
  children: React.ReactNode
  action?: React.ReactNode
}) {
  return (
    <section className="rounded-[1.15rem] border border-border/75 bg-card/70 p-5">
      <div className="mb-4 flex items-center justify-between">
        <h2 className="text-[11px] font-mono uppercase tracking-[0.18em] text-muted-foreground">
          {title}
        </h2>
        {action}
      </div>
      {children}
    </section>
  )
}

function FieldRow({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div className="grid gap-1.5 sm:grid-cols-[14rem_1fr]">
      <p className="text-xs font-medium uppercase tracking-[0.12em] text-muted-foreground/80">
        {label}
      </p>
      <div className="text-sm text-foreground/88">{value}</div>
    </div>
  )
}

function EmptyField({ children = 'Not captured yet' }: { children?: React.ReactNode }) {
  return <span className="text-sm text-muted-foreground/60 italic">{children}</span>
}

export default function BacklogDetailPage() {
  const params = useParams()
  const router = useRouter()
  const ideaId = params.ideaId as string

  const backlog = useBacklog((s) => s.backlog)
  const backlogLoading = useBacklog((s) => s.backlogLoading)
  const error = useBacklog((s) => s.error)
  const loadBacklog = useBacklog((s) => s.loadBacklog)
  const updateBacklogItem = useBacklog((s) => s.updateBacklogItem)
  const selectBacklogItem = useBacklog((s) => s.selectBacklogItem)
  const archiveBacklogItem = useBacklog((s) => s.archiveBacklogItem)
  const deleteBacklogItem = useBacklog((s) => s.deleteBacklogItem)
  const startBacklogItem = useBacklog((s) => s.startBacklogItem)
  const strategy = useStrategy((s) => s.strategy)

  const [busy, setBusy] = useState(false)
  const [actionError, setActionError] = useState<string | null>(null)
  const [deleteConfirm, setDeleteConfirm] = useState(false)
  const [editorialCopying, setEditorialCopying] = useState(false)

  const copyEditorialSummary = async () => {
    if (!item) return
    const summary = {
      title: backlogTitle(item),
      one_line_summary: backlogSummary(item),
      raw_idea: item.raw_idea ?? null,
      constraints: item.constraints ?? null,
      audience: item.audience ?? null,
      persona_detail: item.persona_detail ?? null,
      problem: item.problem ?? null,
      emotional_driver: item.emotional_driver ?? null,
      urgency_level: item.urgency_level ?? null,
      why_now: item.why_now ?? null,
      hook: backlogHook(item) || null,
      content_type: item.content_type ?? null,
      format_duration: item.format_duration ?? null,
      key_message: item.key_message ?? null,
      call_to_action: item.call_to_action ?? null,
      evidence: item.evidence ?? null,
    }
    try {
      setEditorialCopying(true)
      await navigator.clipboard.writeText(JSON.stringify(summary, null, 2))
      await new Promise((r) => setTimeout(r, 1500))
    } finally {
      setEditorialCopying(false)
    }
  }

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

      <BacklogDetailToolbar
        item={item}
        busy={busy}
        updateBacklogItem={updateBacklogItem}
        selectBacklogItem={selectBacklogItem}
        startBacklogItem={startBacklogItem}
        archiveBacklogItem={archiveBacklogItem}
        onDelete={() => setDeleteConfirm(true)}
      />

      {/* Header */}
      <IdeaBacklogHeader item={item} />

      {/* Content sections */}
      <div className="">
        <div className="space-y-5">
          <DetailSection
            title="Editorial summary"
            action={
              <button
                onClick={copyEditorialSummary}
                disabled={editorialCopying}
                className="flex items-center gap-1.5 rounded-md border border-border/60 bg-background/60 px-2.5 py-1 text-[10px] font-mono uppercase tracking-wide text-muted-foreground transition-colors hover:bg-background hover:text-foreground disabled:cursor-not-allowed disabled:opacity-50"
              >
                {editorialCopying ? (
                  <>
                    <CheckCircle2 className="h-3 w-3" />
                    Copied
                  </>
                ) : (
                  <>
                    <Copy className="h-3 w-3" />
                    Copy JSON
                  </>
                )}
              </button>
            }
          >
            <div className="space-y-4">
              <FieldRow
                label="Title"
                value={<span className="text-base font-medium">{backlogTitle(item)}</span>}
              />
              <FieldRow
                label="One-line summary"
                value={<span>{backlogSummary(item)}</span>}
              />
              <FieldRow
                label="Raw idea"
                value={item.raw_idea ? <span>{item.raw_idea}</span> : <EmptyField />}
              />
              <FieldRow
                label="Constraints"
                value={item.constraints ? <span>{item.constraints}</span> : <EmptyField />}
              />
              <FieldRow
                label="Audience"
                value={item.audience ? <span>{item.audience}</span> : <EmptyField />}
              />
              <FieldRow
                label="Persona detail"
                value={item.persona_detail ? <span>{item.persona_detail}</span> : <EmptyField />}
              />
              <FieldRow
                label="Problem"
                value={item.problem ? <span>{item.problem}</span> : <EmptyField />}
              />
              <FieldRow
                label="Emotional driver"
                value={item.emotional_driver ? <span>{item.emotional_driver}</span> : <EmptyField />}
              />
              <FieldRow
                label="Urgency level"
                value={item.urgency_level ? <span>{item.urgency_level}</span> : <EmptyField />}
              />
              <FieldRow
                label="Why now"
                value={item.why_now ? <span>{item.why_now}</span> : <EmptyField />}
              />
              <FieldRow
                label="Hook"
                value={backlogHook(item) ? <span>{backlogHook(item)}</span> : <EmptyField />}
              />
              <FieldRow
                label="Content type"
                value={item.content_type ? <span>{item.content_type}</span> : <EmptyField />}
              />
              <FieldRow
                label="Format duration"
                value={item.format_duration ? <span>{item.format_duration}</span> : <EmptyField />}
              />
              <FieldRow
                label="Key message"
                value={item.key_message ? <span>{item.key_message}</span> : <EmptyField />}
              />
              <FieldRow
                label="Call to action"
                value={item.call_to_action ? <span>{item.call_to_action}</span> : <EmptyField />}
              />
            </div>
          </DetailSection>

          <DetailSection title="Scoring and decisioning">
            <div className="space-y-4">
              <FieldRow
                label="Latest score"
                value={
                  item.latest_score !== undefined ? (
                    <span className="font-mono">{item.latest_score}</span>
                  ) : (
                    <EmptyField />
                  )
                }
              />
              <FieldRow
                label="Priority score"
                value={
                  item.priority_score !== undefined ? (
                    <span className="font-mono">{item.priority_score}</span>
                  ) : (
                    <EmptyField />
                  )
                }
              />
              <FieldRow
                label="Recommendation"
                value={
                  item.latest_recommendation ? (
                    <Badge variant={recommendationBadgeVariant(item.latest_recommendation)}>
                      {item.latest_recommendation}
                    </Badge>
                  ) : (
                    <EmptyField />
                  )
                }
              />
              <FieldRow
                label="Selection reasoning"
                value={
                  item.selection_reasoning ? (
                    <span>{item.selection_reasoning}</span>
                  ) : (
                    <EmptyField />
                  )
                }
              />
              <FieldRow
                label="Expertise reason"
                value={
                  item.expertise_reason ? <span>{item.expertise_reason}</span> : <EmptyField />
                }
              />
              <FieldRow
                label="Genericity risk"
                value={item.genericity_risk ? <span>{item.genericity_risk}</span> : <EmptyField />}
              />
              <FieldRow
                label="Proof gap note"
                value={item.proof_gap_note ? <span>{item.proof_gap_note}</span> : <EmptyField />}
              />
              <FieldRow
                label="Last scored at"
                value={
                  item.last_scored_at ? (
                    <span>{formatTimestamp(item.last_scored_at)}</span>
                  ) : (
                    <EmptyField />
                  )
                }
              />
            </div>
          </DetailSection>
        </div>

        <div className="space-y-5">
          <DetailSection title="Evidence and provenance">
            <div className="space-y-4">
              <FieldRow
                label="Source theme"
                value={item.source_theme ? <span>{item.source_theme}</span> : <EmptyField />}
              />
              <FieldRow
                label="Source"
                value={item.source ? <span>{item.source}</span> : <EmptyField />}
              />
              <FieldRow
                label="Evidence"
                value={item.evidence ? <span>{item.evidence}</span> : <EmptyField />}
              />
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
              <FieldRow
                label="Status"
                value={<Badge variant={statusBadgeVariant(item.status)}>{item.status}</Badge>}
              />
              <FieldRow
                label="Pipeline"
                value={
                  hasActiveProductionStatus(item.production_status) ? (
                    <Badge variant={productionStatusBadgeVariant(item.production_status)}>
                      {formatProductionStatus(item.production_status)}
                    </Badge>
                  ) : (
                    <EmptyField />
                  )
                }
              />
              <FieldRow
                label="Category"
                value={
                  item.category ? <Badge variant="outline">{item.category}</Badge> : <EmptyField />
                }
              />
              <FieldRow
                label="Risk level"
                value={
                  item.risk_level ? (
                    <Badge
                      variant={
                        item.risk_level === 'high'
                          ? 'destructive'
                          : item.risk_level === 'medium'
                            ? 'warning'
                            : 'secondary'
                      }
                    >
                      {item.risk_level}
                    </Badge>
                  ) : (
                    <EmptyField />
                  )
                }
              />
              <FieldRow
                label="Created at"
                value={
                  item.created_at ? <span>{formatTimestamp(item.created_at)}</span> : <EmptyField />
                }
              />
              <FieldRow
                label="Updated at"
                value={
                  item.updated_at ? <span>{formatTimestamp(item.updated_at)}</span> : <EmptyField />
                }
              />
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
                This will permanently remove &ldquo;{backlogTitle(item)}&rdquo; from the backlog.
                This action cannot be undone.
              </DialogDescription>
            </DialogHeader>
            <DialogBody>
              <p className="text-sm text-muted-foreground">
                If this item was generated by a pipeline, its source data may still be available in
                that pipeline&apos;s output.
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
