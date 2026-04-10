import {
  ApiServerMessage,
  ApiSession,
  ApiTelemetryEvent,
  AgentExecution,
  EventFilter,
  InsightStatus,
  InsightCategory,
  LLMReasoning,
  OperatorInsight,
  ServerMessage,
  Session,
  TelemetryEvent,
  TelemetryDerivedState,
  TelemetryMetadata,
  TelemetryStatus,
  ToolExecution,
  WorkflowEdge,
  WorkflowNode,
} from '@/types/telemetry';

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null;
}

function asString(value: unknown, fallback = ''): string {
  return typeof value === 'string' ? value : fallback;
}

function asNullableString(value: unknown): string | null {
  return typeof value === 'string' ? value : null;
}

function asBoolean(value: unknown): boolean {
  return value === true;
}

function asNumberOrNull(value: unknown): number | null {
  if (typeof value === 'number' && Number.isFinite(value)) {
    return value;
  }
  if (typeof value === 'string' && value.trim().length > 0) {
    const parsed = Number(value);
    return Number.isFinite(parsed) ? parsed : null;
  }
  return null;
}

function asMetadata(value: unknown): TelemetryMetadata {
  return isRecord(value) ? value : {};
}

function isValidApiTelemetryEvent(value: unknown): value is ApiTelemetryEvent {
  if (!isRecord(value)) {
    return false;
  }
  return (
    typeof value.event_id === 'string' &&
    typeof value.timestamp === 'string' &&
    typeof value.session_id === 'string' &&
    typeof value.event_type === 'string' &&
    typeof value.category === 'string' &&
    typeof value.name === 'string' &&
    typeof value.status === 'string'
  );
}

function asApiTelemetryEvent(value: Record<string, unknown>): ApiTelemetryEvent | null {
  return isValidApiTelemetryEvent(value) ? value : null;
}

function asTimestamp(value: string): number {
  const parsed = Date.parse(value);
  return Number.isFinite(parsed) ? parsed : 0;
}

function isSortedBySequenceAndTimestamp(events: TelemetryEvent[]): boolean {
  for (let index = 1; index < events.length; index += 1) {
    const previous = events[index - 1];
    const current = events[index];
    if (previous.sequenceNumber > current.sequenceNumber) {
      return false;
    }
    if (
      previous.sequenceNumber === current.sequenceNumber
      && previous.timestamp.localeCompare(current.timestamp) > 0
    ) {
      return false;
    }
  }

  return true;
}

function getSortedEvents(events: TelemetryEvent[]): TelemetryEvent[] {
  if (events.length < 2 || isSortedBySequenceAndTimestamp(events)) {
    return events;
  }

  return [...events].sort((left, right) => {
    if (left.sequenceNumber !== right.sequenceNumber) {
      return left.sequenceNumber - right.sequenceNumber;
    }
    return left.timestamp.localeCompare(right.timestamp);
  });
}

export const STALL_THRESHOLD_MS = 120000;
export const SLOW_THRESHOLD_MS = 30000;

