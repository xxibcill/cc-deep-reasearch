import { useCallback, useEffect, useRef } from 'react';

import useDashboardStore from '@/hooks/useDashboard';
import { dashboardRuntimeConfig } from '@/lib/runtime-config';
import { normalizeEvent, normalizeServerMessage } from '@/lib/telemetry-transformers';
import {
  ClientMessage,
  TelemetryEvent,
  WSHistoryPageMessage,
  WSClientGetHistoryMessage,
  WebSocketServerMessage,
} from '@/types/telemetry';

export function useWebSocket(sessionId: string | null) {
  const connected = useDashboardStore((state) => state.connected);
  const events = useDashboardStore((state) => state.events);
  const wsRef = useRef<WebSocket | null>(null);
  const reconnectTimeoutRef = useRef<number | null>(null);
  const reconnectAttemptsRef = useRef(0);
  const shouldReconnectRef = useRef(false);
  const eventBufferRef = useRef<TelemetryEvent[]>([]);
  const flushHandleRef = useRef<number | null>(null);
  const connectProbeInFlightRef = useRef(false);

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

  const connect = useCallback(() => {
    if (!sessionId) return;

    const wsUrl = `${dashboardRuntimeConfig.websocketBaseUrl}/session/${sessionId}`;
    console.info(
      `[dashboard] opening websocket sessionId=${sessionId} wsUrl=${wsUrl} reconnectAttempt=${reconnectAttemptsRef.current} pageOrigin=${window.location.origin} apiBaseUrl=${dashboardRuntimeConfig.apiBaseUrl}`
    );
    const ws = new WebSocket(wsUrl);
    wsRef.current = ws;

    ws.onopen = () => {
      console.info(`[dashboard] websocket connected sessionId=${sessionId} wsUrl=${wsUrl}`);
      useDashboardStore.getState().setConnected(true);
      reconnectAttemptsRef.current = 0;

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

        if (message.type === 'event' && message.event) {
          eventBufferRef.current.push(normalizeEvent(message.event));
          scheduleFlush();
        } else if (message.type === 'history' && message.events) {
          useDashboardStore.getState().replaceEvents(message.events.map(normalizeEvent));
        } else if (message.type === 'history_page') {
          // Handle cursor-paginated history response
          const pageMessage = message as WSHistoryPageMessage;
          useDashboardStore.getState().replaceEvents(pageMessage.events.map(normalizeEvent));
        } else if (message.type === 'error') {
          console.error('WebSocket error:', message.error);
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
      useDashboardStore.getState().setConnected(false);
    };

    ws.onclose = (event) => {
      console.warn(
        `[dashboard] websocket closed sessionId=${sessionId} wsUrl=${wsUrl} code=${event.code} reason=${event.reason || '-'} wasClean=${event.wasClean} reconnectEnabled=${shouldReconnectRef.current}`
      );
      if (event.code === 1006) {
        void probeBackend();
      }
      useDashboardStore.getState().setConnected(false);

      if (!shouldReconnectRef.current) {
        return;
      }

      if (reconnectAttemptsRef.current < 5) {
        const delay = Math.pow(2, reconnectAttemptsRef.current) * 1000;
        console.info(
          `[dashboard] scheduling websocket reconnect sessionId=${sessionId} wsUrl=${wsUrl} delayMs=${delay} nextAttempt=${reconnectAttemptsRef.current + 1}`
        );

        reconnectTimeoutRef.current = window.setTimeout(() => {
          reconnectAttemptsRef.current += 1;
          connect();
        }, delay);
      }
    };
  }, [scheduleFlush, sessionId]);

  const disconnect = useCallback(() => {
    shouldReconnectRef.current = false;
    clearReconnectTimeout();
    if (flushHandleRef.current !== null) {
      window.clearTimeout(flushHandleRef.current);
      flushHandleRef.current = null;
    }
    flushBufferedEvents();

    if (wsRef.current) {
      wsRef.current.onclose = null;
      wsRef.current.close();
      wsRef.current = null;
    }
    useDashboardStore.getState().setConnected(false);
  }, [clearReconnectTimeout, flushBufferedEvents]);

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

    if (sessionId) {
      shouldReconnectRef.current = true;
      connect();
    } else {
      disconnect();
    }

    return () => {
      disconnect();
      useDashboardStore.getState().resetSessionState();
    };
  }, [connect, disconnect, sessionId]);

  return {
    connected,
    events,
    fetchMoreEvents,
    fetchNextPage,
    fetchPrevPage,
  };
}
