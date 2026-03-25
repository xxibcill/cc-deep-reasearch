"""FastAPI web server for real-time monitoring dashboard."""

from __future__ import annotations

import asyncio
import json
import logging
from contextlib import asynccontextmanager, suppress
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from enum import StrEnum
from typing import Any, cast
from uuid import uuid4

from fastapi import FastAPI, Query, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from cc_deep_research.config import (
    ConfigOverrideError,
    ConfigPatchError,
    ConfigPatchErrorResponse,
    ConfigPatchRequest,
    build_config_response,
    load_config,
    update_config,
)
from cc_deep_research.event_router import EventRouter, WebSocketConnection
from cc_deep_research.reporting import ReportGenerator
from cc_deep_research.research_runs.jobs import ResearchRunJob, ResearchRunJobRegistry
from cc_deep_research.research_runs.models import (
    BulkSessionDeleteRequest,
    ResearchOutputFormat,
    ResearchRunCancelled,
    ResearchRunRequest,
    ResearchRunStatus,
    SessionDeleteRequest,
)
from cc_deep_research.research_runs.service import ResearchRunService
from cc_deep_research.research_runs.session_purge import SessionPurgeService
from cc_deep_research.search_cache import SearchCacheStore
from cc_deep_research.session_store import SessionStore
from cc_deep_research.telemetry import (
    get_default_dashboard_db_path,
    get_default_telemetry_dir,
    query_checkpoint_detail,
    query_checkpoint_lineage,
    query_dashboard_data,
    query_latest_resumable_checkpoint,
    query_live_session_detail,
    query_live_sessions,
    query_session_checkpoints,
    query_session_detail,
)
from cc_deep_research.telemetry.tree import empty_decision_graph

STALE_LIVE_SESSION_AFTER = timedelta(minutes=15)
RUN_CANCELLED_MESSAGE = "Research run was cancelled by the operator."
logger = logging.getLogger(__name__)


class SortOrder(StrEnum):
    """Sort order for session list queries."""

    ASC = "asc"
    DESC = "desc"


class SessionSortBy(StrEnum):
    """Fields available for sorting session lists."""

    CREATED_AT = "created_at"
    LAST_EVENT_AT = "last_event_at"
    TOTAL_TIME_MS = "total_time_ms"


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


def _get_websocket_debug_headers(scope: dict[str, Any]) -> dict[str, str]:
    """Return a safe subset of websocket handshake headers for debugging."""
    allowed = {
        b"host",
        b"origin",
        b"user-agent",
        b"connection",
        b"upgrade",
        b"sec-websocket-version",
        b"sec-websocket-protocol",
        b"x-forwarded-for",
        b"x-forwarded-host",
        b"x-forwarded-proto",
        b"x-forwarded-port",
    }
    headers: dict[str, str] = {}
    for raw_key, raw_value in scope.get("headers", []):
        if raw_key not in allowed:
            continue
        headers[raw_key.decode("latin-1")] = raw_value.decode("latin-1")
    return headers


class WebSocketDiagnosticsMiddleware:
    """Log websocket handshake attempts and outcomes."""

    def __init__(self, app: Any) -> None:
        self.app = app

    async def __call__(self, scope: dict[str, Any], receive: Any, send: Any) -> None:
        if scope["type"] != "websocket":
            await self.app(scope, receive, send)
            return

        path = scope.get("path", "")
        client = scope.get("client")
        query_string = scope.get("query_string", b"").decode("latin-1")
        headers = _get_websocket_debug_headers(scope)
        handshake_status: int | None = None
        accepted = False
        close_code: int | None = None

        logger.info(
            "WebSocket handshake started path=%s client=%s query=%s headers=%s",
            path,
            client,
            query_string or "-",
            headers,
        )

        async def send_wrapper(message: dict[str, Any]) -> None:
            nonlocal handshake_status, accepted, close_code
            message_type = message["type"]
            if message_type == "websocket.accept":
                accepted = True
            elif message_type == "websocket.close":
                close_code = message.get("code")
            elif message_type == "http.response.start":
                handshake_status = int(message.get("status", 0))
            await send(message)

        try:
            await self.app(scope, receive, send_wrapper)
        finally:
            if handshake_status is not None:
                logger.info(
                    "WebSocket handshake finished path=%s client=%s status=%s accepted=%s close_code=%s",
                    path,
                    client,
                    handshake_status,
                    accepted,
                    close_code,
                )
            else:
                logger.info(
                    "WebSocket connection finished path=%s client=%s accepted=%s close_code=%s",
                    path,
                    client,
                    accepted,
                    close_code,
                )


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
    app.add_middleware(WebSocketDiagnosticsMiddleware)

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


def _serialize_timestamp(value: Any) -> str | None:
    """Return a JSON-safe timestamp string."""
    if value is None:
        return None
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return str(value)


def _normalize_historical_event(row: tuple[Any, ...], *, session_id: str) -> dict[str, Any]:
    """Convert a persisted telemetry row into the public API event shape."""
    metadata = json.loads(row[10]) if row[10] else {}
    return {
        "event_id": row[0],
        "parent_event_id": row[1],
        "sequence_number": row[2],
        "timestamp": _serialize_timestamp(row[3]),
        "session_id": session_id,
        "event_type": row[4],
        "category": row[5],
        "name": row[6],
        "status": row[7],
        "duration_ms": row[8],
        "agent_id": row[9],
        "metadata": metadata if isinstance(metadata, dict) else {},
    }


def _normalize_historical_session(
    row: tuple[Any, ...],
    *,
    events: list[dict[str, Any]],
) -> dict[str, Any]:
    """Convert a persisted session row into the public API session shape."""
    return {
        "session_id": row[0],
        "created_at": _serialize_timestamp(row[1]),
        "status": row[2],
        "total_time_ms": row[3],
        "total_sources": row[4],
        "active": False,
        "event_count": len(events),
        "last_event_at": events[-1]["timestamp"] if events else None,
    }


def _parse_timestamp(value: Any) -> datetime | None:
    """Parse ISO-like timestamps used by telemetry files and DuckDB results."""
    if value is None:
        return None
    if isinstance(value, datetime):
        return value if value.tzinfo is not None else value.replace(tzinfo=UTC)
    if not isinstance(value, str) or not value:
        return None

    normalized = value.replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError:
        return None
    return parsed if parsed.tzinfo is not None else parsed.replace(tzinfo=UTC)


def _media_type_for_report(output_format: ResearchOutputFormat) -> str:
    """Return the response media type for one report format."""
    if output_format == ResearchOutputFormat.JSON:
        return "application/json"
    if output_format == ResearchOutputFormat.HTML:
        return "text/html"
    return "text/markdown"