export function deriveOperatorInsights(
  events: TelemetryEvent[],
  derived: TelemetryDerivedState,
  hasReport: boolean = false
): OperatorInsight[] {
  const insights: OperatorInsight[] = [];
  const sortedEvents = getSortedEvents(events);

  const phases = derived.phases;
  const toolFailures = derived.toolExecutions.filter(
    (tool) => tool.status === 'failed' || tool.status === 'error'
  );
  const llmFailures = derived.llmReasoning.filter(
    (item) => item.status === 'failed' || item.status === 'error' || item.status === 'timeout'
  );
  const failedPhases = Array.from(
    new Set(
      toolFailures
        .map((tool) => tool.phase)
        .filter((phase): phase is string => Boolean(phase))
    )
  );
  const hasFailures = toolFailures.length > 0;
  const hasLLMErrors = llmFailures.length > 0;

  const activePhases = phases.filter(
    (phase) =>
      !sortedEvents.some(
        (event) =>
          event.category === 'phase'
          && event.name === phase
          && (event.status === 'completed' || event.status === 'failed')
      )
  );
  const completedPhases = phases.filter(
    (phase) =>
      sortedEvents.some(
        (event) =>
          event.category === 'phase' && event.name === phase && event.status === 'completed'
      )
  );

  const lastEvent = sortedEvents.at(-1);
  const now = Date.now();
  const lastEventTime = lastEvent ? asTimestamp(lastEvent.timestamp) : 0;
  const isStalled = lastEvent && lastEvent.status !== 'completed' && lastEvent.status !== 'failed' && (now - lastEventTime) > STALL_THRESHOLD_MS;
  const allPhasesCompleted =
    phases.length > 0
    && phases.every((phase) =>
      sortedEvents.some(
        (event) =>
          event.category === 'phase' && event.name === phase && event.status === 'completed'
      )
    );

  if (hasFailures || hasLLMErrors) {
    if (toolFailures.length > 0) {
      insights.push({
        id: 'insight-failures',
        status: 'error',
        category: 'failure',
        title:
          toolFailures.length === 1
            ? '1 tool failure detected'
            : `${toolFailures.length} tool failures detected`,
        description:
          failedPhases.length > 0
            ? `Failures occurred in phase${failedPhases.length === 1 ? '' : 's'}: ${failedPhases.join(', ')}.${hasReport ? '' : ' Report generation is blocked until the failing step is understood.'}`
            : `One or more tool executions failed.${hasReport ? '' : ' Report generation is blocked until the failure path is reviewed.'}`,
        actions: [
          { label: 'Inspect tool failures', actionType: 'inspect_tool_failures' },
          ...(!hasReport ? [{ label: 'Compare against a healthy run', actionType: 'compare_runs' as const }] : []),
        ],
        eventId: toolFailures[0].eventId,
        phase: failedPhases[0] ?? null,
      });
    }

    if (hasLLMErrors) {
      insights.push({
        id: 'insight-llm-failures',
        status: 'error',
        category: 'failure',
        title:
          llmFailures.length === 1 ? '1 LLM call failed' : `${llmFailures.length} LLM calls failed`,
        description: hasReport
          ? 'One or more LLM calls failed or timed out. Review the reasoning trace for the exact failure path.'
          : 'One or more LLM calls failed or timed out, which can block report generation or leave the run incomplete.',
        actions: [
          { label: 'Review LLM reasoning', actionType: 'review_llm_reasoning' },
        ],
        eventId: llmFailures[0]?.requestEventId ?? null,
      });
    }
  }

  if (!hasFailures && !hasLLMErrors && allPhasesCompleted) {
    if (hasReport) {
      insights.push({
        id: 'insight-complete',
        status: 'healthy',
        category: 'health',
        title: 'Run completed successfully',
        description: `All ${phases.length} phase${phases.length === 1 ? '' : 's'} completed. Report is available.`,
        actions: [
          { label: 'Open report', actionType: 'open_report' },
        ],
      });
    } else {
      insights.push({
        id: 'insight-complete-no-report',
        status: 'warning',
        category: 'blocker',
        title: 'Run complete, report not available',
        description:
          'All phases completed, but no report artifact is available yet. Review the phase flow before comparing against a previous successful run.',
        actions: [
          { label: 'View phases', actionType: 'view_phases' },
          { label: 'Compare against a successful run', actionType: 'compare_runs' },
        ],
      });
    }
  }

  if (!hasFailures && !hasLLMErrors && !allPhasesCompleted && activePhases.length > 0) {
    if (isStalled) {
      insights.push({
        id: 'insight-stalled',
        status: 'warning',
        category: 'performance',
        title: 'Run appears stalled',
        description: `No events received in the last ${Math.round(STALL_THRESHOLD_MS / 1000)} seconds.${activePhases.length > 0 ? ` Active phase: ${activePhases.join(', ')}.` : ''} The session may be hung or waiting on an external dependency.`,
        actions: [
          { label: 'View phases', actionType: 'view_phases' },
          { label: 'Review LLM reasoning', actionType: 'review_llm_reasoning' },
        ],
      });
    } else {
      insights.push({
        id: 'insight-active',
        status: 'healthy',
        category: 'health',
        title: 'Run is active and healthy',
        description: `${activePhases.join(' → ')} in progress. ${completedPhases.length} of ${phases.length || activePhases.length} tracked phase${(phases.length || activePhases.length) === 1 ? '' : 's'} finished.`,
        actions: [{ label: 'View phases', actionType: 'view_phases' }],
      });
    }
  }

  if (sortedEvents.length === 0) {
    insights.push({
      id: 'insight-empty',
      status: 'unknown',
      category: 'health',
      title: 'No events received',
      description: 'Waiting for telemetry events to arrive.',
      actions: [],
    });
  }

  const slowTools = derived.toolExecutions.filter((t) => (t.duration ?? 0) > SLOW_THRESHOLD_MS && t.status !== 'failed' && t.status !== 'error');
  if (slowTools.length > 0 && !hasFailures) {
    const slowestTool = slowTools.reduce((slowest, current) =>
      current.duration > slowest.duration ? current : slowest
    );
    insights.push({
      id: 'insight-slow',
      status: 'warning',
      category: 'performance',
      title: slowTools.length === 1 ? 'Slow tool detected' : `${slowTools.length} slow tools detected`,
      description: `${slowestTool.toolName} took ${Math.round(slowestTool.duration / 1000)}s.${slowestTool.phase ? ` Slowdown surfaced in ${slowestTool.phase}.` : ''}`,
      actions: [
        { label: 'Inspect slow tool activity', actionType: 'inspect_tool_failures' },
        { label: 'View decisions', actionType: 'view_decisions' },
      ],
      eventId: slowestTool.eventId,
      phase: slowestTool.phase ?? null,
    });
  }

  if (insights.length === 0) {
    insights.push({
      id: 'insight-unknown',
      status: 'unknown',
      category: 'health',
      title: 'Session state unclear',
      description: 'Unable to determine session status from available telemetry.',
      actions: [
        { label: 'Compare runs', actionType: 'compare_runs' },
      ],
    });
  }

  return insights;
}

