import axios from 'axios';
import { dashboardRuntimeConfig } from '@/lib/runtime-config';
import { normalizeEvent, normalizeSession } from '@/lib/telemetry-transformers';
import {
  ApiSession,
  ApiTelemetryEvent,
  Session,
  TelemetryEvent,
  ResearchRunRequest,
  StartResearchRunResponse,
  ResearchRunStatusResponse,
  SessionReportResponse,
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
}

interface SessionResponse {
  session: ApiSession;
}

interface SessionEventsResponse {
  events: ApiTelemetryEvent[];
  count: number;
}

export async function getSessions(activeOnly = false, limit = 100): Promise<Session[]> {
  const response = await apiClient.get<SessionsResponse>('/sessions', {
    params: { active_only: activeOnly, limit },
  });
  return response.data.sessions.map(normalizeSession);
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
