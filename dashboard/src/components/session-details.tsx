import { Activity, List, Network, Zap } from 'lucide-react';

import { TelemetryEvent, ViewMode } from '@/types/telemetry';

interface SessionDetailsProps {
  sessionId: string;
  connected: boolean;
  events: TelemetryEvent[];
  selectedEvent: TelemetryEvent | null;
  viewMode: ViewMode;
  onSelectEvent: (event: TelemetryEvent | null) => void;
  onViewModeChange: (mode: ViewMode) => void;
}

function formatEventTime(timestamp: string): string {
  const date = new Date(timestamp);
  return Number.isNaN(date.getTime()) ? timestamp : date.toLocaleTimeString();
}

function StatusBadge({ connected }: { connected: boolean }) {
  return (
    <span
      className={`text-sm px-2 py-1 rounded-full ${
        connected ? 'bg-green-100 text-green-800' : 'bg-red-100 text-red-800'
      }`}
    >
      {connected ? '● Live' : '○ Offline'}
    </span>
  );
}

function ViewModeSelector({
  currentMode,
  onViewModeChange,
}: {
  currentMode: ViewMode;
  onViewModeChange: (mode: ViewMode) => void;
}) {
  const buttons: Array<{ mode: ViewMode; title: string; icon: typeof Network }> = [
    { mode: 'graph', title: 'Workflow Graph', icon: Network },
    { mode: 'timeline', title: 'Agent Timeline', icon: Activity },
    { mode: 'table', title: 'Event Table', icon: List },
  ];

  return (
    <div className="flex items-center gap-2">
      {buttons.map(({ mode, title, icon: Icon }) => (
        <button
          key={mode}
          onClick={() => onViewModeChange(mode)}
          className={`p-2 rounded-md ${currentMode === mode ? 'bg-accent' : 'hover:bg-muted'}`}
          title={title}
        >
          <Icon className="h-5 w-5" />
        </button>
      ))}
    </div>
  );
}

function StatsCard({
  icon: Icon,
  label,
  value,
  accentClass,
}: {
  icon: typeof Activity;
  label: string;
  value: number;
  accentClass: string;
}) {
  return (
    <div className="border rounded-lg p-4 bg-card">
      <div className="flex items-center gap-2">
        <Icon className={`h-5 w-5 ${accentClass}`} />
        <span className="text-sm text-muted-foreground">{label}</span>
      </div>
      <div className="text-2xl font-bold mt-2">{value}</div>
    </div>
  );
}

function PlaceholderPanel({
  title,
  description,
}: {
  title: string;
  description: string;
}) {
  return (
    <div className="border rounded-lg p-6 bg-card min-h-[500px]">
      <h2 className="text-xl font-semibold mb-4">{title}</h2>
      <div className="flex flex-col items-center justify-center h-[400px] text-muted-foreground text-center">
        <p>{description}</p>
      </div>
    </div>
  );
}

function EventTable({
  events,
  onSelectEvent,
}: {
  events: TelemetryEvent[];
  onSelectEvent: (event: TelemetryEvent) => void;
}) {
  const visibleEvents = events.slice(0, 50);

  return (
    <div className="border rounded-lg p-6 bg-card">
      <h2 className="text-xl font-semibold mb-4">Event Table</h2>
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b">
              <th className="text-left p-3">Time</th>
              <th className="text-left p-3">Type</th>
              <th className="text-left p-3">Category</th>
              <th className="text-left p-3">Name</th>
              <th className="text-left p-3">Status</th>
              <th className="text-left p-3">Agent</th>
            </tr>
          </thead>
          <tbody>
            {visibleEvents.map((event) => (
              <tr
                key={event.eventId}
                onClick={() => onSelectEvent(event)}
                className="border-b hover:bg-accent cursor-pointer"
              >
                <td className="p-3">{formatEventTime(event.timestamp)}</td>
                <td className="p-3 font-mono text-xs">{event.eventType}</td>
                <td className="p-3">{event.category}</td>
                <td className="p-3">{event.name}</td>
                <td className="p-3">
                  <span
                    className={`px-2 py-1 rounded text-xs ${
                      event.status === 'completed'
                        ? 'bg-green-100 text-green-800'
                        : event.status === 'failed'
                          ? 'bg-red-100 text-red-800'
                          : 'bg-gray-100 text-gray-800'
                    }`}
                  >
                    {event.status}
                  </span>
                </td>
                <td className="p-3">{event.agentId || '-'}</td>
              </tr>
            ))}
          </tbody>
        </table>
        {events.length > visibleEvents.length && (
          <p className="text-center text-sm text-muted-foreground mt-4">
            Showing {visibleEvents.length} of {events.length} events
          </p>
        )}
      </div>
    </div>
  );
}

function EventDetailsModal({
  event,
  onClose,
}: {
  event: TelemetryEvent;
  onClose: () => void;
}) {
  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center p-4 z-50">
      <div className="bg-card border rounded-lg max-w-2xl w-full max-h-[80vh] overflow-auto">
        <div className="flex items-center justify-between p-4 border-b">
          <h3 className="text-xl font-semibold">Event Details</h3>
          <button onClick={onClose} className="p-2 hover:bg-muted rounded-md">
            ✕
          </button>
        </div>
        <div className="p-4">
          <pre className="text-sm bg-muted p-4 rounded-md overflow-auto">
            {JSON.stringify(event, null, 2)}
          </pre>
        </div>
      </div>
    </div>
  );
}

export function SessionDetails({
  sessionId,
  connected,
  events,
  selectedEvent,
  viewMode,
  onSelectEvent,
  onViewModeChange,
}: SessionDetailsProps) {
  const agentEvents = events.filter((event) => event.category === 'agent');
  const toolEvents = events.filter((event) => event.category === 'tool');
  const llmEvents = events.filter((event) => event.category === 'llm');

  return (
    <div className="min-h-screen bg-background">
      <header className="border-b bg-card">
        <div className="container mx-auto px-4 py-4">
          <div className="flex items-center justify-between">
            <div>
              <h1 className="text-2xl font-bold">Session: {sessionId.slice(0, 8)}</h1>
              <div className="flex items-center gap-2 mt-1">
                <StatusBadge connected={connected} />
                <span className="text-sm text-muted-foreground">{events.length} events</span>
              </div>
            </div>
            <ViewModeSelector currentMode={viewMode} onViewModeChange={onViewModeChange} />
          </div>
        </div>
      </header>

      <main className="container mx-auto px-4 py-6">
        <div className="grid gap-4 md:grid-cols-4 mb-6">
          <StatsCard icon={Activity} label="Agents" value={agentEvents.length} accentClass="text-blue-600" />
          <StatsCard icon={Zap} label="Tool Calls" value={toolEvents.length} accentClass="text-yellow-600" />
          <StatsCard icon={Network} label="LLM Calls" value={llmEvents.length} accentClass="text-green-600" />
          <StatsCard icon={List} label="Total Events" value={events.length} accentClass="text-purple-600" />
        </div>

        {viewMode === 'graph' && (
          <PlaceholderPanel
            title="Workflow Graph"
            description="Workflow graph visualization coming soon. This panel will show agent dependencies and execution flow."
          />
        )}

        {viewMode === 'timeline' && (
          <PlaceholderPanel
            title="Agent Timeline"
            description="Agent timeline visualization coming soon. This panel will show parallel agent execution over time."
          />
        )}

        {viewMode === 'table' && <EventTable events={events} onSelectEvent={onSelectEvent} />}

        {selectedEvent && <EventDetailsModal event={selectedEvent} onClose={() => onSelectEvent(null)} />}
      </main>
    </div>
  );
}