function toStatus(value: string): TelemetryStatus {
  switch (value) {
    case 'pending':
    case 'scheduled':
    case 'started':
    case 'running':
    case 'completed':
    case 'success':
    case 'failed':
    case 'error':
    case 'timeout':
    case 'selected':
    case 'fallback':
    case 'recorded':
      return value;
    default:
      return 'unknown';
  }
}

function summarizeMetadata(metadata: TelemetryMetadata): string {
  if (typeof metadata.error === 'string' && metadata.error.length > 0) {
    return metadata.error;
  }
  if (typeof metadata.reason === 'string' && metadata.reason.length > 0) {
    return metadata.reason;
  }
  if (typeof metadata.result_count === 'number') {
    return `${metadata.result_count} result(s)`;
  }
  if (typeof metadata.prompt_preview === 'string' && metadata.prompt_preview.length > 0) {
    return metadata.prompt_preview;
  }
  return 'No structured summary available.';
}

function derivePhaseLookup(events: TelemetryEvent[]): Map<string, string | null> {
  const phaseByEvent = new Map<string, string | null>();
  let currentPhase: string | null = null;

  for (const event of events) {
    if (event.eventType === 'phase.started') {
      currentPhase = event.name;
    }
    phaseByEvent.set(event.eventId, currentPhase);
    if (
      (event.eventType === 'phase.completed' || event.eventType === 'phase.failed') &&
      currentPhase === event.name
    ) {
      currentPhase = null;
    }
  }

  return phaseByEvent;
}

