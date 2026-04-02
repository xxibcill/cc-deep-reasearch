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
    default: 'bg-primary text-primary-foreground',
    secondary: 'bg-secondary text-secondary-foreground',
    success: 'bg-success-muted text-success',
    warning: 'bg-warning-muted text-warning',
    destructive: 'bg-error-muted text-error',
    outline: 'border border-border bg-background text-foreground',
    info: 'bg-primary/15 text-primary',
  };

  return (
    <span
      className={cn(
        'inline-flex items-center rounded-full px-2.5 py-1 text-xs font-semibold transition-colors duration-300',
        variants[variant],
        className
      )}
    >
      {children}
    </span>
  );
}
