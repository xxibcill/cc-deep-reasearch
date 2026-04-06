import { useCallback, useEffect, useRef } from 'react';

import useDashboardStore, { DEFAULT_LIVE_STREAM_STATUS } from '@/hooks/useDashboard';
import { dashboardRuntimeConfig } from '@/lib/runtime-config';
import { normalizeEvent, normalizeServerMessage } from '@/lib/telemetry-transformers';
import {
  ClientMessage,
  TelemetryEvent,
  LiveStreamStatus,
  WSHistoryPageMessage,
  WSClientGetHistoryMessage,
  WebSocketServerMessage,
} from '@/types/telemetry';

interface UseWebSocketOptions {
  enabled?: boolean;
  historical?: boolean;
}

const MAX_RECONNECT_ATTEMPTS = DEFAULT_LIVE_STREAM_STATUS.maxReconnectAttempts;

function toIsoTimestamp(timeMs: number = Date.now()): string {
  return new Date(timeMs).toISOString();
}

function getReconnectDelay(attempt: number): number {
  return Math.min(Math.pow(2, Math.max(attempt, 0)) * 1000, 30000);
}

function getCloseReason(event: CloseEvent): string {
  const reason = event.reason.trim();
  if (reason.length > 0) {
    return reason;
  }
  return `Connection closed (code ${event.code})`;
}

