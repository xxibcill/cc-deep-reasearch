import axios, { type AxiosError } from 'axios';
import { dashboardRuntimeConfig } from '@/lib/runtime-config';
import { normalizeEvent, normalizeSession } from '@/lib/telemetry-transformers';
import {
  ApiSession,
  ApiTelemetryEvent,
  BulkSessionDeleteResponse,
  Session,
  TelemetryEvent,
  ResearchRunRequest,
  StartResearchRunResponse,
  ResearchRunStatusResponse,
  StopResearchRunResponse,
  SessionReportResponse,
  SessionDeleteResponse,
  SessionListParams,
  PaginatedSessionsResponse,
  TraceBundle,
  SessionDetailResponse,
  SessionPromptMetadata,
  CriticalPath,
  StateChange,
  Decision,
  Degradation,
  Failure,
  DecisionGraph,
} from '@/types/telemetry';
import type {
  ConfigFieldError,
  ConfigPatchErrorResponse,
  ConfigPatchRequest,
  ConfigResponse,
  ConfigOverrideConflict,
} from '@/types/config';
import type {
  SearchCacheListResponse,
  SearchCacheStats,
  SearchCachePurgeResponse,
  SearchCacheDeleteResponse,
  SearchCacheClearResponse,
} from '@/types/search-cache';

const apiClient = axios.create({
  baseURL: dashboardRuntimeConfig.apiBaseUrl,
  timeout: 10000,
});

const SESSION_DETAIL_TIMEOUT_MS = 30000;
const SESSION_REPORT_TIMEOUT_MS = 120000;
const SESSION_BUNDLE_TIMEOUT_MS = 120000;
const BULK_DELETE_TIMEOUT_MS = 120000;

function extractApiErrorPayload(data: unknown): string | null {
  if (!data || typeof data !== 'object') {
    return null;
  }

  const payload = data as Record<string, unknown>;
  if (typeof payload.error === 'string' && payload.error.length > 0) {
    return payload.error;
  }
  if (typeof payload.detail === 'string' && payload.detail.length > 0) {
    return payload.detail;
  }

  return null;
}

function formatTimedOutRequest(error: AxiosError): string {
  const method = error.config?.method?.toUpperCase() ?? 'REQUEST';
  const path = error.config?.url ?? dashboardRuntimeConfig.apiBaseUrl;
  const timeoutMs = error.config?.timeout;
  const timeoutText =
    typeof timeoutMs === 'number' && timeoutMs > 0
      ? `${(timeoutMs / 1000).toFixed(timeoutMs % 1000 === 0 ? 0 : 1)}s`
      : 'the configured timeout';

  return [
    `${method} ${path} timed out after ${timeoutText} while waiting for the dashboard backend.`,
    'No response body was received before the browser gave up.',
    'If this is Quick Script on the Anthropic route, the backend may still be waiting on the provider or preparing the real provider error.',
  ].join('\n');
}

export function getApiErrorMessage(error: unknown, fallback: string): string {
  if (axios.isAxiosError(error)) {
    const responseError = extractApiErrorPayload(error.response?.data);
    if (responseError) {
      return responseError;
    }
    if (error.code === 'ECONNABORTED') {
      return formatTimedOutRequest(error);
    }
    if (error.message) {
      return error.message;
    }
  }
  if (error instanceof Error && error.message) {
    return error.message;
  }
  return fallback;
}

export interface ConfigUpdateErrorDetails {
  message: string;
  fields: ConfigFieldError[];
  conflicts: ConfigOverrideConflict[];
}

interface SessionsResponse {
  sessions: ApiSession[];
  total: number;
  next_cursor: string | null;
}

interface SessionResponse {
  session: ApiSession;
}

interface SessionEventsResponse {
  events: ApiTelemetryEvent[];
  count: number;
}

export interface SessionListResult {
  sessions: Session[];
  total: number;
  nextCursor: string | null;
}

