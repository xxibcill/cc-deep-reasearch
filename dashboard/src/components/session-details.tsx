import dynamic from 'next/dynamic';
import { useDeferredValue, useMemo, useState } from 'react';
import { Activity, ChevronDown, FileText, GitBranch, List, Network, SlidersHorizontal, Zap } from 'lucide-react';

import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import {
  Dialog,
  DialogBody,
  DialogClose,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
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
  DecisionGraph,
  StateChange,
  Decision,
  Degradation,
  Failure,
  LiveStreamStatus,
  ApiTelemetryEvent,
  SessionPromptMetadata,
  EventFilter,
} from '@/types/telemetry';

const WorkflowGraph = dynamic(
  () => import('@/components/workflow-graph').then((module) => module.WorkflowGraph),
  { ssr: false }
);
const DecisionGraphView = dynamic(
  () => import('@/components/decision-graph').then((module) => module.DecisionGraph),
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
  liveStreamStatus: LiveStreamStatus;
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
    decisionGraph: DecisionGraph;
  };
  // Prompt configuration from session metadata
  promptMetadata?: SessionPromptMetadata;
}

function formatEventTime(timestamp: string): string {
  const date = new Date(timestamp);
  return Number.isNaN(date.getTime()) ? timestamp : date.toLocaleTimeString();
}

