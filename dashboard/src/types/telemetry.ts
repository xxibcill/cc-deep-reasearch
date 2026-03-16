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
  type: 'agent' | 'phase';
  status: 'pending' | 'running' | 'completed' | 'failed' | 'timeout';
  startTime: string;
  endTime: string | null;
  agentId: string;
}

export interface WorkflowEdge {
  source: string;
  target: string;
  phase: string;
}

export interface AgentExecution {
  id: string;
  agentId: string;
  agentName: string;
  startTime: number;
  endTime: number;
  status: string;
  duration: number;
}

export interface ToolExecution {
  id: string;
  toolName: string;
  agentId: string;
  startTime: number;
  endTime: number;
  duration: number;
  status: 'success' | 'failed';
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
  startTime: number;
  endTime: number;
  promptTokens: number;
  completionTokens: number;
  totalTokens: number;
  latency: number;
  prompt: string;
  response: string;
  metadata: TelemetryMetadata;
}

export type EventFilter = {
  phase: string[];
  agent: string[];
  status: string[];
  eventTypes: string[];
  timeRange: { start: number; end: number } | null;
};

export type ViewMode = 'graph' | 'timeline' | 'table';