function buildGraph(events: TelemetryEvent[], phaseLookup: Map<string, string | null>) {
  const nodes = new Map<string, WorkflowNode>();
  const edges = new Map<string, WorkflowEdge>();
  const phaseOrder: string[] = [];

  const sessionId = events[0]?.sessionId ?? 'session';
  nodes.set(`session:${sessionId}`, {
    id: `session:${sessionId}`,
    name: sessionId.slice(0, 8),
    type: 'session',
    status: 'running',
    startTime: events[0]?.timestamp ?? null,
    endTime: null,
    agentId: null,
    phase: null,
    eventIds: events.map((event) => event.eventId),
    latestEventId: events.at(-1)?.eventId ?? null,
  });

  for (const event of events) {
    if (event.category === 'phase') {
      const id = `phase:${event.name}`;
      const existing = nodes.get(id);
      if (!existing) {
        phaseOrder.push(event.name);
      }
      nodes.set(id, {
        id,
        name: event.name,
        type: 'phase',
        status: toStatus(event.status),
        startTime: existing?.startTime ?? event.timestamp,
        endTime:
          event.eventType === 'phase.completed' || event.eventType === 'phase.failed'
            ? event.timestamp
            : existing?.endTime ?? null,
        agentId: null,
        phase: event.name,
        eventIds: [...(existing?.eventIds ?? []), event.eventId],
        latestEventId: event.eventId,
      });
      edges.set(`session:${sessionId}->${id}`, {
        id: `session:${sessionId}->${id}`,
        source: `session:${sessionId}`,
        target: id,
        phase: event.name,
        status: toStatus(event.status),
        eventId: event.eventId,
        label: event.name,
      });
    }

    if (event.category === 'agent' && event.agentId) {
      const phase = phaseLookup.get(event.eventId) ?? null;
      const id = `agent:${event.agentId}`;
      const existing = nodes.get(id);
      nodes.set(id, {
        id,
        name: event.agentId,
        type: 'agent',
        status: toStatus(event.status),
        startTime: existing?.startTime ?? event.timestamp,
        endTime:
          event.status === 'completed' || event.status === 'failed' || event.status === 'timeout'
            ? event.timestamp
            : existing?.endTime ?? null,
        agentId: event.agentId,
        phase,
        eventIds: [...(existing?.eventIds ?? []), event.eventId],
        latestEventId: event.eventId,
      });
      const edgeSource = phase ? `phase:${phase}` : `session:${sessionId}`;
      edges.set(`${edgeSource}->${id}`, {
        id: `${edgeSource}->${id}`,
        source: edgeSource,
        target: id,
        phase,
        status: toStatus(event.status),
        eventId: event.eventId,
        label: phase ?? 'agent',
      });
    }
  }

  for (let index = 1; index < phaseOrder.length; index += 1) {
    const source = `phase:${phaseOrder[index - 1]}`;
    const target = `phase:${phaseOrder[index]}`;
    if (!edges.has(`${source}->${target}`)) {
      edges.set(`${source}->${target}`, {
        id: `${source}->${target}`,
        source,
        target,
        phase: phaseOrder[index],
        status: 'completed',
        eventId: nodes.get(target)?.latestEventId ?? null,
        label: 'next',
      });
    }
  }

  return {
    nodes: Array.from(nodes.values()),
    edges: Array.from(edges.values()),
  };
}

