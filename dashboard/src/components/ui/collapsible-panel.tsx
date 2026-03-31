import { useId, useState } from 'react'
import { ChevronDown, ChevronRight } from 'lucide-react'

import { cn } from '@/lib/utils'

interface CollapsiblePanelProps {
  summary: React.ReactNode
  meta?: React.ReactNode
  actions?: React.ReactNode
  children: React.ReactNode
  defaultOpen?: boolean
  open?: boolean
  onOpenChange?: (open: boolean) => void
  className?: string
  triggerClassName?: string
  contentClassName?: string
}

export function CollapsiblePanel({
  summary,
  meta,
  actions,
  children,
  defaultOpen = false,
  open,
  onOpenChange,
  className,
  triggerClassName,
  contentClassName,
}: CollapsiblePanelProps) {
  const [uncontrolledOpen, setUncontrolledOpen] = useState(defaultOpen)
  const isControlled = open !== undefined
  const isOpen = isControlled ? open : uncontrolledOpen
  const contentId = useId()

  const setOpen = (nextOpen: boolean) => {
    if (!isControlled) {
      setUncontrolledOpen(nextOpen)
    }
    onOpenChange?.(nextOpen)
  }

  return (
    <div className={cn('overflow-hidden rounded-xl border border-border bg-surface', className)}>
      <button
        type="button"
        className={cn(
          'flex w-full items-center justify-between gap-4 px-4 py-3 text-left transition-colors hover:bg-surface-raised/50',
          triggerClassName,
        )}
        aria-expanded={isOpen}
        aria-controls={contentId}
        onClick={() => setOpen(!isOpen)}
      >
        <div className="flex min-w-0 items-start gap-3">
          {isOpen ? (
            <ChevronDown className="mt-0.5 h-4 w-4 shrink-0 text-muted-foreground" />
          ) : (
            <ChevronRight className="mt-0.5 h-4 w-4 shrink-0 text-muted-foreground" />
          )}
          <div className="min-w-0">{summary}</div>
        </div>
        <div className="flex shrink-0 items-center gap-3">
          {meta}
          {actions}
        </div>
      </button>
      {isOpen ? (
        <div
          id={contentId}
          className={cn('border-t border-border px-4 py-4 text-sm animate-fade-in', contentClassName)}
        >
          {children}
        </div>
      ) : null}
    </div>
  )
}
