/**
 * Actionable error guidance for dashboard operators.
 * Maps error categories and route-specific patterns to user-facing recovery guidance.
 * Does not leak secret values, provider keys, or internal implementation details.
 */

export type ErrorRoute =
  | 'monitor'
  | 'content_gen_pipeline'
  | 'content_gen_brief'
  | 'content_gen_script'
  | 'settings'
  | 'benchmark'
  | 'report'
  | 'export'
  | 'session_list'
  | 'unknown';

interface ErrorGuidanceEntry {
  title: string;
  guidance: string;
  category: string;
  /** Route-specific recovery actions, if any */
  actions?: string[];
}

interface ErrorGuidanceMap {
  [key: string]: ErrorGuidanceEntry;
}

const ERROR_MESSAGES: ErrorGuidanceMap = {
  // ─── Network / Connectivity ───────────────────────────────────────────────

  network: {
    title: 'Connection failed',
    guidance:
      'The dashboard cannot reach the backend. Verify the backend service is running and your network allows WebSocket and HTTP connections.',
    category: 'network',
    actions: [
      'Check that the backend process is running',
      'Verify NEXT_PUBLIC_CC_API_BASE_URL and NEXT_PUBLIC_CC_WS_BASE_URL are correct',
    ],
  },

  timeout: {
    title: 'Request timed out',
    guidance:
      'The backend did not respond in time. The operation may still be in progress on the server. Refresh to check for updated results.',
    category: 'timeout',
    actions: [
      'Refresh the page to check for results',
      'If the problem persists, the backend may be overloaded or the session may be waiting on an external provider.',
    ],
  },

  backend_unavailable: {
    title: 'Backend unavailable',
    guidance:
      'The dashboard backend returned a 502 or 503 error. The service may be restarting or temporarily unavailable.',
    category: 'backend_unavailable',
    actions: [
      'Wait a moment and try again',
      'Check backend logs for root cause if this persists',
    ],
  },

  // ─── Session / Resource Errors ────────────────────────────────────────────

  active_session_conflict: {
    title: 'Session is active',
    guidance:
      'This operation cannot complete because the session is currently running. Stop the session first or wait for it to complete.',
    category: 'active_session_conflict',
    actions: [
      'Stop the active research run before retrying this operation',
      'Sessions in "running" or "scheduled" state cannot be deleted or archived',
    ],
  },

  not_found: {
    title: 'Resource not found',
    guidance:
      'The requested resource does not exist or has been removed. Return to the list and refresh to see current sessions.',
    category: 'missing_artifact',
    actions: [
      'Return to the session list',
      'The resource may have been deleted or may have expired',
    ],
  },

  // ─── Validation / Request Errors ───────────────────────────────────────────

  validation_conflict: {
    title: 'Invalid request',
    guidance:
      'The submitted request could not be processed due to invalid parameters. Check the form fields and try again.',
    category: 'validation_conflict',
    actions: [
      'Review the form for missing or invalid fields',
      'If using CLI overrides, verify they are correctly formatted',
    ],
  },

  // ─── Permission / Configuration ──────────────────────────────────────────

  permission_configuration: {
    title: 'Permission denied',
    guidance:
      'The API key or credentials used are invalid, expired, or lack the required permissions. Visit Settings to update your configuration.',
    category: 'permission_configuration',
    actions: [
      'Verify your API keys in Settings',
      'Ensure the key has not expired or been revoked',
    ],
  },

  // ─── Provider Failures ─────────────────────────────────────────────────────

  provider_failure: {
    title: 'External provider error',
    guidance:
      'A third-party service (search, LLM, or other provider) returned an error. The session may still be recoverable by retrying.',
    category: 'provider_failure',
    actions: [
      'Retry the operation — provider errors are often transient',
      'Check provider status pages if the problem affects all requests',
    ],
  },

  // ─── WebSocket Stream ──────────────────────────────────────────────────────

  websocket: {
    title: 'Live updates paused',
    guidance:
      'The real-time telemetry stream disconnected. The dashboard will attempt to reconnect automatically. Historical data remains visible.',
    category: 'websocket',
    actions: [
      'Wait for automatic reconnection',
      'Use "Refresh history" to reload stored events while reconnecting',
    ],
  },

  // ─── Content-Gen Specific ───────────────────────────────────────────────────

  content_gen_pipeline: {
    title: 'Pipeline operation failed',
    guidance:
      'A step in the content generation pipeline could not complete. Check the pipeline status and retry or reset as needed.',
    category: 'provider_failure',
    actions: [
      'Review the pipeline step logs for the specific error',
      'Reset or re-run the failed step if the operation supports it',
    ],
  },

  content_gen_brief: {
    title: 'Brief generation failed',
    guidance:
      'The brief could not be generated from the selected opportunity. Try regenerating or select a different opportunity.',
    category: 'provider_failure',
    actions: [
      'Retry generating the brief',
      'If the problem persists, the opportunity data may be insufficient',
    ],
  },

  content_gen_script: {
    title: 'Script generation failed',
    guidance:
      'The script could not be generated for the given brief. Adjust parameters or retry with a different brief.',
    category: 'provider_failure',
    actions: [
      'Review the brief for completeness',
      'Retry script generation or select a different brief',
    ],
  },

  // ─── Monitor / Report ──────────────────────────────────────────────────────

  monitor_telemetry: {
    title: 'Telemetry unavailable',
    guidance:
      'The telemetry workspace could not load event history. Refresh to retry, or view the session in historical mode if the session has completed.',
    category: 'network',
    actions: [
      'Click "Refresh history" to reload',
      'If the session is completed, use historical mode instead',
    ],
  },

  report_generation: {
    title: 'Report generation failed',
    guidance:
      'The research report could not be generated or retrieved. The session may still be processing, or the report may not be available yet.',
    category: 'provider_failure',
    actions: [
      'Verify the session has completed before requesting the report',
      'If the session is still running, wait for it to complete and try again',
    ],
  },

  benchmark_run: {
    title: 'Benchmark run failed',
    guidance:
      'One or more benchmark cases failed to complete. Check the benchmark page for per-case error details.',
    category: 'provider_failure',
    actions: [
      'Review the failed cases in the benchmark report',
      'Verify your API keys and network connectivity before re-running',
    ],
  },

  // ─── Export ────────────────────────────────────────────────────────────────

  export_failed: {
    title: 'Export failed',
    guidance:
      'The trace bundle or debug export could not be generated. The session may contain too much data or the export request may be invalid.',
    category: 'validation_conflict',
    actions: [
      'Try a smaller export (without payload or report)',
      'If the session has an exceptionally large number of events, some event filtering may be needed',
    ],
  },

  // ─── Settings ──────────────────────────────────────────────────────────────

  settings_update: {
    title: 'Configuration update failed',
    guidance:
      'The settings change could not be applied. Check the error details for which fields are invalid.',
    category: 'validation_conflict',
    actions: [
      'Review the field-level error messages',
      'Verify all API keys and provider settings are correctly formatted',
    ],
  },
};

