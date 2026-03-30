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

function StageNode({ state, label, index, isLast }: {
  state: StageState
  label: string
  index: number
  isLast: boolean
}) {
  return (
    <div className={`relative flex items-start gap-4 ${!isLast ? 'pb-3' : ''}`}>
      {/* Timeline connector */}
      <div className="flex flex-col items-center shrink-0">
        <div
          className={`
            w-[30px] h-[30px] rounded-full flex items-center justify-center shrink-0
            transition-all duration-300
            ${state === 'completed'
              ? 'bg-success/15 border border-success/40'
              : state === 'running'
                ? 'bg-warning/15 border border-warning/50 stage-running'
                : state === 'failed'
                  ? 'bg-error/15 border border-error/40'
                  : 'bg-surface border border-border'
            }
          `}
        >
          {state === 'completed' && (
            <CheckCircle2 className="h-4 w-4 text-success" />
          )}
          {state === 'running' && (
            <Loader2 className="h-4 w-4 text-warning animate-spin" />
          )}
          {state === 'failed' && (
            <XCircle className="h-4 w-4 text-error" />
          )}
          {state === 'pending' && (
            <Circle className="h-3 w-3 text-muted-foreground/30" />
          )}
        </div>
        {/* Connection line */}
        {!isLast && (
          <div
            className={`w-px flex-1 min-h-[16px] transition-colors duration-300 ${
              state === 'completed' ? 'bg-success/25' : 'bg-border'
            }`}
          />
        )}
      </div>

      {/* Label */}
      <div className="pt-[5px] min-w-0">
        <div className="flex items-baseline gap-2">
          <span className="stage-number text-muted-foreground/50 tabular-nums">
            {String(index + 1).padStart(2, '0')}
          </span>
          <span
            className={`text-sm font-medium transition-colors duration-200 ${
              state === 'running'
                ? 'text-warning'
                : state === 'completed'
                  ? 'text-success/80'
                  : state === 'failed'
                    ? 'text-error'
                    : 'text-muted-foreground/60'
            }`}
          >
            {label}
          </span>
        </div>
      </div>
    </div>
  )
}

export function PipelineProgressTracker({
  currentStage,
  totalStages = 12,
  stageStates = {},
}: PipelineProgressTrackerProps) {
  return (
    <div className="flex flex-col">
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
          <StageNode
            key={i}
            state={state}
            label={STAGE_LABELS[i] || `Stage ${i + 1}`}
            index={i}
            isLast={i === totalStages - 1}
          />
        )
      })}
    </div>
  )
}
