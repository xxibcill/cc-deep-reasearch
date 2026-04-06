import dynamic from 'next/dynamic';
import { useDeferredValue, useEffect, useMemo, useState } from 'react';
import { useRouter } from 'next/navigation';
import { Activity, FileText, List, Network, Zap } from 'lucide-react';

import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { ErrorBoundary } from '@/components/error-boundary';
import { Select } from '@/components/ui/select';
import { Tabs } from '@/components/ui/tabs';
import { DerivedOutputsPanel } from '@/components/derived-outputs-panel';
import { EventDetailsModal } from '@/components/telemetry/event-details-modal';
import { EventTable } from '@/components/telemetry/event-table';
import { DetailInspector } from '@/components/telemetry/detail-inspector';
import { FilterPanel, getActiveFilters } from '@/components/telemetry/filter-panel';
import { OperatorInsightsPanel } from '@/components/telemetry/operator-insights-panel';
import { PromptConfigurationPanel } from '@/components/telemetry/prompt-config-panel';
import { StatsCard } from '@/components/telemetry/stats-card';
import { StatusBadge, ViewModeSelector } from '@/components/telemetry/telemetry-header';
import useDashboardStore from '@/hooks/useDashboard';
import { areEventFiltersEqual, sanitizeTelemetryFilters } from '@/lib/saved-views';
import { filterEvents, deriveTelemetryState, deriveOperatorInsights } from '@/lib/telemetry-transformers';
import type {
  TelemetryEvent,
  ViewMode,
  LiveStreamStatus,
  CriticalPath,
  DecisionGraph,
  StateChange,
  Decision,
  Degradation,
  Failure,
  ApiTelemetryEvent,
  SessionPromptMetadata,
  OperatorInsightAction,
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
  derivedOutputs?: {
    narrative: ApiTelemetryEvent[];
    criticalPath: CriticalPath;
    stateChanges: StateChange[];
    decisions: Decision[];
    degradations: Degradation[];
    failures: Failure[];
    decisionGraph: DecisionGraph;
  };
  promptMetadata?: SessionPromptMetadata;
}

type DetailTab = 'inspect' | 'tools' | 'llm' | 'derived' | 'prompts';
type DecisionGraphEdgeMode = 'all' | 'explicit' | 'inferred';

interface DecisionGraphFilters {
  decisionType: string;
  actor: string;
  severity: string;
  edgeMode: DecisionGraphEdgeMode;
}

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

