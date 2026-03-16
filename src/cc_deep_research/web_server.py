"""FastAPI web server for real-time monitoring dashboard."""

from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager, suppress
from dataclasses import dataclass
from typing import cast

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from cc_deep_research.config import get_default_config_path
from cc_deep_research.event_router import EventRouter, WebSocketConnection
from cc_deep_research.research_runs.jobs import ResearchRunJob, ResearchRunJobRegistry
from cc_deep_research.research_runs.models import ResearchRunRequest
from cc_deep_research.research_runs.service import ResearchRunService
from cc_deep_research.telemetry import (
    get_default_telemetry_dir,
    query_dashboard_data,
    query_live_session_detail,
    query_live_sessions,
)


@dataclass(slots=True)
class DashboardBackendRuntime:
    """Process-local runtime dependencies owned by the FastAPI app."""

    event_router: EventRouter
    jobs: ResearchRunJobRegistry

    async def start(self) -> None:
        """Start shared realtime infrastructure."""
        await self.event_router.start()

    async def stop(self) -> None:
        """Stop shared infrastructure and cancel in-flight jobs."""
        await self.jobs.cancel_all()
        await self.event_router.stop()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application lifecycle."""
    runtime = get_backend_runtime(app)
    await runtime.start()
    yield
    await runtime.stop()


def create_app(
    event_router: EventRouter | None = None,
    job_registry: ResearchRunJobRegistry | None = None,
) -> FastAPI:
    """Create FastAPI application.

    Args:
        event_router: Optional EventRouter for WebSocket broadcasting.
        job_registry: Optional in-process run registry for browser-started jobs.

    Returns:
        Configured FastAPI application.
    """
    app = FastAPI(
        title="CC Deep Research Monitoring",
        description="Real-time monitoring dashboard for CC Deep Research",
        version="1.0.0",
        lifespan=lifespan,
    )

    app.state.dashboard_runtime = DashboardBackendRuntime(
        event_router=event_router or EventRouter(),
        jobs=job_registry or ResearchRunJobRegistry(),
    )

    # Configure CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],  # In production, restrict to specific origins
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    register_routes(app)
    return app


# Global app instance
_app: FastAPI | None = None


def get_app() -> FastAPI:
    """Get or create the global FastAPI app instance."""
    global _app
    if _app is None:
        _app = create_app()
    return _app


def get_backend_runtime(app: FastAPI) -> DashboardBackendRuntime:
    """Return the typed dashboard runtime stored on the app."""
    return cast(DashboardBackendRuntime, app.state.dashboard_runtime)


def get_event_router(app: FastAPI) -> EventRouter:
    """Return the shared event router from app runtime state."""
    return get_backend_runtime(app).event_router


def get_job_registry(app: FastAPI) -> ResearchRunJobRegistry:
    """Return the shared job registry from app runtime state."""
    return get_backend_runtime(app).jobs


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

    @app.post("/api/research-runs")
    async def start_research_run(request: ResearchRunRequest) -> JSONResponse:
        """Start a new research run from the browser.

        Args:
            request: The research run request parameters.

        Returns:
            JSON response with run_id for status polling.
        """
        job_registry = get_job_registry(app)
        event_router = get_event_router(app)

        # Create job entry in registry
        job = job_registry.create_job(request)

        # Define background execution coroutine
        async def execute_research_run(job: ResearchRunJob) -> None:
            """Execute the research run and update job status in a thread."""
            service = ResearchRunService()
            try:
                job_registry.mark_running(job.run_id)
                # Run the synchronous service in a thread to avoid blocking
                result = await asyncio.to_thread(
                    service.run,
                    job.request,
                    event_router=event_router,
                )
                job_registry.mark_completed(job.run_id, result=result)
            except Exception as e:
                job_registry.mark_failed(job.run_id, error=str(e))

        # Spawn background task
        task = asyncio.create_task(execute_research_run(job))
        job_registry.attach_task(job.run_id, task)

        # Return immediately with run identifier
        return JSONResponse(
            content={
                "run_id": job.run_id,
                "status": job.status.value,
            },
            status_code=202,
        )

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
        event_router = get_event_router(websocket.app)

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
            with suppress(Exception):
                await connection.send_json(
                    {"type": "error", "error": str(e)}
                )


def start_server(
    host: str = "localhost",
    port: int = 8000,
    event_router: EventRouter | None = None,
    job_registry: ResearchRunJobRegistry | None = None,
) -> None:
    """Start the FastAPI server.

    Args:
        host: Host to bind to.
        port: Port to listen on.
        event_router: Optional EventRouter for WebSocket broadcasting.
        job_registry: Optional process-local registry for browser-started runs.
    """
    import uvicorn

    app = create_app(event_router=event_router, job_registry=job_registry)

    uvicorn.run(
        app,
        host=host,
        port=port,
        log_level="info",
    )


__all__ = [
    "DashboardBackendRuntime",
    "create_app",
    "get_backend_runtime",
    "get_app",
    "get_event_router",
    "get_job_registry",
    "register_routes",
    "start_server",
]