function buildTimeline(events: TelemetryEvent[], phaseLookup: Map<string, string | null>): AgentExecution[] {
  const spans = new Map<string, AgentExecution>();
  const markersByAgent = new Map<string, AgentExecution['markers']>();

  for (const event of events) {
    const agentId = event.agentId;
    const phase = phaseLookup.get(event.eventId) ?? null;
    if (!agentId) {
      continue;
    }

    if (event.category === 'agent') {
      const key = agentId;
      const existing = spans.get(key);
      const startTime = existing?.startTime ?? asTimestamp(event.timestamp);
      const endTime =
        event.status === 'completed' || event.status === 'failed' || event.status === 'timeout'
          ? asTimestamp(event.timestamp)
          : existing?.endTime ?? null;
      spans.set(key, {
        id: key,
        agentId,
        agentName: agentId,
        phase: phase ?? existing?.phase ?? null,
        startTime,
        endTime,
        status: toStatus(event.status),
        duration:
          event.durationMs ?? (endTime !== null ? Math.max(endTime - startTime, 0) : existing?.duration ?? 0),
        eventIds: [...(existing?.eventIds ?? []), event.eventId],
        markers: markersByAgent.get(key) ?? [],
      });
    }

    if (event.category === 'tool' || event.category === 'llm' || event.category === 'phase') {
      const key = agentId;
      const existingMarkers = markersByAgent.get(key) ?? [];
      const newMarker: AgentExecution['markers'][number] = {
        id: event.eventId,
        label: event.name,
        timestamp: asTimestamp(event.timestamp),
        type: event.category === 'tool' ? 'tool' : event.category === 'llm' ? 'llm' : 'phase',
        status: toStatus(event.status),
        eventId: event.eventId,
      };
      const updatedMarkers = [...existingMarkers, newMarker];
      markersByAgent.set(key, updatedMarkers);
      const span = spans.get(key);
      if (span) {
        span.markers = updatedMarkers;
      }
    }
  }

  return Array.from(spans.values())
    .map((span) => ({
      ...span,
      markers: span.markers.sort((left, right) => left.timestamp - right.timestamp),
      endTime: span.endTime,
      duration:
        span.duration || (span.endTime !== null ? Math.max(span.endTime - span.startTime, 0) : 0),
    }))
    .sort((left, right) => left.startTime - right.startTime);
}

function buildToolExecutions(
  events: TelemetryEvent[],
  phaseLookup: Map<string, string | null>
): ToolExecution[] {
  return events
    .filter((event) => event.category === 'tool')
    .map((event) => {
      const metadata = event.metadata;
      const status = toStatus(event.status);
      return {
        id: event.eventId,
        toolName: event.name,
        agentId: event.agentId ?? 'system',
        phase: phaseLookup.get(event.eventId) ?? null,
        startedAt: asTimestamp(event.timestamp) - (event.durationMs ?? 0),
        startTime: asTimestamp(event.timestamp) - (event.durationMs ?? 0),
        endTime: asTimestamp(event.timestamp),
        duration: event.durationMs ?? 0,
        status,
        eventId: event.eventId,
        parentEventId: event.parentEventId,
        summary: summarizeMetadata(metadata),
        request: {
          parameters: metadata,
          prompt: typeof metadata.prompt_preview === 'string' ? metadata.prompt_preview : undefined,
        },
        response: {
          result: metadata.result_count ?? metadata.finish_reason,
          error: typeof metadata.error === 'string' ? metadata.error : undefined,
          tokens: typeof metadata.total_tokens === 'number' ? metadata.total_tokens : undefined,
          latency: event.durationMs ?? undefined,
        },
      };
    })
    .sort((left, right) => right.endTime - left.endTime);
}

