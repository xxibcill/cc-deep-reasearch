import { create } from 'zustand';
import { TelemetryEvent, Session, EventFilter, ViewMode } from '@/types/telemetry';

interface DashboardState {
  sessionId: string | null;
  setSessionId: (id: string | null) => void;
  sessions: Session[];
  sessionsLoading: boolean;
  setSessions: (sessions: Session[]) => void;
  setSessionsLoading: (loading: boolean) => void;

  events: TelemetryEvent[];
  connected: boolean;
  selectedEvent: TelemetryEvent | null;
  replaceEvents: (events: TelemetryEvent[]) => void;
  appendEvent: (event: TelemetryEvent) => void;
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
  events: [],
  connected: false,
  selectedEvent: null,
  replaceEvents: (events) => set({ events: sortEvents(events) }),
  appendEvent: (event) =>
    set((state) => {
      if (state.events.some((existing) => existing.eventId === event.eventId)) {
        return {};
      }
      return { events: sortEvents([...state.events, event]).slice(-1000) };
    }),
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
