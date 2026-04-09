<<<<<<< HEAD
import * as React from 'react'
=======
>>>>>>> 26dcdfe (feat(dashboard): Add dashboard framework upgrade and new UI components)
import type { LucideIcon } from 'lucide-react'

import { cn } from '@/lib/utils'

type MetricCardTone = 'neutral' | 'primary' | 'warning' | 'success'

const toneClasses: Record<MetricCardTone, string> = {
  neutral: 'border-border bg-surface-raised/55',
  primary: 'border-primary/25 bg-surface-raised/70 hover:border-primary/40 hover:bg-surface-raised/85',
  warning: 'border-warning/30 bg-warning-muted/70 hover:border-warning/45 hover:bg-warning-muted/85',
  success: 'border-success/30 bg-success-muted/70 hover:border-success/45 hover:bg-success-muted/85',
}

const iconClasses: Record<MetricCardTone, string> = {
  neutral: 'text-muted-foreground',
  primary: 'text-primary',
  warning: 'text-warning',
  success: 'text-success',
}

<<<<<<< HEAD
interface MetricCardProps extends React.HTMLAttributes<HTMLDivElement> {
=======
interface MetricCardProps {
>>>>>>> 26dcdfe (feat(dashboard): Add dashboard framework upgrade and new UI components)
  label: string
  value: React.ReactNode
  icon: LucideIcon
  description?: string
  tone?: MetricCardTone
  compact?: boolean
<<<<<<< HEAD
=======
  className?: string
>>>>>>> 26dcdfe (feat(dashboard): Add dashboard framework upgrade and new UI components)
  valueClassName?: string
  children?: React.ReactNode
}

<<<<<<< HEAD
const MetricCard = React.forwardRef<HTMLDivElement, MetricCardProps>(({
=======
export function MetricCard({
>>>>>>> 26dcdfe (feat(dashboard): Add dashboard framework upgrade and new UI components)
  label,
  value,
  icon: Icon,
  description,
  tone = 'neutral',
  compact = false,
  className,
  valueClassName,
  children,
<<<<<<< HEAD
  ...props
}, ref) => {
  return (
    <div
      ref={ref}
=======
}: MetricCardProps) {
  return (
    <div
>>>>>>> 26dcdfe (feat(dashboard): Add dashboard framework upgrade and new UI components)
      className={cn(
        'group rounded-[1rem] border p-4 shadow-card transition-colors',
        toneClasses[tone],
        className,
      )}
<<<<<<< HEAD
      {...props}
=======
>>>>>>> 26dcdfe (feat(dashboard): Add dashboard framework upgrade and new UI components)
    >
      <div className="flex items-center justify-between gap-3">
        <p className="eyebrow">{label}</p>
        <Icon className={cn('h-4 w-4', iconClasses[tone])} />
      </div>
      <p
        className={cn(
          compact
            ? 'mt-2 text-2xl font-semibold'
            : 'mt-4 font-display text-[2.8rem] font-semibold leading-none',
          'tabular-nums text-foreground',
          valueClassName,
        )}
      >
        {value}
      </p>
      {description ? (
        <p className="mt-2 text-sm leading-6 text-muted-foreground">{description}</p>
      ) : null}
      {children ? (
        <div className="mt-4 border-t border-border/60 pt-4">
          {children}
        </div>
      ) : null}
    </div>
  )
<<<<<<< HEAD
})
MetricCard.displayName = 'MetricCard'

export { MetricCard }
=======
}
>>>>>>> 26dcdfe (feat(dashboard): Add dashboard framework upgrade and new UI components)