/**
 * Maps an error string or classification to route-specific guidance.
 * Returns a title, guidance text, category, and optional recovery actions.
 */
export function getErrorGuidance(
  error: string,
  route: ErrorRoute = 'unknown'
): { title: string; guidance: string; category: string; actions: string[] } {
  const lower = error.toLowerCase();

  // ─── Pattern matching on raw error strings ─────────────────────────────────

  if (lower.includes('network') || lower.includes('fetch') || lower.includes('econnrefused') || lower.includes('err_network')) {
    return buildGuidance(ERROR_MESSAGES.network, route);
  }
  if (lower.includes('timed out') || lower.includes('timeout') || lower.includes('econnaborted')) {
    return buildGuidance(ERROR_MESSAGES.timeout, route);
  }
  if (lower.includes('502') || lower.includes('503') || lower.includes('bad gateway') || lower.includes('service unavailable')) {
    return buildGuidance(ERROR_MESSAGES.backend_unavailable, route);
  }
  if (lower.includes('409') || lower.includes('active') || lower.includes('conflict')) {
    return buildGuidance(ERROR_MESSAGES.active_session_conflict, route);
  }
  if (lower.includes('404') || lower.includes('not found')) {
    return buildGuidance(ERROR_MESSAGES.not_found, route);
  }
  if (lower.includes('422') || lower.includes('400') || lower.includes('validation') || lower.includes('invalid')) {
    return buildGuidance(ERROR_MESSAGES.validation_conflict, route);
  }
  if (lower.includes('401') || lower.includes('403') || lower.includes('unauthorized') || lower.includes('permission') || lower.includes('forbidden')) {
    return buildGuidance(ERROR_MESSAGES.permission_configuration, route);
  }
  if (lower.includes('provider') || lower.includes('upstream') || lower.includes('504') || lower.includes('gateway timeout')) {
    return buildGuidance(ERROR_MESSAGES.provider_failure, route);
  }
  if (lower.includes('websocket') || lower.includes('ws:') || lower.includes('socket')) {
    return buildGuidance(ERROR_MESSAGES.websocket, route);
  }
  if (lower.includes('telemetry') || lower.includes('workspace') || lower.includes('events')) {
    return buildGuidance({ ...ERROR_MESSAGES.monitor_telemetry, title: 'Telemetry unavailable' }, route);
  }
  if (lower.includes('report') || lower.includes('generation')) {
    return buildGuidance(ERROR_MESSAGES.report_generation, route);
  }
  if (lower.includes('benchmark')) {
    return buildGuidance(ERROR_MESSAGES.benchmark_run, route);
  }
  if (lower.includes('export') || lower.includes('bundle')) {
    return buildGuidance(ERROR_MESSAGES.export_failed, route);
  }
  if (lower.includes('pipeline') || lower.includes('content gen')) {
    return buildGuidance(ERROR_MESSAGES.content_gen_pipeline, route);
  }
  if (lower.includes('brief')) {
    return buildGuidance(ERROR_MESSAGES.content_gen_brief, route);
  }
  if (lower.includes('script')) {
    return buildGuidance(ERROR_MESSAGES.content_gen_script, route);
  }
  if (lower.includes('config') || lower.includes('settings') || lower.includes('update')) {
    return buildGuidance(ERROR_MESSAGES.settings_update, route);
  }

  return { title: 'Something went wrong', guidance: '', category: 'unknown', actions: [] };
}

function buildGuidance(
  entry: ErrorGuidanceEntry,
  route: ErrorRoute
): { title: string; guidance: string; category: string; actions: string[] } {
  return {
    title: entry.title,
    guidance: entry.guidance,
    category: entry.category,
    actions: entry.actions ?? [],
  };
}
