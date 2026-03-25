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
  label?: string | null;
  created_at: string | null;
  total_time_ms: number | null;
  total_sources: number | null;
  status: string;
  active: boolean;
  event_count: number | null;
  last_event_at: string | null;
  query: string | null;
  depth: string | null;
  completed_at: string | null;
  has_session_payload: boolean;
  has_report: boolean;
  archived?: boolean;
}

export type SessionSortBy = 'created_at' | 'last_event_at' | 'total_time_ms';
export type SortOrder = 'asc' | 'desc';

export interface SessionListParams {
  active_only?: boolean;
  archived_only?: boolean;
  limit?: number;
  cursor?: string | null;
  search?: string | null;
  status?: string | null;
  sort_by?: SessionSortBy;
  sort_order?: SortOrder;
}

export interface PaginatedSessionsResponse {
  sessions: ApiSession[];
  total: number;
  next_cursor: string | null;
}

export interface SessionListQueryState {
  search: string;
  status: string;
  activeOnly: boolean;
}

export interface Session {
  sessionId: string;
  label: string;
  createdAt: string | null;
  totalTimeMs: number | null;
  totalSources: number;
  status: string;
  active: boolean;
  eventCount: number | null;
  lastEventAt: string | null;
  query: string | null;
  depth: string | null;
  completedAt: string | null;
  hasSessionPayload: boolean;
  hasReport: boolean;
  archived?: boolean;
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

export type ViewMode = 'graph' | 'decision_graph' | 'timeline' | 'table';

// Research Run API types

export type ResearchRunStatus = 'queued' | 'running' | 'completed' | 'failed' | 'cancelled';

export type ResearchOutputFormat = 'markdown' | 'json' | 'html';

export type ResearchArtifactKind = 'session' | 'report' | 'pdf';

// Prompt override types
export interface AgentPromptOverride {
  system_prompt?: string | null;
  prompt_prefix?: string | null;
}

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
  agent_prompt_overrides?: Record<string, AgentPromptOverride>;
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
  stop_requested?: boolean;
}

export interface StopResearchRunResponse {
  run_id: string;
  status: ResearchRunStatus;
  stop_requested: boolean;
  session_id?: string;
}

export interface SessionReportResponse {
  session_id: string;
  format: ResearchOutputFormat;
  media_type: string;
  content: string;
}

// Session Delete API types

export interface DeletedLayer {
  layer: 'session' | 'telemetry' | 'duckdb';
  deleted: boolean;
  missing?: boolean;
  error?: string;
}

export interface SessionDeleteResponse {
  session_id: string;
  success: boolean;
  deleted_layers: DeletedLayer[];
  active_conflict: boolean;
  error?: string | null;
  outcome: 'deleted' | 'not_found' | 'active_conflict' | 'partial_failure' | 'failed';
}

export interface SessionDeleteError {
  error: string;
  message: string;
  session_id: string;
  active_conflict?: boolean;
}

export interface BulkSessionDeleteSummary {
  requested_count: number;
  deleted_count: number;
  not_found_count: number;
  active_conflict_count: number;
  partial_failure_count: number;
  failed_count: number;
}

export interface BulkSessionDeleteResponse {
  success: boolean;
  partial_success: boolean;
  results: SessionDeleteResponse[];
  summary: BulkSessionDeleteSummary;
}

// =============================================================================
// Derived Output Types (Task 002)
// =============================================================================

export interface CriticalPathStep {
  type: 'phase' | 'agent' | 'tool';
  name: string | null;
  agent_id?: string | null;
  duration_ms: number | null;
  start_event_id: string | null;
  end_event_id: string | null;
}

export interface BottleneckEvent {
  event_id: string | null;
  event_type: string | null;
  name: string | null;
  duration_ms: number;
}

export interface PhaseDuration {
  phase: string | null;
  duration_ms: number | null;
}

export interface CriticalPath {
  path: CriticalPathStep[];
  total_duration_ms: number;
  bottleneck_event: BottleneckEvent | null;
  phase_durations: PhaseDuration[];
}

export interface StateChange {
  event_id: string | null;
  sequence_number: number | null;
  timestamp: string | null;
  state_scope: string | null;
  state_key: string | null;
  before: unknown;
  after: unknown;
  change_type: string | null;
  caused_by_event_id: string | null;
}

export interface Decision {
  event_id: string | null;
  sequence_number: number | null;
  timestamp: string | null;
  decision_type: string | null;
  reason_code: string | null;
  chosen_option: string | null;
  inputs: Record<string, unknown> | null;
  rejected_options: string[] | null;
  confidence: number | null;
  cause_event_ids: string[] | null;
  actor_id: string | null;
}

