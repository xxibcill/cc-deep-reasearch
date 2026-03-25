import axios from 'axios';
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

export function getApiErrorMessage(error: unknown, fallback: string): string {
  if (axios.isAxiosError(error)) {
    const responseError = error.response?.data?.error;
    if (typeof responseError === 'string' && responseError.length > 0) {
      return responseError;
    }
    if (error.code === 'ECONNABORTED') {
      return 'Request timed out while waiting for the dashboard backend.';
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
  const response = await apiClient.post<StartResearchRunResponse>('/research-runs', request);
  return response.data;
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

export async function getSessionBundle(sessionId: string): Promise<{ bundle: TraceBundle }> {
  const response = await apiClient.get<TraceBundle>(`/sessions/${sessionId}/bundle`, {
    timeout: SESSION_BUNDLE_TIMEOUT_MS,
  });
  return { bundle: response.data };
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
