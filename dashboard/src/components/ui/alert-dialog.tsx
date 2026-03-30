import { ReactNode, useEffect, useRef } from 'react'

import { cn } from '@/lib/utils'
import { Button } from '@/components/ui/button'

interface AlertDialogProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  title: string
  description: ReactNode
  confirmLabel?: string
  cancelLabel?: string
  destructive?: boolean
  onConfirm: () => void
  loading?: boolean
  loadingLabel?: string
}

export function AlertDialog({
  open,
  onOpenChange,
  title,
  description,
  confirmLabel = 'Confirm',
  cancelLabel = 'Cancel',
  destructive = false,
  onConfirm,
  loading = false,
  loadingLabel = 'Loading...',
}: AlertDialogProps) {
  const cancelRef = useRef<HTMLButtonElement>(null)

  useEffect(() => {
    if (open) {
      cancelRef.current?.focus()
    }
  }, [open])

  if (!open) {
    return null
  }

  const handleConfirm = () => {
    onConfirm()
  }

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Escape') {
      onOpenChange(false)
    }
  }

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-background/80 p-4 backdrop-blur-sm"
      onKeyDown={handleKeyDown}
    >
      <div className="absolute inset-0" onClick={() => onOpenChange(false)} />
      <div
        className={cn(
          'relative z-10 w-full max-w-md rounded-xl border border-border bg-card p-6 shadow-2xl',
        )}
        role="dialog"
        aria-modal="true"
        aria-labelledby="alert-dialog-title"
        aria-describedby="alert-dialog-description"
      >
        <div className="mb-4">
          <h2 id="alert-dialog-title" className="text-lg font-semibold">
            {title}
          </h2>
        </div>
        <div className="mb-6">
          <div id="alert-dialog-description" className="text-sm text-muted-foreground">
            {description}
          </div>
        </div>
        <div className="flex justify-end gap-3">
          <Button
            ref={cancelRef}
            onClick={() => onOpenChange(false)}
            disabled={loading}
            variant="outline"
          >
            {cancelLabel}
          </Button>
          <Button
            onClick={handleConfirm}
            disabled={loading}
            variant={destructive ? 'destructive' : 'default'}
          >
            {loading ? loadingLabel : confirmLabel}
          </Button>
        </div>
      </div>
    </div>
  )
}