export async function getSessions(params: SessionListParams = {}): Promise<SessionListResult> {
  const response = await apiClient.get<PaginatedSessionsResponse>('/sessions', {
    params: {
      active_only: params.active_only ?? false,
      archived_only: params.archived_only ?? false,
      limit: params.limit ?? 100,
      cursor: params.cursor,
      search: params.search,
      status: params.status,
      sort_by: params.sort_by ?? 'last_event_at',
      sort_order: params.sort_order ?? 'desc',
    },
  });
  return {
    sessions: response.data.sessions.map(normalizeSession),
    total: response.data.total,
    nextCursor: response.data.next_cursor,
  };
}

export async function getConfig(): Promise<ConfigResponse> {
  const response = await apiClient.get<ConfigResponse>('/config');
  return response.data;
}

export async function updateConfig(
  request: ConfigPatchRequest
): Promise<ConfigResponse> {
  const response = await apiClient.patch<ConfigResponse>('/config', request);
  return response.data;
}

export function getConfigUpdateErrorDetails(error: unknown): ConfigUpdateErrorDetails {
  if (axios.isAxiosError(error)) {
    const payload = error.response?.data as ConfigPatchErrorResponse | undefined;
    if (payload && typeof payload.error === 'string') {
      return {
        message: payload.error,
        fields: Array.isArray(payload.fields) ? payload.fields : [],
        conflicts: Array.isArray(payload.conflicts) ? payload.conflicts : [],
      };
    }
  }

  return {
    message: getApiErrorMessage(error, 'Failed to update configuration.'),
    fields: [],
    conflicts: [],
  };
}

export async function getSession(sessionId: string): Promise<{ session: Session }> {
  const response = await apiClient.get<SessionResponse>(`/sessions/${sessionId}`);
  return { session: normalizeSession(response.data.session) };
}

