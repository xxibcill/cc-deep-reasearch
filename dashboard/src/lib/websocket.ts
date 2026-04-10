import { useCallback, useEffect, useRef, useState } from 'react';

import useDashboardStore from '@/hooks/useDashboard';
import { dashboardRuntimeConfig } from '@/lib/runtime-config';
import { normalizeEvent, normalizeServerMessage } from '@/lib/telemetry-transformers';
import {
  ClientMessage,
  LiveStreamPhase,
  LiveStreamStatus,
  TelemetryEvent,
  WSHistoryPageMessage,
  WSClientGetHistoryMessage,
  WebSocketServerMessage,
} from '@/types/telemetry';

const MAX_RECONNECT_ATTEMPTS = 5;
const DEFAULT_HISTORY_LIMIT = 1000;

function derivePhase(connected: boolean, reconnecting: boolean, hasEvents: boolean): LiveStreamPhase {
  if (connected) return 'live';
  if (reconnecting) return 'reconnecting';
  if (hasEvents) return 'historical';
  return 'idle';
}

interface UseWebSocketOptions {
  enabled?: boolean;
  historical?: boolean;
}

export function useWebSocket(sessionId: string | null, options: UseWebSocketOptions = {}) {
  const { enabled = true, historical = false } = options;
  const connected = useDashboardStore((state) => state.connected);
  const events = useDashboardStore((state) => state.events);
  const wsRef = useRef<WebSocket | null>(null);
  const reconnectTimeoutRef = useRef<number | null>(null);
  const reconnectAttemptsRef = useRef(0);
  const shouldReconnectRef = useRef(false);
  const eventBufferRef = useRef<TelemetryEvent[]>([]);
  const flushHandleRef = useRef<number | null>(null);
  const connectProbeInFlightRef = useRef(false);
  const lastMessageAtRef = useRef<string | null>(null);
  const lastEventAtRef = useRef<string | null>(null);
  const lastHistoryAtRef = useRef<string | null>(null);
  const lastDisconnectAtRef = useRef<string | null>(null);
  const failureReasonRef = useRef<string | null>(null);
  const parseErrorCountRef = useRef(0);
  const paginationInFlightRef = useRef<Set<string>>(new Set());

  const [reconnectAttempt, setReconnectAttempt] = useState(0);
  const [nextRetryAt, setNextRetryAt] = useState<string | null>(null);
  const [phase, setPhase] = useState<LiveStreamPhase>(historical ? 'historical' : 'idle');
  const [paginationLoading, setPaginationLoading] = useState(false);

  const liveStreamStatus: LiveStreamStatus = {
    phase,
    connected,
    reconnectAttempt,
    maxReconnectAttempts: MAX_RECONNECT_ATTEMPTS,
    nextRetryAt,
    lastMessageAt: lastMessageAtRef.current,
    lastEventAt: lastEventAtRef.current,
    lastHistoryAt: lastHistoryAtRef.current,
    lastDisconnectAt: lastDisconnectAtRef.current,
    failureReason: failureReasonRef.current,
    canReconnect: reconnectAttemptsRef.current < MAX_RECONNECT_ATTEMPTS,
  };

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
    setNextRetryAt(null);
  }, []);

  const connect = useCallback(() => {
    if (!sessionId) return;

    setPhase('connecting');

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
      setReconnectAttempt(0);
      failureReasonRef.current = null;
      setPhase('live');

      const subscribeMessage: ClientMessage = {
        type: 'subscribe',
        sessionId,
      };
      ws.send(JSON.stringify(subscribeMessage));

      // Request history
      const historyMessage: WSClientGetHistoryMessage = {
        type: 'get_history',
        limit: DEFAULT_HISTORY_LIMIT,
      };
      ws.send(JSON.stringify(historyMessage));
      lastHistoryAtRef.current = new Date().toISOString();
    };

    ws.onmessage = (event) => {
      lastMessageAtRef.current = new Date().toISOString();
      try {
        const parsed = JSON.parse(event.data);
        const message = normalizeServerMessage(parsed) as WebSocketServerMessage | null;
        if (!message) {
          return;
        }

        if (message.type === 'event' && message.event) {
          const normalizedEvent = normalizeEvent(message.event);
          eventBufferRef.current.push(normalizedEvent);
          lastEventAtRef.current = normalizedEvent.timestamp;
          scheduleFlush();
        } else if (message.type === 'history' && message.events) {
          useDashboardStore.getState().replaceEvents(message.events.map(normalizeEvent));
          lastHistoryAtRef.current = new Date().toISOString();
        } else if (message.type === 'history_page') {
          // Handle cursor-paginated history response
          const pageMessage = message as WSHistoryPageMessage;
          useDashboardStore.getState().replaceEvents(pageMessage.events.map(normalizeEvent));
          lastHistoryAtRef.current = new Date().toISOString();
        } else if (message.type === 'error') {
          console.error('WebSocket error:', message.error);
          failureReasonRef.current = message.error ?? 'Unknown error';
        }
      } catch (error) {
        parseErrorCountRef.current += 1;
        console.error(
          `[dashboard] failed to parse WebSocket message (count=${parseErrorCountRef.current}):`,
          error
        );
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
      lastDisconnectAtRef.current = new Date().toISOString();
      console.warn(
        `[dashboard] websocket closed sessionId=${sessionId} wsUrl=${wsUrl} code=${event.code} reason=${event.reason || '-'} wasClean=${event.wasClean} reconnectEnabled=${shouldReconnectRef.current}`
      );
      if (event.code === 1006) {
        void probeBackend();
        failureReasonRef.current = 'Connection closed abnormally (code 1006)';
      }
      useDashboardStore.getState().setConnected(false);

      if (!shouldReconnectRef.current) {
        setPhase(events.length > 0 ? 'historical' : 'failed');
        return;
      }

      if (reconnectAttemptsRef.current < MAX_RECONNECT_ATTEMPTS) {
        const delay = Math.pow(2, reconnectAttemptsRef.current) * 1000;
        const nextRetry = new Date(Date.now() + delay).toISOString();
        setNextRetryAt(nextRetry);
        console.info(
          `[dashboard] scheduling websocket reconnect sessionId=${sessionId} wsUrl=${wsUrl} delayMs=${delay} nextAttempt=${reconnectAttemptsRef.current + 1}`
        );

        reconnectTimeoutRef.current = window.setTimeout(() => {
          reconnectAttemptsRef.current += 1;
          setReconnectAttempt(reconnectAttemptsRef.current);
          setPhase('reconnecting');
          connect();
        }, delay);
      } else {
        failureReasonRef.current = `Max reconnection attempts (${MAX_RECONNECT_ATTEMPTS}) exceeded`;
        setPhase('failed');
      }
    };
  }, [scheduleFlush, sessionId, events.length, probeBackend]);

  const reconnect = useCallback(() => {
    if (!sessionId) return;
    shouldReconnectRef.current = true;
    reconnectAttemptsRef.current = 0;
    setReconnectAttempt(0);
    failureReasonRef.current = null;
    clearReconnectTimeout();
    connect();
  }, [connect, clearReconnectTimeout, sessionId]);

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
  const fetchMoreEvents = useCallback((cursor: number | null, beforeCursor: number | null = null, limit: number = DEFAULT_HISTORY_LIMIT) => {
    if (!wsRef.current || wsRef.current.readyState !== WebSocket.OPEN) {
      return;
    }

    // Track in-flight pagination request to prevent duplicates
    const paginationKey = `cursor:${cursor ?? 'null'}:before:${beforeCursor ?? 'null'}`;
    if (paginationInFlightRef.current.has(paginationKey)) {
      return;
    }
    paginationInFlightRef.current.add(paginationKey);
    setPaginationLoading(true);

    const message: WSClientGetHistoryMessage = {
      type: 'get_history',
      cursor: cursor ?? undefined,
      before_cursor: beforeCursor ?? undefined,
      limit,
    };
    wsRef.current.send(JSON.stringify(message));

    // Clean up after a timeout (fallback in case we don't receive a response)
    window.setTimeout(() => {
      paginationInFlightRef.current.delete(paginationKey);
      setPaginationLoading(false);
    }, 10000);
  }, []);

  /**
   * Fetch next page of events
   */
  const fetchNextPage = useCallback((nextCursor: number) => {
    fetchMoreEvents(nextCursor, null, DEFAULT_HISTORY_LIMIT);
  }, [fetchMoreEvents]);

  /**
   * Fetch previous page of events
   */
  const fetchPrevPage = useCallback((prevCursor: number) => {
    fetchMoreEvents(null, prevCursor, DEFAULT_HISTORY_LIMIT);
  }, [fetchMoreEvents]);

  useEffect(() => {
    useDashboardStore.getState().setSessionId(sessionId);

    if (sessionId && enabled && !historical) {
      shouldReconnectRef.current = true;
      connect();
    } else if (sessionId && historical) {
      shouldReconnectRef.current = false;
      setPhase('historical');
    } else {
      disconnect();
    }

    return () => {
      disconnect();
      useDashboardStore.getState().resetSessionState();
    };
  }, [connect, disconnect, sessionId, enabled, historical]);

  return {
    events,
    liveStreamStatus,
    reconnect,
    connected,
    fetchMoreEvents,
    fetchNextPage,
    fetchPrevPage,
    paginationLoading,
  };
}
