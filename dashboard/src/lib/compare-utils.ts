import { Session } from '@/types/telemetry';

export interface CompareDeltas {
  durationDelta: number | null;
  sourceCountDelta: number | null;
  tokenDelta: number | null;
  routeDelta: Record<string, number> | null;
  degradedReasonDelta: string[] | null;
  failureCountDelta: number | null;
}

export interface SessionPair {
  sessionA: Session | null;
  sessionB: Session | null;
}

function formatDelta(value: number): string {
  const sign = value > 0 ? '+' : '';
  return `${sign}${value}`;
}

export function computeCompareDeltas(pair: SessionPair): CompareDeltas {
  const { sessionA, sessionB } = pair;

  if (!sessionA || !sessionB) {
    return {
      durationDelta: null,
      sourceCountDelta: null,
      tokenDelta: null,
      routeDelta: null,
      degradedReasonDelta: null,
      failureCountDelta: null,
    };
  }

  // Duration delta (B - A)
  const durationDelta =
    sessionA.totalTimeMs != null && sessionB.totalTimeMs != null
      ? sessionB.totalTimeMs - sessionA.totalTimeMs
      : null;

  // Source count delta (B - A)
  const sourceCountDelta = sessionB.totalSources - sessionA.totalSources;

  // Token delta - computed from event_count if available
  const tokenDelta =
    sessionA.eventCount != null && sessionB.eventCount != null
      ? sessionB.eventCount - sessionA.eventCount
      : null;

  // Route delta - provider counts (placeholder - would need event data)
  // This is a simplified version based on session depth
  const routeDelta: Record<string, number> = {};
  if (sessionA.depth !== sessionB.depth) {
    routeDelta.depth_change = sessionA.depth === sessionB.depth ? 0 :
      (sessionB.depth === 'deep' ? 1 : sessionB.depth === 'standard' ? 0 : -1) -
      (sessionA.depth === 'deep' ? 1 : sessionA.depth === 'standard' ? 0 : -1);
  }

  // Degraded reason delta - would need derived outputs
  // Placeholder based on status
  const degradedReasonDelta: string[] = [];
  if (sessionA.status !== sessionB.status) {
    if (sessionB.status === 'failed' || sessionB.status === 'interrupted') {
      degradedReasonDelta.push(`Status changed to ${sessionB.status}`);
    }
  }

  // Failure count delta - based on status
  const failureCountDelta =
    (sessionB.status === 'failed' ? 1 : 0) - (sessionA.status === 'failed' ? 1 : 0);

  return {
    durationDelta,
    sourceCountDelta,
    tokenDelta,
    routeDelta: Object.keys(routeDelta).length > 0 ? routeDelta : null,
    degradedReasonDelta: degradedReasonDelta.length > 0 ? degradedReasonDelta : null,
    failureCountDelta,
  };
}

export function formatDurationDelta(ms: number | null): string {
  if (ms === null) return 'N/A';
  const sign = ms > 0 ? '+' : '';
  const seconds = (ms / 1000).toFixed(2);
  return `${sign}${seconds}s`;
}

export function formatCountDelta(count: number | null): string {
  if (count === null) return 'N/A';
  return formatDelta(count);
}

export function getDeltaColor(value: number | null): string {
  if (value === null) return 'text-gray-600';
  if (value > 0) return 'text-red-600';
  if (value < 0) return 'text-green-600';
  return 'text-gray-600';
}