export interface Degradation {
  event_id: string | null;
  sequence_number: number | null;
  timestamp: string | null;
  reason_code: string | null;
  severity: string | null;
  scope: string | null;
  recoverable: boolean | null;
  mitigation: string | null;
  caused_by_event_id: string | null;
  impact: string | null;
  inferred?: boolean;
}

export interface Failure {
  event_id: string | null;
  sequence_number: number | null;
  timestamp: string | null;
  event_type: string | null;
  category: string | null;
  name: string | null;
  status: string | null;
  severity: string | null;
  reason_code: string | null;
  error_message: string | null;
  phase: string | null;
  actor_id: string | null;
  duration_ms: number | null;
  recoverable: boolean | null;
  stack_trace: string | null;
}

export type DecisionGraphNodeKind =
  | 'decision'
  | 'state_change'
  | 'degradation'
  | 'failure'
  | 'event'
  | 'outcome';

export type DecisionGraphEdgeKind =
  | 'caused_by'
  | 'produced'
  | 'rejected'
  | 'mitigated_by'
  | 'led_to';

export interface DecisionGraphNode {
  id: string;
  kind: DecisionGraphNodeKind;
  label: string;
  event_id: string | null;
  sequence_number: number | null;
  timestamp: string | null;
  event_type: string | null;
  actor_id: string | null;
  status: string | null;
  severity: string | null;
  inferred: boolean;
  metadata: Record<string, unknown>;
}

export interface DecisionGraphEdge {
  id: string;
  source: string;
  target: string;
  kind: DecisionGraphEdgeKind;
  inferred: boolean;
}

export interface DecisionGraphSummary {
  node_count: number;
  edge_count: number;
  explicit_edge_count: number;
  inferred_edge_count: number;
}

export interface DecisionGraph {
  nodes: DecisionGraphNode[];
  edges: DecisionGraphEdge[];
  summary: DecisionGraphSummary;
}

export interface DerivedOutputs {
  narrative: ApiTelemetryEvent[];
  critical_path: CriticalPath;
  state_changes: StateChange[];
  decisions: Decision[];
  degradations: Degradation[];
  failures: Failure[];
  decision_graph: DecisionGraph;
}

// =============================================================================
// Prompt Override Types
// =============================================================================

export interface SessionPromptMetadata {
  overrides_applied: boolean;
  effective_overrides: Record<string, AgentPromptOverride>;
  default_prompts_used: string[];
}

// Internal type for the prompt configuration panel
export interface SessionPromptMetadataInternal {
  overrides_applied: boolean;
  effective_overrides: Record<string, { prompt_prefix?: string | null; system_prompt?: string | null }>;
  default_prompts_used: string[];
}

// =============================================================================
// Cursor-Based Pagination Types
// =============================================================================

export interface EventsPage {
  events: ApiTelemetryEvent[];
  total: number;
  has_more: boolean;
  next_cursor: number | null;
  prev_cursor: number | null;
}

export interface SessionDetailResponse {
  session: ApiSession;
  summary: Record<string, unknown> | null;
  events_page: EventsPage;
  event_tail: ApiTelemetryEvent[];
  agent_timeline: ApiTelemetryEvent[];
  active_phase: string | null;
  narrative: ApiTelemetryEvent[];
  critical_path: CriticalPath;
  state_changes: StateChange[];
  decisions: Decision[];
  degradations: Degradation[];
  failures: Failure[];
  decision_graph: DecisionGraph;
}

export interface PaginatedEventsResponse {
  events: ApiTelemetryEvent[];
  count: number;
  total: number;
  has_more: boolean;
  next_cursor: number | null;
  prev_cursor: number | null;
}

// =============================================================================
// WebSocket Message Types for Cursor Pagination
// =============================================================================

export interface WSHistoryPageMessage {
  type: 'history_page';
  events: ApiTelemetryEvent[];
  total: number;
  has_more: boolean;
  next_cursor: number | null;
  prev_cursor: number | null;
}

export interface WSClientGetHistoryMessage {
  type: 'get_history';
  limit?: number;
  cursor?: number;
  before_cursor?: number;
}

export type WebSocketServerMessage =
  | { type: 'event'; event: ApiTelemetryEvent }
  | { type: 'history'; events: ApiTelemetryEvent[] }
  | WSHistoryPageMessage
  | { type: 'error'; error: string }
  | { type: 'pong' };

export type WebSocketClientMessage =
  | { type: 'subscribe'; sessionId: string }
  | { type: 'unsubscribe'; sessionId: string }
  | WSClientGetHistoryMessage
  | { type: 'ping' };

// =============================================================================
// Trace Bundle Types (Task 003)
// =============================================================================

export interface TraceBundle {
  schema_version: string;
  exported_at: string;
  session_summary: ApiSession;
  events: ApiTelemetryEvent[];
  config_snapshot: Record<string, unknown> | null;
  artifacts: ResearchRunArtifact[];
  derived_outputs: DerivedOutputs;
}
