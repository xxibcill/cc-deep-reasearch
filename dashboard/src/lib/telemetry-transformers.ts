import {
  ApiServerMessage,
  ApiSession,
  ApiTelemetryEvent,
  ServerMessage,
  Session,
  TelemetryEvent,
  TelemetryMetadata,
} from '@/types/telemetry';

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null;
}

function asString(value: unknown, fallback = ''): string {
  return typeof value === 'string' ? value : fallback;
}

function asNullableString(value: unknown): string | null {
  return typeof value === 'string' ? value : null;
}

function asBoolean(value: unknown): boolean {
  return value === true;
}

function asNumberOrNull(value: unknown): number | null {
  if (typeof value === 'number' && Number.isFinite(value)) {
    return value;
  }
  if (typeof value === 'string' && value.trim().length > 0) {
    const parsed = Number(value);
    return Number.isFinite(parsed) ? parsed : null;
  }
  return null;
}

function asMetadata(value: unknown): TelemetryMetadata {
  return isRecord(value) ? value : {};
}

function asApiTelemetryEvent(value: Record<string, unknown>): ApiTelemetryEvent {
  return value as unknown as ApiTelemetryEvent;
}

export function normalizeSession(session: ApiSession): Session {
  return {
    sessionId: asString(session.session_id),
    createdAt: asNullableString(session.created_at),
    totalTimeMs: asNumberOrNull(session.total_time_ms),
    totalSources: asNumberOrNull(session.total_sources) ?? 0,
    status: asString(session.status, 'unknown'),
    active: asBoolean(session.active),
    eventCount: asNumberOrNull(session.event_count),
    lastEventAt: asNullableString(session.last_event_at),
  };
}

export function normalizeEvent(event: ApiTelemetryEvent): TelemetryEvent {
  return {
    eventId: asString(event.event_id),
    parentEventId: asNullableString(event.parent_event_id),
    sequenceNumber: asNumberOrNull(event.sequence_number) ?? 0,
    timestamp: asString(event.timestamp),
    sessionId: asString(event.session_id),
    eventType: asString(event.event_type, 'unknown'),
    category: asString(event.category, 'unknown'),
    name: asString(event.name, 'unknown'),
    status: asString(event.status, 'unknown'),
    durationMs: asNumberOrNull(event.duration_ms),
    agentId: asNullableString(event.agent_id),
    metadata: asMetadata(event.metadata),
  };
}

export function normalizeServerMessage(message: ApiServerMessage | unknown): ServerMessage | null {
  if (!isRecord(message)) {
    return null;
  }

  const type = message.type;
  if (type !== 'event' && type !== 'history' && type !== 'error' && type !== 'pong') {
    return null;
  }

  return {
    type,
    event: isRecord(message.event) ? normalizeEvent(asApiTelemetryEvent(message.event)) : undefined,
    events: Array.isArray(message.events)
      ? message.events.filter(isRecord).map((event) => normalizeEvent(asApiTelemetryEvent(event)))
      : undefined,
    error: typeof message.error === 'string' ? message.error : undefined,
  };
}
