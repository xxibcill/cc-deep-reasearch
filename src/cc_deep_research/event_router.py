"""Event router for real-time dashboard updates via WebSocket."""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from typing import Any

from websockets.client import WebSocketClientProtocol
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
            await self._websocket.send(json.dumps(data))
        except Exception:
            # Connection likely closed
            self._closed = True

    def is_connected(self) -> bool:
        """Check if connection is still active."""
        return not self._closed and not self._websocket.closed

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

    def __init__(self) -> None:
        """Initialize event router."""
        self._subscribers: dict[str, set[WebSocketConnection]] = {}
        self._lock: asyncio.Lock = asyncio.Lock()
        self._active = False

    async def start(self) -> None:
        """Start the event router."""
        self._active = True

    async def stop(self) -> None:
        """Stop the event router and disconnect all clients."""
        self._active = False
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

    async def publish(self, session_id: str, event: dict[str, Any]) -> None:
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


__all__ = [
    "EventRouter",
    "WebSocketConnection",
]
