import axios from 'axios';
import { Session, TelemetryEvent } from '@/types/telemetry';

const API_BASE_URL = 'http://localhost:8000/api';

export async function getSessions(activeOnly = false, limit = 100): Promise<Session[]> {
  const response = await axios.get(`${API_BASE_URL}/sessions`, {
    params: { active_only: activeOnly, limit },
  });
  return response.data.sessions;
}

export async function getSession(sessionId: string): Promise<{ session: Session }> {
  const response = await axios.get(`${API_BASE_URL}/sessions/${sessionId}`);
  return response.data;
}

export async function getSessionEvents(
  sessionId: string,
  limit = 1000,
  offset = 0
): Promise<{ events: TelemetryEvent[]; count: number }> {
  const response = await axios.get(`${API_BASE_URL}/sessions/${sessionId}/events`, {
    params: { limit, offset },
  });
  return response.data;
}
