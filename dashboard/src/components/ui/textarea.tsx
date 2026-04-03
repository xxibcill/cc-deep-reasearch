import * as React from 'react'

import { cn } from '@/lib/utils'

export const Textarea = React.forwardRef<
  HTMLTextAreaElement,
  React.TextareaHTMLAttributes<HTMLTextAreaElement>
>(({ className, ...props }, ref) => (
  <textarea
    ref={ref}
    className={cn(
      'flex min-h-[96px] w-full rounded-[1rem] border border-input/90 bg-surface/72 px-3.5 py-3 text-sm text-foreground transition-all',
      'placeholder:text-muted-foreground/75 focus-visible:border-primary/55 focus-visible:bg-surface-raised focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring/30 focus-visible:ring-offset-0',
      'disabled:cursor-not-allowed disabled:opacity-50',
      className,
    )}
    {...props}
  />
))

Textarea.displayName = 'Textarea'