def _normalize_live_session_state(session: dict[str, Any]) -> dict[str, Any]:
    """Mark abandoned live sessions as interrupted instead of running forever."""
    if not session.get("active"):
        return session

    last_activity = _parse_timestamp(session.get("last_event_at")) or _parse_timestamp(
        session.get("created_at")
    )
    if last_activity is None:
        return session

    if datetime.now(UTC) - last_activity <= STALE_LIVE_SESSION_AFTER:
        return session

    normalized = dict(session)
    normalized["active"] = False
    normalized["status"] = "interrupted"
    return normalized


def _build_interrupted_session_summary(
    *,
    session_id: str,
    detail: dict[str, Any],
    interrupted_at: datetime,
) -> dict[str, Any]:
    """Build a summary payload for an operator-stopped live session."""
    events = detail.get("events", [])
    created_at = detail.get("session", {}).get("created_at")
    created_at_dt = _parse_timestamp(created_at)
    total_time_ms = None
    if created_at_dt is not None:
        total_time_ms = max(int((interrupted_at - created_at_dt).total_seconds() * 1000), 0)

    return {
        "session_id": session_id,
        "status": "interrupted",
        "stop_reason": "cancelled",
        "total_sources": detail.get("session", {}).get("total_sources", 0),
        "providers": [],
        "total_time_ms": total_time_ms,
        "instances_spawned": sum(
            1 for event in events if event.get("event_type") == "agent.spawned"
        ),
        "search_queries": sum(1 for event in events if event.get("event_type") == "search.query"),
        "tool_calls": sum(1 for event in events if event.get("event_type") == "tool.call"),
        "llm_prompt_tokens": 0,
        "llm_completion_tokens": 0,
        "llm_total_tokens": 0,
        "llm_route": {},
        "event_count": len(events) + 1,
        "created_at": created_at or interrupted_at.isoformat(),
    }


def _interrupt_live_session(session_id: str) -> None:
    """Persist interrupted state for a live session so it leaves the active list."""
    telemetry_dir = get_default_telemetry_dir()
    detail = query_live_session_detail(session_id, base_dir=telemetry_dir)
    session = detail.get("session")
    if session is None or not session.get("active"):
        return

    session_dir = telemetry_dir / session_id
    interrupted_at = datetime.now(UTC)
    summary = _build_interrupted_session_summary(
        session_id=session_id,
        detail=detail,
        interrupted_at=interrupted_at,
    )

    events = detail.get("events", [])
    sequence_number = (events[-1].get("sequence_number") if events else 0) or 0
    event = {
        "event_id": f"{session_id}-cancelled-{uuid4().hex[:8]}",
        "parent_event_id": None,
        "sequence_number": sequence_number + 1,
        "timestamp": interrupted_at.isoformat(),
        "session_id": session_id,
        "event_type": "session.finished",
        "category": "session",
        "name": "research-session",
        "status": "interrupted",
        "duration_ms": summary["total_time_ms"],
        "agent_id": None,
        "metadata": summary,
    }

    events_path = session_dir / "events.jsonl"
    with open(events_path, "a", encoding="utf-8") as handle:
        handle.write(json.dumps(event) + "\n")

    summary_path = session_dir / "summary.json"
    with open(summary_path, "w", encoding="utf-8") as handle:
        json.dump(summary, handle, indent=2)


def _raise_if_run_cancelled(job: ResearchRunJob) -> None:
    """Raise the shared cancellation error when a run stop has been requested."""
    if job.stop_requested:
        raise ResearchRunCancelled(RUN_CANCELLED_MESSAGE)


def _normalize_optional_string(value: Any) -> str | None:
    """Return a trimmed string or explicit null."""
    if not isinstance(value, str):
        return None
    normalized = " ".join(value.split()).strip()
    return normalized or None


def _build_session_list_label(
    *,
    session_id: str,
    query: str | None,
    active: bool,
) -> str:
    """Return a human-meaningful session label for list views."""
    if query:
        return query
    prefix = "Active session" if active else "Session"
    return f"{prefix} {session_id[:8]}"


def _normalize_saved_session_summary(saved: dict[str, Any] | None) -> dict[str, Any]:
    """Normalize saved-session metadata into explicit nullable fields."""
    saved = saved or {}
    return {
        "query": _normalize_optional_string(saved.get("query")),
        "depth": _normalize_optional_string(saved.get("depth")),
        "started_at": _serialize_timestamp(saved.get("started_at")),
        "completed_at": _serialize_timestamp(saved.get("completed_at")),
        "total_sources": saved.get("total_sources"),
        "has_session_payload": bool(saved.get("has_session_payload")),
        "has_report": bool(saved.get("has_report")),
        "label": _normalize_optional_string(saved.get("label")),
        "archived": bool(saved.get("archived")),
    }


