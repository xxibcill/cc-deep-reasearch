'use client'

import { useEffect, useRef, useState } from 'react'
import { useParams } from 'next/navigation'
import Link from 'next/link'
import { ArrowLeft, StopCircle } from 'lucide-react'
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
          // Reload full context
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
          <div className="space-y-1 text-sm">
            <p><strong>Niche:</strong> {ctx.strategy.niche || 'Not set'}</p>
            <p><strong>Pillars:</strong> {ctx.strategy.content_pillars?.join(', ') || 'None'}</p>
          </div>
        ) : null
      case 1: // Backlog
        return ctx.backlog ? (
          <div className="text-sm">
            <p>{ctx.backlog.items.length} ideas generated, {ctx.backlog.rejected_count} rejected</p>
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
          <div className="space-y-2 text-sm">
            {ctx.packaging.platform_packages.map((pkg, i) => (
              <div key={i} className="border rounded p-2">
                <strong>{pkg.platform}</strong>: {pkg.primary_hook}
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

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <Link
            href="/content-gen"
            className="text-muted-foreground hover:text-foreground transition-colors"
          >
            <ArrowLeft className="h-5 w-5" />
          </Link>
          <div>
            <h1 className="text-xl font-bold">Pipeline {pipelineId}</h1>
            {currentPipeline && (
              <p className="text-sm text-muted-foreground">{currentPipeline.theme}</p>
            )}
          </div>
        </div>
        {(status === 'running' || status === 'queued') && (
          <button
            onClick={() => stopPipeline(pipelineId)}
            className="flex items-center gap-2 px-3 py-1.5 text-sm text-red-600 border border-red-200 rounded-md hover:bg-red-50 transition-colors"
          >
            <StopCircle className="h-4 w-4" />
            Stop
          </button>
        )}
      </div>

      {error && <p className="text-sm text-red-600">{error}</p>}

      {/* Progress tracker */}
      <PipelineProgressTracker currentStage={currentStage} stageStates={stageStates} />

      {/* Stage panels */}
      <div className="space-y-2">
        {STAGE_LABELS.map((label, idx) => {
          const stageStatus = stageStates[idx] ||
            (idx < currentStage ? 'completed' : idx === currentStage && (status === 'running') ? 'running' : 'pending')

          return (
            <StageResultPanel
              key={idx}
              title={label}
              stageIndex={idx}
              status={stageStatus as 'pending' | 'running' | 'completed' | 'failed'}
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
  )
}
