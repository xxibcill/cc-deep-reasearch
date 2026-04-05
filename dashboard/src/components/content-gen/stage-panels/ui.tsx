'use client'

export function SectionList({
  label,
  items,
  emptyLabel = 'None recorded',
}: {
  label: string
  items: string[]
  emptyLabel?: string
}) {
  return (
    <div className="space-y-2">
      <p className="text-[11px] font-mono uppercase tracking-[0.22em] text-muted-foreground">
        {label}
      </p>
      {items.length > 0 ? (
        <ul className="space-y-2">
          {items.map((item, index) => (
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
}: {
  label: string
  value: string | null | undefined
}) {
  if (!value) {
    return null
  }

  return (
    <div className="rounded-xl border border-border/70 bg-background/55 px-3 py-3">
      <p className="text-[11px] font-mono uppercase tracking-[0.22em] text-muted-foreground">
        {label}
      </p>
      <p className="mt-2 text-sm leading-relaxed text-foreground/82">{value}</p>
    </div>
  )
}
