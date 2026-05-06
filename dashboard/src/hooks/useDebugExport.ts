import { useCallback, useState } from 'react';
import { dashboardRuntimeConfig } from '@/lib/runtime-config';
import { getRecentRequestTelemetry, sanitizeForExport } from '@/lib/request-telemetry';
import type { LiveStreamStatus } from '@/types/telemetry';

export interface DebugExportPayload {
  schema_version: string;
  exported_at: string;
  session_id: string | null;
  route: string;
  session: Record<string, unknown> | null;
  recent_api_failures: ReturnType<typeof sanitizeForExport>;
  websocket: {
    phase: string;
    connected: boolean;
    reconnect_attempt: number;
    last_message_at: string | null;
    last_event_at: string | null;
    last_disconnect_at: string | null;
    last_success_at: string | null;
    failure_reason: string | null;
    can_reconnect: boolean;
    reconnect_history: LiveStreamStatus['reconnectHistory'];
  };
  ui_state: {
    filters: Record<string, unknown>;
    view_mode: string;
  };
  config: {
    api_base_url: string;
    websocket_base_url: string;
  };
}

async function fetchDebugExport(sessionId: string): Promise<DebugExportPayload> {
  const [debugResponse, recentFailures] = await Promise.all([
    fetch(`${dashboardRuntimeConfig.apiBaseUrl}/sessions/${sessionId}/debug-export`, {
      cache: 'no-store',
    }),
    Promise.resolve(sanitizeForExport(getRecentRequestTelemetry())),
  ]);

  if (!debugResponse.ok) {
    throw new Error(`Debug export endpoint returned ${debugResponse.status}`);
  }

  const debugData = await debugResponse.json() as Record<string, unknown>;
  return {
    ...debugData,
    recent_api_failures: recentFailures,
  } as DebugExportPayload;
}

export function useDebugExport(sessionId: string | null) {
  const [isExporting, setIsExporting] = useState(false);
  const [exportError, setExportError] = useState<string | null>(null);

  const exportDebugBundle = useCallback(
    async (liveStreamStatus: LiveStreamStatus, uiState: { viewMode: string; filters: Record<string, unknown> }) => {
      if (!sessionId) return;

      setIsExporting(true);
      setExportError(null);

      try {
        const payload = await fetchDebugExport(sessionId);

        payload.websocket = {
          phase: liveStreamStatus.phase,
          connected: liveStreamStatus.connected,
          reconnect_attempt: liveStreamStatus.reconnectAttempt,
          last_message_at: liveStreamStatus.lastMessageAt,
          last_event_at: liveStreamStatus.lastEventAt,
          last_disconnect_at: liveStreamStatus.lastDisconnectAt,
          last_success_at: liveStreamStatus.lastSuccessAt,
          failure_reason: liveStreamStatus.failureReason,
          can_reconnect: liveStreamStatus.canReconnect,
          reconnect_history: liveStreamStatus.reconnectHistory,
        };

        payload.ui_state = {
          view_mode: uiState.viewMode,
          filters: uiState.filters,
        };

        payload.config = {
          api_base_url: dashboardRuntimeConfig.apiBaseUrl,
          websocket_base_url: dashboardRuntimeConfig.websocketBaseUrl,
        };

        const blob = new Blob([JSON.stringify(payload, null, 2)], { type: 'application/json' });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `debug-export-${sessionId.slice(0, 8)}.json`;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        URL.revokeObjectURL(url);
      } catch (err) {
        setExportError(err instanceof Error ? err.message : 'Failed to export debug bundle');
      } finally {
        setIsExporting(false);
      }
    },
    [sessionId]
  );

  return { exportDebugBundle, isExporting, exportError };
}
