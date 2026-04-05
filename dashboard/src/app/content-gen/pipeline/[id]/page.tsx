'use client'

import { useEffect, useRef, useState } from 'react'
import { useParams } from 'next/navigation'
import { StopCircle } from 'lucide-react'

import { PipelineProgressTracker, type StageState } from '@/components/content-gen/pipeline-progress-tracker'
import { StageResultPanel } from '@/components/content-gen/stage-result-panel'
import { StageTraceSummary } from '@/components/content-gen/stage-trace-summary'
import {
  LoadStrategyPanel,
  PlanOpportunityPanel,
  BuildBacklogPanel,
  ScoreIdeasPanel,
  GenerateAnglesPanel,
  BuildResearchPackPanel,
  RunScriptingPanel,
  VisualTranslationPanel,
  ProductionBriefPanel,
  PackagingPanel,
  HumanQCPanel,
  PublishQueuePanel,
  PerformanceAnalysisPanel,
} from '@/components/content-gen/stage-panels'
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import useContentGen from '@/hooks/useContentGen'
import type { PipelineContext, PipelineStageName, PipelineStageTrace } from '@/types/content-gen'
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

const STAGE_PANEL_MAP: Record<
  PipelineStageName,
  (props: { ctx: PipelineContext; pipelineId?: string; onApprove?: (pipelineId: string) => Promise<void> }) => React.ReactNode
> = {
  load_strategy: ({ ctx }) => <LoadStrategyPanel ctx={ctx} />,
  plan_opportunity: ({ ctx }) => <PlanOpportunityPanel ctx={ctx} />,
  build_backlog: ({ ctx }) => <BuildBacklogPanel ctx={ctx} />,
  score_ideas: ({ ctx }) => <ScoreIdeasPanel ctx={ctx} />,
  generate_angles: ({ ctx }) => <GenerateAnglesPanel ctx={ctx} />,
  build_research_pack: ({ ctx }) => <BuildResearchPackPanel ctx={ctx} />,
  run_scripting: ({ ctx }) => <RunScriptingPanel ctx={ctx} />,
  visual_translation: ({ ctx }) => <VisualTranslationPanel ctx={ctx} />,
  production_brief: ({ ctx }) => <ProductionBriefPanel ctx={ctx} />,
  packaging: ({ ctx }) => <PackagingPanel ctx={ctx} />,
  human_qc: ({ ctx, pipelineId, onApprove }) =>
    pipelineId && onApprove ? <HumanQCPanel ctx={ctx} pipelineId={pipelineId} onApprove={onApprove} /> : null,
  publish_queue: ({ ctx }) => <PublishQueuePanel ctx={ctx} />,
  performance_analysis: ({ ctx }) => <PerformanceAnalysisPanel ctx={ctx} />,
}

function renderStageContent(
  ctx: PipelineContext,
  stageName: PipelineStageName,
  pipelineId: string,
  onApprove: (pipelineId: string) => Promise<void>,
) {
  const Panel = STAGE_PANEL_MAP[stageName]

  return Panel({ ctx, pipelineId, onApprove })
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
                    renderStageContent(pipelineContext, stageName, pipelineId, approveQC) ?? (
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
