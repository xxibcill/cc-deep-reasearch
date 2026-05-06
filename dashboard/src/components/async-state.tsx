'use client';

import { AlertCircle, RefreshCw } from 'lucide-react';
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert';
import { Button } from '@/components/ui/button';
import { EmptyState } from '@/components/ui/empty-state';
import { SkeletonCard } from '@/components/ui/skeleton';
import { getErrorGuidance, type ErrorRoute } from '@/lib/error-messages';

export { EmptyState };

export interface LoadingStateProps {
  /** Number of skeleton cards to show (default 4) */
  count?: number;
  className?: string;
}

export function LoadingState({ count = 4, className }: LoadingStateProps) {
  return (
    <div className={className} role="status" aria-label="Loading">
      {Array.from({ length: count }).map((_, i) => (
        <SkeletonCard key={i} />
      ))}
    </div>
  );
}

export interface ErrorStateProps {
  error: string;
  onRetry?: () => void;
  /** Route hint for more specific guidance */
  route?: ErrorRoute;
  title?: string;
}

export function ErrorState({ error, onRetry, route = 'unknown', title }: ErrorStateProps) {
  const { title: errorTitle, guidance } = getErrorGuidance(error, route);
  return (
    <Alert variant="destructive" className="rounded-[1.2rem]">
      <div className="flex items-start gap-3">
        <AlertCircle className="h-5 w-5 shrink-0 mt-0.5" />
        <div className="space-y-2">
          <AlertTitle>{title ?? errorTitle}</AlertTitle>
          <AlertDescription>{error}</AlertDescription>
          {guidance ? (
            <p className="text-xs text-muted-foreground">{guidance}</p>
          ) : null}
          {onRetry ? (
            <Button onClick={onRetry} type="button" variant="outline" size="sm">
              <RefreshCw className="mr-2 h-4 w-4" />
              Retry
            </Button>
          ) : null}
        </div>
      </div>
    </Alert>
  );
}

export interface PartialErrorStateProps {
  title: string;
  description: string;
  onRetry?: () => void;
  variant?: 'warning' | 'error';
}

export function PartialErrorState({
  title,
  description,
  onRetry,
  variant = 'warning',
}: PartialErrorStateProps) {
  return (
    <Alert variant={variant === 'warning' ? 'warning' : 'destructive'}>
      <div className="flex items-start gap-3">
        <AlertCircle className="h-5 w-5 shrink-0 mt-0.5" />
        <div className="space-y-2">
          <AlertTitle>{title}</AlertTitle>
          <AlertDescription>{description}</AlertDescription>
          {onRetry ? (
            <Button onClick={onRetry} type="button" variant="outline" size="sm">
              <RefreshCw className="mr-2 h-4 w-4" />
              Retry
            </Button>
          ) : null}
        </div>
      </div>
    </Alert>
  );
}
