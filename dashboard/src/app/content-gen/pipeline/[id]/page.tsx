'use client'

import { useEffect, useRef, useState } from 'react'
import { useParams } from 'next/navigation'
import { StopCircle } from 'lucide-react'

import { PipelineProgressTracker, type StageState } from '@/components/content-gen/pipeline-progress-tracker'
import { QCGatePanel } from '@/components/content-gen/qc-gate-panel'
import { ScriptViewer } from '@/components/content-gen/script-viewer'
import { StageResultPanel } from '@/components/content-gen/stage-result-panel'
import { StageTraceSummary } from '@/components/content-gen/stage-trace-summary'
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import useContentGen from '@/hooks/useContentGen'
import { getStatusBadgeVariant } from '@/lib/utils'
import type { BacklogItem, IdeaScores, PipelineContext, PipelineStageName, PipelineStageTrace } from '@/types/content-gen'
import {
  PIPELINE_STAGE_ORDER,
  PIPELINE_STAGE_SHORT_LABELS,
  TOTAL_PIPELINE_STAGES,
} from '@/types/content-gen'

function normalizeTraceState(status: string): Exclude<StageState, 'pending' | 'running'> {
  if (status === 'failed' || status === 'skipped') {
    return status
  }
  return 'completed'
}

function findSelectedIdeaId(ctx: PipelineContext): string | null {
  return (
    ctx.angles?.idea_id ||
    ctx.research_pack?.idea_id ||
    ctx.visual_plan?.idea_id ||
    ctx.production_brief?.idea_id ||
    ctx.packaging?.idea_id ||
    ctx.publish_item?.idea_id ||
    ctx.backlog?.items.find((item) => item.status === 'selected')?.idea_id ||
    ctx.scoring?.produce_now[0] ||
    null
  )
}

function findSelectedIdea(ctx: PipelineContext): { item: BacklogItem | null; score: IdeaScores | null } {
  const selectedIdeaId = findSelectedIdeaId(ctx)
  return {
    item: selectedIdeaId ? ctx.backlog?.items.find((item) => item.idea_id === selectedIdeaId) ?? null : null,
    score: selectedIdeaId ? ctx.scoring?.scores.find((score) => score.idea_id === selectedIdeaId) ?? null : null,
  }
}

function buildShortlist(ctx: PipelineContext): Array<{ item: BacklogItem; score: IdeaScores | null }> {
  const scoredIdeas = [...(ctx.scoring?.scores ?? [])].sort((left, right) => right.total_score - left.total_score)
  const shortlistIds = ctx.scoring?.produce_now?.length
    ? ctx.scoring.produce_now
    : scoredIdeas.slice(0, 3).map((score) => score.idea_id)

  return shortlistIds
    .map((ideaId) => ({
      item: ctx.backlog?.items.find((candidate) => candidate.idea_id === ideaId) ?? null,
      score: ctx.scoring?.scores.find((candidate) => candidate.idea_id === ideaId) ?? null,
    }))
    .filter((entry): entry is { item: BacklogItem; score: IdeaScores | null } => Boolean(entry.item))
}

function SectionList({
  label,
  items,
  emptyLabel = 'None recorded',
}: {
  label: string
  items: string[]
  emptyLabel?: string
}) {
  return (
    <div className="space-y-2">
      <p className="text-[11px] font-mono uppercase tracking-[0.22em] text-muted-foreground">
        {label}
      </p>
      {items.length > 0 ? (
        <ul className="space-y-2">
          {items.map((item, index) => (
            <li
              key={`${label}-${index}`}
              className="rounded-xl border border-border/70 bg-background/55 px-3 py-2 text-sm text-foreground/80"
            >
              {item}
            </li>
          ))}
        </ul>
      ) : (
        <p className="text-sm text-muted-foreground">{emptyLabel}</p>
      )}
    </div>
  )
}

