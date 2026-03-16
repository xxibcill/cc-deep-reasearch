import { create } from 'zustand';
import { TelemetryEvent, Session, EventFilter, ViewMode } from '@/types/telemetry';

interface DashboardState {
  // Session selection
  sessionId: string | null;
  setSessionId: (id: string | null) => void;
  sessions: Session[];
  setSessions: (sessions: Session[]) => void;

  // Events
  events: TelemetryEvent[];
  setEvents: (events: TelemetryEvent[]) => void;
  addEvent: (event: TelemetryEvent) => void;

  // Filters
  filters: EventFilter;
  setFilters: (filters: Partial<EventFilter>) => void;
  
  // View mode
  viewMode: ViewMode;
  setViewMode: (mode: ViewMode) => void;

  // Auto-scroll
  autoScroll: boolean;
  toggleAutoScroll: () => void;
}

const useDashboardStore = create<DashboardState>((set) => ({
  sessionId: null,
  setSessionId: (id) => set({ sessionId: id }),
  sessions: [],
  setSessions: (sessions) => set({ sessions }),
  
  events: [],
  setEvents: (events) => set({ events }),
  addEvent: (event) => set((state) => ({ 
    events: [...state.events, event].slice(-1000) // Keep last 1000 events
  })),
  
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
