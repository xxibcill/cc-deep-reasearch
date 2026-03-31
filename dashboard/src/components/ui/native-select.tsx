import * as React from 'react'

import { cn } from '@/lib/utils'

export const NativeSelect = React.forwardRef<
  HTMLSelectElement,
  React.SelectHTMLAttributes<HTMLSelectElement>
>(({ className, children, ...props }, ref) => (
  <select
    ref={ref}
    className={cn(
      'flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm text-foreground transition-colors',
      'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring/50 focus-visible:ring-offset-0',
      'disabled:cursor-not-allowed disabled:opacity-50',
      className,
    )}
    {...props}
  >
    {children}
  </select>
))

NativeSelect.displayName = 'NativeSelect'
