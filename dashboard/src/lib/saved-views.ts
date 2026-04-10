import type { EventFilter, SessionListQueryState } from '@/types/telemetry';

export interface SavedView<T> {
  name: string;
  value: T;
  updatedAt: string;
}

export interface TelemetryFilterOptions {
  agents: string[];
  phases: string[];
  tools: string[];
  providers: string[];
  statuses: string[];
  eventTypes: string[];
}

const EMPTY_SESSION_LIST_QUERY: SessionListQueryState = {
  search: '',
  status: '',
  activeOnly: false,
};

const EMPTY_EVENT_FILTERS: EventFilter = {
  phase: [],
  agent: [],
  tool: [],
  provider: [],
  status: [],
  eventTypes: [],
  timeRange: null,
};

function isRecord(value: unknown): value is Record<string, unknown> {
  return Boolean(value) && typeof value === 'object' && !Array.isArray(value);
}

function sortSavedViews<T>(views: SavedView<T>[]): SavedView<T>[] {
  return [...views].sort((left, right) => right.updatedAt.localeCompare(left.updatedAt));
}

export function normalizeSavedViewName(name: string): string {
  return name.trim().replace(/\s+/g, ' ').toLowerCase();
}

export function loadSavedViews<T>(
  storageKey: string,
  sanitizeValue: (value: unknown) => T
): SavedView<T>[] {
  if (typeof window === 'undefined') {
    return [];
  }

  try {
    const raw = window.localStorage.getItem(storageKey);
    if (!raw) {
      return [];
    }

    const parsed = JSON.parse(raw);
    if (!Array.isArray(parsed)) {
      return [];
    }

    const views: SavedView<T>[] = [];

    for (const item of parsed) {
      if (!isRecord(item) || typeof item.name !== 'string' || item.name.trim().length === 0) {
        continue;
      }

      views.push({
        name: item.name.trim(),
        value: sanitizeValue(item.value),
        updatedAt:
          typeof item.updatedAt === 'string' && item.updatedAt.length > 0
            ? item.updatedAt
            : new Date(0).toISOString(),
      });
    }

    return sortSavedViews(views);
  } catch (error) {
    console.warn(`Failed to load saved views for ${storageKey}`, error);
    return [];
  }
}

export function persistSavedViews<T>(storageKey: string, views: SavedView<T>[]) {
  if (typeof window === 'undefined') {
    return;
  }

  window.localStorage.setItem(storageKey, JSON.stringify(views));
}

export function upsertSavedView<T>(
  views: SavedView<T>[],
  name: string,
  value: T
): SavedView<T>[] {
  const trimmedName = name.trim().replace(/\s+/g, ' ');
  if (!trimmedName) {
    return views;
  }

  const normalizedName = normalizeSavedViewName(trimmedName);
  const nextViews = views.filter((view) => normalizeSavedViewName(view.name) !== normalizedName);
  nextViews.unshift({
    name: trimmedName,
    value,
    updatedAt: new Date().toISOString(),
  });
  return sortSavedViews(nextViews);
}

export function deleteSavedView<T>(views: SavedView<T>[], name: string): SavedView<T>[] {
  const normalizedName = normalizeSavedViewName(name);
  return views.filter((view) => normalizeSavedViewName(view.name) !== normalizedName);
}

export function findSavedView<T>(views: SavedView<T>[], name: string): SavedView<T> | null {
  const normalizedName = normalizeSavedViewName(name);
  return (
    views.find((view) => normalizeSavedViewName(view.name) === normalizedName) ?? null
  );
}

export function findMatchingSavedViewName<T>(
  views: SavedView<T>[],
  value: T,
  isEqual: (left: T, right: T) => boolean
): string | null {
  return views.find((view) => isEqual(view.value, value))?.name ?? null;
}

export function sanitizeSessionListQuery(
  value: unknown,
  allowedStatuses: string[]
): SessionListQueryState {
  if (!isRecord(value)) {
    return EMPTY_SESSION_LIST_QUERY;
  }

  const status =
    typeof value.status === 'string' && allowedStatuses.includes(value.status)
      ? value.status
      : '';

  return {
    search: typeof value.search === 'string' ? value.search : '',
    status,
    activeOnly: Boolean(value.activeOnly),
  };
}

function sanitizeFilterValues(value: unknown, allowedValues: string[]): string[] {
  if (!Array.isArray(value) || allowedValues.length === 0) {
    return [];
  }

  const allowed = new Set(allowedValues);
  return value.filter((item): item is string => typeof item === 'string' && allowed.has(item));
}

function sanitizeTimeRange(value: unknown): EventFilter['timeRange'] {
  if (!isRecord(value)) {
    return null;
  }

  const start = typeof value.start === 'number' ? value.start : Number.NaN;
  const end = typeof value.end === 'number' ? value.end : Number.NaN;
  if (!Number.isFinite(start) || !Number.isFinite(end) || start > end) {
    return null;
  }

  return { start, end };
}

function sanitizeFilterShape(value: unknown): string[] {
  if (!Array.isArray(value)) {
    return [];
  }

  return value.filter((item): item is string => typeof item === 'string');
}

export function sanitizeTelemetryFilterShape(value: unknown): EventFilter {
  if (!isRecord(value)) {
    return EMPTY_EVENT_FILTERS;
  }

  return {
    phase: sanitizeFilterShape(value.phase),
    agent: sanitizeFilterShape(value.agent),
    tool: sanitizeFilterShape(value.tool),
    provider: sanitizeFilterShape(value.provider),
    status: sanitizeFilterShape(value.status),
    eventTypes: sanitizeFilterShape(value.eventTypes),
    timeRange: sanitizeTimeRange(value.timeRange),
  };
}

export function sanitizeTelemetryFilters(
  value: unknown,
  options: TelemetryFilterOptions
): EventFilter {
  const shape = sanitizeTelemetryFilterShape(value);

  return {
    phase: sanitizeFilterValues(shape.phase, options.phases),
    agent: sanitizeFilterValues(shape.agent, options.agents),
    tool: sanitizeFilterValues(shape.tool, options.tools),
    provider: sanitizeFilterValues(shape.provider, options.providers),
    status: sanitizeFilterValues(shape.status, options.statuses),
    eventTypes: sanitizeFilterValues(shape.eventTypes, options.eventTypes),
    timeRange: shape.timeRange,
  };
}

export function areSessionListQueriesEqual(
  left: SessionListQueryState,
  right: SessionListQueryState
): boolean {
  return (
    left.search === right.search &&
    left.status === right.status &&
    left.activeOnly === right.activeOnly
  );
}

export function areEventFiltersEqual(left: EventFilter, right: EventFilter): boolean {
  return (
    left.phase.join('|') === right.phase.join('|')
    && left.agent.join('|') === right.agent.join('|')
    && left.tool.join('|') === right.tool.join('|')
    && left.provider.join('|') === right.provider.join('|')
    && left.status.join('|') === right.status.join('|')
    && left.eventTypes.join('|') === right.eventTypes.join('|')
    && (left.timeRange?.start ?? null) === (right.timeRange?.start ?? null)
    && (left.timeRange?.end ?? null) === (right.timeRange?.end ?? null)
  );
}
