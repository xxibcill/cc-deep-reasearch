"""Research run HTTP API routes."""

from __future__ import annotations

import asyncio
import json
import logging
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from typing import Any, cast
from uuid import uuid4

from fastapi import FastAPI
from fastapi.responses import JSONResponse

from cc_deep_research.llm.runtime_context import llm_request_scope
from cc_deep_research.models import ResearchSession
from cc_deep_research.research_runs.jobs import ResearchRunJob
from cc_deep_research.research_runs.models import (
    ResearchOutputFormat,
    ResearchRunCancelled,
    ResearchRunRequest,
    ResearchRunResult,
    ResearchRunStatus,
)
from cc_deep_research.research_runs.recovery import (
    RecoveryAttempt,
    RecoveryOutcome,
    RecoveryStrategy,
    build_alternate_recovery_request,
    finalize_recovery_result,
    is_retriable_failure,
    is_terminal_failure,
    load_latest_recovery_checkpoint,
    materialize_failure_result,
    safe_failure_reason,
)
from cc_deep_research.research_runs.resume import ResearchResumeState
from cc_deep_research.telemetry import (
    get_default_telemetry_dir,
    query_live_session_detail,
)
from cc_deep_research.web_runtime import get_event_router, get_job_registry
from cc_deep_research.web_server_routes._shared import parse_timestamp

STALE_LIVE_SESSION_AFTER = timedelta(minutes=15)
RUN_CANCELLED_MESSAGE = "Research run was cancelled by the operator."
RECOVERY_FAILURE_MESSAGE = (
    "Research run did not complete; automatic recovery preserved a final report."
)
logger = logging.getLogger(__name__)


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
    created_at_dt = parse_timestamp(created_at)
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


def _media_type_for_report(output_format: ResearchOutputFormat) -> str:
    """Return the response media type for one report format."""
    if output_format == ResearchOutputFormat.JSON:
        return "application/json"
    if output_format == ResearchOutputFormat.HTML:
        return "text/html"
    return "text/markdown"


async def _execute_service_attempt(
    service: Any,
    *,
    request: ResearchRunRequest,
    resume_state: Any | None,
    event_router: Any,
    cancellation_check: Callable[[], None],
    on_session_started: Callable[[str], None],
) -> ResearchRunResult:
    """Run one fresh or resumed service attempt without blocking the event loop."""
    if resume_state is not None:
        return cast(
            "ResearchRunResult",
            await asyncio.to_thread(
                service.resume,
                resume_state,
                event_router=event_router,
                cancellation_check=cancellation_check,
                on_session_started=on_session_started,
            ),
        )
    return cast(
        "ResearchRunResult",
        await asyncio.to_thread(
            service.run,
            request,
            event_router=event_router,
            cancellation_check=cancellation_check,
            on_session_started=on_session_started,
        ),
    )


def _materialize_terminal_failure(
    service: Any,
    job: ResearchRunJob,
    failure_reasons: list[str],
    *,
    preserved_session: ResearchSession | None = None,
    recovery_state: ResearchResumeState | None = None,
) -> ResearchRunResult:
    """Create a dependency-free final report after execution recovery is exhausted."""
    custom_materializer = getattr(service, "materialize_failure_result", None)
    if callable(custom_materializer):
        try:
            return cast(
                "ResearchRunResult",
                custom_materializer(
                    job.request,
                    session_id=job.session_id,
                    failure_reasons=failure_reasons,
                ),
            )
        except Exception as error:  # pragma: no cover - custom integration boundary
            logger.exception("Custom terminal report materialization failed")
            failure_reasons.append(safe_failure_reason("Terminal report", error))

    return materialize_failure_result(
        job.request,
        session_id=job.session_id,
        failure_reasons=failure_reasons,
        preserved_session=preserved_session,
        recovery_state=recovery_state,
    )


async def _finalize_recovery(
    result: ResearchRunResult,
    *,
    attempts: list[RecoveryAttempt],
    failure_reasons: list[str],
) -> ResearchRunResult:
    """Persist automatic-recovery provenance without blocking the event loop."""
    return await asyncio.to_thread(
        finalize_recovery_result,
        result,
        attempts=attempts,
        failure_reasons=failure_reasons,
    )


