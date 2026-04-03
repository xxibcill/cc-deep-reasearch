import * as React from 'react'

import { cn } from '@/lib/utils'

export const Input = React.forwardRef<HTMLInputElement, React.InputHTMLAttributes<HTMLInputElement>>(
  ({ className, type = 'text', ...props }, ref) => (
    <input
      ref={ref}
      type={type}
      className={cn(
        'flex h-11 w-full rounded-[0.95rem] border border-input/90 bg-surface/72 px-3.5 py-2 text-sm text-foreground transition-all',
        'placeholder:text-muted-foreground/75 focus-visible:border-primary/55 focus-visible:bg-surface-raised focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring/30 focus-visible:ring-offset-0',
        'disabled:cursor-not-allowed disabled:opacity-50',
        className,
      )}
      {...props}
    />
  ),
)

Input.displayName = 'Input'
