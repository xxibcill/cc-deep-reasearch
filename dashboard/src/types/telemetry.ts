// Telemetry event types

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
  metadata: Record<string, any>;
}

export interface Session {
  sessionId: string;
  createdAt?: string;
  totalTimeMs?: number;
  totalSources?: number;
  status: string;
  active: boolean;
  eventCount?: number;
  lastEventAt?: string;
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
    parameters: Record<string, any>;
    prompt?: string;
  };
  response: {
    result?: any;
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
  metadata: Record<string, any>;
}

export type EventFilter = {
  phase: string[];
  agent: string[];
  status: string[];
  eventTypes: string[];
  timeRange: { start: number; end: number } | null;
};

export type ViewMode = 'graph' | 'timeline' | 'table';
