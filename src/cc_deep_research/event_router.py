"""Event router for real-time dashboard updates via WebSocket."""

from __future__ import annotations

import asyncio
from typing import Any

from websockets.server import WebSocketServerProtocol


class WebSocketConnection:
    """Wrapper for WebSocket connections with metadata."""

    def __init__(self, websocket: WebSocketServerProtocol, session_id: str) -> None:
        """Initialize WebSocket connection wrapper.

        Args:
            websocket: The WebSocket server protocol instance.
            session_id: The session ID this connection is subscribed to.
        """
        self._websocket = websocket
        self.session_id = session_id
        self._closed = False

    async def send_json(self, data: dict[str, Any]) -> None:
        """Send JSON data over WebSocket.

        Args:
            data: Dictionary to send as JSON.
        """
        import json

        try:
            if hasattr(self._websocket, "send_json"):
                await self._websocket.send_json(data)
            elif hasattr(self._websocket, "send_text"):
                await self._websocket.send_text(json.dumps(data))
            else:
                await self._websocket.send(json.dumps(data))
        except Exception:
            # Connection likely closed
            self._closed = True

    def is_connected(self) -> bool:
        """Check if connection is still active."""
        closed = getattr(self._websocket, "closed", False)
        client_state = getattr(self._websocket, "client_state", None)
        application_state = getattr(self._websocket, "application_state", None)
        return (
            not self._closed
            and not closed
            and getattr(client_state, "name", None) != "DISCONNECTED"
            and getattr(application_state, "name", None) != "DISCONNECTED"
        )

    async def close(self) -> None:
        """Close the WebSocket connection."""
        self._closed = True
        try:
            await self._websocket.close()
        except Exception:
            pass


class EventRouter:
    """In-memory event router for real-time dashboard updates.

    Subscribes WebSocket clients to session-specific event streams
    and broadcasts telemetry events to connected clients.
    """

    def __init__(self, *, max_publish_queue_size: int = 1000) -> None:
        """Initialize event router."""
        self._subscribers: dict[str, set[WebSocketConnection]] = {}
        self._lock: asyncio.Lock = asyncio.Lock()
        self._active = False
        self._max_publish_queue_size = max(1, max_publish_queue_size)
        self._publish_queue: asyncio.Queue[tuple[str, dict[str, Any]]] | None = None
        self._publish_task: asyncio.Task[None] | None = None
        self._publish_loop: asyncio.AbstractEventLoop | None = None
        self._dropped_publish_count = 0

    async def start(self) -> None:
        """Start the event router."""
        self._active = True
        self._ensure_publish_worker()

    async def stop(self) -> None:
        """Stop the event router and disconnect all clients."""
        self._active = False
        publish_task = self._publish_task
        self._publish_task = None
        if publish_task is not None:
            publish_task.cancel()
            await asyncio.gather(publish_task, return_exceptions=True)
        self._publish_queue = None
        self._publish_loop = None
        async with self._lock:
            # Close all connections
            for session_id, connections in self._subscribers.items():
                for connection in connections:
                    await connection.close()
            self._subscribers.clear()

    async def subscribe(self, session_id: str, connection: WebSocketConnection) -> None:
        """Subscribe a connection to a session's events.

        Args:
            session_id: The session ID to subscribe to.
            connection: The WebSocket connection to subscribe.
        """
        async with self._lock:
            if session_id not in self._subscribers:
                self._subscribers[session_id] = set()
            self._subscribers[session_id].add(connection)

    async def unsubscribe(self, session_id: str, connection: WebSocketConnection) -> None:
        """Unsubscribe a connection from a session.

        Args:
            session_id: The session ID to unsubscribe from.
            connection: The WebSocket connection to unsubscribe.
        """
        async with self._lock:
            if session_id in self._subscribers:
                self._subscribers[session_id].discard(connection)
                # Clean up empty session entries
                if not self._subscribers[session_id]:
                    del self._subscribers[session_id]

    def _ensure_publish_worker(self) -> bool:
        """Ensure a bounded fire-and-forget publish worker exists for the current loop."""
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            return False
        if self._publish_loop is not None and self._publish_loop is not loop:
            return not self._publish_loop.is_closed()
        if self._publish_queue is None:
            self._publish_queue = asyncio.Queue(maxsize=self._max_publish_queue_size)
            self._publish_loop = loop
        if self._publish_task is None or self._publish_task.done():
            self._publish_task = loop.create_task(self._publish_worker())
        return True

    async def _publish_worker(self) -> None:
        """Drain queued live events without creating one task per telemetry event."""
        if self._publish_queue is None:
            return
        while True:
            session_id, event = await self._publish_queue.get()
            try:
                await self._deliver(session_id, event)
            finally:
                self._publish_queue.task_done()

    def _enqueue_publish(self, session_id: str, event: dict[str, Any]) -> bool:
        """Place a publish event on the bounded router-owned queue."""
        if not self._active or self._publish_queue is None:
            return False
        try:
            self._publish_queue.put_nowait((session_id, event))
        except asyncio.QueueFull:
            self._dropped_publish_count += 1
            return False
        return True

    def publish_nowait(self, session_id: str, event: dict[str, Any]) -> bool:
        """Queue an event for bounded background delivery.

        Returns False when the router is inactive, no owner event loop exists, or
        the bounded queue is full. Calls from worker threads are forwarded to the
        router-owned loop without creating one task per telemetry event.
        """
        if not self._active:
            return False

        try:
            running_loop = asyncio.get_running_loop()
        except RuntimeError:
            running_loop = None

        owner_loop = self._publish_loop
        if owner_loop is not None and running_loop is not owner_loop:
            if owner_loop.is_closed():
                return False
            try:
                owner_loop.call_soon_threadsafe(
                    self._enqueue_publish, session_id, event
                )
            except RuntimeError:
                return False
            return True

        if not self._ensure_publish_worker():
            return False
        return self._enqueue_publish(session_id, event)

    async def _deliver(self, session_id: str, event: dict[str, Any]) -> None:
        """Publish event to all subscribers of a session.

        Args:
            session_id: The session ID to publish to.
            event: The event payload to publish.
        """
        if not self._active:
            return

        async with self._lock:
            subscribers = self._subscribers.get(session_id, set()).copy()

        # Broadcast to all subscribers (non-blocking)
        tasks = [
            conn.send_json(event) for conn in subscribers if conn.is_connected()
        ]
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)

    async def publish(self, session_id: str, event: dict[str, Any]) -> None:
        """Publish event to all subscribers of a session.

        Awaited callers keep the previous direct-delivery behavior. Fire-and-forget
        callers should use publish_nowait() to avoid unbounded task growth.
        """
        await self._deliver(session_id, event)

    def get_active_sessions(self) -> list[str]:
        """Get list of sessions with active subscribers.

        Returns:
            List of session IDs with at least one subscriber.
        """
        return list(self._subscribers.keys())

    def get_subscriber_count(self, session_id: str) -> int:
        """Get number of subscribers for a session.

        Args:
            session_id: The session ID to check.

        Returns:
            Number of active subscribers for the session.
        """
        return len(self._subscribers.get(session_id, set()))

    def is_active(self) -> bool:
        """Check if event router is active."""
        return self._active

    def get_pending_publish_count(self) -> int:
        """Return the number of queued fire-and-forget publish events."""
        return self._publish_queue.qsize() if self._publish_queue is not None else 0

    def get_dropped_publish_count(self) -> int:
        """Return queued publish events dropped because the bounded queue was full."""
        return self._dropped_publish_count


__all__ = [
    "EventRouter",
    "WebSocketConnection",
]
