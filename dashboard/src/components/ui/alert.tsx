import * as React from 'react'

import { cn } from '@/lib/utils'

type AlertVariant = 'default' | 'info' | 'warning' | 'destructive' | 'success'
type AlertProps = React.HTMLAttributes<HTMLDivElement> & { variant?: AlertVariant }

const Alert = React.forwardRef<HTMLDivElement, AlertProps>(
  ({ className, variant = 'default', children, ...props }, ref) => {
    const variantClasses: Record<AlertVariant, string> = {
      default: 'border-border/80 bg-card/90 text-foreground',
      info: 'border-primary/30 bg-primary/10 text-primary',
      warning: 'border-warning/25 bg-warning-muted/30 text-warning',
      destructive: 'border-error/25 bg-error-muted/30 text-error',
      success: 'border-success/25 bg-success-muted/30 text-success',
    }
    return (
      <div
        ref={ref}
        role="alert"
        className={cn('rounded-[1rem] border px-4 py-3 shadow-card', variantClasses[variant], className)}
        {...props}
      >
        {children}
      </div>
    )
  }
)
Alert.displayName = 'Alert'

export function AlertTitle({ className, ...props }: React.HTMLAttributes<HTMLHeadingElement>) {
  return <h4 className={cn('text-sm font-semibold', className)} {...props} />
}

export function AlertDescription({
  className,
  ...props
}: React.HTMLAttributes<HTMLDivElement>) {
  return <div className={cn('text-sm leading-relaxed opacity-90', className)} {...props} />
}
