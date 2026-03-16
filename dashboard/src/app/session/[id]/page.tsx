'use client';

import { useEffect, useState } from 'react';
import { useWebSocket } from '@/lib/websocket';
import { getSessionEvents } from '@/lib/api';
import { TelemetryEvent, ViewMode } from '@/types/telemetry';
import { Activity, Zap, List, Network } from 'lucide-react';

export default function SessionPage({ params }: { params: { id: string } }) {
  const sessionId = params.id;
  const { connected, events } = useWebSocket(sessionId);
  const [viewMode, setViewMode] = useState<ViewMode>('graph');
  const [filteredEvents, setFilteredEvents] = useState<TelemetryEvent[]>([]);
  const [selectedEvent, setSelectedEvent] = useState<TelemetryEvent | null>(null);

  useEffect(() => {
    if (events.length > 0) {
      setFilteredEvents(events);
    }
  }, [events]);

  const agentEvents = events.filter(e => e.category === 'agent');
  const toolEvents = events.filter(e => e.category === 'tool');
  const llmEvents = events.filter(e => e.category === 'llm');

  return (
    <div className="min-h-screen bg-background">
      {/* Header */}
      <header className="border-b bg-card">
        <div className="container mx-auto px-4 py-4">
          <div className="flex items-center justify-between">
            <div>
              <h1 className="text-2xl font-bold">Session: {sessionId.slice(0, 8)}</h1>
              <div className="flex items-center gap-2 mt-1">
                <span className={`text-sm px-2 py-1 rounded-full ${
                  connected ? 'bg-green-100 text-green-800' : 'bg-red-100 text-red-800'
                }`}>
                  {connected ? '● Live' : '○ Offline'}
                </span>
                <span className="text-sm text-muted-foreground">
                  {events.length} events
                </span>
              </div>
            </div>

            {/* View mode selector */}
            <div className="flex items-center gap-2">
              <button
                onClick={() => setViewMode('graph')}
                className={`p-2 rounded-md ${
                  viewMode === 'graph' ? 'bg-accent' : 'hover:bg-muted'
                }`}
                title="Workflow Graph"
              >
                <Network className="h-5 w-5" />
              </button>
              <button
                onClick={() => setViewMode('timeline')}
                className={`p-2 rounded-md ${
                  viewMode === 'timeline' ? 'bg-accent' : 'hover:bg-muted'
                }`}
                title="Agent Timeline"
              >
                <Activity className="h-5 w-5" />
              </button>
              <button
                onClick={() => setViewMode('table')}
                className={`p-2 rounded-md ${
                  viewMode === 'table' ? 'bg-accent' : 'hover:bg-muted'
                }`}
                title="Event Table"
              >
                <List className="h-5 w-5" />
              </button>
            </div>
          </div>
        </div>
      </header>

      {/* Main content */}
      <main className="container mx-auto px-4 py-6">
        {/* Stats cards */}
        <div className="grid gap-4 md:grid-cols-4 mb-6">
          <div className="border rounded-lg p-4 bg-card">
            <div className="flex items-center gap-2">
              <Activity className="h-5 w-5 text-blue-600" />
              <span className="text-sm text-muted-foreground">Agents</span>
            </div>
            <div className="text-2xl font-bold mt-2">{agentEvents.length}</div>
          </div>
          
          <div className="border rounded-lg p-4 bg-card">
            <div className="flex items-center gap-2">
              <Zap className="h-5 w-5 text-yellow-600" />
              <span className="text-sm text-muted-foreground">Tool Calls</span>
            </div>
            <div className="text-2xl font-bold mt-2">{toolEvents.length}</div>
          </div>
          
          <div className="border rounded-lg p-4 bg-card">
            <div className="flex items-center gap-2">
              <Network className="h-5 w-5 text-green-600" />
              <span className="text-sm text-muted-foreground">LLM Calls</span>
            </div>
            <div className="text-2xl font-bold mt-2">{llmEvents.length}</div>
          </div>
          
          <div className="border rounded-lg p-4 bg-card">
            <div className="flex items-center gap-2">
              <List className="h-5 w-5 text-purple-600" />
              <span className="text-sm text-muted-foreground">Total Events</span>
            </div>
            <div className="text-2xl font-bold mt-2">{events.length}</div>
          </div>
        </div>

        {/* View mode content */}
        {viewMode === 'graph' && (
          <div className="border rounded-lg p-6 bg-card min-h-[500px]">
            <h2 className="text-xl font-semibold mb-4">Workflow Graph</h2>
            <div className="flex items-center justify-center h-[400px] text-muted-foreground">
              <p>Workflow graph visualization coming soon...</p>
              <p className="text-sm mt-2">
                This will show agent dependencies and execution flow with D3.js
              </p>
            </div>
          </div>
        )}

        {viewMode === 'timeline' && (
          <div className="border rounded-lg p-6 bg-card min-h-[500px]">
            <h2 className="text-xl font-semibold mb-4">Agent Timeline</h2>
            <div className="flex items-center justify-center h-[400px] text-muted-foreground">
              <p>Agent timeline visualization coming soon...</p>
              <p className="text-sm mt-2">
                This will show parallel agent execution over time
              </p>
            </div>
          </div>
        )}

        {viewMode === 'table' && (
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
                  {events.slice(0, 50).map((event, index) => (
                    <tr
                      key={event.eventId}
                      onClick={() => setSelectedEvent(event)}
                      className="border-b hover:bg-accent cursor-pointer"
                    >
                      <td className="p-3">{new Date(event.timestamp).toLocaleTimeString()}</td>
                      <td className="p-3 font-mono text-xs">{event.eventType}</td>
                      <td className="p-3">{event.category}</td>
                      <td className="p-3">{event.name}</td>
                      <td className="p-3">
                        <span className={`px-2 py-1 rounded text-xs ${
                          event.status === 'completed' ? 'bg-green-100 text-green-800' :
                          event.status === 'failed' ? 'bg-red-100 text-red-800' :
                          'bg-gray-100 text-gray-800'
                        }`}>
                          {event.status}
                        </span>
                      </td>
                      <td className="p-3">{event.agentId || '-'}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
              {events.length > 50 && (
                <p className="text-center text-sm text-muted-foreground mt-4">
                  Showing 50 of {events.length} events
                </p>
              )}
            </div>
          </div>
        )}

        {/* Selected event detail modal */}
        {selectedEvent && (
          <div className="fixed inset-0 bg-black/50 flex items-center justify-center p-4 z-50">
            <div className="bg-card border rounded-lg max-w-2xl w-full max-h-[80vh] overflow-auto">
              <div className="flex items-center justify-between p-4 border-b">
                <h3 className="text-xl font-semibold">Event Details</h3>
                <button
                  onClick={() => setSelectedEvent(null)}
                  className="p-2 hover:bg-muted rounded-md"
                >
                  ✕
                </button>
              </div>
              <div className="p-4">
                <pre className="text-sm bg-muted p-4 rounded-md overflow-auto">
                  {JSON.stringify(selectedEvent, null, 2)}
                </pre>
              </div>
            </div>
          </div>
        )}
      </main>
    </div>
  );
}
