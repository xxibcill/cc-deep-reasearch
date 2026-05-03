import { create } from 'zustand';
import {
  TelemetryEvent,
  Session,
  EventFilter,
  ViewMode,
  SessionListQueryState,
  LiveStreamStatus,
} from '@/types/telemetry';

export const DEFAULT_SESSION_LIST_QUERY: SessionListQueryState = {
  search: '',
  status: '',
  activeOnly: false,
  archivedOnly: false,
};

export const DEFAULT_EVENT_FILTERS: EventFilter = {
  phase: [],
  agent: [],
  tool: [],
  provider: [],
  status: [],
  eventTypes: [],
  timeRange: null,
};

export const MAX_BUFFERED_EVENTS = 4000;

export const DEFAULT_LIVE_STREAM_STATUS: LiveStreamStatus = {
  phase: 'idle',
  connected: false,
  reconnectAttempt: 0,
  maxReconnectAttempts: 5,
  nextRetryAt: null,
  lastMessageAt: null,
  lastEventAt: null,
  lastHistoryAt: null,
  lastDisconnectAt: null,
  lastSuccessAt: null,
  failureReason: null,
  canReconnect: false,
  reconnectHistory: [],
};

interface DashboardState {
  sessionId: string | null;
  setSessionId: (id: string | null) => void;
  sessions: Session[];
  sessionsLoading: boolean;
  sessionsLoadingMore: boolean;
  sessionsTotal: number;
  sessionsNextCursor: string | null;
  sessionListQuery: SessionListQueryState;
  setSessions: (sessions: Session[], options?: {
    total?: number;
    nextCursor?: string | null;
    append?: boolean;
  }) => void;
  setSessionsLoading: (loading: boolean) => void;
  setSessionsLoadingMore: (loading: boolean) => void;
  setSessionListQuery: (query: Partial<SessionListQueryState>) => void;
  selectedSessionIds: string[];
  toggleSessionSelection: (sessionId: string) => void;
  setSelectedSessionIds: (sessionIds: string[]) => void;
  clearSessionSelection: () => void;
  removeSession: (sessionId: string) => void;
  removeSessions: (sessionIds: string[]) => void;
  reconcileSession: (sessionId: string, changes: Partial<Session>) => void;

  deleteError: string | null;
  deleteSuccess: boolean;
  setDeleteError: (error: string | null) => void;
  setDeleteSuccess: (success: boolean) => void;
  clearDeleteStatus: () => void;

  events: TelemetryEvent[];
  eventIdSet: Set<string>;
  connected: boolean;
  liveStreamStatus: LiveStreamStatus;
  selectedEvent: TelemetryEvent | null;
  replaceEvents: (events: TelemetryEvent[]) => void;
  appendEvent: (event: TelemetryEvent) => void;
  appendEvents: (events: TelemetryEvent[]) => void;
  appendBufferedEvents: (events: TelemetryEvent[]) => void;
  setConnected: (connected: boolean) => void;
  setLiveStreamStatus: (status: Partial<LiveStreamStatus>) => void;
  appendReconnectHistory: (entry: import('@/types/telemetry').ReconnectHistoryEntry) => void;
  setSelectedEvent: (event: TelemetryEvent | null) => void;
  resetSessionState: () => void;

  filters: EventFilter;
  setFilters: (filters: Partial<EventFilter>) => void;
  viewMode: ViewMode;
  setViewMode: (mode: ViewMode) => void;
  autoScroll: boolean;
  toggleAutoScroll: () => void;

  compareMode: boolean;
  setCompareMode: (enabled: boolean) => void;
  compareSessionIds: [string | null, string | null];
  setCompareSessionIds: (ids: [string | null, string | null]) => void;
  toggleCompareSessionId: (sessionId: string) => void;
  clearCompareSessionIds: () => void;
}

function sortEvents(events: TelemetryEvent[]): TelemetryEvent[] {
  return [...events].sort((left, right) => {
    if (left.sequenceNumber !== right.sequenceNumber) {
      return left.sequenceNumber - right.sequenceNumber;
    }
    return left.timestamp.localeCompare(right.timestamp);
  });
}

function mergeEvents(
  existing: TelemetryEvent[],
  incoming: TelemetryEvent[],
  options?: { limit?: number }
): TelemetryEvent[] {
  const byId = new Map(existing.map((event) => [event.eventId, event]));
  for (const event of incoming) {
    byId.set(event.eventId, event);
  }
  const merged = sortEvents(Array.from(byId.values()));
  return typeof options?.limit === 'number' ? merged.slice(-options.limit) : merged;
}

