import { clsx, type ClassValue } from 'clsx';
import { twMerge } from 'tailwind-merge';

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

export type BadgeVariant = 'default' | 'secondary' | 'success' | 'warning' | 'destructive' | 'outline' | 'info';

/** Maps generic event/operation status strings to badge variants. */
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
  if (status === 'timeout' || status === 'fallback') {
    return 'warning';
  }
  return 'secondary';
}
