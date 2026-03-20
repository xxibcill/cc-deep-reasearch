import dynamic from 'next/dynamic';
import { useDeferredValue, useMemo, useState } from 'react';
import { Activity, List, Network, Zap, FileText } from 'lucide-react';

import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Dialog } from '@/components/ui/dialog';
import { ScrollArea } from '@/components/ui/scroll-area';
import { Select } from '@/components/ui/select';
import { Tabs } from '@/components/ui/tabs';
import { DerivedOutputsPanel } from '@/components/derived-outputs-panel';
import useDashboardStore from '@/hooks/useDashboard';
import { filterEvents, deriveTelemetryState } from '@/lib/telemetry-transformers';
import {
  LLMReasoning,
  TelemetryEvent,
  ToolExecution,
  ViewMode,
  CriticalPath,
  StateChange,
  Decision,
  Degradation,
  Failure,
  ApiTelemetryEvent,
  SessionPromptMetadata,
} from '@/types/telemetry';

const WorkflowGraph = dynamic(
  () => import('@/components/workflow-graph').then((module) => module.WorkflowGraph),
  { ssr: false }
);
const AgentTimeline = dynamic(
  () => import('@/components/agent-timeline').then((module) => module.AgentTimeline),
  { ssr: false }
);
const ToolExecutionPanel = dynamic(
  () => import('@/components/tool-execution-panel').then((module) => module.ToolExecutionPanel),
  { ssr: false }
);
const LLMReasoningPanel = dynamic(
  () => import('@/components/llm-reasoning-panel').then((module) => module.LLMReasoningPanel),
  { ssr: false }
);

interface SessionDetailsProps {
  sessionId: string;
  connected: boolean;
  events: TelemetryEvent[];
  selectedEvent: TelemetryEvent | null;
  viewMode: ViewMode;
  onSelectEvent: (event: TelemetryEvent | null) => void;
  onViewModeChange: (mode: ViewMode) => void;
  // Derived outputs from API
  derivedOutputs?: {
    narrative: ApiTelemetryEvent[];
    criticalPath: CriticalPath;
    stateChanges: StateChange[];
    decisions: Decision[];
    degradations: Degradation[];
    failures: Failure[];
  };
  // Prompt configuration from session metadata
  promptMetadata?: SessionPromptMetadata;
}

function formatEventTime(timestamp: string): string {
  const date = new Date(timestamp);
  return Number.isNaN(date.getTime()) ? timestamp : date.toLocaleTimeString();
}

function StatusBadge({
  connected,
  eventCount,
}: {
  connected: boolean;
  eventCount: number;
}) {
  if (connected) {
    return <Badge variant="success">Live</Badge>;
  }

  if (eventCount > 0) {
    return <Badge variant="secondary">Snapshot</Badge>;
  }

  return <Badge variant="destructive">Offline</Badge>;
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
        <Button
          key={mode}
          onClick={() => onViewModeChange(mode)}
          variant={currentMode === mode ? 'default' : 'outline'}
          size="icon"
          title={title}
        >
          <Icon className="h-5 w-5" />
        </Button>
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
    <Card>
      <CardContent className="p-3">
        <div className="flex items-center gap-2">
          <Icon className={`h-4 w-4 ${accentClass}`} />
          <span className="text-xs text-muted-foreground">{label}</span>
        </div>
        <div className="mt-1 text-xl font-bold">{value}</div>
      </CardContent>
    </Card>
  );
}

