import * as React from 'react';

import { cn } from '@/lib/utils';

export function Card({ className, ...props }: React.HTMLAttributes<HTMLDivElement>) {
  return (
    <div
      className={cn(
        "panel-shell rounded-[1.15rem] text-card-foreground shadow-card",
        "before:absolute before:left-5 before:right-5 before:top-0 before:h-px before:bg-gradient-to-r before:from-transparent before:via-primary/65 before:to-transparent before:content-['']",
        className
      )}
      {...props}
    />
  );
}

export function CardHeader({ className, ...props }: React.HTMLAttributes<HTMLDivElement>) {
  return <div className={cn('flex flex-col gap-2 p-6', className)} {...props} />;
}

type CardTitleProps = React.HTMLAttributes<HTMLHeadingElement> & {
  as?: React.ElementType;
};

export function CardTitle({ className, as: Comp = 'h2', ...props }: CardTitleProps) {
  return (
    <Comp
      className={cn(
        'font-display text-[1.75rem] font-semibold uppercase tracking-[0.02em] text-foreground',
        className
      )}
      {...props}
    />
  );
}

export function CardDescription({ className, ...props }: React.HTMLAttributes<HTMLParagraphElement>) {
  return <p className={cn('text-sm text-muted-foreground', className)} {...props} />;
}

export function CardContent({ className, ...props }: React.HTMLAttributes<HTMLDivElement>) {
  return <div className={cn('p-6 pt-0', className)} {...props} />;
}
