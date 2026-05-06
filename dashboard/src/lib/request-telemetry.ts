/**
 * Request telemetry for dashboard API calls.
 * Tracks timing, request IDs, retry counts, and sanitized error classification.
 * Does NOT log secrets, prompt bodies, full reports, provider keys, or large payloads.
 */

export type RequestErrorCategory =
  | 'network'
  | 'timeout'
  | 'backend_unavailable'
  | 'validation_conflict'
  | 'active_session_conflict'
  | 'missing_artifact'
  | 'provider_failure'
  | 'permission_configuration'
  | 'unknown';

export interface RequestTelemetryEntry {
  requestId: string;
  method: string;
  path: string;
  statusCode: number | null;
  durationMs: number;
  retryCount: number;
  errorCategory: RequestErrorCategory | null;
  errorMessage: string | null;
  timestamp: string;
}

const MAX_TELEMETRY_ENTRIES = 50;

const requestTelemetryStore: {
  entries: RequestTelemetryEntry[];
  push: (entry: RequestTelemetryEntry) => void;
  getRecent: () => RequestTelemetryEntry[];
} = {
  entries: [],
  push(entry: RequestTelemetryEntry) {
    this.entries.push(entry);
    if (this.entries.length > MAX_TELEMETRY_ENTRIES) {
      this.entries = this.entries.slice(-MAX_TELEMETRY_ENTRIES);
    }
  },
  getRecent() {
    return this.entries.slice(-20);
  },
};

export function generateRequestId(): string {
  return `req_${Date.now().toString(36)}${Math.random().toString(36).slice(2, 9)}`;
}

export function classifyError(error: unknown): {
  category: RequestErrorCategory;
  message: string | null;
} {
  if (typeof error !== 'object' || error === null) {
    return { category: 'unknown', message: null };
  }

  const err = error as Record<string, unknown>;
  const message = typeof err.message === 'string' ? err.message : '';
  const code = typeof err.code === 'string' ? err.code : '';
  const responseObj = err.response as Record<string, unknown> | undefined;
  const statusCode = typeof err.status === 'number' ? err.status : (typeof responseObj?.status === 'number' ? responseObj.status : null);

  if (code === 'ECONNABORTED' || message.includes('timed out')) {
    return { category: 'timeout', message: null };
  }
  if (code === 'ERR_NETWORK' || code === 'ECONNREFUSED' || message.includes('fetch') || message.includes('NetworkError')) {
    return { category: 'network', message: null };
  }
  if (statusCode === 409) {
    return { category: 'active_session_conflict', message: null };
  }
  if (statusCode === 404) {
    return { category: 'missing_artifact', message: null };
  }
  if (statusCode === 422 || statusCode === 400) {
    return { category: 'validation_conflict', message: null };
  }
  if (statusCode === 401 || statusCode === 403) {
    return { category: 'permission_configuration', message: null };
  }
  if (statusCode === 502 || statusCode === 503 || statusCode === 504) {
    return { category: 'provider_failure', message: null };
  }
  return { category: 'unknown', message: null };
}

export function recordRequestTelemetry(entry: RequestTelemetryEntry): void {
  requestTelemetryStore.push(entry);
}

export function getRecentRequestTelemetry(): RequestTelemetryEntry[] {
  return requestTelemetryStore.getRecent();
}

export function sanitizeForExport(entries: RequestTelemetryEntry[]): RequestTelemetryEntry[] {
  return entries.map((entry) => ({
    ...entry,
    errorMessage: entry.errorMessage ? '[redacted]' : null,
  }));
}