function buildLLMReasoning(
  events: TelemetryEvent[],
  phaseLookup: Map<string, string | null>
): LLMReasoning[] {
  const interactions = new Map<string, LLMReasoning>();
  const pendingByAgent = new Map<string, string[]>();

  for (const event of events) {
    if (event.eventType === 'llm.route_selected') {
      continue;
    }

    if (event.eventType === 'llm.route_request' && event.agentId) {
      const metadata = event.metadata;
      const key = `${event.agentId}:${event.name}:${event.eventId}`;
      const interaction: LLMReasoning = {
        id: key,
        agentId: event.agentId,
        operation: String(metadata.operation ?? event.name),
        model: String(metadata.model ?? 'unknown'),
        provider: String(metadata.provider ?? 'unknown'),
        transport: String(metadata.transport ?? 'unknown'),
        status: 'started',
        phase: phaseLookup.get(event.eventId) ?? null,
        startTime: asTimestamp(event.timestamp),
        endTime: null,
        promptTokens: 0,
        completionTokens: 0,
        totalTokens: 0,
        latency: 0,
        prompt: typeof metadata.prompt_preview === 'string' ? metadata.prompt_preview : '',
        response: '',
        requestEventId: event.eventId,
        completionEventId: null,
        routeEventId: null,
        fallbackEventId: null,
        finishReason: null,
        metadata,
      };
      interactions.set(key, interaction);
      const queue = pendingByAgent.get(event.agentId) ?? [];
      queue.push(key);
      pendingByAgent.set(event.agentId, queue);
      continue;
    }

    if (event.eventType === 'llm.route_fallback' && event.agentId) {
      const queue = pendingByAgent.get(event.agentId) ?? [];
      const active = queue.at(-1);
      if (!active) {
        continue;
      }
      const interaction = interactions.get(active);
      if (!interaction) {
        continue;
      }
      interaction.fallbackEventId = event.eventId;
      interaction.metadata = { ...interaction.metadata, fallback: event.metadata };
      continue;
    }

    if (event.eventType === 'llm.route_completion' && event.agentId) {
      const queue = pendingByAgent.get(event.agentId) ?? [];
      const key = queue.shift();
      if (!key) {
        continue;
      }
      pendingByAgent.set(event.agentId, queue);
      const interaction = interactions.get(key);
      if (!interaction) {
        continue;
      }
      const metadata = event.metadata;
      interaction.status = toStatus(event.status);
      interaction.endTime = asTimestamp(event.timestamp);
      interaction.latency = event.durationMs ?? 0;
      interaction.promptTokens = Number(metadata.prompt_tokens ?? 0);
      interaction.completionTokens = Number(metadata.completion_tokens ?? 0);
      interaction.totalTokens = Number(metadata.total_tokens ?? 0);
      interaction.response =
        typeof metadata.response_preview === 'string'
          ? metadata.response_preview
          : typeof metadata.finish_reason === 'string'
            ? `Finish reason: ${metadata.finish_reason}`
            : '';
      interaction.completionEventId = event.eventId;
      interaction.finishReason = typeof metadata.finish_reason === 'string' ? metadata.finish_reason : null;
      interaction.metadata = { ...interaction.metadata, ...metadata };
    }
  }

  return Array.from(interactions.values())
    .filter((interaction) => interaction.requestEventId !== null || interaction.routeEventId !== null)
    .sort((left, right) => right.startTime - left.startTime);
}

export function filterEvents(
  events: TelemetryEvent[],
  filters: EventFilter,
  phaseLookup: Map<string, string | null> = derivePhaseLookup(events)
): TelemetryEvent[] {
  return events.filter((event) => {
    const timestamp = asTimestamp(event.timestamp);
    const metadata = event.metadata;

    if (filters.phase.length > 0) {
      const phase =
        typeof metadata.phase === 'string'
          ? metadata.phase
          : event.category === 'phase'
            ? event.name
            : phaseLookup.get(event.eventId) ?? null;
      if (!phase || !filters.phase.includes(phase)) {
        return false;
      }
    }

    if (filters.agent.length > 0) {
      if (!event.agentId || !filters.agent.includes(event.agentId)) {
        return false;
      }
    }

    if (filters.tool.length > 0) {
      if (event.category !== 'tool' || !filters.tool.includes(event.name)) {
        return false;
      }
    }

    if (filters.provider.length > 0) {
      const provider = typeof metadata.provider === 'string' ? metadata.provider : null;
      if (!provider || !filters.provider.includes(provider)) {
        return false;
      }
    }

    if (filters.status.length > 0 && !filters.status.includes(event.status)) {
      return false;
    }

    if (filters.eventTypes.length > 0 && !filters.eventTypes.includes(event.eventType)) {
      return false;
    }

    if (filters.timeRange && (timestamp < filters.timeRange.start || timestamp > filters.timeRange.end)) {
      return false;
    }

    return true;
  });
}

