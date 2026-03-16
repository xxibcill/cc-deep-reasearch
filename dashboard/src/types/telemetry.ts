export type TelemetryMetadata = Record<string, unknown>;

export interface ApiTelemetryEvent {
  event_id: string;
  parent_event_id: string | null;
  sequence_number: number | null;
  timestamp: string;
  session_id: string;
  event_type: string;
  category: string;
  name: string;
  status: string;
  duration_ms: number | null;
  agent_id: string | null;
  metadata: TelemetryMetadata;
}

export interface TelemetryEvent {
  eventId: string;
  parentEventId: string | null;
  sequenceNumber: number;
  timestamp: string;
  sessionId: string;
  eventType: string;
  category: string;
  name: string;
  status: string;
  durationMs: number | null;
  agentId: string | null;
  metadata: TelemetryMetadata;
}

export type TelemetryStatus =
  | 'pending'
  | 'scheduled'
  | 'started'
  | 'running'
  | 'completed'
  | 'success'
  | 'failed'
  | 'error'
  | 'timeout'
  | 'selected'
  | 'fallback'
  | 'recorded'
  | 'unknown';

export interface ApiSession {
  session_id: string;
  created_at: string | null;
  total_time_ms: number | null;
  total_sources: number | null;
  status: string;
  active: boolean;
  event_count: number | null;
  last_event_at: string | null;
}

export interface Session {
  sessionId: string;
  createdAt: string | null;
  totalTimeMs: number | null;
  totalSources: number;
  status: string;
  active: boolean;
  eventCount: number | null;
  lastEventAt: string | null;
}

export interface ApiServerMessage {
  type: 'event' | 'history' | 'error' | 'pong';
  event?: ApiTelemetryEvent;
  events?: ApiTelemetryEvent[];
  error?: string;
}

export interface ServerMessage {
  type: 'event' | 'history' | 'error' | 'pong';
  event?: TelemetryEvent;
  events?: TelemetryEvent[];
  error?: string;
}

export interface ClientMessage {
  type: 'subscribe' | 'unsubscribe' | 'get_history' | 'ping';
  sessionId?: string;
  limit?: number;
}

export interface WorkflowNode {
  id: string;
  name: string;
  type: 'session' | 'phase' | 'agent';
  status: TelemetryStatus;
  startTime: string | null;
  endTime: string | null;
  agentId: string | null;
  phase: string | null;
  eventIds: string[];
  latestEventId: string | null;
}

export interface WorkflowEdge {
  id: string;
  source: string;
  target: string;
  phase: string | null;
  status: TelemetryStatus;
  eventId: string | null;
  label: string;
}

export interface AgentExecution {
  id: string;
  agentId: string;
  agentName: string;
  phase: string | null;
  startTime: number;
  endTime: number | null;
  status: TelemetryStatus;
  duration: number;
  eventIds: string[];
  markers: Array<{
    id: string;
    label: string;
    timestamp: number;
    type: 'tool' | 'llm' | 'phase';
    status: TelemetryStatus;
    eventId: string;
  }>;
}

export interface ToolExecution {
  id: string;
  toolName: string;
  agentId: string;
  phase: string | null;
  startedAt: number;
  startTime: number;
  endTime: number;
  duration: number;
  status: TelemetryStatus;
  eventId: string;
  parentEventId: string | null;
  summary: string;
  request: {
    parameters: Record<string, unknown>;
    prompt?: string;
  };
  response: {
    result?: unknown;
    error?: string;
    tokens?: number;
    latency?: number;
  };
}

export interface LLMReasoning {
  id: string;
  agentId: string;
  operation: string;
  model: string;
  provider: string;
  transport: string;
  status: TelemetryStatus;
  phase: string | null;
  startTime: number;
  endTime: number | null;
  promptTokens: number;
  completionTokens: number;
  totalTokens: number;
  latency: number;
  prompt: string;
  response: string;
  requestEventId: string | null;
  completionEventId: string | null;
  routeEventId: string | null;
  fallbackEventId: string | null;
  finishReason: string | null;
  metadata: TelemetryMetadata;
}

export interface TelemetryDerivedState {
  graph: {
    nodes: WorkflowNode[];
    edges: WorkflowEdge[];
  };
  timeline: AgentExecution[];
  toolExecutions: ToolExecution[];
  llmReasoning: LLMReasoning[];
  phases: string[];
  agents: string[];
  tools: string[];
  providers: string[];
  statuses: string[];
  eventTypes: string[];
}

export type EventFilter = {
  phase: string[];
  agent: string[];
  tool: string[];
  provider: string[];
  status: string[];
  eventTypes: string[];
  timeRange: { start: number; end: number } | null;
};

export type ViewMode = 'graph' | 'timeline' | 'table';

// Research Run API types

export type ResearchRunStatus = 'queued' | 'running' | 'completed' | 'failed';

export type ResearchOutputFormat = 'markdown' | 'json' | 'html';

export type ResearchArtifactKind = 'session' | 'report' | 'pdf';

export interface ResearchRunRequest {
  query: string;
  depth?: 'quick' | 'standard' | 'deep';
  min_sources?: number | null;
  output_format?: ResearchOutputFormat;
  search_providers?: string[] | null;
  cross_reference_enabled?: boolean | null;
  team_size?: number | null;
  parallel_mode?: boolean | null;
  num_researchers?: number | null;
  realtime_enabled?: boolean;
  pdf_enabled?: boolean;
}

export interface ResearchRunArtifact {
  kind: ResearchArtifactKind;
  path: string;
  format: string | null;
  media_type: string | null;
}

export interface ResearchRunResult {
  session_id: string;
  report_format: ResearchOutputFormat;
  report_path: string | null;
  artifacts: ResearchRunArtifact[];
}

export interface StartResearchRunResponse {
  run_id: string;
  status: ResearchRunStatus;
}

export interface ResearchRunStatusResponse {
  run_id: string;
  status: ResearchRunStatus;
  created_at: string;
  session_id?: string;
  started_at?: string;
  completed_at?: string;
  error?: string;
  result?: ResearchRunResult;
}

export interface SessionReportResponse {
  session_id: string;
  format: ResearchOutputFormat;
  media_type: string;
  content: string;
}
