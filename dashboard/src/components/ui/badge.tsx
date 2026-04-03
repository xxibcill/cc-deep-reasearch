import { cn } from '@/lib/utils';

export function Badge({
  className,
  variant = 'default',
  children,
}: {
  className?: string;
  variant?: 'default' | 'secondary' | 'success' | 'warning' | 'destructive' | 'outline' | 'info';
  children: React.ReactNode;
}) {
  const variants = {
    default: 'border border-primary/30 bg-primary/14 text-primary',
    secondary: 'border border-border/70 bg-secondary/70 text-secondary-foreground',
    success: 'border border-success/30 bg-success-muted/80 text-success',
    warning: 'border border-warning/30 bg-warning-muted/80 text-warning',
    destructive: 'border border-error/30 bg-error-muted/80 text-error',
    outline: 'border border-border bg-background/75 text-foreground',
    info: 'border border-primary/26 bg-primary/12 text-primary',
  };

  return (
    <span
      className={cn(
        'inline-flex items-center rounded-md px-2.5 py-1 font-mono text-[0.68rem] font-medium uppercase tracking-[0.16em] transition-colors duration-300',
        variants[variant],
        className
      )}
    >
      {children}
    </span>
  );
}
