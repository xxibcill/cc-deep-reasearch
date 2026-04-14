"use client"

import * as CollapsiblePrimitive from "@radix-ui/react-collapsible"
import { ChevronDown } from "lucide-react"
import { useId, useState } from "react"

import { cn } from "@/lib/utils"

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
    <CollapsiblePrimitive.Root
      open={isOpen}
      onOpenChange={setOpen}
      className={cn(
        "group overflow-hidden rounded-xl border border-border bg-surface transition-all duration-200",
        "hover:border-border/80 hover:bg-surface-raised/30",
        isOpen && "bg-surface-raised/40",
        className
      )}
    >
      <CollapsiblePrimitive.Trigger
        className={cn(
          "flex w-full items-center justify-between gap-4 px-4 py-3 text-left",
          "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring/50 focus-visible:ring-offset-2 focus-visible:ring-offset-surface",
          "data-[state=open]:border-b data-[state=open]:border-border/60",
          triggerClassName
        )}
      >
        <div className="flex min-w-0 items-start gap-3">
          <ChevronDown
            className={cn(
              "mt-0.5 h-4 w-4 shrink-0 text-muted-foreground transition-all duration-300 ease-out",
              "group-hover:text-foreground/70",
              isOpen ? "rotate-0" : "-rotate-90"
            )}
          />
          <div className="min-w-0">{summary}</div>
        </div>
        <div className="flex shrink-0 items-center gap-3">
          {meta}
          {actions}
        </div>
      </CollapsiblePrimitive.Trigger>

      <CollapsiblePrimitive.Content
        className={cn(
          "overflow-hidden data-[state=closed]:animate-collapsible-up data-[state=open]:animate-collapsible-down",
          contentClassName
        )}
      >
        <div className="border-t border-border/60 px-4 py-4 text-sm">
          {children}
        </div>
      </CollapsiblePrimitive.Content>
    </CollapsiblePrimitive.Root>
  )
}