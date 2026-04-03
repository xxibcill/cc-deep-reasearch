import * as React from 'react'

import { cn } from '@/lib/utils'

export const Label = React.forwardRef<HTMLLabelElement, React.LabelHTMLAttributes<HTMLLabelElement>>(
  ({ className, ...props }, ref) => (
    <label
      ref={ref}
      className={cn(
        'font-mono text-[0.72rem] uppercase tracking-[0.22em] text-muted-foreground',
        className,
      )}
      {...props}
    />
  ),
)

Label.displayName = 'Label'