export interface SessionDetailResult {
  session: Session;
  events: TelemetryEvent[];
  derivedOutputs: {
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

function normalizePromptMetadata(summary: Record<string, unknown> | null | undefined): SessionPromptMetadata | undefined {
  if (!summary || typeof summary !== 'object') {
    return undefined;
  }

  const metadata = summary.metadata;
  if (!metadata || typeof metadata !== 'object') {
    return undefined;
  }

  const prompts = (metadata as Record<string, unknown>).prompts;
  if (!prompts || typeof prompts !== 'object') {
    return undefined;
  }

  const payload = prompts as Record<string, unknown>;
  const rawOverrides = payload.effective_overrides;
  const effectiveOverrides: SessionPromptMetadata['effective_overrides'] = {};

  if (rawOverrides && typeof rawOverrides === 'object') {
    for (const [agentId, value] of Object.entries(rawOverrides as Record<string, unknown>)) {
      if (!value || typeof value !== 'object') {
        continue;
      }
      const override = value as Record<string, unknown>;
      effectiveOverrides[agentId] = {
        prompt_prefix:
          typeof override.prompt_prefix === 'string' ? override.prompt_prefix : null,
        system_prompt:
          typeof override.system_prompt === 'string' ? override.system_prompt : null,
      };
    }
  }

  return {
    overrides_applied: Boolean(payload.overrides_applied),
    effective_overrides: effectiveOverrides,
    default_prompts_used: Array.isArray(payload.default_prompts_used)
      ? payload.default_prompts_used.map((value) => String(value))
      : [],
  };
}

export async function getSessionDetail(sessionId: string): Promise<SessionDetailResult> {
  const response = await apiClient.get<SessionDetailResponse>(`/sessions/${sessionId}`, {
    params: { include_derived: true },
    timeout: SESSION_DETAIL_TIMEOUT_MS,
  });
  return {
    session: normalizeSession(response.data.session),
    events: response.data.events_page.events.map(normalizeEvent),
    derivedOutputs: {
      narrative: response.data.narrative,
      criticalPath: response.data.critical_path,
      stateChanges: response.data.state_changes,
      decisions: response.data.decisions,
      degradations: response.data.degradations,
      failures: response.data.failures,
      decisionGraph: response.data.decision_graph,
    },
    promptMetadata: normalizePromptMetadata(response.data.summary),
  };
}

export async function getSessionEvents(
  sessionId: string,
  limit = 1000,
  offset = 0
): Promise<{ events: TelemetryEvent[]; count: number }> {
  const response = await apiClient.get<SessionEventsResponse>(`/sessions/${sessionId}/events`, {
    params: { limit, offset },
  });
  return {
    events: response.data.events.map(normalizeEvent),
    count: response.data.count,
  };
}

// Research Run API helpers

export async function startResearchRun(
  request: ResearchRunRequest
): Promise<StartResearchRunResponse> {
  const controller = new AbortController();
  const timeoutId = window.setTimeout(() => controller.abort(), 10000);

  try {
    const response = await fetch(`${dashboardRuntimeConfig.apiBaseUrl}/research-runs`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(request),
      signal: controller.signal,
    });

    const payload = (await response.json()) as StartResearchRunResponse & {
      error?: string;
      detail?: string;
    };

    if (!response.ok) {
      throw new Error(payload.error || payload.detail || 'Failed to start research run.');
    }

    return payload;
  } catch (error) {
    if (error instanceof DOMException && error.name === 'AbortError') {
      throw new Error('POST /research-runs timed out after 10s while waiting for the dashboard backend.');
    }
    throw error;
  } finally {
    window.clearTimeout(timeoutId);
  }
}

export async function getResearchRunStatus(runId: string): Promise<ResearchRunStatusResponse> {
  const response = await apiClient.get<ResearchRunStatusResponse>(`/research-runs/${runId}`);
  return response.data;
}

export async function stopResearchRun(runId: string): Promise<StopResearchRunResponse> {
  const response = await apiClient.post<StopResearchRunResponse>(`/research-runs/${runId}/stop`);
  return response.data;
}

export async function getSessionReport(
  sessionId: string,
  format: 'markdown' | 'json' | 'html' = 'markdown'
): Promise<SessionReportResponse> {
  const response = await apiClient.get<SessionReportResponse>(
    `/sessions/${sessionId}/report`,
    {
      params: { format },
      timeout: SESSION_REPORT_TIMEOUT_MS,
    }
  );
  return response.data;
}

export interface DeleteSessionResult {
  success: boolean;
  response?: SessionDeleteResponse;
  error?: string;
  activeConflict?: boolean;
}

function getSessionDeleteError(response: SessionDeleteResponse): string {
  if (response.error) {
    return response.error;
  }

  const layerErrors = response.deleted_layers
    .map((layer) => layer.error)
    .filter((error): error is string => Boolean(error));

  if (layerErrors.length > 0) {
    return layerErrors.join('; ');
  }

  if (response.outcome === 'active_conflict') {
    return 'Cannot delete: session is currently active';
  }

  if (response.outcome === 'not_found') {
    return 'Session not found';
  }

  return 'Delete operation failed';
}

export async function deleteSession(sessionId: string, force: boolean = false): Promise<DeleteSessionResult> {
  try {
    const url = force ? `/sessions/${sessionId}?force=true` : `/sessions/${sessionId}`;
    const response = await apiClient.delete<SessionDeleteResponse>(url);
    if (response.data.outcome === 'deleted' || response.data.outcome === 'not_found') {
      return { success: true, response: response.data };
    }
    return {
      success: false,
      response: response.data,
      error: getSessionDeleteError(response.data),
      activeConflict: response.data.active_conflict,
    };
  } catch (error) {
    if (axios.isAxiosError(error)) {
      if (error.response?.status === 409) {
        return {
          success: false,
          error: 'Cannot delete: session is currently active',
          activeConflict: true,
        };
      }
      if (error.response?.status === 404) {
        return { success: false, error: 'Session not found' };
      }
      const serverError = error.response?.data?.error;
      if (typeof serverError === 'string' && serverError.length > 0) {
        return { success: false, error: serverError };
      }
    }
    return { success: false, error: getApiErrorMessage(error, 'Failed to delete session') };
  }
}

export async function bulkDeleteSessions(
  sessionIds: string[],
  force: boolean = false
): Promise<BulkSessionDeleteResponse> {
  const response = await apiClient.post<BulkSessionDeleteResponse>(
    '/sessions/bulk-delete',
    {
      session_ids: sessionIds,
      force,
    },
    {
      timeout: BULK_DELETE_TIMEOUT_MS,
    }
  );
  return response.data;
}

export interface ArchiveSessionResult {
  success: boolean;
  sessionId: string;
  error?: string;
}

export async function archiveSession(sessionId: string): Promise<ArchiveSessionResult> {
  try {
    const response = await apiClient.post<{ session_id: string; archived: boolean }>(
      `/sessions/${sessionId}/archive`
    );
    return { success: true, sessionId: response.data.session_id };
  } catch (error) {
    if (axios.isAxiosError(error)) {
      const serverError = error.response?.data?.error;
      if (typeof serverError === 'string' && serverError.length > 0) {
        return { success: false, sessionId, error: serverError };
      }
    }
    return { success: false, sessionId, error: getApiErrorMessage(error, 'Failed to archive session') };
  }
}

export async function restoreSession(sessionId: string): Promise<ArchiveSessionResult> {
  try {
    const response = await apiClient.post<{ session_id: string; archived: boolean }>(
      `/sessions/${sessionId}/restore`
    );
    return { success: true, sessionId: response.data.session_id };
  } catch (error) {
    if (axios.isAxiosError(error)) {
      const serverError = error.response?.data?.error;
      if (typeof serverError === 'string' && serverError.length > 0) {
        return { success: false, sessionId, error: serverError };
      }
    }
    return { success: false, sessionId, error: getApiErrorMessage(error, 'Failed to restore session') };
  }
}

export interface SessionPurgeSummary {
  archived_sessions_count: number;
  no_artifacts_count: number;
  active_count: number;
  recommendations: Array<{
    category: string;
    description: string;
    action: string;
    count: number;
  }>;
}

export interface PurgeArchivedResult {
  dry_run: boolean;
  deleted?: number;
  would_delete?: number;
  session_ids: string[];
  message: string;
  results?: unknown;
}

export async function getSessionPurgeSummary(): Promise<SessionPurgeSummary> {
  const response = await apiClient.get<SessionPurgeSummary>('/sessions/purge-summary');
  return response.data;
}

export async function purgeArchivedSessions(
  dryRun: boolean = true,
  force: boolean = false
): Promise<PurgeArchivedResult> {
  const response = await apiClient.post<PurgeArchivedResult>('/sessions/purge-archived', null, {
    params: { dry_run: dryRun, force },
  });
  return response.data;
}

export interface TraceBundleOptions {
  includePayload?: boolean;
  includeReport?: boolean;
}

export async function getSessionBundle(
  sessionId: string,
  options: TraceBundleOptions = {}
): Promise<{ bundle: TraceBundle }> {
  const response = await apiClient.get<TraceBundle>(`/sessions/${sessionId}/bundle`, {
    params: {
      include_payload: options.includePayload ?? false,
      include_report: options.includeReport ?? false,
    },
    timeout: SESSION_BUNDLE_TIMEOUT_MS,
  });
  return { bundle: response.data };
}

export interface SessionArtifactInfo {
  present: boolean;
  provenance: 'direct' | 'derived';
  description: string;
  formats?: string[];
  count?: number;
  latest_checkpoint_id?: string | null;
  resume_available?: boolean;
  reason?: string;
}

export interface SessionArtifactsResponse {
  session_id: string;
  provenance: Record<string, unknown>;
  available: Record<string, SessionArtifactInfo>;
  missing?: Record<string, Omit<SessionArtifactInfo, 'present'> & { reason: string }>;
}

export async function getSessionArtifacts(
  sessionId: string
): Promise<SessionArtifactsResponse> {
  const response = await apiClient.get<SessionArtifactsResponse>(
    `/sessions/${sessionId}/artifacts`
  );
  return response.data;
}

// Search Cache API helpers

export async function getSearchCacheEntries(
  includeExpired: boolean = false,
  limit: number = 100,
  offset: number = 0
): Promise<SearchCacheListResponse> {
  const response = await apiClient.get<SearchCacheListResponse>('/search-cache', {
    params: { include_expired: includeExpired, limit, offset },
  });
  return response.data;
}

export async function getSearchCacheStats(): Promise<SearchCacheStats> {
  const response = await apiClient.get<SearchCacheStats>('/search-cache/stats');
  return response.data;
}

export async function purgeExpiredSearchCacheEntries(): Promise<SearchCachePurgeResponse> {
  const response = await apiClient.post<SearchCachePurgeResponse>('/search-cache/purge-expired');
  return response.data;
}

export async function deleteSearchCacheEntry(cacheKey: string): Promise<SearchCacheDeleteResponse> {
  const response = await apiClient.delete<SearchCacheDeleteResponse>(`/search-cache/${encodeURIComponent(cacheKey)}`);
  return response.data;
}

export async function clearSearchCache(): Promise<SearchCacheClearResponse> {
  const response = await apiClient.delete<SearchCacheClearResponse>('/search-cache');
  return response.data;
}

export interface BenchmarkCorpus {
  version: string;
  description: string;
  cases: BenchmarkCase[];
}

export interface BenchmarkCase {
  case_id: string;
  query: string;
  category: string;
  rationale: string;
  date_sensitive: boolean;
  tags: string[];
}

export interface BenchmarkRun {
  run_id: string;
  path: string;
  corpus_version?: string;
  generated_at?: string;
  configuration?: Record<string, unknown>;
  total_cases?: number;
  average_validation_score?: number | null;
  average_latency_ms?: number | null;
}

export interface BenchmarkRunReport {
  harness_version: string;
  corpus_version: string;
  generated_at: string;
  configuration: Record<string, unknown>;
  scorecard: BenchmarkScorecard;
  cases: BenchmarkCaseReport[];
}

export interface BenchmarkScorecard {
  total_cases: number;
  average_source_count: number;
  average_unique_domains: number;
  average_source_type_diversity: number;
  average_iteration_count: number;
  average_latency_ms: number;
  average_validation_score: number | null;
  date_sensitive_cases: number;
  stop_reasons: Record<string, number>;
  categories: Record<string, number>;
}

export interface BenchmarkCaseReport {
  case_id: string;
  query: string;
  category: string;
  rationale: string;
  date_sensitive: boolean;
  tags: string[];
  metrics: {
    source_count: number;
    unique_domains: number;
    source_type_diversity: number;
    iteration_count: number;
    latency_ms: number;
    validation_score: number | null;
  };
  session_id?: string;
  configured_depth: string;
  stop_reason: string;
  validation_issues: string[];
  failure_modes: string[];
  source_domains: string[];
  source_types: string[];
}

export interface BenchmarkRunsResponse {
  runs: BenchmarkRun[];
  total: number;
}

export async function getBenchmarkCorpus(): Promise<BenchmarkCorpus> {
  const response = await apiClient.get<BenchmarkCorpus>('/benchmarks/corpus');
  return response.data;
}

export async function listBenchmarkRuns(): Promise<BenchmarkRunsResponse> {
  const response = await apiClient.get<BenchmarkRunsResponse>('/benchmarks/runs');
  return response.data;
}

export async function getBenchmarkRun(runId: string): Promise<BenchmarkRunReport> {
  const response = await apiClient.get<BenchmarkRunReport>(`/benchmarks/runs/${runId}`);
  return response.data;
}

export async function getBenchmarkCaseReport(
  runId: string,
  caseId: string
): Promise<BenchmarkCaseReport> {
  const response = await apiClient.get<BenchmarkCaseReport>(
    `/benchmarks/runs/${runId}/cases/${caseId}`
  );
  return response.data;
}

export interface ResearchThemeInfo {
  theme: string;
  display_name: string;
  description: string;
  source: 'builtin' | 'custom';
}

export interface ThemesListResponse {
  themes: ResearchThemeInfo[];
  total: number;
}

export async function listResearchThemes(): Promise<ThemesListResponse> {
  const response = await apiClient.get<ThemesListResponse>('/themes');
  return response.data;
}
