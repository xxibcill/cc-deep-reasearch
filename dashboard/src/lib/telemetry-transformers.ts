import {
  ApiServerMessage,
  ApiSession,
  ApiTelemetryEvent,
  AgentExecution,
  EventFilter,
  LLMReasoning,
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

function asApiTelemetryEvent(value: Record<string, unknown>): ApiTelemetryEvent {
  return value as unknown as ApiTelemetryEvent;
}

function asTimestamp(value: string): number {
  const parsed = Date.parse(value);
  return Number.isFinite(parsed) ? parsed : 0;
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
      const markers = markersByAgent.get(key) ?? [];
      markers.push({
        id: event.eventId,
        label: event.name,
        timestamp: asTimestamp(event.timestamp),
        type: event.category === 'tool' ? 'tool' : event.category === 'llm' ? 'llm' : 'phase',
        status: toStatus(event.status),
        eventId: event.eventId,
      });
      markersByAgent.set(key, markers);
      const span = spans.get(key);
      if (span) {
        span.markers = markers;
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

  const attachRouteSelection = (event: TelemetryEvent) => {
    if (!event.agentId) {
      return;
    }
    const metadata = event.metadata;
    const key = `selection:${event.agentId}:${metadata.operation ?? event.sequenceNumber}`;
    interactions.set(key, {
      id: key,
      agentId: event.agentId,
      operation: String(metadata.operation ?? event.name),
      model: String(metadata.model ?? 'unknown'),
      provider: String(metadata.provider ?? 'unknown'),
      transport: String(metadata.transport ?? 'unknown'),
      status: toStatus(event.status),
      phase: phaseLookup.get(event.eventId) ?? null,
      startTime: asTimestamp(event.timestamp),
      endTime: null,
      promptTokens: 0,
      completionTokens: 0,
      totalTokens: 0,
      latency: 0,
      prompt: typeof metadata.prompt_preview === 'string' ? metadata.prompt_preview : '',
      response: '',
      requestEventId: null,
      completionEventId: null,
      routeEventId: event.eventId,
      fallbackEventId: null,
      finishReason: null,
      metadata,
    });
  };

  for (const event of events) {
    if (event.eventType === 'llm.route_selected') {
      attachRouteSelection(event);
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

export function filterEvents(events: TelemetryEvent[], filters: EventFilter): TelemetryEvent[] {
  const phaseLookup = derivePhaseLookup(events);
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
  const sortedEvents = [...events].sort((left, right) => {
    if (left.sequenceNumber !== right.sequenceNumber) {
      return left.sequenceNumber - right.sequenceNumber;
    }
    return left.timestamp.localeCompare(right.timestamp);
  });
  const phaseLookup = derivePhaseLookup(sortedEvents);
  const timeline = buildTimeline(sortedEvents, phaseLookup);
  const toolExecutions = buildToolExecutions(sortedEvents, phaseLookup);
  const llmReasoning = buildLLMReasoning(sortedEvents, phaseLookup);

  return {
    graph: buildGraph(sortedEvents, phaseLookup),
    timeline,
    toolExecutions,
    llmReasoning,
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
  };
}

export function normalizeSession(session: ApiSession): Session {
  return {
    sessionId: asString(session.session_id),
    createdAt: asNullableString(session.created_at),
    totalTimeMs: asNumberOrNull(session.total_time_ms),
    totalSources: asNumberOrNull(session.total_sources) ?? 0,
    status: asString(session.status, 'unknown'),
    active: asBoolean(session.active),
    eventCount: asNumberOrNull(session.event_count),
    lastEventAt: asNullableString(session.last_event_at),
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
    event: isRecord(message.event) ? normalizeEvent(asApiTelemetryEvent(message.event)) : undefined,
    events: Array.isArray(message.events)
      ? message.events.filter(isRecord).map((event) => normalizeEvent(asApiTelemetryEvent(event)))
      : undefined,
    error: typeof message.error === 'string' ? message.error : undefined,
  };
}
