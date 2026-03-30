'use client'

import { useEffect, useRef, useState } from 'react'
import { useParams } from 'next/navigation'
import { StopCircle } from 'lucide-react'
import useContentGen from '@/hooks/useContentGen'
import { PipelineProgressTracker } from '@/components/content-gen/pipeline-progress-tracker'
import { StageResultPanel } from '@/components/content-gen/stage-result-panel'
import { QCGatePanel } from '@/components/content-gen/qc-gate-panel'
import { ScriptViewer } from '@/components/content-gen/script-viewer'
import type { PipelineContext } from '@/types/content-gen'

const STAGE_LABELS = [
  'Load Strategy',
  'Build Backlog',
  'Score Ideas',
  'Generate Angles',
  'Build Research',
  'Run Scripting',
  'Visual Translation',
  'Production Brief',
  'Packaging',
  'Human QC',
  'Publish Queue',
  'Performance',
]

export default function PipelineDetailPage() {
  const params = useParams()
  const pipelineId = params.id as string
  const wsRef = useRef<WebSocket | null>(null)

  const selectPipeline = useContentGen((s) => s.selectPipeline)
  const stopPipeline = useContentGen((s) => s.stopPipeline)
  const approveQC = useContentGen((s) => s.approveQC)
  const pipelineContext = useContentGen((s) => s.pipelineContext)
  const pipelines = useContentGen((s) => s.pipelines)
  const error = useContentGen((s) => s.error)

  const currentPipeline = pipelines.find((p) => p.pipeline_id === pipelineId)
  const status = currentPipeline?.status ?? 'unknown'

  const [stageStates, setStageStates] = useState<Record<number, 'pending' | 'running' | 'completed' | 'failed'>>({})

  useEffect(() => {
    if (pipelineId) {
      selectPipeline(pipelineId)
    }
  }, [pipelineId, selectPipeline])

  // WebSocket connection for real-time updates
  useEffect(() => {
    if (!pipelineId) return

    const wsBaseUrl = process.env.NEXT_PUBLIC_CC_WS_BASE_URL || 'ws://localhost:8000/ws'
    const wsUrl = `${wsBaseUrl}/content-gen/pipeline/${pipelineId}`
    const ws = new WebSocket(wsUrl)
    wsRef.current = ws

    ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data)
        if (data.type === 'pipeline_stage_started') {
          setStageStates((prev) => ({
            ...prev,
            [data.stage_index]: 'running',
          }))
        } else if (data.type === 'pipeline_stage_completed') {
          setStageStates((prev) => ({
            ...prev,
            [data.stage_index]: 'completed',
          }))
        } else if (data.type === 'pipeline_stage_error') {
          setStageStates((prev) => ({
            ...prev,
            [data.stage_index]: 'failed',
          }))
        } else if (data.type === 'pipeline_completed') {
          selectPipeline(pipelineId)
        }
      } catch {
        // ignore parse errors
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

  const currentStage = pipelineContext?.current_stage ?? 0

  const renderStageContent = (ctx: PipelineContext, stageIndex: number) => {
    switch (stageIndex) {
      case 0: // Strategy
        return ctx.strategy ? (
          <div className="space-y-2">
            <div className="flex items-start gap-4 text-sm">
              <div className="min-w-[80px]">
                <span className="text-xs font-mono uppercase tracking-wider text-muted-foreground">Niche</span>
              </div>
              <span className="text-foreground/80">{ctx.strategy.niche || 'Not set'}</span>
            </div>
            <div className="flex items-start gap-4 text-sm">
              <div className="min-w-[80px]">
                <span className="text-xs font-mono uppercase tracking-wider text-muted-foreground">Pillars</span>
              </div>
              <span className="text-foreground/80">{ctx.strategy.content_pillars?.join(', ') || 'None'}</span>
            </div>
          </div>
        ) : null
      case 1: // Backlog
        return ctx.backlog ? (
          <div className="text-sm">
            <span className="text-foreground/80">
              {ctx.backlog.items.length} ideas generated
            </span>
            {ctx.backlog.rejected_count > 0 && (
              <span className="text-muted-foreground ml-2">
                ({ctx.backlog.rejected_count} rejected)
              </span>
            )}
          </div>
        ) : null
      case 5: // Scripting
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
      case 8: // Packaging
        return ctx.packaging ? (
          <div className="space-y-2">
            {ctx.packaging.platform_packages.map((pkg, i) => (
              <div key={i} className="flex items-start gap-3 text-sm py-1.5 border-b border-border last:border-0">
                <span className="text-xs font-mono uppercase tracking-wider text-muted-foreground min-w-[80px] pt-0.5">
                  {pkg.platform}
                </span>
                <span className="text-foreground/70">{pkg.primary_hook}</span>
              </div>
            ))}
          </div>
        ) : null
      case 9: // QC Gate
        return ctx.qc_gate ? (
          <QCGatePanel qcGate={ctx.qc_gate} pipelineId={pipelineId} onApprove={approveQC} />
        ) : null
      default:
        return <p className="text-sm text-muted-foreground">Stage output available</p>
    }
  }

  const getStageStatus = (idx: number) => {
    const explicit = stageStates[idx]
    if (explicit) return explicit
    if (idx < currentStage) return 'completed' as const
    if (idx === currentStage && status === 'running') return 'running' as const
    return 'pending' as const
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-4">
          <div>
            <h1 className="text-lg font-display font-semibold tracking-tight">
              Pipeline
            </h1>
            {currentPipeline && (
              <p className="text-xs text-muted-foreground mt-0.5">{currentPipeline.theme}</p>
            )}
          </div>
        </div>
        <div className="flex items-center gap-3">
          <span className="text-[11px] font-mono text-muted-foreground tabular-nums">
            {pipelineId.slice(0, 8)}
          </span>
          {(status === 'running' || status === 'queued') && (
            <button
              onClick={() => stopPipeline(pipelineId)}
              className="flex items-center gap-1.5 px-2.5 py-1.5 text-xs text-error border border-error/20 rounded-sm
                hover:bg-error/10 transition-colors"
            >
              <StopCircle className="h-3.5 w-3.5" />
              Stop
            </button>
          )}
        </div>
      </div>

      {error && (
        <div className="text-sm text-error bg-error-muted/20 border border-error/20 rounded-sm px-3 py-2">
          {error}
        </div>
      )}

      {/* Two-column layout: timeline + stage details */}
      <div className="grid grid-cols-1 lg:grid-cols-[200px_1fr] gap-8">
        {/* Timeline sidebar */}
        <aside className="hidden lg:block">
          <div className="sticky top-8">
            <PipelineProgressTracker currentStage={currentStage} stageStates={stageStates} />
          </div>
        </aside>

        {/* Mobile timeline */}
        <div className="lg:hidden">
          <PipelineProgressTracker currentStage={currentStage} stageStates={stageStates} />
        </div>

        {/* Stage panels */}
        <div className="space-y-1.5">
          {STAGE_LABELS.map((label, idx) => {
            const stageStatus = getStageStatus(idx)
            return (
              <StageResultPanel
                key={idx}
                title={label}
                stageIndex={idx}
                status={stageStatus}
                defaultOpen={stageStatus === 'completed'}
              >
                {pipelineContext ? renderStageContent(pipelineContext, idx) : (
                  <p className="text-sm text-muted-foreground">Loading...</p>
                )}
              </StageResultPanel>
            )
          })}
        </div>
      </div>
    </div>
  )
}