export function useWebSocket(sessionId: string | null, options: UseWebSocketOptions = {}) {
  const { enabled = true, historical = false } = options;
  const connected = useDashboardStore((state) => state.connected);
  const events = useDashboardStore((state) => state.events);
  const liveStreamStatus = useDashboardStore((state) => state.liveStreamStatus);
  const wsRef = useRef<WebSocket | null>(null);
  const reconnectTimeoutRef = useRef<number | null>(null);
  const reconnectAttemptsRef = useRef(0);
  const shouldReconnectRef = useRef(false);
  const manualCloseRef = useRef(false);
  const eventBufferRef = useRef<TelemetryEvent[]>([]);
  const flushHandleRef = useRef<number | null>(null);
  const connectProbeInFlightRef = useRef(false);
  const latestFailureReasonRef = useRef<string | null>(null);

  const setLiveStreamStatus = useDashboardStore((state) => state.setLiveStreamStatus);

  const probeBackend = useCallback(async () => {
    if (!sessionId || connectProbeInFlightRef.current) {
      return;
    }

    connectProbeInFlightRef.current = true;
    const probeUrl = `${dashboardRuntimeConfig.apiBaseUrl}/sessions/${sessionId}`;
    try {
      const response = await fetch(probeUrl, {
        method: 'GET',
        cache: 'no-store',
      });
      console.info(
        `[dashboard] backend probe sessionId=${sessionId} status=${response.status} ok=${response.ok} probeUrl=${probeUrl}`
      );
    } catch (error) {
      console.error(
        `[dashboard] backend probe failed sessionId=${sessionId} probeUrl=${probeUrl}`,
        error
      );
    } finally {
      connectProbeInFlightRef.current = false;
    }
  }, [sessionId]);

  const flushBufferedEvents = useCallback(() => {
    flushHandleRef.current = null;
    const buffered = eventBufferRef.current;
    if (buffered.length === 0) {
      return;
    }
    eventBufferRef.current = [];
    useDashboardStore.getState().appendEvents(buffered);
  }, []);

  const updateLiveStreamStatus = useCallback(
    (status: Partial<LiveStreamStatus>) => {
      setLiveStreamStatus(status);
    },
    [setLiveStreamStatus]
  );

  const scheduleFlush = useCallback(() => {
    if (flushHandleRef.current !== null) {
      return;
    }
    flushHandleRef.current = window.setTimeout(flushBufferedEvents, 80);
  }, [flushBufferedEvents]);

  const clearReconnectTimeout = useCallback(() => {
    if (reconnectTimeoutRef.current !== null) {
      window.clearTimeout(reconnectTimeoutRef.current);
      reconnectTimeoutRef.current = null;
    }
  }, []);

  const teardownSocket = useCallback(
    (closeCode?: number, closeReason?: string) => {
      const socket = wsRef.current;
      if (!socket) {
        return;
      }

      wsRef.current = null;
      socket.onopen = null;
      socket.onmessage = null;
      socket.onerror = null;
      socket.onclose = null;

      if (
        socket.readyState === WebSocket.OPEN
        || socket.readyState === WebSocket.CONNECTING
      ) {
        manualCloseRef.current = true;
        socket.close(closeCode, closeReason);
      }
    },
    []
  );

  const connect = useCallback(() => {
    if (!sessionId || !enabled || historical) {
      return;
    }

    clearReconnectTimeout();
    teardownSocket();

    const wsUrl = `${dashboardRuntimeConfig.websocketBaseUrl}/session/${sessionId}`;
    const attempt = reconnectAttemptsRef.current;
    console.info(
      `[dashboard] opening websocket sessionId=${sessionId} wsUrl=${wsUrl} reconnectAttempt=${attempt} pageOrigin=${window.location.origin} apiBaseUrl=${dashboardRuntimeConfig.apiBaseUrl}`
    );
    updateLiveStreamStatus({
      phase: attempt > 0 ? 'reconnecting' : 'connecting',
      connected: false,
      reconnectAttempt: attempt,
      maxReconnectAttempts: MAX_RECONNECT_ATTEMPTS,
      nextRetryAt: null,
      failureReason: latestFailureReasonRef.current,
      canReconnect: true,
    });

    const ws = new WebSocket(wsUrl);
    wsRef.current = ws;
    manualCloseRef.current = false;

    ws.onopen = () => {
      console.info(`[dashboard] websocket connected sessionId=${sessionId} wsUrl=${wsUrl}`);
      reconnectAttemptsRef.current = 0;
      latestFailureReasonRef.current = null;
      updateLiveStreamStatus({
        phase: 'live',
        connected: true,
        reconnectAttempt: 0,
        nextRetryAt: null,
        failureReason: null,
        canReconnect: true,
      });

      const subscribeMessage: ClientMessage = {
        type: 'subscribe',
        sessionId,
      };
      ws.send(JSON.stringify(subscribeMessage));

      // Request history
      const historyMessage: WSClientGetHistoryMessage = {
        type: 'get_history',
        limit: 1000,
      };
      ws.send(JSON.stringify(historyMessage));
    };

    ws.onmessage = (event) => {
      try {
        const parsed = JSON.parse(event.data);
        const message = normalizeServerMessage(parsed) as WebSocketServerMessage | null;
        if (!message) {
          return;
        }

        const receivedAt = toIsoTimestamp();
        updateLiveStreamStatus({
          lastMessageAt: receivedAt,
          failureReason: null,
        });

        if (message.type === 'event' && message.event) {
          eventBufferRef.current.push(normalizeEvent(message.event));
          updateLiveStreamStatus({
            lastEventAt: receivedAt,
            phase: 'live',
            connected: true,
          });
          scheduleFlush();
        } else if (message.type === 'history' && message.events) {
          flushBufferedEvents();
          useDashboardStore.getState().appendEvents(message.events.map(normalizeEvent));
          updateLiveStreamStatus({
            lastHistoryAt: receivedAt,
          });
        } else if (message.type === 'history_page') {
          const pageMessage = message as WSHistoryPageMessage;
          flushBufferedEvents();
          useDashboardStore.getState().appendEvents(pageMessage.events.map(normalizeEvent));
          updateLiveStreamStatus({
            lastHistoryAt: receivedAt,
          });
        } else if (message.type === 'error') {
          console.error('WebSocket error:', message.error);
          latestFailureReasonRef.current = message.error;
          updateLiveStreamStatus({
            failureReason: message.error,
          });
        }
      } catch (error) {
        console.error('Failed to parse WebSocket message:', error);
      }
    };

    ws.onerror = (error) => {
      console.error(
        `[dashboard] websocket error sessionId=${sessionId} wsUrl=${wsUrl} readyState=${ws.readyState}`,
        error
      );
      void probeBackend();
      latestFailureReasonRef.current = 'Live stream connection failed.';
      updateLiveStreamStatus({
        connected: false,
        failureReason: latestFailureReasonRef.current,
      });
    };

    ws.onclose = (event) => {
      console.warn(
        `[dashboard] websocket closed sessionId=${sessionId} wsUrl=${wsUrl} code=${event.code} reason=${event.reason || '-'} wasClean=${event.wasClean} reconnectEnabled=${shouldReconnectRef.current}`
      );
      if (event.code === 1006) {
        void probeBackend();
      }
      flushBufferedEvents();

      if (manualCloseRef.current) {
        manualCloseRef.current = false;
        return;
      }

      const closedAt = toIsoTimestamp();
      latestFailureReasonRef.current = latestFailureReasonRef.current ?? getCloseReason(event);
      updateLiveStreamStatus({
        connected: false,
        lastDisconnectAt: closedAt,
        failureReason: latestFailureReasonRef.current,
      });

      if (!shouldReconnectRef.current) {
        return;
      }

      if (reconnectAttemptsRef.current < MAX_RECONNECT_ATTEMPTS) {
        const nextAttempt = reconnectAttemptsRef.current + 1;
        const delay = getReconnectDelay(reconnectAttemptsRef.current);
        const nextRetryAt = toIsoTimestamp(Date.now() + delay);
        console.info(
          `[dashboard] scheduling websocket reconnect sessionId=${sessionId} wsUrl=${wsUrl} delayMs=${delay} nextAttempt=${nextAttempt}`
        );
        updateLiveStreamStatus({
          phase: 'reconnecting',
          connected: false,
          reconnectAttempt: nextAttempt,
          nextRetryAt,
          maxReconnectAttempts: MAX_RECONNECT_ATTEMPTS,
          canReconnect: true,
        });

        reconnectTimeoutRef.current = window.setTimeout(() => {
          reconnectTimeoutRef.current = null;
          reconnectAttemptsRef.current = nextAttempt;
          connect();
        }, delay);
        return;
      }

      updateLiveStreamStatus({
        phase: 'failed',
        connected: false,
        nextRetryAt: null,
        reconnectAttempt: reconnectAttemptsRef.current,
        maxReconnectAttempts: MAX_RECONNECT_ATTEMPTS,
        canReconnect: true,
      });
    };
  }, [
    enabled,
    flushBufferedEvents,
    historical,
    probeBackend,
    scheduleFlush,
    sessionId,
    clearReconnectTimeout,
    teardownSocket,
    updateLiveStreamStatus,
  ]);

  const disconnect = useCallback((resetStatus: boolean = false) => {
    shouldReconnectRef.current = false;
    clearReconnectTimeout();
    if (flushHandleRef.current !== null) {
      window.clearTimeout(flushHandleRef.current);
      flushHandleRef.current = null;
    }
    flushBufferedEvents();
    latestFailureReasonRef.current = null;

    teardownSocket(1000, 'dashboard disconnect');
    if (resetStatus) {
      updateLiveStreamStatus(DEFAULT_LIVE_STREAM_STATUS);
    } else {
      updateLiveStreamStatus({
        connected: false,
        nextRetryAt: null,
        canReconnect: false,
      });
    }
  }, [clearReconnectTimeout, flushBufferedEvents, teardownSocket, updateLiveStreamStatus]);

  const reconnect = useCallback(() => {
    if (!sessionId || historical) {
      return;
    }

    shouldReconnectRef.current = true;
    reconnectAttemptsRef.current = 0;
    clearReconnectTimeout();
    latestFailureReasonRef.current = null;
    updateLiveStreamStatus({
      phase: 'reconnecting',
      connected: false,
      reconnectAttempt: 0,
      maxReconnectAttempts: MAX_RECONNECT_ATTEMPTS,
      nextRetryAt: null,
      failureReason: null,
      canReconnect: true,
    });
    connect();
  }, [clearReconnectTimeout, connect, historical, sessionId, updateLiveStreamStatus]);

  /**
   * Fetch more events using cursor-based pagination
   */
  const fetchMoreEvents = useCallback((cursor: number | null, beforeCursor: number | null = null, limit: number = 1000) => {
    if (!wsRef.current || wsRef.current.readyState !== WebSocket.OPEN) {
      return;
    }

    const message: WSClientGetHistoryMessage = {
      type: 'get_history',
      cursor: cursor ?? undefined,
      before_cursor: beforeCursor ?? undefined,
      limit,
    };
    wsRef.current.send(JSON.stringify(message));
  }, []);

  /**
   * Fetch next page of events
   */
  const fetchNextPage = useCallback((nextCursor: number) => {
    fetchMoreEvents(nextCursor, null, 1000);
  }, [fetchMoreEvents]);

  /**
   * Fetch previous page of events
   */
  const fetchPrevPage = useCallback((prevCursor: number) => {
    fetchMoreEvents(null, prevCursor, 1000);
  }, [fetchMoreEvents]);

  useEffect(() => {
    useDashboardStore.getState().setSessionId(sessionId);
  }, [sessionId]);

  useEffect(() => {
    if (!sessionId) {
      disconnect(true);
    } else if (historical) {
      disconnect();
      updateLiveStreamStatus({
        ...DEFAULT_LIVE_STREAM_STATUS,
        phase: 'historical',
        canReconnect: false,
      });
    } else if (enabled) {
      shouldReconnectRef.current = true;
      connect();
    } else {
      disconnect();
    }

    return () => {
      disconnect();
    };
  }, [connect, disconnect, enabled, historical, sessionId, updateLiveStreamStatus]);

  useEffect(() => () => {
    disconnect(true);
    useDashboardStore.getState().resetSessionState();
  }, [disconnect]);

  return {
    connected,
    events,
    liveStreamStatus,
    fetchMoreEvents,
    fetchNextPage,
    fetchPrevPage,
    reconnect,
  };
}
