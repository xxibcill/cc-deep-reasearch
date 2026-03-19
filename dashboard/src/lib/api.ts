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
} from '@/types/telemetry';

const apiClient = axios.create({
  baseURL: dashboardRuntimeConfig.apiBaseUrl,
  timeout: 10000,
});

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

export async function getSession(sessionId: string): Promise<{ session: Session }> {
  const response = await apiClient.get<SessionResponse>(`/sessions/${sessionId}`);
  return { session: normalizeSession(response.data.session) };
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
    { params: { format } }
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

export async function deleteSession(sessionId: string): Promise<DeleteSessionResult> {
  try {
    const response = await apiClient.delete<SessionDeleteResponse>(`/sessions/${sessionId}`);
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
  sessionIds: string[]
): Promise<BulkSessionDeleteResponse> {
  const response = await apiClient.post<BulkSessionDeleteResponse>('/sessions/bulk-delete', {
    session_ids: sessionIds,
  });
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
