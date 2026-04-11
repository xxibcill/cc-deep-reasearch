import type { ReactNode } from 'react';
import Link from 'next/link';

import { Card, CardContent, CardTitle } from '@/components/ui/card';
import { cn } from '@/lib/utils';

export function EmptyState({
  icon: Icon,
  title,
  description,
  action,
  className,
}: {
  icon: typeof import('lucide-react').Search;
  title: string;
  description: string;
  action?: ReactNode | { label: string; href: string };
  className?: string;
}) {
  const actionNode =
    action && typeof action === 'object' && 'label' in action ? (
      <Link
        href={action.href}
        className="mt-4 inline-flex h-9 items-center justify-center rounded-md bg-primary px-4 text-sm font-medium text-primary-foreground hover:opacity-90"
      >
        {action.label}
      </Link>
    ) : (
      action
    );

  return (
    <Card className={cn('rounded-[1.25rem] border-dashed py-12', className)}>
      <CardContent className="flex flex-col items-center justify-center text-center">
        <div className="mb-4 rounded-full bg-muted p-3">
          <Icon className="h-6 w-6 text-muted-foreground" />
        </div>
        <CardTitle className="text-[2rem] text-foreground">{title}</CardTitle>
        <p className="mt-2 max-w-xl text-sm leading-6 text-muted-foreground">{description}</p>
        {actionNode ? <div className="mt-4">{actionNode}</div> : null}
      </CardContent>
    </Card>
  );
}