def _build_session_list_row(
    *,
    session_id: str,
    created_at: Any = None,
    total_time_ms: Any = None,
    total_sources: Any = None,
    status: Any = None,
    active: bool = False,
    event_count: Any = None,
    last_event_at: Any = None,
    saved: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build the normalized session-list payload shared across storage layers."""
    saved_summary = _normalize_saved_session_summary(saved)
    query = saved_summary["query"]
    created_at_value = _serialize_timestamp(created_at) or saved_summary["started_at"]
    completed_at_value = saved_summary["completed_at"]
    last_event_value = _serialize_timestamp(last_event_at) or completed_at_value or created_at_value
    total_sources_value = total_sources
    if total_sources_value is None:
        total_sources_value = saved_summary["total_sources"]

    return {
        "session_id": session_id,
        "label": saved_summary["label"]
        or _build_session_list_label(session_id=session_id, query=query, active=active),
        "created_at": created_at_value,
        "total_time_ms": total_time_ms,
        "total_sources": total_sources_value,
        "status": _normalize_optional_string(status)
        or ("completed" if completed_at_value else "unknown"),
        "active": active,
        "event_count": event_count,
        "last_event_at": last_event_value,
        "query": query,
        "depth": saved_summary["depth"],
        "completed_at": completed_at_value,
        "has_session_payload": saved_summary["has_session_payload"],
        "has_report": saved_summary["has_report"],
        "archived": saved_summary["archived"],
    }


def _query_session_api_detail(
    session_id: str,
    *,
    tail_limit: int,
    subprocess_chunk_limit: int,
    cursor: int | None = None,
    before_cursor: int | None = None,
    limit: int | None = None,
    include_derived: bool = True,
) -> dict[str, Any]:
    """Return session detail from live telemetry, or DuckDB when only historical data exists.

    Args:
        session_id: The session ID to query.
        tail_limit: Maximum events to return in event_tail (for backward compat).
        subprocess_chunk_limit: Maximum chunks per subprocess stream.
        cursor: Sequence number to start after (forward pagination).
        before_cursor: Sequence number to end before (backward pagination).
        limit: Maximum events to return in paged slice.
        include_derived: Whether to include derived outputs.

    Returns:
        Dict with session info, events, and derived outputs.
    """
    telemetry_dir = get_default_telemetry_dir()
    live_detail = query_live_session_detail(
        session_id,
        base_dir=telemetry_dir,
        tail_limit=tail_limit,
        subprocess_chunk_limit=subprocess_chunk_limit,
        cursor=cursor,
        before_cursor=before_cursor,
        limit=limit,
        include_derived=include_derived,
    )
    if live_detail["session"]:
        live_detail["session"] = _normalize_live_session_state(live_detail["session"])
        return live_detail

    historical = query_session_detail(
        session_id,
        db_path=get_default_dashboard_db_path(),
        cursor=cursor,
        before_cursor=before_cursor,
        limit=limit or tail_limit,
        include_derived=include_derived,
    )
    session_data = historical.get("session")
    if session_data is None:
        return live_detail

    events = historical.get("events", [])
    # Build session object from normalized dict
    session = {
        "session_id": session_data.get("session_id"),
        "created_at": session_data.get("created_at"),
        "status": session_data.get("status"),
        "total_time_ms": session_data.get("total_time_ms"),
        "total_sources": session_data.get("total_sources", 0),
        "active": False,
        "event_count": len(events),
        "last_event_at": events[-1].get("timestamp") if events else None,
    }
    return {
        "session": session,
        "summary": None,
        "events": events,
        "event_tail": events[-tail_limit:],
        "events_page": historical.get("events_page", {"events": [], "total": 0, "has_more": False, "next_cursor": None, "prev_cursor": None}),
        "agent_timeline": [event for event in events if event.get("category") == "agent"],
        "event_tree": {"root_events": [], "total_events": len(events), "session_id": session_id},
        "subprocess_streams": [],
        "llm_route_analytics": {},
        "active_phase": historical.get("active_phase"),
        # Derived outputs
        "narrative": historical.get("narrative", []),
        "critical_path": historical.get("critical_path", {}),
        "state_changes": historical.get("state_changes", []),
        "decisions": historical.get("decisions", []),
        "degradations": historical.get("degradations", []),
        "failures": historical.get("failures", []),
        "decision_graph": historical.get("decision_graph", empty_decision_graph()),
    }


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

    @app.get("/api/config")
    async def get_config() -> JSONResponse:
        """Return persisted and effective config for the settings page."""
        response = build_config_response()
        return JSONResponse(content=response.model_dump(mode="json"))

    @app.patch("/api/config")
    async def patch_config(request: ConfigPatchRequest) -> JSONResponse:
        """Apply and persist a partial config update."""
        try:
            response = update_config(
                request.updates,
                save_overridden_fields=request.save_overridden_fields,
            )
        except ConfigOverrideError as error:
            payload = ConfigPatchErrorResponse(
                error=error.message,
                conflicts=error.conflicts,
            )
            return JSONResponse(
                content=payload.model_dump(mode="json"),
                status_code=409,
            )
        except ConfigPatchError as error:
            payload = ConfigPatchErrorResponse(
                error=error.message,
                fields=error.fields,
            )
            return JSONResponse(
                content=payload.model_dump(mode="json"),
                status_code=400,
            )

        return JSONResponse(content=response.model_dump(mode="json"))

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
                if job.stop_requested:
                    job_registry.mark_cancelled(job.run_id, error=RUN_CANCELLED_MESSAGE)
                    return
                job_registry.mark_running(job.run_id)
                # Run the synchronous service in a thread to avoid blocking
                result = await asyncio.to_thread(
                    service.run,
                    job.request,
                    event_router=event_router,
                    cancellation_check=lambda: _raise_if_run_cancelled(job),
                    on_session_started=lambda session_id: job_registry.set_session_id(
                        job.run_id,
                        session_id=session_id,
                    ),
                )
                job_registry.mark_completed(job.run_id, result=result)
            except ResearchRunCancelled:
                if job.session_id:
                    _interrupt_live_session(job.session_id)
                job_registry.mark_cancelled(job.run_id, error=RUN_CANCELLED_MESSAGE)
            except asyncio.CancelledError:
                if job.session_id:
                    _interrupt_live_session(job.session_id)
                job_registry.mark_cancelled(job.run_id, error=RUN_CANCELLED_MESSAGE)
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

    @app.get("/api/research-runs/{run_id}")
    async def get_research_run_status(run_id: str) -> JSONResponse:
        """Get the status of a research run.

        Args:
            run_id: The research run identifier.

        Returns:
            JSON response with run status, session_id, and result metadata.
        """
        job_registry = get_job_registry(app)
        job = job_registry.get_job(run_id)

        if job is None:
            return JSONResponse(
                content={"error": f"Research run not found: {run_id}"},
                status_code=404,
            )

        response: dict = {
            "run_id": job.run_id,
            "status": job.status.value,
            "created_at": job.created_at.isoformat(),
            "stop_requested": job.stop_requested,
        }

        if job.session_id:
            response["session_id"] = job.session_id

        if job.started_at:
            response["started_at"] = job.started_at.isoformat()

        if job.completed_at:
            response["completed_at"] = job.completed_at.isoformat()

        if job.error:
            response["error"] = job.error

        if job.result is not None:
            response["result"] = {
                "session_id": job.result.session_id,
                "report_format": job.result.report.format.value,
                "report_path": str(job.result.report.path) if job.result.report.path else None,
                "artifacts": [
                    {
                        "kind": artifact.kind.value,
                        "path": str(artifact.path),
                        "media_type": artifact.media_type,
                    }
                    for artifact in job.result.artifacts
                ],
            }

        return JSONResponse(content=response)

    @app.post("/api/research-runs/{run_id}/stop")
    async def stop_research_run(run_id: str) -> JSONResponse:
        """Request cancellation of an in-process browser-started run."""
        job_registry = get_job_registry(app)
        job = job_registry.get_job(run_id)

        if job is None:
            return JSONResponse(
                content={"error": f"Research run not found: {run_id}"},
                status_code=404,
            )

        if not job.is_active:
            return JSONResponse(
                content={"error": f"Research run is not active: {run_id}"},
                status_code=409,
            )

        job_registry.request_cancel(run_id)

        if job.status == ResearchRunStatus.QUEUED:
            if job.task is not None and not job.task.done():
                job.task.cancel()
            job = job_registry.mark_cancelled(run_id, error=RUN_CANCELLED_MESSAGE)

        return JSONResponse(
            content={
                "run_id": job.run_id,
                "status": job.status.value,
                "stop_requested": job.stop_requested,
                "session_id": job.session_id,
            },
            status_code=202,
        )

    @app.get("/api/sessions")
    async def list_sessions(
        active_only: bool = False,
        archived_only: bool = False,
        limit: int = Query(default=100, ge=1, le=500),
        cursor: str | None = Query(
            default=None, description="Session ID to start after for stable pagination"
        ),
        search: str | None = Query(default=None, description="Search text for session query"),
        status: str | None = Query(default=None, description="Filter by session status"),
        sort_by: SessionSortBy = Query(
            default=SessionSortBy.LAST_EVENT_AT, description="Sort field"
        ),
        sort_order: SortOrder = Query(default=SortOrder.DESC, description="Sort order"),
    ) -> JSONResponse:
        """List research sessions with query, filter, sort, and pagination support.

        Args:
            active_only: If True, only return active sessions.
            archived_only: If True, only return archived sessions.
            limit: Maximum number of sessions to return (1-500).
            cursor: Session ID to start after for stable pagination.
            search: Search text to filter by session query.
            status: Filter by session status (completed, interrupted, running, etc.).
            sort_by: Field to sort by (created_at, last_event_at, total_time_ms).
            sort_order: Sort direction (asc or desc).

        Returns:
            JSON response with paginated session list including merged saved-session
            metadata (query, depth, completed_at) and artifact state
            (has_session_payload, has_report).
        """
        telemetry_dir = get_default_telemetry_dir()
        live_sessions = query_live_sessions(base_dir=telemetry_dir)
        historical = query_dashboard_data(get_default_dashboard_db_path())

        session_store = SessionStore()
        saved_sessions = session_store.list_sessions()
        archived_session_ids = session_store.get_archived_session_ids() if archived_only else set()
        saved_by_id = {s["session_id"]: s for s in saved_sessions}

        sessions_by_id: dict[str, dict[str, Any]] = {}

        for session in live_sessions:
            if active_only and not session.get("active"):
                continue
            normalized_session = _normalize_live_session_state(session)
            if active_only and not normalized_session.get("active"):
                continue
            session_id = normalized_session["session_id"]
            sessions_by_id[session_id] = _build_session_list_row(
                session_id=session_id,
                created_at=normalized_session.get("created_at"),
                total_time_ms=normalized_session.get("total_time_ms"),
                total_sources=normalized_session.get("total_sources", 0),
                status=normalized_session.get("status", "unknown"),
                active=bool(normalized_session.get("active", False)),
                event_count=normalized_session.get("event_count"),
                last_event_at=normalized_session.get("last_event_at"),
                saved=saved_by_id.get(session_id),
            )

        for session_data in historical["sessions"]:
            if active_only:
                continue
            session_id = session_data[0]
            if session_id in sessions_by_id:
                existing = sessions_by_id[session_id]
                if not existing.get("active"):
                    existing["status"] = session_data[8]
                if existing.get("total_time_ms") is None:
                    existing["total_time_ms"] = session_data[2]
                if existing.get("total_sources") in (None, 0):
                    existing["total_sources"] = session_data[3]
                if existing.get("created_at") is None:
                    existing["created_at"] = _serialize_timestamp(session_data[1])
                if existing.get("last_event_at") is None:
                    existing["last_event_at"] = existing.get("completed_at") or existing.get(
                        "created_at"
                    )
                continue
            sessions_by_id[session_id] = _build_session_list_row(
                session_id=session_id,
                created_at=session_data[1],
                total_time_ms=session_data[2],
                total_sources=session_data[3],
                status=session_data[8],
                active=False,
                event_count=None,
                last_event_at=None,
                saved=saved_by_id.get(session_id),
            )

        for saved in saved_sessions:
            session_id = saved["session_id"]
            if session_id in sessions_by_id:
                continue
            if active_only:
                continue
            is_archived = session_id in archived_session_ids or saved.get("archived", False)
            if is_archived and not archived_only:
                continue
            sessions_by_id[session_id] = _build_session_list_row(
                session_id=session_id,
                created_at=saved.get("started_at"),
                total_time_ms=None,
                total_sources=saved.get("total_sources"),
                status=None,
                active=False,
                event_count=None,
                last_event_at=saved.get("completed_at") or saved.get("started_at"),
                saved=saved,
            )

        sessions = list(sessions_by_id.values())

        if search:
            search_lower = search.lower()
            sessions = [
                s
                for s in sessions
                if search_lower in (s.get("query") or "").lower()
                or search_lower in (s.get("label") or "").lower()
                or search_lower in s["session_id"].lower()
            ]

        if status:
            sessions = [s for s in sessions if s.get("status") == status]

        sessions = [s for s in sessions if archived_only == (s.get("archived") or session_store.is_session_archived(s.get("session_id", "")))]

        def sort_key(s: dict[str, Any]) -> Any:
            sort_field_value = s.get(sort_by.value)
            if sort_by == SessionSortBy.TOTAL_TIME_MS:
                return sort_field_value if isinstance(sort_field_value, (int, float)) else -1
            return sort_field_value if isinstance(sort_field_value, str) else ""

        reverse = sort_order == SortOrder.DESC
        sessions.sort(key=sort_key, reverse=reverse)
        sessions.sort(key=lambda session: 0 if session.get("active") else 1)

        total = len(sessions)

        if cursor:
            cursor_index = None
            for i, s in enumerate(sessions):
                if s["session_id"] == cursor:
                    cursor_index = i + 1
                    break
            if cursor_index is not None:
                sessions = sessions[cursor_index:]

        remaining_sessions = len(sessions)
        sessions = sessions[:limit]

        next_cursor = None
        if len(sessions) == limit and remaining_sessions > limit:
            next_cursor = sessions[-1]["session_id"]

        return JSONResponse(
            content={
                "sessions": sessions,
                "total": total,
                "next_cursor": next_cursor,
            }
        )

    @app.get("/api/sessions/{session_id}")
    async def get_session(
        session_id: str,
        cursor: int | None = Query(default=None, description="Sequence number to start after"),
        before_cursor: int | None = Query(default=None, description="Sequence number to end before"),
        limit: int = Query(default=1000, ge=1, le=5000, description="Maximum events to return"),
        include_derived: bool = Query(default=True, description="Include derived outputs"),
        include_checkpoints: bool = Query(default=True, description="Include checkpoint inventory"),
    ) -> JSONResponse:
        """Get details for a specific session.

        Args:
            session_id: The session ID.
            cursor: Sequence number to start after (forward pagination).
            before_cursor: Sequence number to end before (backward pagination).
            limit: Maximum events to return.
            include_derived: Whether to include derived outputs.
            include_checkpoints: Whether to include checkpoint inventory.

        Returns:
            JSON response with session details including derived outputs,
            cursor-based pagination metadata, and checkpoint information.
        """
        detail = _query_session_api_detail(
            session_id,
            tail_limit=1000,
            subprocess_chunk_limit=100,
            cursor=cursor,
            before_cursor=before_cursor,
            limit=limit,
            include_derived=include_derived,
        )

        if not detail["session"]:
            return JSONResponse(content={"error": "Session not found"}, status_code=404)

        response_content = {
            "session": detail["session"],
            "summary": detail.get("summary"),
            "events_page": detail.get("events_page", {
                "events": detail.get("events", [])[:limit],
                "total": len(detail.get("events", [])),
                "has_more": False,
                "next_cursor": None,
                "prev_cursor": None,
            }),
            "event_tail": detail.get("event_tail", []),
            "agent_timeline": detail.get("agent_timeline", []),
            "active_phase": detail.get("active_phase"),
            # Derived outputs
            "narrative": detail.get("narrative", []),
            "critical_path": detail.get("critical_path", {}),
            "state_changes": detail.get("state_changes", []),
            "decisions": detail.get("decisions", []),
            "degradations": detail.get("degradations", []),
            "failures": detail.get("failures", []),
            "decision_graph": detail.get("decision_graph", empty_decision_graph()),
        }

        # Include checkpoint inventory if requested
        if include_checkpoints:
            telemetry_dir = get_default_telemetry_dir()
            checkpoint_manifest = query_session_checkpoints(session_id, base_dir=telemetry_dir)
            response_content["checkpoints"] = {
                "total": len(checkpoint_manifest.get("checkpoints", [])),
                "latest_checkpoint_id": checkpoint_manifest.get("latest_checkpoint_id"),
                "latest_resume_safe_checkpoint_id": checkpoint_manifest.get("latest_resume_safe_checkpoint_id"),
                "resume_available": checkpoint_manifest.get("latest_resume_safe_checkpoint_id") is not None,
            }

        return JSONResponse(content=response_content)

    @app.delete("/api/sessions/{session_id}")
    async def delete_session(
        session_id: str,
        force: bool = False,
    ) -> JSONResponse:
        """Delete a research session from all storage layers.

        Args:
            session_id: The session ID to delete.
            force: If true, delete even if session is active.

        Returns:
            JSON response with deletion results per layer.
        """
        request = SessionDeleteRequest(session_id=session_id, force=force)
        service = SessionPurgeService()
        response = service.delete_session(request)

        status_code = 409 if response.active_conflict else 200
        return JSONResponse(
            content=response.model_dump(mode="json"),
            status_code=status_code,
        )

    @app.post("/api/sessions/bulk-delete")
    async def bulk_delete_sessions(request: BulkSessionDeleteRequest) -> JSONResponse:
        """Delete multiple research sessions with explicit per-session outcomes."""
        service = SessionPurgeService()
        response = service.delete_sessions(request)
        return JSONResponse(content=response.model_dump(mode="json"))

    @app.post("/api/sessions/{session_id}/archive")
    async def archive_session(session_id: str) -> JSONResponse:
        """Archive a session, hiding it from the default session list.

        Args:
            session_id: The session ID to archive.

        Returns:
            JSON response indicating success or failure.
        """
        store = SessionStore()
        if not store.session_exists(session_id):
            return JSONResponse(
                content={"error": f"Session not found: {session_id}"},
                status_code=404,
            )

        success = store.archive_session(session_id)
        if success:
            return JSONResponse(
                content={
                    "session_id": session_id,
                    "archived": True,
                }
            )
        return JSONResponse(
            content={"error": f"Failed to archive session: {session_id}"},
            status_code=500,
        )

    @app.post("/api/sessions/{session_id}/restore")
    async def restore_session(session_id: str) -> JSONResponse:
        """Restore an archived session to the active list.

        Args:
            session_id: The session ID to restore.

        Returns:
            JSON response indicating success or failure.
        """
        store = SessionStore()
        if not store.session_exists(session_id):
            return JSONResponse(
                content={"error": f"Session not found: {session_id}"},
                status_code=404,
            )

        success = store.restore_session(session_id)
        if success:
            return JSONResponse(
                content={
                    "session_id": session_id,
                    "archived": False,
                }
            )
        return JSONResponse(
            content={"error": f"Failed to restore session: {session_id}"},
            status_code=500,
        )

    @app.get("/api/sessions/{session_id}/events")
    async def get_session_events(
        session_id: str,
        limit: int = Query(default=1000, ge=1, le=5000, description="Maximum events to return"),
        cursor: int | None = Query(default=None, description="Sequence number to start after"),
        before_cursor: int | None = Query(default=None, description="Sequence number to end before"),
        offset: int = Query(default=0, ge=0, description="Number of events to skip (deprecated, use cursor)"),
    ) -> JSONResponse:
        """Get events for a specific session with cursor-based pagination.

        Args:
            session_id: The session ID.
            limit: Maximum number of events to return.
            cursor: Sequence number to start after (forward pagination).
            before_cursor: Sequence number to end before (backward pagination).
            offset: Number of events to skip (deprecated, prefer cursor).

        Returns:
            JSON response with paginated events and cursor metadata.
        """
        detail = _query_session_api_detail(
            session_id,
            tail_limit=limit * 2,  # Get more for backward compat
            subprocess_chunk_limit=0,
            cursor=cursor,
            before_cursor=before_cursor,
            limit=limit,
            include_derived=False,
        )

        # Use the paginated events page if available
        events_page = detail.get("events_page", {})

        if not events_page.get("events"):
            # Fall back to event_tail for backward compatibility
            events = detail.get("event_tail") or detail.get("events") or []
            if offset > 0:
                events = events[offset : offset + limit]
            else:
                events = events[:limit]

            return JSONResponse(content={
                "events": events,
                "count": len(events),
                "total": len(detail.get("events", [])),
                "has_more": False,
                "next_cursor": None,
                "prev_cursor": None,
            })

        return JSONResponse(content={
            "events": events_page["events"],
            "count": len(events_page["events"]),
            "total": events_page["total"],
            "has_more": events_page["has_more"],
            "next_cursor": events_page["next_cursor"],
            "prev_cursor": events_page["prev_cursor"],
        })

    @app.get("/api/sessions/{session_id}/report")
    async def get_session_report(
        session_id: str,
        format: str = "markdown",
    ) -> JSONResponse:
        """Get the rendered report for a completed session.

        Args:
            session_id: The session ID.
            format: Output format (markdown, json, html).

        Returns:
            JSON response with report content and metadata.
        """
        # Validate format
        try:
            output_format = ResearchOutputFormat(format.lower())
        except ValueError:
            return JSONResponse(
                content={"error": f"Invalid format: {format}. Supported: markdown, json, html"},
                status_code=400,
            )

        # Load session from store
        store = SessionStore()
        session = store.load_session(session_id)

        if session is None:
            return JSONResponse(
                content={"error": f"Session not found: {session_id}"},
                status_code=404,
            )

        cached_report = store.load_report(session_id, output_format)
        if cached_report is not None:
            return JSONResponse(
                content={
                    "session_id": session_id,
                    "format": output_format.value,
                    "media_type": _media_type_for_report(output_format),
                    "content": cached_report,
                }
            )

        # Check if session has analysis data
        analysis = session.metadata.get("analysis", {})
        if not analysis:
            return JSONResponse(
                content={"error": "Session has no analysis data yet"},
                status_code=404,
            )

        # Generate report in requested format
        config = load_config()
        reporter = ReportGenerator(config)

        if output_format == ResearchOutputFormat.JSON:
            content = reporter.generate_json_report(session, analysis)
        elif output_format == ResearchOutputFormat.HTML:
            markdown = store.load_report(session_id, ResearchOutputFormat.MARKDOWN)
            if markdown is None:
                markdown = reporter.generate_markdown_report(session, analysis)
                store.save_report(session_id, ResearchOutputFormat.MARKDOWN, markdown)
            content = reporter.render_html_report(markdown)
        else:
            content = reporter.generate_markdown_report(session, analysis)
        store.save_report(session_id, output_format, content)

        return JSONResponse(
            content={
                "session_id": session_id,
                "format": output_format.value,
                "media_type": _media_type_for_report(output_format),
                "content": content,
            }
        )

    @app.get("/api/sessions/{session_id}/bundle")
    async def get_session_bundle(
        session_id: str,
        include_payload: bool = Query(default=False, description="Include full session payload"),
        include_report: bool = Query(default=False, description="Include report content"),
    ) -> JSONResponse:
        """Get a portable trace bundle for a session.

        Args:
            session_id: The session ID.
            include_payload: Include full session payload in the bundle.
            include_report: Include report content in the bundle.

        Returns:
            JSON response with trace bundle containing events, derived outputs,
            and optional artifacts.
        """
        store = SessionStore()

        if not store.session_exists(session_id):
            return JSONResponse(
                content={"error": f"Session not found: {session_id}"},
                status_code=404,
            )

        bundle = store.export_trace_bundle(
            session_id,
            include_payload=include_payload,
            include_report=include_report,
        )

        if bundle is None:
            return JSONResponse(
                content={"error": f"Failed to export bundle for session: {session_id}"},
                status_code=500,
            )

        return JSONResponse(content=bundle)

    @app.get("/api/sessions/{session_id}/checkpoints")
    async def get_session_checkpoints(session_id: str) -> JSONResponse:
        """Get checkpoint inventory for a session.

        Args:
            session_id: The session ID.

        Returns:
            JSON response with checkpoint manifest including all checkpoints
            and metadata about latest resumable checkpoint.
        """
        telemetry_dir = get_default_telemetry_dir()
        session_dir = telemetry_dir / session_id

        if not session_dir.exists():
            return JSONResponse(
                content={"error": f"Session not found: {session_id}"},
                status_code=404,
            )

        manifest = query_session_checkpoints(session_id, base_dir=telemetry_dir)
        return JSONResponse(content=manifest)

    @app.get("/api/sessions/{session_id}/checkpoints/{checkpoint_id}")
    async def get_checkpoint_detail(session_id: str, checkpoint_id: str) -> JSONResponse:
        """Get detailed information for a specific checkpoint.

        Args:
            session_id: The session ID.
            checkpoint_id: The checkpoint ID.

        Returns:
            JSON response with full checkpoint details including lineage.
        """
        telemetry_dir = get_default_telemetry_dir()
        checkpoint = query_checkpoint_detail(session_id, checkpoint_id, base_dir=telemetry_dir)

        if checkpoint is None:
            return JSONResponse(
                content={"error": f"Checkpoint not found: {checkpoint_id}"},
                status_code=404,
            )

        # Include lineage information
        lineage = query_checkpoint_lineage(session_id, checkpoint_id, base_dir=telemetry_dir)
        checkpoint["lineage"] = [cp.get("checkpoint_id") for cp in lineage]

        return JSONResponse(content=checkpoint)

    @app.get("/api/sessions/{session_id}/checkpoints/{checkpoint_id}/lineage")
    async def get_checkpoint_lineage_endpoint(session_id: str, checkpoint_id: str) -> JSONResponse:
        """Get checkpoint lineage from start to specified checkpoint.

        Args:
            session_id: The session ID.
            checkpoint_id: The checkpoint ID.

        Returns:
            JSON response with ordered list of checkpoints in lineage.
        """
        telemetry_dir = get_default_telemetry_dir()
        lineage = query_checkpoint_lineage(session_id, checkpoint_id, base_dir=telemetry_dir)

        return JSONResponse(content={
            "session_id": session_id,
            "checkpoint_id": checkpoint_id,
            "lineage": lineage,
            "depth": len(lineage),
        })

    @app.post("/api/sessions/{session_id}/resume")
    async def resume_session(
        session_id: str,
        checkpoint_id: str | None = Query(default=None, description="Checkpoint to resume from"),
        mode: str = Query(default="resume_latest", description="Resume mode"),
    ) -> JSONResponse:
        """Resume a session from a checkpoint.

        Args:
            session_id: The session ID to resume.
            checkpoint_id: Optional specific checkpoint (default: latest safe).
            mode: Resume mode (resume_latest, resume_from_checkpoint).

        Returns:
            JSON response with resume result indicating success or failure.
        """
        from cc_deep_research.models.checkpoint import ResumeRequest, ResumeResult

        telemetry_dir = get_default_telemetry_dir()
        session_dir = telemetry_dir / session_id

        if not session_dir.exists():
            return JSONResponse(
                content={"error": f"Session not found: {session_id}"},
                status_code=404,
            )

        # Get the checkpoint to resume from
        if checkpoint_id is None:
            checkpoint = query_latest_resumable_checkpoint(session_id, base_dir=telemetry_dir)
            if checkpoint is None:
                return JSONResponse(
                    content={"error": "No resumable checkpoint available"},
                    status_code=404,
                )
            checkpoint_id = checkpoint["checkpoint_id"]
        else:
            checkpoint = query_checkpoint_detail(session_id, checkpoint_id, base_dir=telemetry_dir)
            if checkpoint is None:
                return JSONResponse(
                    content={"error": f"Checkpoint not found: {checkpoint_id}"},
                    status_code=404,
                )
            if not checkpoint.get("resume_safe"):
                return JSONResponse(
                    content={"error": f"Checkpoint {checkpoint_id} is not safe to resume from"},
                    status_code=409,
                )

        # Get lineage for tracking
        lineage = query_checkpoint_lineage(session_id, checkpoint_id, base_dir=telemetry_dir)
        lineage_ids = [cp.get("checkpoint_id") for cp in lineage]

        # Note: Actual resume execution would require spawning a new research run
        # This endpoint provides the checkpoint info needed for resume
        result = ResumeResult(
            success=True,
            session_id=f"{session_id}-resumed",
            original_session_id=session_id,
            resumed_from_checkpoint_id=checkpoint_id,
            resume_mode=mode,
            checkpoint_lineage=lineage_ids,
            message=f"Ready to resume from checkpoint {checkpoint_id}. Use the checkpoint info to start a new run.",
        )

        return JSONResponse(content=result.model_dump(mode="json"))

    @app.post("/api/sessions/{session_id}/rerun-step")
    async def rerun_step(request: dict) -> JSONResponse:
        """Rerun a single step from a checkpoint in debug mode.

        Args:
            request: Dict containing session_id, checkpoint_id, and options.

        Returns:
            JSON response with rerun result.
        """
        from cc_deep_research.models.checkpoint import RerunStepRequest, RerunStepResult

        session_id = request.get("session_id")
        checkpoint_id = request.get("checkpoint_id")

        if not session_id or not checkpoint_id:
            return JSONResponse(
                content={"error": "session_id and checkpoint_id are required"},
                status_code=400,
            )

        telemetry_dir = get_default_telemetry_dir()
        checkpoint = query_checkpoint_detail(session_id, checkpoint_id, base_dir=telemetry_dir)

        if checkpoint is None:
            return JSONResponse(
                content={"error": f"Checkpoint not found: {checkpoint_id}"},
                status_code=404,
            )

        if not checkpoint.get("replayable"):
            reason = checkpoint.get("replayable_reason", "Unknown reason")
            return JSONResponse(
                content={"error": f"Checkpoint is not replayable: {reason}"},
                status_code=409,
            )

        # Note: Actual rerun execution would require reconstructing inputs
        # and executing the step. This endpoint validates and prepares for rerun.
        result = RerunStepResult(
            success=True,
            session_id=session_id,
            checkpoint_id=checkpoint_id,
            output_match=None,  # Would be determined after actual rerun
            message=f"Checkpoint {checkpoint_id} is ready for rerun. Input refs: {checkpoint.get('input_ref')}",
        )

        return JSONResponse(content=result.model_dump(mode="json"))

    @app.websocket("/ws/session/{session_id}")
    async def websocket_endpoint(websocket: WebSocket, session_id: str) -> None:
        """WebSocket endpoint for real-time event streaming.

        Args:
            websocket: The WebSocket connection.
            session_id: The session ID to subscribe to.
        """
        logger.info(
            "Accepting session websocket session_id=%s client=%s url=%s",
            session_id,
            websocket.client,
            websocket.url,
        )
        await websocket.accept()

        # Create connection wrapper
        connection = WebSocketConnection(websocket, session_id)
        event_router = get_event_router(websocket.app)

        # Subscribe to session events
        await event_router.subscribe(session_id, connection)
        logger.info(
            "Subscribed websocket session_id=%s subscribers=%s",
            session_id,
            event_router.get_subscriber_count(session_id),
        )

        # Send history on connect
        detail = _query_session_api_detail(
            session_id,
            tail_limit=100,
            subprocess_chunk_limit=0,
        )

        # Send initial history
        await connection.send_json({"type": "history", "events": detail["event_tail"] or []})
        logger.info(
            "Sent websocket history session_id=%s event_count=%s",
            session_id,
            len(detail["event_tail"] or []),
        )

        # Listen for client messages
        try:
            while True:
                data = await websocket.receive_json()

                message_type = data.get("type")
                logger.debug(
                    "Received websocket message session_id=%s type=%s payload_keys=%s",
                    session_id,
                    message_type,
                    sorted(data.keys()),
                )

                if message_type == "ping":
                    # Respond to ping with pong
                    await connection.send_json({"type": "pong"})
                elif message_type == "get_history":
                    # Send history with cursor-based pagination
                    cursor = data.get("cursor")
                    before_cursor = data.get("before_cursor")
                    limit = data.get("limit", 1000)
                    new_detail = _query_session_api_detail(
                        session_id,
                        tail_limit=limit * 2,  # Get extra for backward compat
                        subprocess_chunk_limit=0,
                        cursor=cursor,
                        before_cursor=before_cursor,
                        limit=limit,
                    )
                    # Use paginated events page if cursor-based request
                    if cursor is not None or before_cursor is not None:
                        events_page = new_detail.get("events_page", {})
                        await connection.send_json(
                            {
                                "type": "history_page",
                                "events": events_page.get("events", []),
                                "total": events_page.get("total", 0),
                                "has_more": events_page.get("has_more", False),
                                "next_cursor": events_page.get("next_cursor"),
                                "prev_cursor": events_page.get("prev_cursor"),
                            }
                        )
                        logger.info(
                            "Served paginated websocket history session_id=%s limit=%s cursor=%s before_cursor=%s returned=%s",
                            session_id,
                            limit,
                            cursor,
                            before_cursor,
                            len(events_page.get("events", [])),
                        )
                    else:
                        # Backward compat: simple tail-based history
                        await connection.send_json(
                            {
                                "type": "history",
                                "events": new_detail["event_tail"] or [],
                            }
                        )
                        logger.info(
                            "Served websocket history refresh session_id=%s limit=%s returned=%s",
                            session_id,
                            limit,
                            len(new_detail["event_tail"] or []),
                        )
                elif message_type == "subscribe":
                    # Subscribe to session (redundant but explicit)
                    await event_router.subscribe(session_id, connection)
                    logger.info("Received websocket subscribe session_id=%s", session_id)
                elif message_type == "unsubscribe":
                    # Unsubscribe from session
                    await event_router.unsubscribe(session_id, connection)
                    logger.info("Received websocket unsubscribe session_id=%s", session_id)
                else:
                    logger.warning(
                        "Received unsupported websocket message session_id=%s type=%s payload=%s",
                        session_id,
                        message_type,
                        data,
                    )

        except WebSocketDisconnect as exc:
            # Client disconnected
            logger.info(
                "WebSocket disconnected session_id=%s code=%s",
                session_id,
                exc.code,
            )
            await event_router.unsubscribe(session_id, connection)
        except Exception as e:
            # Error occurred
            logger.exception("WebSocket session handler failed session_id=%s", session_id)
            await event_router.unsubscribe(session_id, connection)
            with suppress(Exception):
                await connection.send_json({"type": "error", "error": str(e)})
        finally:
            logger.info(
                "WebSocket handler finished session_id=%s subscribers=%s",
                session_id,
                event_router.get_subscriber_count(session_id),
            )

    # Search Cache Management Routes

    @app.get("/api/search-cache")
    async def list_search_cache_entries(
        include_expired: bool = Query(default=False, description="Include expired entries"),
        limit: int = Query(default=100, ge=1, le=500),
        offset: int = Query(default=0, ge=0),
    ) -> JSONResponse:
        """List search cache entries.

        Args:
            include_expired: Whether to include expired entries.
            limit: Maximum entries to return.
            offset: Number of entries to skip.

        Returns:
            JSON response with cache entries list.
        """
        config = load_config()
        if not config.search_cache.enabled:
            return JSONResponse(
                content={"entries": [], "total": 0, "message": "Cache is disabled"},
            )

        db_path = config.search_cache.resolve_db_path()
        if not db_path.exists():
            return JSONResponse(
                content={"entries": [], "total": 0},
            )

        store = SearchCacheStore(db_path, max_entries=config.search_cache.max_entries)
        entries = store.list_entries(
            include_expired=include_expired,
            limit=limit,
            offset=offset,
        )

        return JSONResponse(
            content={
                "entries": [
                    {
                        "cache_key": entry.cache_key,
                        "provider": entry.provider,
                        "normalized_query": entry.normalized_query,
                        "created_at": entry.created_at.isoformat(),
                        "expires_at": entry.expires_at.isoformat(),
                        "last_accessed_at": entry.last_accessed_at.isoformat(),
                        "hit_count": entry.hit_count,
                        "is_expired": entry.is_expired(),
                    }
                    for entry in entries
                ],
                "total": len(entries),
            }
        )

    @app.get("/api/search-cache/stats")
    async def get_search_cache_stats() -> JSONResponse:
        """Get search cache statistics.

        Returns:
            JSON response with cache stats including entry counts and hit totals.
        """
        config = load_config()
        cache_enabled = config.search_cache.enabled
        db_path = config.search_cache.resolve_db_path()

        response: dict[str, Any] = {
            "enabled": cache_enabled,
            "db_path": str(db_path),
            "ttl_seconds": config.search_cache.ttl_seconds,
            "max_entries": config.search_cache.max_entries,
        }

        if not cache_enabled:
            response.update({
                "total_entries": 0,
                "active_entries": 0,
                "expired_entries": 0,
                "total_hits": 0,
                "approximate_size_bytes": 0,
                "db_exists": False,
            })
            return JSONResponse(content=response)

        if not db_path.exists():
            response.update({
                "total_entries": 0,
                "active_entries": 0,
                "expired_entries": 0,
                "total_hits": 0,
                "approximate_size_bytes": 0,
                "db_exists": False,
            })
            return JSONResponse(content=response)

        store = SearchCacheStore(db_path, max_entries=config.search_cache.max_entries)
        stats = store.get_stats()
        response.update(stats)
        response["db_exists"] = True

        return JSONResponse(content=response)

    @app.post("/api/search-cache/purge-expired")
    async def purge_expired_search_cache_entries() -> JSONResponse:
        """Purge expired entries from the search cache.

        Returns:
            JSON response with count of purged entries.
        """
        config = load_config()
        if not config.search_cache.enabled:
            return JSONResponse(
                content={"error": "Cache is disabled", "purged": 0},
                status_code=400,
            )

        db_path = config.search_cache.resolve_db_path()
        if not db_path.exists():
            return JSONResponse(
                content={"error": "Cache database not found", "purged": 0},
                status_code=404,
            )

        store = SearchCacheStore(db_path, max_entries=config.search_cache.max_entries)
        purged = store.purge_expired()

        return JSONResponse(
            content={
                "purged": purged,
                "message": f"Purged {purged} expired entries",
            }
        )

    @app.delete("/api/search-cache/{cache_key}")
    async def delete_search_cache_entry(cache_key: str) -> JSONResponse:
        """Delete a specific cache entry.

        Args:
            cache_key: The cache key to delete.

        Returns:
            JSON response indicating success or failure.
        """
        config = load_config()
        if not config.search_cache.enabled:
            return JSONResponse(
                content={"error": "Cache is disabled", "deleted": False},
                status_code=400,
            )

        db_path = config.search_cache.resolve_db_path()
        if not db_path.exists():
            return JSONResponse(
                content={"error": "Cache database not found", "deleted": False},
                status_code=404,
            )

        store = SearchCacheStore(db_path, max_entries=config.search_cache.max_entries)
        deleted = store.delete(cache_key)

        if not deleted:
            return JSONResponse(
                content={"error": f"Entry not found: {cache_key}", "deleted": False},
                status_code=404,
            )

        return JSONResponse(
            content={
                "cache_key": cache_key,
                "deleted": True,
            }
        )

    @app.delete("/api/search-cache")
    async def clear_search_cache() -> JSONResponse:
        """Clear all entries from the search cache.

        Returns:
            JSON response with count of cleared entries.
        """
        config = load_config()
        if not config.search_cache.enabled:
            return JSONResponse(
                content={"error": "Cache is disabled", "cleared": 0},
                status_code=400,
            )

        db_path = config.search_cache.resolve_db_path()
        if not db_path.exists():
            return JSONResponse(
                content={"cleared": 0, "message": "Cache database does not exist"},
            )

        store = SearchCacheStore(db_path, max_entries=config.search_cache.max_entries)
        cleared = store.clear()

        return JSONResponse(
            content={
                "cleared": cleared,
                "message": f"Cleared {cleared} entries from cache",
            }
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
        ws="websockets-sansio",
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
