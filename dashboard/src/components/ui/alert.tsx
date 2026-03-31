import * as React from 'react'

import { cn } from '@/lib/utils'

type AlertVariant = 'default' | 'warning' | 'destructive' | 'success'

const variantClasses: Record<AlertVariant, string> = {
  default: 'border-border bg-card text-foreground',
  warning: 'border-warning/25 bg-warning-muted/20 text-warning',
  destructive: 'border-error/25 bg-error-muted/20 text-error',
  success: 'border-success/25 bg-success-muted/20 text-success',
}

export function Alert({
  className,
  variant = 'default',
  ...props
}: React.HTMLAttributes<HTMLDivElement> & { variant?: AlertVariant }) {
  return (
    <div
      role="alert"
      className={cn('rounded-xl border px-4 py-3', variantClasses[variant], className)}
      {...props}
    />
  )
}

export function AlertTitle({ className, ...props }: React.HTMLAttributes<HTMLHeadingElement>) {
  return <h4 className={cn('text-sm font-semibold', className)} {...props} />
}

export function AlertDescription({
  className,
  ...props
}: React.HTMLAttributes<HTMLParagraphElement>) {
  return <p className={cn('text-sm leading-relaxed opacity-90', className)} {...props} />
}
