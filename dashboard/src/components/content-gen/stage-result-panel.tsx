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

  const statusColor =
    status === 'completed'
      ? 'border-l-green-500'
      : status === 'running'
        ? 'border-l-blue-500'
        : status === 'failed'
          ? 'border-l-red-500'
          : 'border-l-muted'

  return (
    <div className={`border rounded-md border-l-4 ${statusColor}`}>
      <button
        onClick={() => setIsOpen(!isOpen)}
        className="w-full flex items-center justify-between px-4 py-3 text-sm font-medium text-left hover:bg-muted/50 transition-colors"
      >
        <span className="flex items-center gap-2">
          <span className="text-muted-foreground tabular-nums">
            {String(stageIndex + 1).padStart(2, '0')}
          </span>
          {title}
        </span>
        {isOpen ? (
          <ChevronDown className="h-4 w-4 shrink-0" />
        ) : (
          <ChevronRight className="h-4 w-4 shrink-0" />
        )}
      </button>
      {isOpen && (
        <div className="px-4 pb-4 pt-2 border-t text-sm">{children}</div>
      )}
    </div>
  )
}