function SummaryField({
  label,
  value,
}: {
  label: string
  value: string | null | undefined
}) {
  if (!value) {
    return null
  }

  return (
    <div className="rounded-xl border border-border/70 bg-background/55 px-3 py-3">
      <p className="text-[11px] font-mono uppercase tracking-[0.22em] text-muted-foreground">
        {label}
      </p>
      <p className="mt-2 text-sm leading-relaxed text-foreground/82">{value}</p>
    </div>
  )
}

export default function PipelineDetailPage() {
  const params = useParams()
  const pipelineId = params.id as string
  const wsRef = useRef<WebSocket | null>(null)

  const selectPipeline = useContentGen((state) => state.selectPipeline)
  const stopPipeline = useContentGen((state) => state.stopPipeline)
  const approveQC = useContentGen((state) => state.approveQC)
  const pipelineContext = useContentGen((state) => state.pipelineContext)
  const pipelines = useContentGen((state) => state.pipelines)
  const error = useContentGen((state) => state.error)

  const currentPipeline = pipelines.find((pipeline) => pipeline.pipeline_id === pipelineId)
  const status = currentPipeline?.status ?? 'unknown'
  const pipelineTheme = pipelineContext?.theme || currentPipeline?.theme || 'Pipeline'
  const currentStage = pipelineContext?.current_stage ?? currentPipeline?.current_stage ?? 0
  const stageTraces = pipelineContext?.stage_traces ?? []
  const traceByStage = new Map<number, PipelineStageTrace>(stageTraces.map((trace) => [trace.stage_index, trace]))
  const selectedIdea = pipelineContext ? findSelectedIdea(pipelineContext) : { item: null, score: null }
  const shortlistedIdeas = pipelineContext ? buildShortlist(pipelineContext) : []
  const alternateIdeas = shortlistedIdeas.filter((entry) => entry.item.idea_id !== selectedIdea.item?.idea_id)
  const selectedAngle = pipelineContext?.angles?.angle_options.find(
    (option) => option.angle_id === pipelineContext.angles?.selected_angle_id,
  )
  const alternateAngles = pipelineContext?.angles?.angle_options.filter(
    (option) => option.angle_id !== pipelineContext.angles?.selected_angle_id,
  ) ?? []

  const [stageStates, setStageStates] = useState<Record<number, StageState>>({})

  useEffect(() => {
    if (pipelineId) {
      void selectPipeline(pipelineId)
    }
  }, [pipelineId, selectPipeline])

  useEffect(() => {
    if (!pipelineContext?.stage_traces?.length) {
      return
    }

    setStageStates((previous) => {
      const nextState = { ...previous }
      for (const trace of pipelineContext.stage_traces) {
        nextState[trace.stage_index] = normalizeTraceState(trace.status)
      }
      return nextState
    })
  }, [pipelineContext])

  useEffect(() => {
    if (!pipelineId) {
      return
    }

    const wsBaseUrl = process.env.NEXT_PUBLIC_CC_WS_BASE_URL || 'ws://localhost:8000/ws'
    const wsUrl = `${wsBaseUrl}/content-gen/pipeline/${pipelineId}`
    const ws = new WebSocket(wsUrl)
    wsRef.current = ws

    ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data) as Record<string, unknown>
        if (data.type === 'pipeline_stage_started' && typeof data.stage_index === 'number') {
          const stageIndex = data.stage_index
          setStageStates((previous) => ({
            ...previous,
            [stageIndex]: 'running',
          }))
        } else if (data.type === 'pipeline_stage_completed' && typeof data.stage_index === 'number') {
          const stageIndex = data.stage_index
          setStageStates((previous) => ({
            ...previous,
            [stageIndex]:
              data.stage_status === 'failed' || data.stage_status === 'skipped'
                ? data.stage_status
                : 'completed',
          }))
        } else if (data.type === 'pipeline_stage_failed' && typeof data.stage_index === 'number') {
          const stageIndex = data.stage_index
          setStageStates((previous) => ({
            ...previous,
            [stageIndex]: 'failed',
          }))
        } else if (data.type === 'pipeline_stage_skipped' && typeof data.stage_index === 'number') {
          const stageIndex = data.stage_index
          setStageStates((previous) => ({
            ...previous,
            [stageIndex]: 'skipped',
          }))
        } else if (data.type === 'pipeline_completed' || data.type === 'pipeline_cancelled') {
          void selectPipeline(pipelineId)
        }
      } catch {
        // Ignore malformed websocket payloads.
      }
    }

    ws.onclose = () => {
      wsRef.current = null
    }

    return () => {
      ws.close()
      wsRef.current = null
    }
  }, [pipelineId, selectPipeline])

  const renderStageContent = (ctx: PipelineContext, stageName: PipelineStageName) => {
    switch (stageName) {
      case 'load_strategy':
        return ctx.strategy ? (
          <div className="grid gap-3 lg:grid-cols-2">
            <SummaryField label="Niche" value={ctx.strategy.niche || 'Not set'} />
            <SummaryField label="Tone rules" value={ctx.strategy.tone_rules.join(' | ') || 'No tone rules yet'} />
            <SectionList label="Content pillars" items={ctx.strategy.content_pillars} emptyLabel="No pillars configured" />
            <SectionList label="Platforms" items={ctx.strategy.platforms} emptyLabel="No platforms configured" />
          </div>
        ) : null

      case 'plan_opportunity':
        return ctx.opportunity_brief ? (
          <div className="space-y-4">
            <div className="grid gap-3 lg:grid-cols-2">
              <SummaryField label="Goal" value={ctx.opportunity_brief.goal || 'No goal captured'} />
              <SummaryField
                label="Primary audience"
                value={ctx.opportunity_brief.primary_audience_segment || 'No audience captured'}
              />
              <SummaryField
                label="Content objective"
                value={ctx.opportunity_brief.content_objective || 'No content objective captured'}
              />
              <SummaryField
                label="Freshness rationale"
                value={ctx.opportunity_brief.freshness_rationale || 'No freshness rationale captured'}
              />
            </div>
            <div className="grid gap-4 lg:grid-cols-2">
              <SectionList label="Problem statements" items={ctx.opportunity_brief.problem_statements} />
              <SectionList label="Sub-angles" items={ctx.opportunity_brief.sub_angles} />
              <SectionList label="Proof requirements" items={ctx.opportunity_brief.proof_requirements} />
              <SectionList label="Success criteria" items={ctx.opportunity_brief.success_criteria} />
            </div>
          </div>
        ) : null

      case 'build_backlog':
        return ctx.backlog ? (
          <div className="space-y-4">
            <div className="flex flex-wrap gap-2">
              <Badge variant="info">{ctx.backlog.items.length} ideas</Badge>
              <Badge variant="secondary">
                {ctx.backlog.items.filter((item) => item.status === 'selected').length} selected
              </Badge>
              {ctx.backlog.rejected_count > 0 ? (
                <Badge variant="warning">{ctx.backlog.rejected_count} rejected</Badge>
              ) : null}
            </div>
            {selectedIdea.item ? (
              <div className="rounded-[1rem] border border-border/80 bg-background/55 p-4">
                <p className="text-[11px] font-mono uppercase tracking-[0.22em] text-muted-foreground">
                  Selected backlog item
                </p>
                <p className="mt-2 text-sm font-medium text-foreground">{selectedIdea.item.idea}</p>
                <p className="mt-2 text-sm leading-relaxed text-foreground/75">{selectedIdea.item.potential_hook}</p>
              </div>
            ) : null}
            <SectionList
              label="Rejected reasons"
              items={ctx.backlog.rejection_reasons}
              emptyLabel="No backlog rejections recorded"
            />
          </div>
        ) : null

      case 'score_ideas':
        return ctx.scoring ? (
          <div className="space-y-4">
            <div className="flex flex-wrap gap-2">
              <Badge variant="success">{ctx.scoring.produce_now.length} produce now</Badge>
              <Badge variant="secondary">{ctx.scoring.hold.length} hold</Badge>
              <Badge variant="destructive">{ctx.scoring.killed.length} kill</Badge>
            </div>

            {selectedIdea.item ? (
              <div className="rounded-[1rem] border border-success/25 bg-success-muted/10 p-4">
                <div className="flex flex-wrap items-center gap-2">
                  <Badge variant="success">Chosen idea</Badge>
                  {selectedIdea.score ? (
                    <Badge variant="outline">score {selectedIdea.score.total_score}</Badge>
                  ) : null}
                  {selectedIdea.score?.recommendation ? (
                    <Badge variant={getStatusBadgeVariant(selectedIdea.score.recommendation)}>
                      {selectedIdea.score.recommendation}
                    </Badge>
                  ) : null}
                </div>
                <p className="mt-3 text-sm font-medium text-foreground">{selectedIdea.item.idea}</p>
                <p className="mt-2 text-sm text-foreground/72">
                  {selectedIdea.item.problem}
                </p>
                {selectedIdea.score?.reason ? (
                  <p className="mt-3 text-sm leading-relaxed text-foreground/78">
                    {selectedIdea.score.reason}
                  </p>
                ) : null}
              </div>
            ) : null}

            <div className="space-y-3">
              <p className="text-[11px] font-mono uppercase tracking-[0.22em] text-muted-foreground">
                Shortlist context
              </p>
              {alternateIdeas.length > 0 ? (
                <div className="grid gap-3">
                  {alternateIdeas.map(({ item, score }) => (
                    <div
                      key={item.idea_id}
                      className="rounded-[1rem] border border-border/70 bg-background/45 px-4 py-3"
                    >
                      <div className="flex flex-wrap items-center gap-2">
                        <Badge variant="secondary">{item.idea_id}</Badge>
                        {score ? <Badge variant="outline">score {score.total_score}</Badge> : null}
                        {score?.recommendation ? (
                          <Badge variant={getStatusBadgeVariant(score.recommendation)}>
                            {score.recommendation}
                          </Badge>
                        ) : null}
                      </div>
                      <p className="mt-2 text-sm font-medium text-foreground/90">{item.idea}</p>
                      {score?.reason ? (
                        <p className="mt-2 text-sm leading-relaxed text-foreground/72">{score.reason}</p>
                      ) : null}
                    </div>
                  ))}
                </div>
              ) : (
                <p className="text-sm text-muted-foreground">No alternate shortlist ideas recorded.</p>
              )}
            </div>
          </div>
        ) : null

      case 'generate_angles':
        return ctx.angles ? (
          <div className="space-y-4">
            {selectedAngle ? (
              <div className="rounded-[1rem] border border-primary/20 bg-primary/10 p-4">
                <div className="flex flex-wrap items-center gap-2">
                  <Badge variant="info">Selected angle</Badge>
                  <Badge variant="outline">{selectedAngle.format || 'Format pending'}</Badge>
                </div>
                <p className="mt-3 text-sm font-medium text-foreground">{selectedAngle.core_promise}</p>
                <p className="mt-2 text-sm text-foreground/72">{selectedAngle.viewer_problem}</p>
                {ctx.angles.selection_reasoning ? (
                  <p className="mt-3 text-sm leading-relaxed text-foreground/78">
                    {ctx.angles.selection_reasoning}
                  </p>
                ) : null}
              </div>
            ) : null}

            <div className="space-y-3">
              <p className="text-[11px] font-mono uppercase tracking-[0.22em] text-muted-foreground">
                Alternate angles
              </p>
              {alternateAngles.length > 0 ? (
                <div className="grid gap-3">
                  {alternateAngles.map((angle) => (
                    <div
                      key={angle.angle_id}
                      className="rounded-[1rem] border border-border/70 bg-background/45 px-4 py-3"
                    >
                      <p className="text-sm font-medium text-foreground/88">{angle.core_promise}</p>
                      <p className="mt-2 text-sm text-foreground/72">{angle.why_this_version_should_exist}</p>
                    </div>
                  ))}
                </div>
              ) : (
                <p className="text-sm text-muted-foreground">No alternate angles recorded.</p>
              )}
            </div>
          </div>
        ) : null

      case 'build_research_pack':
        return ctx.research_pack ? (
          <div className="grid gap-4 lg:grid-cols-2">
            <SectionList label="Proof points" items={ctx.research_pack.proof_points} />
            <SectionList label="Claims requiring verification" items={ctx.research_pack.claims_requiring_verification} />
            <SectionList label="Key facts" items={ctx.research_pack.key_facts} />
            <SummaryField
              label="Research stop reason"
              value={ctx.research_pack.research_stop_reason || 'No stop reason recorded'}
            />
          </div>
        ) : null

      case 'run_scripting':
        return ctx.scripting ? (
          <ScriptViewer
            content={
              ctx.scripting.qc?.final_script ||
              ctx.scripting.tightened?.content ||
              ctx.scripting.draft?.content ||
              ''
            }
            label="Final Script"
          />
        ) : null

      case 'visual_translation':
        return ctx.visual_plan ? (
          <div className="space-y-4">
            <SummaryField
              label="Visual refresh check"
              value={ctx.visual_plan.visual_refresh_check || 'No visual refresh note captured'}
            />
            <SectionList
              label="Beat coverage"
              items={ctx.visual_plan.visual_plan.map((beat) => `${beat.beat}: ${beat.visual || beat.on_screen_text}`)}
            />
          </div>
        ) : null

      case 'production_brief':
        return ctx.production_brief ? (
          <div className="grid gap-4 lg:grid-cols-2">
            <SummaryField label="Location" value={ctx.production_brief.location || 'No location captured'} />
            <SummaryField label="Setup" value={ctx.production_brief.setup || 'No setup captured'} />
            <SectionList label="Props" items={ctx.production_brief.props} emptyLabel="No props listed" />
            <SectionList label="Assets to prepare" items={ctx.production_brief.assets_to_prepare} emptyLabel="No assets listed" />
          </div>
        ) : null

      case 'packaging':
        return ctx.packaging ? (
          <div className="space-y-3">
            {ctx.packaging.platform_packages.map((pkg, index) => (
              <div
                key={`${pkg.platform}-${index}`}
                className="rounded-[1rem] border border-border/70 bg-background/45 px-4 py-3"
              >
                <div className="flex flex-wrap items-center gap-2">
                  <Badge variant="outline">{pkg.platform}</Badge>
                  <Badge variant="secondary">{pkg.keywords.length} keywords</Badge>
                </div>
                <p className="mt-2 text-sm font-medium text-foreground/90">{pkg.primary_hook}</p>
                {pkg.alternate_hooks.length > 0 ? (
                  <p className="mt-2 text-sm text-foreground/72">
                    Alternates: {pkg.alternate_hooks.join(' | ')}
                  </p>
                ) : null}
              </div>
            ))}
          </div>
        ) : null

      case 'human_qc':
        return ctx.qc_gate ? (
          <QCGatePanel qcGate={ctx.qc_gate} pipelineId={pipelineId} onApprove={approveQC} />
        ) : null

      case 'publish_queue':
        return ctx.publish_item ? (
          <div className="grid gap-3 lg:grid-cols-2">
            <SummaryField label="Platform" value={ctx.publish_item.platform || 'No platform recorded'} />
            <SummaryField label="Publish time" value={ctx.publish_item.publish_datetime || 'No publish time recorded'} />
            <SectionList label="Cross-post targets" items={ctx.publish_item.cross_post_targets} emptyLabel="No cross-post targets" />
            <SummaryField
              label="First 30 minute plan"
              value={ctx.publish_item.first_30_minute_engagement_plan || 'No engagement plan recorded'}
            />
          </div>
        ) : null

      case 'performance_analysis':
        return ctx.performance ? (
          <div className="grid gap-4 lg:grid-cols-2">
            <SectionList label="What worked" items={ctx.performance.what_worked} />
            <SectionList label="What failed" items={ctx.performance.what_failed} />
            <SectionList label="Follow-up ideas" items={ctx.performance.follow_up_ideas} />
            <SummaryField label="Next test" value={ctx.performance.next_test || 'No next test recorded'} />
          </div>
        ) : null
    }
  }

  const getStageStatus = (stageIndex: number): StageState => {
    const explicitState = stageStates[stageIndex]
    if (explicitState) {
      return explicitState
    }

    const trace = traceByStage.get(stageIndex)
    if (trace) {
      return normalizeTraceState(trace.status)
    }

    if (idxIsCompleted(stageIndex, currentStage, status)) {
      return 'completed'
    }
    if (stageIndex === currentStage && status === 'running') {
      return 'running'
    }
    return 'pending'
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-4">
          <div>
            <h1 className="text-lg font-display font-semibold tracking-tight">
              Pipeline
            </h1>
            <p className="mt-0.5 text-xs text-muted-foreground">{pipelineTheme}</p>
          </div>
          {pipelineContext?.iteration_state ? (
            <Badge variant="info">
              iteration {pipelineContext.iteration_state.current_iteration}/{pipelineContext.iteration_state.max_iterations}
            </Badge>
          ) : null}
        </div>
        <div className="flex items-center gap-3">
          <span className="text-[11px] font-mono text-muted-foreground tabular-nums">
            {pipelineId.slice(0, 8)}
          </span>
          {(status === 'running' || status === 'queued') && (
            <Button
              type="button"
              variant="destructive"
              onClick={() => void stopPipeline(pipelineId)}
              className="h-9 gap-1.5 px-3"
            >
              <StopCircle className="h-3.5 w-3.5" />
              Stop
            </Button>
          )}
        </div>
      </div>

      {error ? (
        <Alert variant="destructive">
          <AlertTitle>Pipeline error</AlertTitle>
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      ) : null}

      {stageTraces.length > 0 ? (
        <div className="flex flex-wrap gap-2">
          <Badge variant="success">
            {stageTraces.filter((trace) => trace.status === 'completed').length} completed
          </Badge>
          <Badge variant="warning">
            {stageTraces.filter((trace) => trace.status === 'skipped').length} skipped
          </Badge>
          <Badge variant="destructive">
            {stageTraces.filter((trace) => trace.status === 'failed').length} failed
          </Badge>
          <Badge variant="outline">
            {stageTraces.reduce((count, trace) => count + trace.warnings.length, 0)} warnings
          </Badge>
        </div>
      ) : null}

      <div className="grid grid-cols-1 gap-8 lg:grid-cols-[200px_1fr]">
        <aside className="hidden lg:block">
          <div className="sticky top-8">
            <PipelineProgressTracker currentStage={currentStage} stageStates={stageStates} />
          </div>
        </aside>

        <div className="lg:hidden">
          <PipelineProgressTracker currentStage={currentStage} stageStates={stageStates} />
        </div>

        <div className="space-y-1.5">
          {PIPELINE_STAGE_ORDER.map((stageName, stageIndex) => {
            const stageStatus = getStageStatus(stageIndex)
            const trace = traceByStage.get(stageIndex)

            return (
              <StageResultPanel
                key={stageName}
                title={PIPELINE_STAGE_SHORT_LABELS[stageName]}
                stageIndex={stageIndex}
                status={stageStatus}
                defaultOpen={stageStatus !== 'pending'}
              >
                <div className="space-y-4">
                  <StageTraceSummary trace={trace} />
                  {pipelineContext ? (
                    renderStageContent(pipelineContext, stageName) ?? (
                      <p className="text-sm text-muted-foreground">No stage output recorded yet.</p>
                    )
                  ) : (
                    <p className="text-sm text-muted-foreground">Loading pipeline context...</p>
                  )}
                </div>
              </StageResultPanel>
            )
          })}
        </div>
      </div>
    </div>
  )
}

function idxIsCompleted(stageIndex: number, currentStage: number, status: string): boolean {
  if (status === 'completed' || status === 'failed' || status === 'cancelled') {
    return stageIndex <= Math.min(currentStage, TOTAL_PIPELINE_STAGES - 1)
  }
  return stageIndex < currentStage
}
