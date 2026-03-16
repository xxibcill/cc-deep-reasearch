import axios from 'axios';
import { dashboardRuntimeConfig } from '@/lib/runtime-config';
import { normalizeEvent, normalizeSession } from '@/lib/telemetry-transformers';
import { ApiSession, ApiTelemetryEvent, Session, TelemetryEvent } from '@/types/telemetry';

const apiClient = axios.create({
  baseURL: dashboardRuntimeConfig.apiBaseUrl,
});

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
