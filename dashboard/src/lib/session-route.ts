import type { ResearchRunStatus, Session } from '@/types/telemetry';

export function isRunRouteId(routeId: string): boolean {
  return routeId.startsWith('run-');
}

export function toRunStatus(session: Session): ResearchRunStatus | null {
  if (session.active || session.status === 'running') {
    return 'running';
  }

  if (session.status === 'completed') {
    return 'completed';
  }

  if (session.status === 'failed') {
    return 'failed';
  }

  if (session.status === 'interrupted') {
    return 'cancelled';
  }

  return null;
}

export function isTerminalStatus(status: ResearchRunStatus | null): boolean {
  return status === 'completed' || status === 'failed' || status === 'cancelled';
}

export function mergeRunStatus(
  current: ResearchRunStatus | null,
  next: ResearchRunStatus | null
): ResearchRunStatus | null {
  if (!next) {
    return current;
  }

  if (isTerminalStatus(current)) {
    return current;
  }

  return next;
}

export function runStatusBadgeVariant(
  status: ResearchRunStatus | null
): 'default' | 'secondary' | 'success' | 'destructive' | 'warning' {
  if (status === 'completed') {
    return 'success';
  }

  if (status === 'failed') {
    return 'destructive';
  }

  if (status === 'cancelled') {
    return 'warning';
  }

  if (status === 'running') {
    return 'default';
  }

  return 'secondary';
}
