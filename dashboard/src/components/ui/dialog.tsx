import { cn } from '@/lib/utils'

export function Dialog({
  open,
  onOpenChange,
  title,
  children,
}: {
  open: boolean
  onOpenChange: (open: boolean) => void
  title: string
  children: React.ReactNode
}) {
  if (!open) {
    return null
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-background/80 backdrop-blur-sm p-4">
      <div className="absolute inset-0" onClick={() => onOpenChange(false)} />
      <div
        className={cn(
          'relative z-10 max-h-[85vh] w-full max-w-4xl overflow-hidden rounded-2xl border border-border bg-surface shadow-2xl',
        )}
      >
        <div className="flex items-center justify-between border-b px-5 py-4">
          <h2 className="text-lg font-semibold">{title}</h2>
          <button
            aria-label="Close dialog"
            className="rounded-md px-3 py-2 text-sm text-muted-foreground hover:bg-surface-raised hover:text-foreground"
            onClick={() => onOpenChange(false)}
          >
            Close
          </button>
        </div>
        <div className="max-h-[calc(85vh-4.5rem)] overflow-auto">{children}</div>
      </div>
    </div>
  )
}
