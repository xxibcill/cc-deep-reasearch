import { clsx, type ClassValue } from 'clsx';
import { twMerge } from 'tailwind-merge';

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

export function getStatusBadgeVariant(
  status: string
): 'success' | 'warning' | 'destructive' | 'secondary' | 'default' | 'info' | 'outline' {
  switch (status) {
    case 'completed':
    case 'success':
    case 'healthy':
      return 'success';
    case 'running':
    case 'started':
    case 'pending':
    case 'scheduled':
      return 'info';
    case 'failed':
    case 'error':
    case 'timeout':
    case 'destructive':
      return 'destructive';
    case 'warning':
    case 'cancelled':
    case 'stalled':
      return 'warning';
    case 'secondary':
    case 'unknown':
    case 'selected':
    case 'recorded':
    case 'fallback':
      return 'secondary';
    case 'outline':
      return 'outline';
    default:
      return 'default';
  }
}
