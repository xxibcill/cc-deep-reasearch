import * as React from 'react'

import { cn } from '@/lib/utils'

export const NativeSelect = React.forwardRef<
  HTMLSelectElement,
  React.SelectHTMLAttributes<HTMLSelectElement>
>(({ className, children, ...props }, ref) => (
  <select
    ref={ref}
    className={cn(
      'flex h-11 w-full rounded-[0.95rem] border border-input/90 bg-surface/72 px-3.5 py-2 text-sm text-foreground transition-all',
      'focus-visible:border-primary/55 focus-visible:bg-surface-raised focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring/30 focus-visible:ring-offset-0',
      'disabled:cursor-not-allowed disabled:opacity-50',
      className,
    )}
    {...props}
  >
    {children}
  </select>
))

NativeSelect.displayName = 'NativeSelect'
