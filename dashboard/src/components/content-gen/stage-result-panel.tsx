'use client'

import { useEffect, useState } from 'react'

import { Badge } from '@/components/ui/badge'
import { CollapsiblePanel } from '@/components/ui/collapsible-panel'

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

  useEffect(() => {
    if (status === 'running' || status === 'completed') {
      setIsOpen(true)
    }
  }, [status])

  const stateStyles: Record<StageResultPanelProps['status'], string> = {
    completed: 'border-success/30',
    running: 'border-warning/40 stage-running',
    failed: 'border-error/30',
    pending: 'border-border',
  }

  return (
    <CollapsiblePanel
      open={isOpen}
      onOpenChange={setIsOpen}
      className={stateStyles[status]}
      summary={
        <div className="flex items-center gap-3">
          <span className="stage-number text-muted-foreground/40 tabular-nums">
            {String(stageIndex + 1).padStart(2, '0')}
          </span>
          <span className="text-sm font-medium font-display">{title}</span>
        </div>
      }
      meta={
        status === 'pending' ? null : (
          <Badge
            variant={
              status === 'completed'
                ? 'success'
                : status === 'running'
                  ? 'warning'
                  : 'destructive'
            }
            className="rounded-md px-2 py-1 font-mono text-[10px] uppercase tracking-[0.2em]"
          >
            {status}
          </Badge>
        )
      }
      contentClassName="text-sm"
    >
      {children}
    </CollapsiblePanel>
  )
}
