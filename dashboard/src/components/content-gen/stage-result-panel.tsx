'use client'

import { useState } from 'react'
import { ChevronDown, ChevronRight } from 'lucide-react'

interface StageResultPanelProps {
  title: string
  stageIndex: number
  status: 'pending' | 'running' | 'completed' | 'failed'
  children: React.ReactNode
  defaultOpen?: boolean
}

export function StageResultPanel({
  title,
  stageIndex,
  status,
  children,
  defaultOpen = false,
}: StageResultPanelProps) {
  const [isOpen, setIsOpen] = useState(defaultOpen || status === 'completed')

  const stateStyles: Record<string, string> = {
    completed: 'border-l-success/50',
    running: 'border-l-warning/60',
    failed: 'border-l-error/50',
    pending: 'border-l-border',
  }

  return (
    <div
      className={[
        'bg-surface border border-border border-l-2 rounded-sm',
        stateStyles[status],
        status === 'running' ? 'stage-running' : '',
        isOpen ? 'animate-fade-in' : '',
      ].join(' ')}
    >
      <button
        onClick={() => setIsOpen(!isOpen)}
        className="w-full flex items-center justify-between px-4 py-3 text-left hover:bg-surface-raised/50 transition-colors"
      >
        <div className="flex items-center gap-3">
          <span className="stage-number text-muted-foreground/40 tabular-nums">
            {String(stageIndex + 1).padStart(2, '0')}
          </span>
          <span className="text-sm font-medium font-display">{title}</span>
          {status === 'running' && (
            <span className="text-[10px] uppercase tracking-wider text-warning font-mono font-medium">
              running
            </span>
          )}
        </div>
        <div className="flex items-center gap-2">
          {isOpen ? (
            <ChevronDown className="h-4 w-4 text-muted-foreground shrink-0" />
          ) : (
            <ChevronRight className="h-4 w-4 text-muted-foreground shrink-0" />
          )}
        </div>
      </button>
      {isOpen && (
        <div className="px-4 pb-4 pt-1 border-t border-border text-sm animate-fade-in">
          {children}
        </div>
      )}
    </div>
  )
}