export function deriveTelemetryState(events: TelemetryEvent[]): TelemetryDerivedState {
  const sortedEvents = getSortedEvents(events);
  const phaseLookup = derivePhaseLookup(sortedEvents);
  const eventIndex = new Map(sortedEvents.map((event) => [event.eventId, event]));
  const timeline = buildTimeline(sortedEvents, phaseLookup);
  const toolExecutions = buildToolExecutions(sortedEvents, phaseLookup);
  const llmReasoning = buildLLMReasoning(sortedEvents, phaseLookup);
  const categoryCounts = sortedEvents.reduce(
    (counts, event) => {
      counts.total += 1;
      if (event.category === 'agent') {
        counts.agent += 1;
      } else if (event.category === 'tool') {
        counts.tool += 1;
      } else if (event.category === 'llm') {
        counts.llm += 1;
      }
      return counts;
    },
    { total: 0, agent: 0, tool: 0, llm: 0 }
  );

  return {
    graph: buildGraph(sortedEvents, phaseLookup),
    timeline,
    toolExecutions,
    llmReasoning,
    phaseLookup,
    eventIndex,
    phases: Array.from(new Set(timeline.map((item) => item.phase).filter((value): value is string => Boolean(value)))),
    agents: Array.from(
      new Set(sortedEvents.map((event) => event.agentId).filter((value): value is string => Boolean(value)))
    ),
    tools: Array.from(
      new Set(toolExecutions.map((execution) => execution.toolName))
    ).sort((left, right) => left.localeCompare(right)),
    providers: Array.from(
      new Set(
        llmReasoning
          .map((interaction) => interaction.provider)
          .filter((value) => value && value !== 'unknown')
      )
    ).sort((left, right) => left.localeCompare(right)),
    statuses: Array.from(new Set(sortedEvents.map((event) => event.status))).sort((left, right) =>
      left.localeCompare(right)
    ),
    eventTypes: Array.from(new Set(sortedEvents.map((event) => event.eventType))).sort((left, right) =>
      left.localeCompare(right)
    ),
    categoryCounts,
  };
}

export function normalizeSession(session: ApiSession): Session {
  const sessionId = asString(session.session_id);
  const query = asNullableString(session.query);
  return {
    sessionId,
    label: asString(session.label, query ?? `Session ${sessionId.slice(0, 8)}`),
    createdAt: asNullableString(session.created_at),
    totalTimeMs: asNumberOrNull(session.total_time_ms),
    totalSources: asNumberOrNull(session.total_sources) ?? 0,
    status: asString(session.status, 'unknown'),
    active: asBoolean(session.active),
    eventCount: asNumberOrNull(session.event_count),
    lastEventAt: asNullableString(session.last_event_at),
    query,
    depth: asNullableString(session.depth),
    completedAt: asNullableString(session.completed_at),
    hasSessionPayload: asBoolean(session.has_session_payload),
    hasReport: asBoolean(session.has_report),
  };
}

export function normalizeEvent(event: ApiTelemetryEvent): TelemetryEvent {
  return {
    eventId: asString(event.event_id),
    parentEventId: asNullableString(event.parent_event_id),
    sequenceNumber: asNumberOrNull(event.sequence_number) ?? 0,
    timestamp: asString(event.timestamp),
    sessionId: asString(event.session_id),
    eventType: asString(event.event_type, 'unknown'),
    category: asString(event.category, 'unknown'),
    name: asString(event.name, 'unknown'),
    status: asString(event.status, 'unknown'),
    durationMs: asNumberOrNull(event.duration_ms),
    agentId: asNullableString(event.agent_id),
    metadata: asMetadata(event.metadata),
  };
}

export function normalizeServerMessage(message: ApiServerMessage | unknown): ServerMessage | null {
  if (!isRecord(message)) {
    return null;
  }

  const type = message.type;
  if (type !== 'event' && type !== 'history' && type !== 'error' && type !== 'pong') {
    return null;
  }

  return {
    type,
    event: isRecord(message.event)
      ? (() => {
          const normalized = asApiTelemetryEvent(message.event);
          return normalized ? normalizeEvent(normalized) : undefined;
        })()
      : undefined,
    events: Array.isArray(message.events)
      ? message.events
          .map((event) => {
            if (!isRecord(event)) return null;
            const normalized = asApiTelemetryEvent(event);
            return normalized ? normalizeEvent(normalized) : null;
          })
          .filter((event): event is TelemetryEvent => event !== null)
      : undefined,
    error: typeof message.error === 'string' ? message.error : undefined,
  };
}
