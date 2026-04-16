'use client'

import type { ReactNode } from 'react'

export function SectionList({
  label,
  items,
  emptyLabel = 'None recorded',
  children,
}: {
  label: string
  items?: string[] | null
  emptyLabel?: string
  children?: ReactNode
}) {
  const list = items ?? []
  return (
    <div className="space-y-2">
      <p className="text-[11px] font-mono uppercase tracking-[0.22em] text-muted-foreground">
        {label}
      </p>
      {children ? (
        children
      ) : list.length > 0 ? (
        <ul className="space-y-2">
          {list.map((item, index) => (
            <li
              key={`${label}-${index}`}
              className="rounded-xl border border-border/70 bg-background/55 px-3 py-2 text-sm text-foreground/80"
            >
              {item}
            </li>
          ))}
        </ul>
      ) : (
        <p className="text-sm text-muted-foreground">{emptyLabel}</p>
      )}
    </div>
  )
}

export function SummaryField({
  label,
  value,
  fallback,
}: {
  label: string
  value: string | null | undefined
  fallback?: string
}) {
  const displayValue = value?.trim() || (fallback ?? '')

  return (
    <div className="rounded-xl border border-border/70 bg-background/55 px-3 py-3">
      <p className="text-[11px] font-mono uppercase tracking-[0.22em] text-muted-foreground">
        {label}
      </p>
      <p className={`mt-2 text-sm leading-relaxed ${displayValue ? 'text-foreground/82' : 'text-muted-foreground italic'}`}>
        {displayValue || fallback}
      </p>
    </div>
  )
}