function getActiveDecisionGraphFilters(
  filters: DecisionGraphFilters
): Array<{ label: string; value: string }> {
  return [
    { label: 'Decision Type', value: filters.decisionType },
    { label: 'Actor', value: filters.actor },
    { label: 'Severity', value: filters.severity },
    {
      label: 'Links',
      value: filters.edgeMode === 'all' ? '' : filters.edgeMode,
    },
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
  const router = useRouter();
  const [detailTab, setDetailTab] = useState<DetailTab>('inspect');
  const [decisionGraphFilters, setDecisionGraphFilters] = useState<DecisionGraphFilters>(
    EMPTY_DECISION_GRAPH_FILTERS
  );
  const storedFilters = useDashboardStore((state) => state.filters);
  const setFilters = useDashboardStore((state) => state.setFilters);
  const deferredEvents = useDeferredValue(events);
  const derived = useMemo(() => deriveTelemetryState(deferredEvents), [deferredEvents]);
  const filters = useMemo(
    () => sanitizeTelemetryFilters(storedFilters, derived),
    [derived, storedFilters]
  );
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
  const { agentEvents, toolEvents, llmEvents } = useMemo(() => ({
    agentEvents: filteredEvents.filter((event) => event.category === 'agent'),
    toolEvents: filteredEvents.filter((event) => event.category === 'tool'),
    llmEvents: filteredEvents.filter((event) => event.category === 'llm'),
  }), [filteredEvents]);
  const activeFilters = useMemo(() => getActiveFilters(filters), [filters]);
  const activeDecisionGraphFilters = useMemo(
    () => getActiveDecisionGraphFilters(decisionGraphFilters),
    [decisionGraphFilters]
  );
  const [filtersOpen, setFiltersOpen] = useState(() => activeFilters.length > 0);
  const hasDecisionGraph = Boolean(derivedOutputs?.decisionGraph.nodes.length);
  const insights = useMemo(
    () => deriveOperatorInsights(deferredEvents, derived, Boolean(derivedOutputs?.narrative?.length)),
    [deferredEvents, derived, derivedOutputs]
  );

  useEffect(() => {
    if (areEventFiltersEqual(storedFilters, filters)) {
      return;
    }
    setFilters(filters);
  }, [filters, setFilters, storedFilters]);

  const focusInsightEvent = (eventId?: string | null) => {
    if (!eventId) {
      return;
    }
    const event = eventIndex.get(eventId);
    if (event) {
      onSelectEvent(event);
    }
  };
  const handleInsightAction = (action: OperatorInsightAction) => {
    focusInsightEvent(action.eventId);

    switch (action.actionType) {
      case 'inspect_tool_failures':
        setDetailTab('tools');
        break;
      case 'review_llm_reasoning':
        setDetailTab('llm');
        break;
      case 'open_report':
        router.push(`/session/${sessionId}/report`);
        break;
      case 'view_phases':
        onViewModeChange('graph');
        break;
      case 'view_decisions':
        if (hasDecisionGraph) {
          onViewModeChange('decision_graph');
        } else {
          setDetailTab('derived');
        }
        break;
      case 'compare_runs':
        router.push('/compare');
        break;
    }
  };
  const detailTabs = [
    { value: 'inspect', label: 'Inspect', icon: List },
    { value: 'tools', label: 'Tools', icon: Zap },
    { value: 'llm', label: 'LLM', icon: Network },
    { value: 'derived', label: 'Derived', icon: Activity },
    { value: 'prompts', label: 'Prompts', icon: FileText },
  ];

  return (
    <div className="space-y-5">
      <Card className="overflow-hidden">
        <CardHeader className="border-b border-border/60 bg-surface-raised/45">
          <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
            <div className="space-y-2">
              <div className="flex flex-wrap items-center gap-2">
                <CardTitle>Telemetry Explorer</CardTitle>
                <StatusBadge liveStreamStatus={liveStreamStatus} eventCount={deferredEvents.length} />
              </div>
              <p className="text-sm text-muted-foreground">
                <span className="font-mono text-xs text-foreground">{sessionId}</span> —{' '}
                {deferredEvents.length} events buffered.
                {liveStreamStatus.phase === 'live'
                  ? ' Streaming live updates.'
                  : liveStreamStatus.phase === 'reconnecting'
                    ? ' Showing buffered events while the live stream reconnects.'
                    : liveStreamStatus.phase === 'historical'
                      ? ' Viewing stored session history only.'
                      : liveStreamStatus.phase === 'failed'
                        ? ' Live stream unavailable; using the latest buffered snapshot.'
                        : ''}
              </p>
            </div>
            <div className="flex items-center gap-3">
              <span className="text-xs font-medium uppercase tracking-[0.2em] text-muted-foreground">
                View
              </span>
              <ViewModeSelector currentMode={viewMode} onViewModeChange={onViewModeChange} />
            </div>
          </div>
        </CardHeader>
        <CardContent className="space-y-5 p-5">
          <OperatorInsightsPanel insights={insights} onAction={handleInsightAction} />
          <div className="grid grid-cols-2 gap-3 xl:grid-cols-4">
            <StatsCard
              icon={Activity}
              label="Agents"
              value={agentEvents.length}
              accentClass="text-primary"
            />
            <StatsCard
              icon={Zap}
              label="Tool Calls"
              value={toolEvents.length}
              accentClass="text-warning"
            />
            <StatsCard
              icon={Network}
              label="LLM Calls"
              value={llmEvents.length}
              accentClass="text-success"
            />
            <StatsCard
              icon={List}
              label="Total Events"
              value={filteredEvents.length}
              accentClass="text-foreground"
              prominence="primary"
            />
          </div>

          <div className="grid gap-5 xl:grid-cols-[minmax(0,1fr)_360px]">
            <div className="space-y-5">
              {viewMode === 'graph' && (
                <ErrorBoundary>
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
                </ErrorBoundary>
              )}

              {viewMode === 'decision_graph' && (
                <ErrorBoundary>
                <Card>
                  <CardHeader className="space-y-4">
                    <div className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
                      <div>
                        <CardTitle>Decision Graph</CardTitle>
                        <p className="text-sm text-muted-foreground">
                          Causal decision links derived from explicit telemetry, with inferred edges shown separately.
                        </p>
                      </div>
                      {activeDecisionGraphFilters.length > 0 ? (
                        <Button
                          onClick={() => setDecisionGraphFilters(EMPTY_DECISION_GRAPH_FILTERS)}
                          size="sm"
                          type="button"
                          variant="ghost"
                        >
                          Clear filters
                        </Button>
                      ) : null}
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
                    {activeDecisionGraphFilters.length > 0 ? (
                      <div className="flex flex-wrap gap-2">
                        {activeDecisionGraphFilters.map((filter) => (
                          <Badge key={filter.label} variant="outline">
                            {filter.label}: {filter.value}
                          </Badge>
                        ))}
                      </div>
                    ) : null}
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
                </ErrorBoundary>
              )}

              {viewMode === 'timeline' && (
                <ErrorBoundary>
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
                </ErrorBoundary>
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
                    hasDecisionGraph={hasDecisionGraph}
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
                    <CardContent className="py-10">
                      <Alert variant="default">
                        <AlertTitle>Derived outputs unavailable</AlertTitle>
                        <AlertDescription>
                          This data is loaded from historical sessions and is not available for the
                          current view.
                        </AlertDescription>
                      </Alert>
                    </CardContent>
                  </Card>
                )}
                {detailTab === 'prompts' && (
                  <PromptConfigurationPanel promptMetadata={promptMetadata} />
                )}
              </div>

              <FilterPanel
                filters={filters}
                derived={derived}
                filtersOpen={filtersOpen}
                onFiltersOpenChange={setFiltersOpen}
                onFiltersChange={setFilters}
              />
            </div>
          </div>
        </CardContent>
      </Card>

      {selectedEvent && <EventDetailsModal event={selectedEvent} onClose={() => onSelectEvent(null)} />}
    </div>
  );
}
