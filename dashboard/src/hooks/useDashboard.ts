import { create } from 'zustand';
import {
  TelemetryEvent,
  Session,
  EventFilter,
  ViewMode,
  SessionListQueryState,
} from '@/types/telemetry';

const defaultSessionListQuery: SessionListQueryState = {
  search: '',
  status: '',
  activeOnly: false,
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
  removeSession: (sessionId: string) => void;
  reconcileSession: (sessionId: string, changes: Partial<Session>) => void;

  deleteError: string | null;
  deleteSuccess: boolean;
  setDeleteError: (error: string | null) => void;
  setDeleteSuccess: (success: boolean) => void;
  clearDeleteStatus: () => void;

  events: TelemetryEvent[];
  connected: boolean;
  selectedEvent: TelemetryEvent | null;
  replaceEvents: (events: TelemetryEvent[]) => void;
  appendEvent: (event: TelemetryEvent) => void;
  appendEvents: (events: TelemetryEvent[]) => void;
  setConnected: (connected: boolean) => void;
  setSelectedEvent: (event: TelemetryEvent | null) => void;
  resetSessionState: () => void;

  filters: EventFilter;
  setFilters: (filters: Partial<EventFilter>) => void;
  viewMode: ViewMode;
  setViewMode: (mode: ViewMode) => void;
  autoScroll: boolean;
  toggleAutoScroll: () => void;
}

function sortEvents(events: TelemetryEvent[]): TelemetryEvent[] {
  return [...events].sort((left, right) => {
    if (left.sequenceNumber !== right.sequenceNumber) {
      return left.sequenceNumber - right.sequenceNumber;
    }
    return left.timestamp.localeCompare(right.timestamp);
  });
}

function mergeEvents(existing: TelemetryEvent[], incoming: TelemetryEvent[]): TelemetryEvent[] {
  const byId = new Map(existing.map((event) => [event.eventId, event]));
  for (const event of incoming) {
    byId.set(event.eventId, event);
  }
  return sortEvents(Array.from(byId.values())).slice(-4000);
}

function mergeSessions(existing: Session[], incoming: Session[]): Session[] {
  const byId = new Map(existing.map((session) => [session.sessionId, session]));
  for (const session of incoming) {
    byId.set(session.sessionId, session);
  }
  return Array.from(byId.values());
}

function matchesSessionListQuery(session: Session, query: SessionListQueryState): boolean {
  if (query.activeOnly && !session.active) {
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
            connected: false,
            selectedEvent: null,
          }
  ),
  sessions: [],
  sessionsLoading: true,
  sessionsLoadingMore: false,
  sessionsTotal: 0,
  sessionsNextCursor: null,
  sessionListQuery: defaultSessionListQuery,
  setSessions: (sessions, options) =>
    set((state) => ({
      sessions: options?.append ? mergeSessions(state.sessions, sessions) : sessions,
      sessionsTotal: options?.total ?? state.sessionsTotal,
      sessionsNextCursor:
        options && Object.prototype.hasOwnProperty.call(options, 'nextCursor')
          ? options.nextCursor ?? null
          : state.sessionsNextCursor,
    })),
  setSessionsLoading: (sessionsLoading) => set({ sessionsLoading }),
  setSessionsLoadingMore: (sessionsLoadingMore) => set({ sessionsLoadingMore }),
  setSessionListQuery: (query) =>
    set((state) => ({
      sessionListQuery: { ...state.sessionListQuery, ...query },
    })),
  removeSession: (sessionId) =>
    set((state) => ({
      sessions: state.sessions.filter((s) => s.sessionId !== sessionId),
      sessionsTotal: Math.max(state.sessionsTotal - 1, 0),
      sessionsNextCursor:
        state.sessionsNextCursor === sessionId ? null : state.sessionsNextCursor,
    })),
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
  connected: false,
  selectedEvent: null,
  replaceEvents: (events) => set({ events: sortEvents(events) }),
  appendEvent: (event) =>
    set((state) => {
      if (state.events.some((existing) => existing.eventId === event.eventId)) {
        return {};
      }
      return { events: mergeEvents(state.events, [event]) };
    }),
  appendEvents: (events) =>
    set((state) => ({ events: mergeEvents(state.events, events) })),
  setConnected: (connected) => set({ connected }),
  setSelectedEvent: (selectedEvent) => set({ selectedEvent }),
  resetSessionState: () =>
    set({
      sessionId: null,
      events: [],
      connected: false,
      selectedEvent: null,
      viewMode: 'graph',
    }),
  filters: {
    phase: [],
    agent: [],
    tool: [],
    provider: [],
    status: [],
    eventTypes: [],
    timeRange: null,
  },
  setFilters: (filters) => set((state) => ({
    filters: { ...state.filters, ...filters }
  })),
  viewMode: 'graph',
  setViewMode: (mode) => set({ viewMode: mode }),
  autoScroll: true,
  toggleAutoScroll: () => set((state) => ({ 
    autoScroll: !state.autoScroll 
  })),
}));

export default useDashboardStore;
