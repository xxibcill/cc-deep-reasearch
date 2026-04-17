'use client'

import { LayoutGrid, List } from 'lucide-react'
import { cn } from '@/lib/utils'

export type ItemsViewMode = 'grid' | 'list'

interface ItemsViewToggleProps {
  value: ItemsViewMode
  onChange: (value: ItemsViewMode) => void
  label?: string
}

export function ItemsViewToggle({ value, onChange, label = 'View' }: ItemsViewToggleProps) {
  return (
    <div
      className="relative grid grid-cols-2 rounded-[0.95rem] border border-border/70 bg-background/40 p-1 shadow-[inset_0_1px_0_rgba(255,255,255,0.03)]"
      role="group"
      aria-label={`${label} view`}
    >
      <div
        aria-hidden="true"
        className={cn(
          'pointer-events-none absolute inset-y-1 left-1 w-[calc(50%-0.25rem)] rounded-[0.72rem] bg-card shadow-[0_12px_30px_rgba(0,0,0,0.22)] transition-transform duration-200 ease-[cubic-bezier(0.22,1,0.36,1)] motion-reduce:transition-none',
          value === 'grid' ? 'translate-x-0' : 'translate-x-full'
        )}
      />
      {[
        { value: 'grid' as const, label: 'Grid', icon: LayoutGrid },
        { value: 'list' as const, label: 'List', icon: List },
      ].map(({ value: v, label: l, icon: Icon }) => (
        <button
          key={v}
          type="button"
          aria-pressed={value === v}
          onClick={() => onChange(v)}
          className={cn(
            'relative z-10 flex min-w-[7rem] items-center justify-center gap-2 rounded-[0.72rem] px-3 py-2 text-[0.76rem] font-semibold uppercase tracking-[0.16em] transition-colors duration-200 motion-reduce:transition-none',
            value === v ? 'text-foreground' : 'text-muted-foreground hover:text-foreground'
          )}
        >
          <Icon className="h-4 w-4" />
          <span>{l}</span>
        </button>
      ))}
    </div>
  )
}

interface ItemsViewHeaderProps {
  title: string
  totalCount: number
  visibleCount?: number
  stats?: React.ReactNode
  controls?: React.ReactNode
}

export function ItemsViewHeader({ title, totalCount, visibleCount, stats, controls }: ItemsViewHeaderProps) {
  return (
    <div className="rounded-[1.15rem] border border-border/75 bg-surface/62 p-4 shadow-[inset_0_1px_0_rgba(255,255,255,0.04)]">
      <div className="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
        <div className="space-y-1">
          <p className="text-sm font-medium text-foreground">{title}</p>
          <p className="text-xs text-muted-foreground">
            {totalCount} {title.toLowerCase().replace(/s$/, '')}{totalCount === 1 ? '' : 's'} total
            {visibleCount !== undefined && visibleCount !== totalCount && (
              <span className="text-muted-foreground/60"> ({visibleCount} visible)</span>
            )}
          </p>
        </div>
        {stats}
        {controls && <div className="flex flex-col gap-3 xl:items-end">{controls}</div>}
      </div>
    </div>
  )
}

interface ItemsViewProps {
  mode: ItemsViewMode
  children: React.ReactNode
}

export function ItemsView({ mode, children }: ItemsViewProps) {
  return (
    <div
      key={mode}
      className="animate-in fade-in-0 slide-in-from-bottom-2 duration-200 motion-reduce:animate-none"
    >
      {mode === 'grid' ? (
        <div className="grid gap-4 xl:grid-cols-2 2xl:grid-cols-3">{children}</div>
      ) : (
        <div className="overflow-hidden rounded-xl border border-border bg-card/95 shadow-sm">
          {children}
        </div>
      )}
    </div>
  )
}

export function ItemsViewLoading({ label }: { label: string }) {
  return <div className="py-8 text-center text-sm text-muted-foreground">Loading {label}...</div>
}

export function ItemsViewEmpty({
  label,
  message,
  secondaryMessage,
}: {
  label: string
  message: string
  secondaryMessage?: string
}) {
  return (
    <div className="rounded-xl border border-dashed border-border bg-card/70 py-16 text-center">
      <p className="text-sm text-muted-foreground">{message}</p>
      {secondaryMessage && (
        <p className="mt-1 text-xs text-muted-foreground/60">{secondaryMessage}</p>
      )}
    </div>
  )
}