function StatusBadge({
  liveStreamStatus,
  eventCount,
}: {
  liveStreamStatus: LiveStreamStatus;
  eventCount: number;
}) {
  if (liveStreamStatus.phase === 'live') {
    return <Badge variant="success">Live</Badge>;
  }

  if (liveStreamStatus.phase === 'historical') {
    return <Badge variant="secondary">Historical</Badge>;
  }

  if (liveStreamStatus.phase === 'reconnecting') {
    return <Badge variant="warning">Reconnecting</Badge>;
  }

  if (eventCount > 0) {
    return <Badge variant="outline">Snapshot</Badge>;
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
    { mode: 'decision_graph', title: 'Decision Graph', icon: GitBranch },
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
          aria-label={title}
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
  const sortedEvents = useMemo(() => {
    return [...events].sort((left, right) => {
      const timestampOrder = right.timestamp.localeCompare(left.timestamp);
      if (timestampOrder !== 0) {
        return timestampOrder;
      }

      return right.sequenceNumber - left.sequenceNumber;
    });
  }, [events]);
  const totalHeight = sortedEvents.length * rowHeight;
  const startIndex = Math.max(Math.floor(scrollTop / rowHeight) - overscan, 0);
  const visibleCount = Math.ceil(viewportHeight / rowHeight) + overscan * 2;
  const visibleEvents = sortedEvents.slice(startIndex, startIndex + visibleCount);
  const columnTemplate =
    'minmax(120px,0.95fr) minmax(160px,1.2fr) minmax(110px,0.8fr) minmax(220px,1.35fr) minmax(120px,0.8fr) minmax(110px,0.7fr)';

  return (
    <Card>
      <CardHeader>
        <CardTitle>Event Table</CardTitle>
      </CardHeader>
      <CardContent>
        <ScrollArea
          className="h-[520px]"
          onScroll={(event) => setScrollTop(event.currentTarget.scrollTop)}
        >
          <div className="min-w-[920px] text-sm">
            <div
              className="sticky top-0 z-10 grid border-b bg-card"
              style={{ gridTemplateColumns: columnTemplate }}
            >
              <div className="p-3 font-medium">Time</div>
              <div className="p-3 font-medium">Type</div>
              <div className="p-3 font-medium">Category</div>
              <div className="p-3 font-medium">Name</div>
              <div className="p-3 font-medium">Status</div>
              <div className="p-3 font-medium">Agent</div>
            </div>
            <div style={{ height: totalHeight, position: 'relative' }}>
              <div
                className="absolute inset-x-0"
                style={{ transform: `translateY(${startIndex * rowHeight}px)` }}
              >
                {visibleEvents.map((event) => (
                  <button
                    key={event.eventId}
                    onClick={() => onSelectEvent(event)}
                    className="grid w-full cursor-pointer border-b text-left hover:bg-accent"
                    style={{ gridTemplateColumns: columnTemplate, minHeight: rowHeight }}
                    type="button"
                  >
                    <div className="p-3">{formatEventTime(event.timestamp)}</div>
                    <div className="p-3 font-mono text-xs">{event.eventType}</div>
                    <div className="p-3">{event.category}</div>
                    <div className="p-3">{event.name}</div>
                    <div className="p-3">
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
                    </div>
                    <div className="p-3">{event.agentId || '-'}</div>
                  </button>
                ))}
              </div>
            </div>
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
    <Dialog open={Boolean(event)} onOpenChange={(open) => !open && onClose()}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Event Details</DialogTitle>
          <DialogClose />
        </DialogHeader>
        <DialogBody>
          <pre className="text-sm bg-muted p-4 rounded-md overflow-auto">
            {JSON.stringify(event, null, 2)}
          </pre>
        </DialogBody>
      </DialogContent>
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

type DetailTab = 'inspect' | 'tools' | 'llm' | 'derived' | 'prompts';
type DecisionGraphEdgeMode = 'all' | 'explicit' | 'inferred';

interface DecisionGraphFilters {
  decisionType: string;
  actor: string;
  severity: string;
  edgeMode: DecisionGraphEdgeMode;
}

const EMPTY_FILTERS: Partial<EventFilter> = {
  agent: [],
  phase: [],
  tool: [],
  provider: [],
  status: [],
  eventTypes: [],
};

const EMPTY_DECISION_GRAPH_FILTERS: DecisionGraphFilters = {
  decisionType: '',
  actor: '',
  severity: '',
  edgeMode: 'all',
};

const EMPTY_DECISION_GRAPH: DecisionGraph = {
  nodes: [],
  edges: [],
  summary: {
    node_count: 0,
    edge_count: 0,
    explicit_edge_count: 0,
    inferred_edge_count: 0,
  },
};

function getActiveFilters(filters: EventFilter): Array<{ label: string; value: string }> {
  return [
    { label: 'Agent', value: filters.agent[0] ?? '' },
    { label: 'Phase', value: filters.phase[0] ?? '' },
    { label: 'Tool', value: filters.tool[0] ?? '' },
    { label: 'Provider', value: filters.provider[0] ?? '' },
    { label: 'Status', value: filters.status[0] ?? '' },
    { label: 'Event Type', value: filters.eventTypes[0] ?? '' },
  ].filter((entry): entry is { label: string; value: string } => Boolean(entry.value));
}

function buildDecisionGraphOptions(graph?: DecisionGraph) {
  const decisionTypes = new Set<string>();
  const actors = new Set<string>();
  const severities = new Set<string>();

  for (const node of graph?.nodes ?? []) {
    const decisionType = typeof node.metadata.decision_type === 'string'
      ? node.metadata.decision_type
      : null;
    if (decisionType) {
      decisionTypes.add(decisionType);
    }
    if (node.actor_id) {
      actors.add(node.actor_id);
    }
    if (node.severity) {
      severities.add(node.severity);
    }
  }

  return {
    decisionTypes: [...decisionTypes].sort(),
    actors: [...actors].sort(),
    severities: [...severities].sort(),
  };
}

function filterDecisionGraph(
  graph: DecisionGraph | undefined,
  filters: DecisionGraphFilters
): DecisionGraph {
  if (!graph) {
    return EMPTY_DECISION_GRAPH;
  }

  const hasNodeFilters = Boolean(filters.decisionType || filters.actor || filters.severity);
  const matchesNode = (node: DecisionGraph['nodes'][number]) => {
    const decisionType =
      typeof node.metadata.decision_type === 'string' ? node.metadata.decision_type : '';
    if (filters.decisionType && decisionType !== filters.decisionType) {
      return false;
    }
    if (filters.actor && node.actor_id !== filters.actor) {
      return false;
    }
    if (filters.severity && node.severity !== filters.severity) {
      return false;
    }
    return true;
  };
  const matchesEdge = (inferred: boolean) => {
    if (filters.edgeMode === 'explicit') {
      return !inferred;
    }
    if (filters.edgeMode === 'inferred') {
      return inferred;
    }
    return true;
  };

  const baseNodeIds = new Set(
    (hasNodeFilters ? graph.nodes.filter(matchesNode) : graph.nodes).map((node) => node.id)
  );
  const eligibleEdges = graph.edges.filter((edge) => matchesEdge(edge.inferred));
  const expandedNodeIds = new Set(baseNodeIds);

  for (const edge of eligibleEdges) {
    if (
      baseNodeIds.size === 0
      || baseNodeIds.has(edge.source)
      || baseNodeIds.has(edge.target)
    ) {
      expandedNodeIds.add(edge.source);
      expandedNodeIds.add(edge.target);
    }
  }

  const nodes = graph.nodes.filter((node) => expandedNodeIds.has(node.id));
  const nodeIds = new Set(nodes.map((node) => node.id));
  const edges = eligibleEdges.filter(
    (edge) => nodeIds.has(edge.source) && nodeIds.has(edge.target)
  );

  return {
    nodes,
    edges,
    summary: {
      node_count: nodes.length,
      edge_count: edges.length,
      explicit_edge_count: edges.filter((edge) => !edge.inferred).length,
      inferred_edge_count: edges.filter((edge) => edge.inferred).length,
    },
  };
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
  liveStreamStatus,
  events,
  selectedEvent,
  viewMode,
  onSelectEvent,
  onViewModeChange,
  derivedOutputs,
  promptMetadata,
}: SessionDetailsProps) {
  const [detailTab, setDetailTab] = useState<DetailTab>('inspect');
  const [decisionGraphFilters, setDecisionGraphFilters] = useState<DecisionGraphFilters>(
    EMPTY_DECISION_GRAPH_FILTERS
  );
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
  const decisionGraphOptions = useMemo(
    () => buildDecisionGraphOptions(derivedOutputs?.decisionGraph),
    [derivedOutputs?.decisionGraph]
  );
  const filteredDecisionGraph = useMemo(
    () => filterDecisionGraph(derivedOutputs?.decisionGraph, decisionGraphFilters),
    [decisionGraphFilters, derivedOutputs?.decisionGraph]
  );
  const agentEvents = filteredEvents.filter((event) => event.category === 'agent');
  const toolEvents = filteredEvents.filter((event) => event.category === 'tool');
  const llmEvents = filteredEvents.filter((event) => event.category === 'llm');
  const activeFilters = useMemo(() => getActiveFilters(filters), [filters]);
  const [filtersOpen, setFiltersOpen] = useState(() => activeFilters.length > 0);
  const detailTabs = [
    { value: 'inspect', label: 'Inspect', icon: List, hideLabel: true },
    { value: 'tools', label: 'Tools', icon: Zap, hideLabel: true },
    { value: 'llm', label: 'LLM', icon: Network, hideLabel: true },
    { value: 'derived', label: 'Derived', icon: Activity, hideLabel: true },
    { value: 'prompts', label: 'Prompts', icon: FileText, hideLabel: true },
  ];

  return (
    <div className="space-y-5">
      <Card className="overflow-hidden border-slate-200/80 shadow-sm">
        <CardHeader className="border-b bg-[linear-gradient(135deg,rgba(15,23,42,0.04),rgba(14,165,233,0.10))]">
          <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
            <div className="space-y-2">
              <div className="flex flex-wrap items-center gap-2">
                <CardTitle>Telemetry Explorer</CardTitle>
                <StatusBadge liveStreamStatus={liveStreamStatus} eventCount={deferredEvents.length} />
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

              {viewMode === 'decision_graph' && (
                <Card>
                  <CardHeader className="space-y-4">
                    <div>
                      <CardTitle>Decision Graph</CardTitle>
                      <p className="text-sm text-muted-foreground">
                        Causal decision links derived from explicit telemetry, with inferred edges shown separately.
                      </p>
                    </div>
                    <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-4">
                      <Select
                        label="Decision Type"
                        value={decisionGraphFilters.decisionType}
                        options={decisionGraphOptions.decisionTypes}
                        onChange={(value) =>
                          setDecisionGraphFilters((current) => ({
                            ...current,
                            decisionType: value,
                          }))
                        }
                      />
                      <Select
                        label="Actor"
                        value={decisionGraphFilters.actor}
                        options={decisionGraphOptions.actors}
                        onChange={(value) =>
                          setDecisionGraphFilters((current) => ({
                            ...current,
                            actor: value,
                          }))
                        }
                      />
                      <Select
                        label="Severity"
                        value={decisionGraphFilters.severity}
                        options={decisionGraphOptions.severities}
                        onChange={(value) =>
                          setDecisionGraphFilters((current) => ({
                            ...current,
                            severity: value,
                          }))
                        }
                      />
                      <Select
                        label="Links"
                        value={
                          decisionGraphFilters.edgeMode === 'all'
                            ? ''
                            : decisionGraphFilters.edgeMode
                        }
                        options={['explicit', 'inferred']}
                        onChange={(value) =>
                          setDecisionGraphFilters((current) => ({
                            ...current,
                            edgeMode: value ? (value as DecisionGraphEdgeMode) : 'all',
                          }))
                        }
                      />
                    </div>
                  </CardHeader>
                  <CardContent>
                    <DecisionGraphView
                      eventIndex={eventIndex}
                      graph={filteredDecisionGraph}
                      onSelectEvent={(event) => {
                        onSelectEvent(event);
                        setDetailTab('inspect');
                      }}
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
              <div className="space-y-3">
                <Tabs
                  tabs={detailTabs}
                  value={detailTab}
                  onValueChange={(value) => setDetailTab(value as DetailTab)}
                  variant="prominent"
                  stretch
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
                    hasDecisionGraph={derivedOutputs.decisionGraph.nodes.length > 0}
                    onOpenDecisionGraph={() => onViewModeChange('decision_graph')}
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

              <Card className="border-dashed border-slate-200/80 bg-slate-50/70 shadow-none">
                <CardHeader className="gap-3 pb-3">
                  <div className="flex items-start justify-between gap-3">
                    <div className="space-y-1">
                      <div className="flex items-center gap-2 text-[11px] font-semibold uppercase tracking-[0.24em] text-slate-500">
                        <SlidersHorizontal className="h-3.5 w-3.5" />
                        Refine Results
                      </div>
                      <CardTitle className="text-sm font-semibold">Filters</CardTitle>
                      <p className="text-xs text-muted-foreground">
                        {activeFilters.length === 0
                          ? 'Showing all telemetry data. Open filters only when you need to narrow the view.'
                          : `${activeFilters.length} active filter${activeFilters.length === 1 ? '' : 's'} narrowing the workspace.`}
                      </p>
                    </div>
                    <div className="flex items-center gap-2">
                      {activeFilters.length > 0 && (
                        <Button
                          className="text-slate-600"
                          onClick={() => {
                            setFilters(EMPTY_FILTERS);
                            setFiltersOpen(false);
                          }}
                          size="sm"
                          type="button"
                          variant="ghost"
                        >
                          Clear
                        </Button>
                      )}
                      <Button
                        className="gap-2 text-slate-700"
                        onClick={() => setFiltersOpen((open) => !open)}
                        size="sm"
                        type="button"
                        variant="outline"
                      >
                        {filtersOpen ? 'Hide' : 'Show'}
                        <ChevronDown
                          className={`h-4 w-4 transition-transform ${filtersOpen ? 'rotate-180' : ''}`}
                        />
                      </Button>
                    </div>
                  </div>
                  {activeFilters.length > 0 && (
                    <div className="flex flex-wrap gap-2">
                      {activeFilters.map((filter) => (
                        <Badge key={filter.label} variant="outline" className="bg-white/80 text-[11px]">
                          {filter.label}: {filter.value}
                        </Badge>
                      ))}
                    </div>
                  )}
                </CardHeader>
                {filtersOpen && (
                  <CardContent className="pt-0">
                    <div className="grid gap-3 sm:grid-cols-2">
                      <Select
                        label="Agent"
                        value={filters.agent[0] ?? ''}
                        options={derived.agents}
                        onChange={(value) => setFilters({ agent: value ? [value] : [] })}
                        className="h-9 bg-white/90"
                        labelClassName="min-w-0 gap-1 text-[11px] tracking-[0.18em] text-slate-500"
                      />
                      <Select
                        label="Phase"
                        value={filters.phase[0] ?? ''}
                        options={derived.phases}
                        onChange={(value) => setFilters({ phase: value ? [value] : [] })}
                        className="h-9 bg-white/90"
                        labelClassName="min-w-0 gap-1 text-[11px] tracking-[0.18em] text-slate-500"
                      />
                      <Select
                        label="Tool"
                        value={filters.tool[0] ?? ''}
                        options={derived.tools}
                        onChange={(value) => setFilters({ tool: value ? [value] : [] })}
                        className="h-9 bg-white/90"
                        labelClassName="min-w-0 gap-1 text-[11px] tracking-[0.18em] text-slate-500"
                      />
                      <Select
                        label="Provider"
                        value={filters.provider[0] ?? ''}
                        options={derived.providers}
                        onChange={(value) => setFilters({ provider: value ? [value] : [] })}
                        className="h-9 bg-white/90"
                        labelClassName="min-w-0 gap-1 text-[11px] tracking-[0.18em] text-slate-500"
                      />
                      <Select
                        label="Status"
                        value={filters.status[0] ?? ''}
                        options={derived.statuses}
                        onChange={(value) => setFilters({ status: value ? [value] : [] })}
                        className="h-9 bg-white/90"
                        labelClassName="min-w-0 gap-1 text-[11px] tracking-[0.18em] text-slate-500"
                      />
                      <Select
                        label="Event Type"
                        value={filters.eventTypes[0] ?? ''}
                        options={derived.eventTypes}
                        onChange={(value) => setFilters({ eventTypes: value ? [value] : [] })}
                        className="h-9 bg-white/90"
                        labelClassName="min-w-0 gap-1 text-[11px] tracking-[0.18em] text-slate-500"
                      />
                    </div>
                  </CardContent>
                )}
              </Card>
            </div>
          </div>
        </CardContent>
      </Card>

      {selectedEvent && <EventDetailsModal event={selectedEvent} onClose={() => onSelectEvent(null)} />}
    </div>
  );
}
