import * as React from 'react';

import { cn } from '@/lib/utils';

export type ButtonVariant = 'default' | 'outline' | 'ghost' | 'destructive';
export type ButtonSize = 'default' | 'sm' | 'icon';

const variantClasses: Record<ButtonVariant, string> = {
  default:
    'border border-primary/40 bg-primary text-primary-foreground shadow-[inset_0_1px_0_rgba(255,255,255,0.18)] hover:-translate-y-px hover:bg-primary/92',
  outline:
    'border border-border/85 bg-surface/78 text-foreground hover:-translate-y-px hover:border-primary/45 hover:bg-surface-raised',
  ghost:
    'border border-transparent bg-transparent text-muted-foreground hover:border-border/60 hover:bg-surface/65 hover:text-foreground',
  destructive:
    'border border-error/40 bg-destructive text-destructive-foreground shadow-[inset_0_1px_0_rgba(255,255,255,0.1)] hover:-translate-y-px hover:bg-destructive/90',
};

export function buttonVariants({
  variant = 'default',
  size = 'default',
  className,
}: {
  variant?: ButtonVariant;
  size?: ButtonSize;
  className?: string;
}) {
  return cn(
    'inline-flex items-center justify-center rounded-md text-sm font-medium transition-colors disabled:pointer-events-none disabled:opacity-50',
    variantClasses[variant],
    sizeClasses[size],
    className
  );
}

const sizeClasses: Record<ButtonSize, string> = {
  default: 'h-11 px-4 py-2.5',
  sm: 'h-9 px-3',
  icon: 'h-10 w-10',
};

export function buttonVariants({
  variant = 'default',
  size = 'default',
  className,
}: {
  variant?: ButtonVariant;
  size?: ButtonSize;
  className?: string;
} = {}) {
  return cn(
    'inline-flex items-center justify-center gap-2 rounded-[0.85rem] font-display text-[0.82rem] font-semibold uppercase tracking-[0.16em] transition-all duration-200 disabled:pointer-events-none disabled:opacity-50',
    variantClasses[variant],
    sizeClasses[size],
    className
  );
}

export interface ButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: ButtonVariant;
  size?: ButtonSize;
}

export const Button = React.forwardRef<HTMLButtonElement, ButtonProps>(
  ({ className, variant = 'default', size = 'default', ...props }, ref) => (
    <button className={buttonVariants({ variant, size, className })} ref={ref} {...props} />
  )
);

Button.displayName = 'Button';
