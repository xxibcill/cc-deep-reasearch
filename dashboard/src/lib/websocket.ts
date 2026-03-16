import { useCallback, useEffect, useRef } from 'react';

import useDashboardStore from '@/hooks/useDashboard';
import { dashboardRuntimeConfig } from '@/lib/runtime-config';
import { normalizeServerMessage } from '@/lib/telemetry-transformers';
import { ClientMessage, TelemetryEvent } from '@/types/telemetry';

export function useWebSocket(sessionId: string | null) {
  const connected = useDashboardStore((state) => state.connected);
  const events = useDashboardStore((state) => state.events);
  const wsRef = useRef<WebSocket | null>(null);
  const reconnectTimeoutRef = useRef<number | null>(null);
  const reconnectAttemptsRef = useRef(0);
  const shouldReconnectRef = useRef(false);
  const eventBufferRef = useRef<TelemetryEvent[]>([]);
  const flushHandleRef = useRef<number | null>(null);

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
    const ws = new WebSocket(wsUrl);
    wsRef.current = ws;

    ws.onopen = () => {
      useDashboardStore.getState().setConnected(true);
      reconnectAttemptsRef.current = 0;

      const subscribeMessage: ClientMessage = {
        type: 'subscribe',
        sessionId,
      };
      ws.send(JSON.stringify(subscribeMessage));

      // Request history
      const historyMessage: ClientMessage = {
        type: 'get_history',
        sessionId,
        limit: 1000,
      };
      ws.send(JSON.stringify(historyMessage));
    };

    ws.onmessage = (event) => {
      try {
        const message = normalizeServerMessage(JSON.parse(event.data));
        if (!message) {
          return;
        }

        if (message.type === 'event' && message.event) {
          eventBufferRef.current.push(message.event);
          scheduleFlush();
        } else if (message.type === 'history' && message.events) {
          useDashboardStore.getState().replaceEvents(message.events);
        } else if (message.type === 'error') {
          console.error('WebSocket error:', message.error);
        }
      } catch (error) {
        console.error('Failed to parse WebSocket message:', error);
      }
    };

    ws.onerror = (error) => {
      console.error('WebSocket error:', error);
      useDashboardStore.getState().setConnected(false);
    };

    ws.onclose = () => {
      useDashboardStore.getState().setConnected(false);

      if (!shouldReconnectRef.current) {
        return;
      }

      if (reconnectAttemptsRef.current < 5) {
        const delay = Math.pow(2, reconnectAttemptsRef.current) * 1000;

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

  return { connected, events };
}
