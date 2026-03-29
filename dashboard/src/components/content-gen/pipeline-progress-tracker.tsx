'use client'

import { CheckCircle2, Circle, Loader2, XCircle } from 'lucide-react'

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

export type StageState = 'pending' | 'running' | 'completed' | 'failed'

interface PipelineProgressTrackerProps {
  currentStage: number
  totalStages?: number
  stageStates?: Record<number, StageState>
}

export function PipelineProgressTracker({
  currentStage,
  totalStages = 12,
  stageStates = {},
}: PipelineProgressTrackerProps) {
  return (
    <div className="w-full">
      <div className="flex items-center gap-1 overflow-x-auto pb-2">
        {Array.from({ length: totalStages }, (_, i) => {
          const explicit = stageStates[i]
          let state: StageState
          if (explicit) {
            state = explicit
          } else if (i < currentStage) {
            state = 'completed'
          } else if (i === currentStage) {
            state = 'running'
          } else {
            state = 'pending'
          }

          return (
            <div key={i} className="flex items-center shrink-0">
              <div className="flex flex-col items-center gap-1 min-w-[80px]">
                {state === 'completed' && (
                  <CheckCircle2 className="h-5 w-5 text-green-500" />
                )}
                {state === 'running' && (
                  <Loader2 className="h-5 w-5 text-blue-500 animate-spin" />
                )}
                {state === 'failed' && <XCircle className="h-5 w-5 text-red-500" />}
                {state === 'pending' && (
                  <Circle className="h-5 w-5 text-muted-foreground/40" />
                )}
                <span
                  className={`text-[10px] leading-tight text-center ${
                    state === 'running'
                      ? 'text-blue-600 font-medium'
                      : state === 'completed'
                        ? 'text-green-600'
                        : state === 'failed'
                          ? 'text-red-600'
                          : 'text-muted-foreground'
                  }`}
                >
                  {STAGE_LABELS[i] || `Stage ${i + 1}`}
                </span>
              </div>
              {i < totalStages - 1 && (
                <div
                  className={`h-px w-4 mx-1 ${
                    i < currentStage ? 'bg-green-300' : 'bg-border'
                  }`}
                />
              )}
            </div>
          )
        })}
      </div>
    </div>
  )
}
