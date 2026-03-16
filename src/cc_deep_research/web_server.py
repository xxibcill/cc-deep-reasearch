"""FastAPI web server for real-time monitoring dashboard."""

from __future__ import annotations

import asyncio
import json
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.websockets import WebSocketState

from cc_deep_research.config import Config, get_default_config_path
from cc_deep_research.event_router import EventRouter, WebSocketConnection
from cc_deep_research.telemetry import (
    get_default_telemetry_dir,
    query_dashboard_data,
    query_live_session_detail,
    query_live_sessions,
)


@asynccontextmanager
async def lifespan(app: FastAPI):  # noqa: ARG001
    """Manage application lifecycle."""
    # Start event router
    await app.state.event_router.start()
    yield
    # Shutdown event router
    await app.state.event_router.stop()


def create_app(event_router: EventRouter | None = None) -> FastAPI:
    """Create FastAPI application.

    Args:
        event_router: Optional EventRouter for WebSocket broadcasting.

    Returns:
        Configured FastAPI application.
    """
    app = FastAPI(
        title="CC Deep Research Monitoring",
        description="Real-time monitoring dashboard for CC Deep Research",
        version="1.0.0",
        lifespan=lifespan,
    )

    # Store event router in app state
    app.state.event_router = event_router or EventRouter()

    # Configure CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],  # In production, restrict to specific origins
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    return app


# Global app instance
_app: FastAPI | None = None


def get_app() -> FastAPI:
    """Get or create the global FastAPI app instance."""
    global _app
    if _app is None:
        _app = create_app()
    return _app


def register_routes(app: FastAPI) -> None:
    """Register all API and WebSocket routes.

    Args:
        app: The FastAPI application instance.
    """

    @app.get("/")
    async def root() -> dict[str, str]:
        """Root endpoint."""
        return {
            "message": "CC Deep Research Monitoring API",
            "version": "1.0.0",
        }

    @app.get("/api/sessions")
    async def list_sessions(
        active_only: bool = False,
        limit: int = 100,
    ) -> JSONResponse:
        """List all research sessions.

        Args:
            active_only: If True, only return active sessions.
            limit: Maximum number of sessions to return.

        Returns:
            JSON response with session list.
        """
        telemetry_dir = get_default_telemetry_dir()
        live_sessions = query_live_sessions(base_dir=telemetry_dir)
        historical = query_dashboard_data(get_default_config_path().parent / "dashboard.db")

        # Merge live and historical sessions
        sessions = []

        # Add live sessions
        for session in live_sessions:
            if active_only and not session.get("active"):
                continue
            sessions.append(
                {
                    "session_id": session["session_id"],
                    "created_at": session.get("created_at"),
                    "total_time_ms": session.get("total_time_ms"),
                    "total_sources": session.get("total_sources", 0),
                    "status": session.get("status", "unknown"),
                    "active": session.get("active", False),
                    "event_count": session.get("event_count"),
                    "last_event_at": session.get("last_event_at"),
                }
            )

        # Add historical sessions
        for session_data in historical["sessions"]:
            if active_only:
                continue
            sessions.append(
                {
                    "session_id": session_data[0],
                    "created_at": session_data[1],
                    "total_time_ms": session_data[2],
                    "total_sources": session_data[3],
                    "status": session_data[8],
                    "active": False,
                    "event_count": None,
                    "last_event_at": None,
                }
            )

        # Sort: active first, then by last event time
        sessions.sort(
            key=lambda s: (
                0 if s.get("active") else 1,
                s.get("last_event_at") or s.get("created_at") or "",
            )
        )

        # Apply limit
        sessions = sessions[:limit]

        return JSONResponse(content={"sessions": sessions})

    @app.get("/api/sessions/{session_id}")
    async def get_session(session_id: str) -> JSONResponse:
        """Get details for a specific session.

        Args:
            session_id: The session ID.

        Returns:
            JSON response with session details.
        """
        telemetry_dir = get_default_telemetry_dir()
        detail = query_live_session_detail(
            session_id,
            base_dir=telemetry_dir,
            tail_limit=1000,
            subprocess_chunk_limit=100,
        )

        if not detail["session"]:
            return JSONResponse(
                content={"error": "Session not found"}, status_code=404
            )

        return JSONResponse(content={"session": detail["session"]})

    @app.get("/api/sessions/{session_id}/events")
    async def get_session_events(
        session_id: str,
        limit: int = 1000,
        offset: int = 0,
    ) -> JSONResponse:
        """Get events for a specific session.

        Args:
            session_id: The session ID.
            limit: Maximum number of events to return.
            offset: Number of events to skip.

        Returns:
            JSON response with event list.
        """
        telemetry_dir = get_default_telemetry_dir()
        detail = query_live_session_detail(
            session_id,
            base_dir=telemetry_dir,
            tail_limit=limit,
            subprocess_chunk_limit=0,
        )

        events = detail["event_tail"] or []

        # Apply offset
        events = events[offset : offset + limit] if offset > 0 else events[:limit]

        return JSONResponse(content={"events": events, "count": len(events)})

    @app.websocket("/ws/session/{session_id}")
    async def websocket_endpoint(websocket: WebSocket, session_id: str) -> None:
        """WebSocket endpoint for real-time event streaming.

        Args:
            websocket: The WebSocket connection.
            session_id: The session ID to subscribe to.
        """
        await websocket.accept()

        # Create connection wrapper
        connection = WebSocketConnection(websocket, session_id)
        event_router = websocket.app.state.event_router

        # Subscribe to session events
        await event_router.subscribe(session_id, connection)

        # Send history on connect
        telemetry_dir = get_default_telemetry_dir()
        detail = query_live_session_detail(
            session_id,
            base_dir=telemetry_dir,
            tail_limit=100,
            subprocess_chunk_limit=0,
        )

        # Send initial history
        await connection.send_json(
            {"type": "history", "events": detail["event_tail"] or []}
        )

        # Listen for client messages
        try:
            while True:
                data = await websocket.receive_json()

                message_type = data.get("type")

                if message_type == "ping":
                    # Respond to ping with pong
                    await connection.send_json({"type": "pong"})
                elif message_type == "get_history":
                    # Send more history
                    limit = data.get("limit", 1000)
                    new_detail = query_live_session_detail(
                        session_id,
                        base_dir=telemetry_dir,
                        tail_limit=limit,
                        subprocess_chunk_limit=0,
                    )
                    await connection.send_json(
                        {
                            "type": "history",
                            "events": new_detail["event_tail"] or [],
                        }
                    )
                elif message_type == "subscribe":
                    # Subscribe to session (redundant but explicit)
                    await event_router.subscribe(session_id, connection)
                elif message_type == "unsubscribe":
                    # Unsubscribe from session
                    await event_router.unsubscribe(session_id, connection)

        except WebSocketDisconnect:
            # Client disconnected
            await event_router.unsubscribe(session_id, connection)
        except Exception as e:
            # Error occurred
            await event_router.unsubscribe(session_id, connection)
            try:
                await connection.send_json(
                    {"type": "error", "error": str(e)}
                )
            except Exception:
                pass


def start_server(
    host: str = "localhost",
    port: int = 8000,
    event_router: EventRouter | None = None,
) -> None:
    """Start the FastAPI server.

    Args:
        host: Host to bind to.
        port: Port to listen on.
        event_router: Optional EventRouter for WebSocket broadcasting.
    """
    import uvicorn

    app = create_app(event_router)
    register_routes(app)

    uvicorn.run(
        app,
        host=host,
        port=port,
        log_level="info",
    )


__all__ = [
    "create_app",
    "get_app",
    "register_routes",
    "start_server",
]