function mergeSessions(existing: Session[], incoming: Session[]): Session[] {
  const byId = new Map(existing.map((session) => [session.sessionId, session]));
  for (const session of incoming) {
    byId.set(session.sessionId, session);
  }
  return Array.from(byId.values());
}

function pruneSelectedSessionIds(sessions: Session[], selectedSessionIds: string[]): string[] {
  const visibleIds = new Set(sessions.map((session) => session.sessionId));
  return selectedSessionIds.filter((sessionId) => visibleIds.has(sessionId));
}

function matchesSessionListQuery(session: Session, query: SessionListQueryState): boolean {
  if (query.activeOnly && !session.active) {
    return false;
  }
  if (query.archivedOnly && !session.archived) {
    return false;
  }
  if (query.status && session.status !== query.status) {
    return false;
  }
  return true;
}

const useDashboardStore = create<DashboardState>((set) => ({
  sessionId: null,
  setSessionId: (id) =>
    set((state) =>
      state.sessionId === id
        ? {}
        : {
            sessionId: id,
            events: [],
            eventIdSet: new Set<string>(),
            connected: false,
            liveStreamStatus: DEFAULT_LIVE_STREAM_STATUS,
            selectedEvent: null,
          }
    ),
  sessions: [],
  sessionsLoading: true,
  sessionsLoadingMore: false,
  sessionsTotal: 0,
  sessionsNextCursor: null,
  sessionListQuery: DEFAULT_SESSION_LIST_QUERY,
  setSessions: (sessions, options) =>
    set((state) => {
      const nextSessions = options?.append ? mergeSessions(state.sessions, sessions) : sessions;
      return {
        sessions: nextSessions,
        sessionsTotal: options?.total ?? state.sessionsTotal,
        sessionsNextCursor:
          options && Object.prototype.hasOwnProperty.call(options, 'nextCursor')
            ? options.nextCursor ?? null
            : state.sessionsNextCursor,
        selectedSessionIds: pruneSelectedSessionIds(nextSessions, state.selectedSessionIds),
      };
    }),
  setSessionsLoading: (sessionsLoading) => set({ sessionsLoading }),
  setSessionsLoadingMore: (sessionsLoadingMore) => set({ sessionsLoadingMore }),
  setSessionListQuery: (query) =>
    set((state) => ({
      sessionListQuery: { ...state.sessionListQuery, ...query },
      selectedSessionIds: [],
    })),
  selectedSessionIds: [],
  toggleSessionSelection: (sessionId) =>
    set((state) => ({
      selectedSessionIds: state.selectedSessionIds.includes(sessionId)
        ? state.selectedSessionIds.filter((id) => id !== sessionId)
        : [...state.selectedSessionIds, sessionId],
    })),
  setSelectedSessionIds: (selectedSessionIds) => set({ selectedSessionIds }),
  clearSessionSelection: () => set({ selectedSessionIds: [] }),
  removeSession: (sessionId) =>
    set((state) => ({
      sessions: state.sessions.filter((s) => s.sessionId !== sessionId),
      sessionsTotal: Math.max(state.sessionsTotal - 1, 0),
      sessionsNextCursor:
        state.sessionsNextCursor === sessionId ? null : state.sessionsNextCursor,
      selectedSessionIds: state.selectedSessionIds.filter((id) => id !== sessionId),
    })),
  removeSessions: (sessionIds) =>
    set((state) => {
      const removedIds = new Set(sessionIds);
      const removedCount = state.sessions.filter((session) => removedIds.has(session.sessionId)).length;
      return {
        sessions: state.sessions.filter((session) => !removedIds.has(session.sessionId)),
        sessionsTotal: Math.max(state.sessionsTotal - removedCount, 0),
        sessionsNextCursor:
          state.sessionsNextCursor && removedIds.has(state.sessionsNextCursor)
            ? null
            : state.sessionsNextCursor,
        selectedSessionIds: state.selectedSessionIds.filter((id) => !removedIds.has(id)),
      };
    }),
  reconcileSession: (sessionId, changes) =>
    set((state) => {
      const current = state.sessions.find((session) => session.sessionId === sessionId);
      if (!current) {
        return {};
      }

      const nextSession = { ...current, ...changes };
      if (!matchesSessionListQuery(nextSession, state.sessionListQuery)) {
        return {
          sessions: state.sessions.filter((session) => session.sessionId !== sessionId),
          sessionsTotal: Math.max(state.sessionsTotal - 1, 0),
        };
      }

      return {
        sessions: state.sessions.map((session) =>
          session.sessionId === sessionId ? nextSession : session
        ),
      };
    }),

  deleteError: null,
  deleteSuccess: false,
  setDeleteError: (deleteError) => set({ deleteError }),
  setDeleteSuccess: (deleteSuccess) => set({ deleteSuccess }),
  clearDeleteStatus: () => set({ deleteError: null, deleteSuccess: false }),

  events: [],
  eventIdSet: new Set<string>(),
  connected: false,
  liveStreamStatus: DEFAULT_LIVE_STREAM_STATUS,
  selectedEvent: null,
  replaceEvents: (events) => {
    const newEventIdSet = new Set<string>();
    for (const event of events) {
      newEventIdSet.add(event.eventId);
    }
    return { events: sortEvents(events), eventIdSet: newEventIdSet };
  },
  appendEvent: (event) =>
    set((state) => {
      if (state.eventIdSet.has(event.eventId)) {
        return {};
      }
      const newEventIdSet = new Set(state.eventIdSet);
      newEventIdSet.add(event.eventId);
      const newEvents = mergeEvents(state.events, [event], {
        limit: MAX_BUFFERED_EVENTS,
      });
      // Rebuild eventIdSet from merged events (limit may have removed some)
      const rebuiltEventIdSet = new Set<string>();
      for (const e of newEvents) {
        rebuiltEventIdSet.add(e.eventId);
      }
      return { events: newEvents, eventIdSet: rebuiltEventIdSet };
    }),
  appendEvents: (events) =>
    set((state) => {
      let changed = false;
      const newEventIdSet = new Set(state.eventIdSet);
      const newEventsList: TelemetryEvent[] = [...state.events];
      for (const event of events) {
        if (!newEventIdSet.has(event.eventId)) {
          newEventIdSet.add(event.eventId);
          newEventsList.push(event);
          changed = true;
        }
      }
      if (!changed) {
        return {};
      }
      const sorted = sortEvents(newEventsList);
      return { events: sorted, eventIdSet: newEventIdSet };
    }),
  appendBufferedEvents: (events) =>
    set((state) => {
      const newEventIdSet = new Set(state.eventIdSet);
      const newEventsList: TelemetryEvent[] = [...state.events];
      for (const event of events) {
        if (!newEventIdSet.has(event.eventId)) {
          newEventIdSet.add(event.eventId);
          newEventsList.push(event);
        }
      }
      const sorted = sortEvents(newEventsList);
      const trimmed = sorted.slice(-MAX_BUFFERED_EVENTS);
      const trimmedEventIdSet = new Set<string>();
      for (const e of trimmed) {
        trimmedEventIdSet.add(e.eventId);
      }
      return { events: trimmed, eventIdSet: trimmedEventIdSet };
    }),
  setConnected: (connected) => set({ connected }),
  setLiveStreamStatus: (status) =>
    set((state) => ({
      liveStreamStatus: { ...state.liveStreamStatus, ...status },
      connected:
        Object.prototype.hasOwnProperty.call(status, 'connected')
          ? Boolean(status.connected)
          : state.connected,
    })),
  appendReconnectHistory: (entry) =>
    set((state) => ({
      liveStreamStatus: {
        ...state.liveStreamStatus,
        reconnectHistory: [
          ...state.liveStreamStatus.reconnectHistory,
          entry,
        ].slice(-20),
      },
    })),
  setSelectedEvent: (selectedEvent) => set({ selectedEvent }),
  resetSessionState: () =>
    set({
      sessionId: null,
      events: [],
      eventIdSet: new Set<string>(),
      connected: false,
      liveStreamStatus: DEFAULT_LIVE_STREAM_STATUS,
      selectedEvent: null,
      viewMode: 'graph',
    }),
  filters: DEFAULT_EVENT_FILTERS,
  setFilters: (filters) => set((state) => ({
    filters: { ...state.filters, ...filters }
  })),
  viewMode: 'graph',
  setViewMode: (mode) => set({ viewMode: mode }),
  autoScroll: true,
  toggleAutoScroll: () => set((state) => ({
    autoScroll: !state.autoScroll
  })),

  compareMode: false,
  setCompareMode: (enabled) => set({ compareMode: enabled, compareSessionIds: [null, null] }),
  compareSessionIds: [null, null],
  setCompareSessionIds: (ids) => set({ compareSessionIds: ids }),
  toggleCompareSessionId: (sessionId) =>
    set((state) => {
      const [a, b] = state.compareSessionIds;
      if (a === sessionId) {
        return { compareSessionIds: [null, b] };
      }
      if (b === sessionId) {
        return { compareSessionIds: [a, null] };
      }
      if (!a) {
        return { compareSessionIds: [sessionId, null] };
      }
      if (!b) {
        return { compareSessionIds: [a, sessionId] };
      }
      return {};
    }),
  clearCompareSessionIds: () => set({ compareSessionIds: [null, null] }),
}));

export default useDashboardStore;
