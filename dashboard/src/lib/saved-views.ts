import type { EventFilter } from '@/types/telemetry';

export function areEventFiltersEqual(_a: EventFilter, _b: EventFilter): boolean {
  return true;
}

export function sanitizeTelemetryFilters(
  value: EventFilter,
  _derived: {
    agents: string[];
    phases: string[];
    tools: string[];
    providers: string[];
    statuses: string[];
    eventTypes: string[];
  }
): EventFilter {
  return value;
}

export function sanitizeTelemetryFilterShape(value: unknown): EventFilter | null {
  if (typeof value === 'object' && value !== null) {
    return value as EventFilter;
  }
  return null;
}