async def _execute_with_automatic_recovery(
    service: Any,
    job: ResearchRunJob,
    *,
    resume_state: ResearchResumeState | None,
    event_router: Any,
    cancellation_check: Callable[[], None],
    on_session_started: Callable[[str], None],
) -> ResearchRunResult:
    """Execute a bounded checkpoint/alternate recovery policy for one job."""
    attempts: list[RecoveryAttempt] = []
    failure_reasons: list[str] = []
    initial_exception: Exception | None = None
    partial_session: ResearchSession | None = None
    recovery_evidence = resume_state

    try:
        initial_result = await _execute_service_attempt(
            service,
            request=job.request,
            resume_state=resume_state,
            event_router=event_router,
            cancellation_check=cancellation_check,
            on_session_started=on_session_started,
        )
    except (ResearchRunCancelled, asyncio.CancelledError):
        raise
    except Exception as error:
        initial_exception = error
        failure_reasons.append(safe_failure_reason("Initial execution", error))
        if not is_retriable_failure(error):
            failed_result = await asyncio.to_thread(
                _materialize_terminal_failure,
                service,
                job,
                failure_reasons,
                recovery_state=recovery_evidence,
            )
            return await _finalize_recovery(
                failed_result,
                attempts=attempts,
                failure_reasons=failure_reasons,
            )
    else:
        if not is_terminal_failure(initial_result):
            return initial_result
        partial_session = initial_result.session
        failure_reasons.append("Initial execution returned terminal status 'failed'.")

    if initial_exception is not None:
        checkpoint_session_id = job.session_id or job.original_session_id
        checkpoint = None
        if checkpoint_session_id is not None:
            try:
                checkpoint = await asyncio.to_thread(
                    load_latest_recovery_checkpoint,
                    checkpoint_session_id,
                )
            except Exception as error:
                logger.exception(
                    "Automatic checkpoint discovery failed for session %s",
                    checkpoint_session_id,
                )
                failure_reasons.append(
                    safe_failure_reason("Checkpoint discovery", error)
                )

        if checkpoint is not None:
            recovery_evidence = checkpoint.state
            _raise_if_run_cancelled(job)
            logger.info(
                "Automatically resuming research run %s from checkpoint %s",
                job.run_id,
                checkpoint.checkpoint_id,
            )
            try:
                checkpoint_result = await _execute_service_attempt(
                    service,
                    request=job.request,
                    resume_state=checkpoint.state,
                    event_router=event_router,
                    cancellation_check=cancellation_check,
                    on_session_started=on_session_started,
                )
            except (ResearchRunCancelled, asyncio.CancelledError):
                raise
            except Exception as error:
                reason = safe_failure_reason("Checkpoint resume", error)
                failure_reasons.append(reason)
                attempts.append(
                    RecoveryAttempt(
                        strategy=RecoveryStrategy.CHECKPOINT_RESUME,
                        outcome=RecoveryOutcome.FAILED,
                        session_id=checkpoint.session_id,
                        checkpoint_id=checkpoint.checkpoint_id,
                        reason=reason,
                    )
                )
            else:
                if is_terminal_failure(checkpoint_result):
                    partial_session = checkpoint_result.session
                    reason = "Checkpoint resume returned terminal status 'failed'."
                    failure_reasons.append(reason)
                    attempts.append(
                        RecoveryAttempt(
                            strategy=RecoveryStrategy.CHECKPOINT_RESUME,
                            outcome=RecoveryOutcome.FAILED,
                            session_id=checkpoint_result.session_id,
                            checkpoint_id=checkpoint.checkpoint_id,
                            reason=reason,
                        )
                    )
                else:
                    attempts.append(
                        RecoveryAttempt(
                            strategy=RecoveryStrategy.CHECKPOINT_RESUME,
                            outcome=RecoveryOutcome.COMPLETED,
                            session_id=checkpoint_result.session_id,
                            checkpoint_id=checkpoint.checkpoint_id,
                        )
                    )
                    return await _finalize_recovery(
                        checkpoint_result,
                        attempts=attempts,
                        failure_reasons=failure_reasons,
                    )

    _raise_if_run_cancelled(job)
    alternate_request = build_alternate_recovery_request(job.request)
    logger.info(
        "Retrying research run %s with workflow=%s provider=%s and sequential collection",
        job.run_id,
        alternate_request.workflow.value,
        alternate_request.search_providers,
    )
    try:
        alternate_result = await _execute_service_attempt(
            service,
            request=alternate_request,
            resume_state=None,
            event_router=event_router,
            cancellation_check=cancellation_check,
            on_session_started=on_session_started,
        )
    except (ResearchRunCancelled, asyncio.CancelledError):
        raise
    except Exception as error:
        reason = safe_failure_reason("Alternate execution", error)
        failure_reasons.append(reason)
        attempts.append(
            RecoveryAttempt(
                strategy=RecoveryStrategy.ALTERNATE_EXECUTION,
                outcome=RecoveryOutcome.FAILED,
                session_id=job.session_id,
                reason=reason,
            )
        )
        failed_result = await asyncio.to_thread(
            _materialize_terminal_failure,
            service,
            job,
            failure_reasons,
            preserved_session=partial_session,
            recovery_state=recovery_evidence,
        )
        return await _finalize_recovery(
            failed_result,
            attempts=attempts,
            failure_reasons=failure_reasons,
        )

    if is_terminal_failure(alternate_result):
        reason = "Alternate execution returned terminal status 'failed'."
        failure_reasons.append(reason)
        attempts.append(
            RecoveryAttempt(
                strategy=RecoveryStrategy.ALTERNATE_EXECUTION,
                outcome=RecoveryOutcome.FAILED,
                session_id=alternate_result.session_id,
                reason=reason,
            )
        )
    else:
        attempts.append(
            RecoveryAttempt(
                strategy=RecoveryStrategy.ALTERNATE_EXECUTION,
                outcome=RecoveryOutcome.COMPLETED,
                session_id=alternate_result.session_id,
            )
        )
    return await _finalize_recovery(
        alternate_result,
        attempts=attempts,
        failure_reasons=failure_reasons,
    )


