"""Research run HTTP API routes."""

from __future__ import annotations

import asyncio
import json
import logging
from datetime import UTC, datetime, timedelta
from typing import Any, cast
from uuid import uuid4

from fastapi import FastAPI, Query
from fastapi.responses import JSONResponse

from cc_deep_research.config import load_config
from cc_deep_research.event_router import EventRouter
from cc_deep_research.reporting import ReportGenerator
from cc_deep_research.research_runs.jobs import ResearchRunJob, ResearchRunJobRegistry
from cc_deep_research.research_runs.models import (
    ResearchOutputFormat,
    ResearchRunCancelled,
    ResearchRunRequest,
    ResearchRunStatus,
)
from cc_deep_research.research_runs.service import ResearchRunService  # noqa: F401
from cc_deep_research.session_store import SessionStore
from cc_deep_research.telemetry import (
    get_default_telemetry_dir,
    query_live_session_detail,
)

STALE_LIVE_SESSION_AFTER = timedelta(minutes=15)
RUN_CANCELLED_MESSAGE = "Research run was cancelled by the operator."
logger = logging.getLogger(__name__)


def _serialize_timestamp(value: Any) -> str | None:
    """Return a JSON-safe timestamp string."""
    if value is None:
        return None
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return str(value)


def _raise_if_run_cancelled(job: ResearchRunJob) -> None:
    """Raise the shared cancellation error when a run stop has been requested."""
    if job.stop_requested:
        raise ResearchRunCancelled(RUN_CANCELLED_MESSAGE)


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


def _media_type_for_report(output_format: ResearchOutputFormat) -> str:
    """Return the response media type for one report format."""
    if output_format == ResearchOutputFormat.JSON:
        return "application/json"
    if output_format == ResearchOutputFormat.HTML:
        return "text/html"
    return "text/markdown"


def register_research_run_routes(app: FastAPI) -> None:
    """Register research run HTTP API routes.

    Args:
        app: The FastAPI application instance.
    """

    @app.post("/api/research-runs")
    async def start_research_run(request: ResearchRunRequest) -> JSONResponse:
        """Start a new research run from the browser.

        Args:
            request: The research run request parameters.

        Returns:
            JSON response with run_id for status polling.
        """
        from cc_deep_research.web_server import get_event_router, get_job_registry

        job_registry = get_job_registry(app)
        event_router = get_event_router(app)

        # Create job entry in registry
        job = job_registry.create_job(request)

        # Define background execution coroutine
        async def execute_research_run(job: ResearchRunJob) -> None:
            """Execute the research run and update job status in a thread."""
            # Import from web_server to support monkeypatching in tests
            from cc_deep_research.web_server import ResearchRunService
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
        from cc_deep_research.web_server import get_job_registry

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
        from cc_deep_research.web_server import get_job_registry

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
