import { clsx, type ClassValue } from 'clsx';
import { twMerge } from 'tailwind-merge';

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

export type BadgeVariant = 'default' | 'secondary' | 'success' | 'warning' | 'destructive' | 'outline' | 'info';

/**
 * Maps generic event/operation status strings to badge variants.
 *
 * Mapping philosophy:
 * - success/completed/healthy → success (positive outcomes)
 * - failed/error/timeout → destructive (errors/failures)
 * - running/started/pending/scheduled → default (in-progress states)
 * - queued/secondary/unknown/etc → secondary (neutral/informational)
 * - cancelled/skipped/stalled/warning → warning (attention needed but not errors)
 * - outline → outline (explicit styling request)
 */
export function getStatusBadgeVariant(status: string): BadgeVariant {
  if (status === 'completed' || status === 'success') {
    return 'success';
  }
  if (status === 'failed' || status === 'error') {
    return 'destructive';
  }
  if (status === 'running') {
    return 'default';
  }
  if (status === 'queued') {
    return 'secondary';
  }
  if (status === 'cancelled') {
    return 'warning';
  }
  if (status === 'skipped') {
    return 'warning';
  }
  if (status === 'timeout' || status === 'fallback') {
    return 'warning';
  }
  return 'secondary';
}