async def _execute_research_run(
    app: FastAPI,
    job: ResearchRunJob,
    *,
    resume_state: ResearchResumeState | None = None,
) -> None:
    """Execute a new or resumed run and persist its lifecycle transitions."""
    from cc_deep_research.web_server import ResearchRunService, get_backend_runtime

    job_registry = get_job_registry(app)
    event_router = get_event_router(app)
    service = ResearchRunService(
        codex_runtime=get_backend_runtime(app).codex_runtime,
    )
    try:
        if job.stop_requested:
            job_registry.mark_cancelled(job.run_id, error=RUN_CANCELLED_MESSAGE)
            return
        job_registry.mark_running(job.run_id)

        def cancellation_check() -> None:
            _raise_if_run_cancelled(job)

        on_session_started = cast(
            "Callable[[str], None]",
            lambda session_id: job_registry.set_session_id(
                job.run_id, session_id=session_id
            ),
        )
        result = await _execute_with_automatic_recovery(
            service,
            job,
            resume_state=resume_state,
            event_router=event_router,
            cancellation_check=cancellation_check,
            on_session_started=on_session_started,
        )
        if is_terminal_failure(result):
            job_registry.mark_failed(
                job.run_id,
                error=RECOVERY_FAILURE_MESSAGE,
                result=result,
            )
        else:
            job_registry.mark_completed(job.run_id, result=result)
    except ResearchRunCancelled:
        if job.session_id:
            _interrupt_live_session(job.session_id)
        job_registry.mark_cancelled(job.run_id, error=RUN_CANCELLED_MESSAGE)
    except asyncio.CancelledError:
        if job.session_id:
            _interrupt_live_session(job.session_id)
        job_registry.mark_cancelled(job.run_id, error=RUN_CANCELLED_MESSAGE)
    except Exception as exc:
        logger.exception("Research run %s failed", job.run_id)
        failure_reasons = [safe_failure_reason("Recovery controller", exc)]
        try:
            result = await asyncio.to_thread(
                materialize_failure_result,
                job.request,
                session_id=job.session_id,
                failure_reasons=failure_reasons,
            )
            result = await _finalize_recovery(
                result,
                attempts=[],
                failure_reasons=failure_reasons,
            )
        except Exception:
            logger.exception("Unable to create a terminal report for run %s", job.run_id)
            job_registry.mark_failed(job.run_id, error=RECOVERY_FAILURE_MESSAGE)
        else:
            job_registry.mark_failed(
                job.run_id,
                error=RECOVERY_FAILURE_MESSAGE,
                result=result,
            )


def queue_research_run(
    app: FastAPI,
    job: ResearchRunJob,
    *,
    resume_state: ResearchResumeState | None = None,
) -> None:
    """Schedule one research job on the active application event loop."""
    job_registry = get_job_registry(app)
    with llm_request_scope(job.run_id):
        task = asyncio.create_task(
            _execute_research_run(app, job, resume_state=resume_state)
        )
    job_registry.attach_task(job.run_id, task)


async def queue_interrupted_research_run_recoveries(app: FastAPI) -> None:
    """Queue one idempotent checkpoint resume for each restart-interrupted job."""
    job_registry = get_job_registry(app)
    for interrupted_job in job_registry.interrupted_restart_jobs():
        session_id = interrupted_job.session_id or interrupted_job.original_session_id
        if session_id is None:
            continue

        try:
            checkpoint = await asyncio.to_thread(
                load_latest_recovery_checkpoint,
                session_id,
            )
        except Exception:
            logger.exception(
                "Unable to inspect restart recovery checkpoints for run %s",
                interrupted_job.run_id,
            )
            continue
        if checkpoint is None:
            continue

        reservation = job_registry.reserve_resume_job(
            interrupted_job,
            checkpoint_id=checkpoint.checkpoint_id,
            idempotency_key=(
                f"automatic-restart:{interrupted_job.run_id}:{checkpoint.checkpoint_id}"
            ),
        )
        if not reservation.created:
            continue
        queue_research_run(
            app,
            reservation.job,
            resume_state=checkpoint.state,
        )


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
        job_registry = get_job_registry(app)

        # Create job entry in registry
        job = job_registry.create_job(request)

        queue_research_run(app, job)

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
            "original_run_id": job.original_run_id,
            "original_session_id": job.original_session_id,
            "resumed_from_checkpoint_id": job.resumed_from_checkpoint_id,
            "resume_attempt": job.resume_attempt,
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
        elif job.result_metadata is not None:
            response["result"] = job.result_metadata

        return JSONResponse(content=response)

    @app.post("/api/research-runs/{run_id}/stop")
    async def stop_research_run(run_id: str) -> JSONResponse:
        """Request cancellation of an in-process browser-started run."""
        from cc_deep_research.web_server import get_backend_runtime

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
        get_backend_runtime(app).codex_runtime.request_cancel_scope(run_id)

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