function EventTable({
  events,
  onSelectEvent,
}: {
  events: TelemetryEvent[];
  onSelectEvent: (event: TelemetryEvent) => void;
}) {
  const [scrollTop, setScrollTop] = useState(0);
  const rowHeight = 56;
  const viewportHeight = 520;
  const overscan = 10;
  const totalHeight = events.length * rowHeight;
  const startIndex = Math.max(Math.floor(scrollTop / rowHeight) - overscan, 0);
  const visibleCount = Math.ceil(viewportHeight / rowHeight) + overscan * 2;
  const visibleEvents = events.slice(startIndex, startIndex + visibleCount);

  return (
    <Card>
      <CardHeader>
        <CardTitle>Event Table</CardTitle>
      </CardHeader>
      <CardContent>
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
        </table>
        <ScrollArea
          className="mt-2 h-[520px]"
          onScroll={(event) => setScrollTop(event.currentTarget.scrollTop)}
        >
          <div style={{ height: totalHeight, position: 'relative' }}>
            <table className="w-full text-sm">
              <tbody
                style={{
                  transform: `translateY(${startIndex * rowHeight}px)`,
                  position: 'absolute',
                  insetInline: 0,
                }}
              >
                {visibleEvents.map((event) => (
                  <tr
                    key={event.eventId}
                    onClick={() => onSelectEvent(event)}
                    className="cursor-pointer border-b hover:bg-accent"
                  >
                    <td className="p-3">{formatEventTime(event.timestamp)}</td>
                    <td className="p-3 font-mono text-xs">{event.eventType}</td>
                    <td className="p-3">{event.category}</td>
                    <td className="p-3">{event.name}</td>
                    <td className="p-3">
                      <span
                        className={`rounded px-2 py-1 text-xs ${
                          event.status === 'completed'
                            ? 'bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-100'
                            : event.status === 'failed'
                              ? 'bg-red-100 text-red-800 dark:bg-red-900 dark:text-red-100'
                              : 'bg-gray-100 text-gray-800 dark:bg-gray-800 dark:text-gray-200'
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
          </div>
        </ScrollArea>
      </CardContent>
    </Card>
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
    <Dialog open={Boolean(event)} onOpenChange={(open) => !open && onClose()} title="Event Details">
      <div className="p-4">
        <pre className="text-sm bg-muted p-4 rounded-md overflow-auto">
          {JSON.stringify(event, null, 2)}
        </pre>
      </div>
    </Dialog>
  );
}

function statusAccent(
  status: string
): 'success' | 'warning' | 'destructive' | 'secondary' {
  if (status === 'completed' || status === 'success') {
    return 'success';
  }
  if (status === 'failed' || status === 'error') {
    return 'destructive';
  }
  if (status === 'timeout' || status === 'fallback') {
    return 'warning';
  }
  return 'secondary';
}

function DetailInspector({
  event,
  toolExecution,
  reasoning,
}: {
  event: TelemetryEvent | null;
  toolExecution: ToolExecution | null;
  reasoning: LLMReasoning | null;
}) {
  return (
    <Card className="h-full">
      <CardHeader>
        <CardTitle>Inspection</CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        {toolExecution && (
          <div className="space-y-3 rounded-xl border p-4">
            <div className="flex items-center justify-between gap-3">
              <div className="font-semibold">{toolExecution.toolName}</div>
              <Badge variant={statusAccent(toolExecution.status)}>{toolExecution.status}</Badge>
            </div>
            <div className="text-xs text-muted-foreground">
              {toolExecution.agentId} • {toolExecution.duration} ms • {toolExecution.phase ?? 'No phase'}
            </div>
            <pre className="overflow-auto rounded-lg bg-slate-950 p-3 text-xs text-slate-100">
              {JSON.stringify(toolExecution.request.parameters, null, 2)}
            </pre>
          </div>
        )}
        {reasoning && (
          <div className="space-y-3 rounded-xl border p-4">
            <div className="flex items-center justify-between gap-3">
              <div className="font-semibold">{reasoning.operation}</div>
              <Badge variant={statusAccent(reasoning.status)}>{reasoning.status}</Badge>
            </div>
            <div className="text-xs text-muted-foreground">
              {reasoning.provider}/{reasoning.transport} • {reasoning.model} • {reasoning.totalTokens} tokens • {reasoning.latency} ms
            </div>
            <div className="grid gap-3 md:grid-cols-2">
              <pre className="overflow-auto rounded-lg bg-slate-950 p-3 text-xs text-slate-100">
                {reasoning.prompt || 'No prompt preview captured.'}
              </pre>
              <pre className="overflow-auto rounded-lg bg-slate-950 p-3 text-xs text-slate-100">
                {reasoning.response || 'No response preview captured.'}
              </pre>
            </div>
          </div>
        )}
        {event && (
          <div className="space-y-3 rounded-xl border p-4">
            <div className="flex items-center justify-between gap-3">
              <div className="font-semibold">{event.name}</div>
              <Badge variant={statusAccent(event.status)}>{event.status}</Badge>
            </div>
            <div className="text-xs text-muted-foreground">
              {event.eventType} • {event.category} • {event.agentId ?? 'system'}
            </div>
            <pre className="overflow-auto rounded-lg bg-slate-100 p-3 text-xs text-slate-800 dark:bg-slate-900 dark:text-slate-200">
              {JSON.stringify(event.metadata, null, 2)}
            </pre>
          </div>
        )}
        {!event && !toolExecution && !reasoning && (
          <div className="rounded-xl border border-dashed p-8 text-sm text-muted-foreground">
            Select a graph node, timeline span, event row, tool execution, or LLM interaction to inspect structured details.
          </div>
        )}
      </CardContent>
    </Card>
  );
}

function PromptConfigurationPanel({
  promptMetadata,
}: {
  promptMetadata?: SessionPromptMetadata;
}) {
  if (!promptMetadata) {
    return (
      <Card className="h-full">
        <CardContent className="flex items-center justify-center py-10 text-sm text-muted-foreground">
          Prompt configuration not available. This data is loaded from historical sessions.
        </CardContent>
      </Card>
    );
  }

  const agentLabels: Record<string, string> = {
    analyzer: 'Analyzer',
    deep_analyzer: 'Deep Analyzer',
    report_quality_evaluator: 'Report Quality Evaluator',
  };

  return (
    <Card className="h-full">
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <FileText className="h-5 w-5" />
          Prompt Configuration
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="flex items-center gap-2">
          <Badge variant={promptMetadata.overrides_applied ? 'default' : 'secondary'}>
            {promptMetadata.overrides_applied ? 'Custom Prompts Applied' : 'Default Prompts'}
          </Badge>
        </div>

        {promptMetadata.overrides_applied && (
          <div className="space-y-3">
            <h4 className="text-sm font-medium">Effective Overrides</h4>
            {Object.entries(promptMetadata.effective_overrides).map(([agentId, override]) => (
              <div key={agentId} className="rounded-xl border p-3 space-y-2">
                <div className="font-medium text-sm">
                  {agentLabels[agentId] || agentId}
                </div>
                {override.prompt_prefix && (
                  <div className="space-y-1">
                    <span className="text-xs text-muted-foreground">Prompt Prefix:</span>
                    <pre className="overflow-auto rounded-lg bg-slate-100 p-2 text-xs text-slate-800 dark:bg-slate-900 dark:text-slate-200 max-h-32">
                      {override.prompt_prefix}
                    </pre>
                  </div>
                )}
                {override.system_prompt && (
                  <div className="space-y-1">
                    <span className="text-xs text-muted-foreground">System Prompt Override:</span>
                    <pre className="overflow-auto rounded-lg bg-slate-100 p-2 text-xs text-slate-800 dark:bg-slate-900 dark:text-slate-200 max-h-32">
                      {override.system_prompt}
                    </pre>
                  </div>
                )}
              </div>
            ))}
          </div>
        )}

        {promptMetadata.default_prompts_used.length > 0 && (
          <div className="space-y-2">
            <h4 className="text-sm font-medium">Agents Using Default Prompts</h4>
            <div className="flex flex-wrap gap-2">
              {promptMetadata.default_prompts_used.map((agentId) => (
                <Badge key={agentId} variant="outline">
                  {agentLabels[agentId] || agentId}
                </Badge>
              ))}
            </div>
          </div>
        )}
      </CardContent>
    </Card>
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
  derivedOutputs,
  promptMetadata,
}: SessionDetailsProps) {
  const [detailTab, setDetailTab] = useState<'inspect' | 'tools' | 'llm' | 'derived' | 'prompts'>('inspect');
  const filters = useDashboardStore((state) => state.filters);
  const setFilters = useDashboardStore((state) => state.setFilters);
  const deferredEvents = useDeferredValue(events);
  const derived = useMemo(() => deriveTelemetryState(deferredEvents), [deferredEvents]);
  const [selectedToolId, setSelectedToolId] = useState<string | null>(null);
  const [selectedReasoningId, setSelectedReasoningId] = useState<string | null>(null);
  const eventIndex = useMemo(
    () => new Map(deferredEvents.map((event) => [event.eventId, event])),
    [deferredEvents]
  );
  const filteredEvents = useMemo(
    () => filterEvents(deferredEvents, filters),
    [deferredEvents, filters]
  );
  const filteredDerived = useMemo(() => deriveTelemetryState(filteredEvents), [filteredEvents]);
  const selectedTool = filteredDerived.toolExecutions.find((execution) => execution.id === selectedToolId) ?? null;
  const selectedReasoning =
    filteredDerived.llmReasoning.find((item) => item.id === selectedReasoningId) ?? null;
  const selectedEventId = selectedEvent?.eventId ?? null;
  const agentEvents = filteredEvents.filter((event) => event.category === 'agent');
  const toolEvents = filteredEvents.filter((event) => event.category === 'tool');
  const llmEvents = filteredEvents.filter((event) => event.category === 'llm');

  return (
    <div className="space-y-5">
      <Card className="overflow-hidden border-slate-200/80 shadow-sm">
        <CardHeader className="border-b bg-[linear-gradient(135deg,rgba(15,23,42,0.04),rgba(14,165,233,0.10))]">
          <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
            <div className="space-y-2">
              <div className="flex flex-wrap items-center gap-2">
                <CardTitle>Telemetry Explorer</CardTitle>
                <StatusBadge connected={connected} eventCount={deferredEvents.length} />
              </div>
              <p className="text-sm text-muted-foreground">
                Session <span className="font-mono text-xs text-foreground">{sessionId}</span> with{' '}
                {deferredEvents.length} buffered events ready for inspection.
              </p>
            </div>
            <div className="flex items-center gap-3">
              <span className="text-xs font-medium uppercase tracking-[0.2em] text-slate-500">
                View
              </span>
              <ViewModeSelector currentMode={viewMode} onViewModeChange={onViewModeChange} />
            </div>
          </div>
        </CardHeader>
        <CardContent className="space-y-5 p-5">
          <div className="grid grid-cols-2 gap-3 xl:grid-cols-4">
            <StatsCard
              icon={Activity}
              label="Agents"
              value={agentEvents.length}
              accentClass="text-sky-600"
            />
            <StatsCard
              icon={Zap}
              label="Tool Calls"
              value={toolEvents.length}
              accentClass="text-amber-600"
            />
            <StatsCard
              icon={Network}
              label="LLM Calls"
              value={llmEvents.length}
              accentClass="text-emerald-600"
            />
            <StatsCard
              icon={List}
              label="Total Events"
              value={filteredEvents.length}
              accentClass="text-slate-700"
            />
          </div>

          <div className="grid gap-5 xl:grid-cols-[minmax(0,1fr)_360px]">
            <div className="space-y-5">
              {viewMode === 'graph' && (
                <Card>
                  <CardHeader className="flex flex-row items-center justify-between">
                    <div>
                      <CardTitle>Workflow Graph</CardTitle>
                      <p className="text-sm text-muted-foreground">
                        D3-powered phase and agent flow with pan, zoom, and click-to-inspect.
                      </p>
                    </div>
                  </CardHeader>
                  <CardContent>
                    <WorkflowGraph
                      edges={filteredDerived.graph.edges}
                      eventIndex={eventIndex}
                      nodes={filteredDerived.graph.nodes}
                      onSelectEvent={onSelectEvent}
                      selectedEventId={selectedEventId}
                    />
                  </CardContent>
                </Card>
              )}

              {viewMode === 'timeline' && (
                <Card>
                  <CardHeader>
                    <CardTitle>Agent Timeline</CardTitle>
                  </CardHeader>
                  <CardContent>
                    <AgentTimeline
                      eventIndex={eventIndex}
                      lanes={filteredDerived.timeline}
                      onSelectEvent={onSelectEvent}
                    />
                  </CardContent>
                </Card>
              )}

              {viewMode === 'table' && (
                <EventTable events={filteredEvents} onSelectEvent={onSelectEvent} />
              )}
            </div>

            <div className="space-y-5">
              <Card>
                <CardHeader className="pb-3">
                  <CardTitle className="text-base">Filters</CardTitle>
                </CardHeader>
                <CardContent>
                  <div className="grid grid-cols-2 gap-2">
                    <Select
                      label="Agent"
                      value={filters.agent[0] ?? ''}
                      options={derived.agents}
                      onChange={(value) => setFilters({ agent: value ? [value] : [] })}
                    />
                    <Select
                      label="Phase"
                      value={filters.phase[0] ?? ''}
                      options={derived.phases}
                      onChange={(value) => setFilters({ phase: value ? [value] : [] })}
                    />
                    <Select
                      label="Tool"
                      value={filters.tool[0] ?? ''}
                      options={derived.tools}
                      onChange={(value) => setFilters({ tool: value ? [value] : [] })}
                    />
                    <Select
                      label="Provider"
                      value={filters.provider[0] ?? ''}
                      options={derived.providers}
                      onChange={(value) => setFilters({ provider: value ? [value] : [] })}
                    />
                    <Select
                      label="Status"
                      value={filters.status[0] ?? ''}
                      options={derived.statuses}
                      onChange={(value) => setFilters({ status: value ? [value] : [] })}
                    />
                    <Select
                      label="Event Type"
                      value={filters.eventTypes[0] ?? ''}
                      options={derived.eventTypes}
                      onChange={(value) => setFilters({ eventTypes: value ? [value] : [] })}
                    />
                  </div>
                </CardContent>
              </Card>

              <div className="space-y-3">
                <Tabs
                  tabs={[
                    { value: 'inspect', label: 'Inspect' },
                    { value: 'tools', label: 'Tools' },
                    { value: 'llm', label: 'LLM' },
                    { value: 'derived', label: 'Derived' },
                    { value: 'prompts', label: 'Prompts' },
                  ]}
                  value={detailTab}
                  onValueChange={(value) =>
                    setDetailTab(value as 'inspect' | 'tools' | 'llm' | 'derived' | 'prompts')
                  }
                />
                {detailTab === 'inspect' && (
                  <DetailInspector
                    event={selectedEvent}
                    reasoning={selectedReasoning}
                    toolExecution={selectedTool}
                  />
                )}
                {detailTab === 'tools' && (
                  <ToolExecutionPanel
                    executions={filteredDerived.toolExecutions}
                    onSelectExecution={(execution) => {
                      setSelectedToolId(execution.id);
                      onSelectEvent(eventIndex.get(execution.eventId) ?? null);
                    }}
                    selectedExecutionId={selectedToolId}
                  />
                )}
                {detailTab === 'llm' && (
                  <LLMReasoningPanel
                    items={filteredDerived.llmReasoning}
                    onSelectReasoning={(item) => {
                      setSelectedReasoningId(item.id);
                      const eventId =
                        item.completionEventId ?? item.requestEventId ?? item.routeEventId;
                      onSelectEvent(eventId ? eventIndex.get(eventId) ?? null : null);
                    }}
                    selectedReasoningId={selectedReasoningId}
                  />
                )}
                {detailTab === 'derived' && derivedOutputs && (
                  <DerivedOutputsPanel
                    narrative={derivedOutputs.narrative}
                    criticalPath={derivedOutputs.criticalPath}
                    stateChanges={derivedOutputs.stateChanges}
                    decisions={derivedOutputs.decisions}
                    degradations={derivedOutputs.degradations}
                    failures={derivedOutputs.failures}
                    onSelectEvent={(eventId) => {
                      const event = eventIndex.get(eventId);
                      if (event) {
                        onSelectEvent(event);
                        setDetailTab('inspect');
                      }
                    }}
                  />
                )}
                {detailTab === 'derived' && !derivedOutputs && (
                  <Card className="h-full">
                    <CardContent className="flex items-center justify-center py-10 text-sm text-muted-foreground">
                      Derived outputs not available. This data is loaded from historical sessions.
                    </CardContent>
                  </Card>
                )}
                {detailTab === 'prompts' && (
                  <PromptConfigurationPanel promptMetadata={promptMetadata} />
                )}
              </div>
            </div>
          </div>
        </CardContent>
      </Card>

      {selectedEvent && <EventDetailsModal event={selectedEvent} onClose={() => onSelectEvent(null)} />}
    </div>
  );
}
