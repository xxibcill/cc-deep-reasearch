import { create } from 'zustand';
import { TelemetryEvent, Session, EventFilter, ViewMode } from '@/types/telemetry';

interface DashboardState {
  sessionId: string | null;
  setSessionId: (id: string | null) => void;
  sessions: Session[];
  sessionsLoading: boolean;
  setSessions: (sessions: Session[]) => void;
  setSessionsLoading: (loading: boolean) => void;
  removeSession: (sessionId: string) => void;

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
  setSessions: (sessions) => set({ sessions }),
  setSessionsLoading: (sessionsLoading) => set({ sessionsLoading }),
  removeSession: (sessionId) =>
    set((state) => ({
      sessions: state.sessions.filter((s) => s.sessionId !== sessionId),
    })),

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
