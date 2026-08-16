"""Startup scheduling for research runs interrupted by a backend restart."""

from __future__ import annotations

import asyncio
import logging

from fastapi import FastAPI

from cc_deep_research.research_runs.jobs import ResearchRunJob, ResearchRunJobRegistry
from cc_deep_research.research_runs.recovery import (
    load_latest_recovery_checkpoint,
    materialize_failure_result,
)
from cc_deep_research.research_runs.recovery_controller import (
    RECOVERY_FAILURE_MESSAGE,
    finalize_recovery_result_async,
)
from cc_deep_research.web_runtime import get_job_registry

logger = logging.getLogger(__name__)


async def _materialize_restart_failure(
    job_registry: ResearchRunJobRegistry,
    job: ResearchRunJob,
    *,
    reason: str,
) -> None:
    """Attach a final degraded report when restart recovery cannot resume."""
    failure_reasons = [reason]
    try:
        result = await asyncio.to_thread(
            materialize_failure_result,
            job.request,
            session_id=job.session_id or job.original_session_id,
            failure_reasons=failure_reasons,
        )
        result = await finalize_recovery_result_async(
            result,
            attempts=[],
            failure_reasons=failure_reasons,
        )
    except Exception:
        logger.exception("Unable to materialize restart failure for run %s", job.run_id)
        return

    job_registry.mark_failed(
        job.run_id,
        error=RECOVERY_FAILURE_MESSAGE,
        result=result,
    )


async def queue_interrupted_research_run_recoveries(app: FastAPI) -> None:
    """Queue one idempotent checkpoint resume for each restart-interrupted job."""
    from cc_deep_research.web_server_routes.research_run_routes import queue_research_run

    job_registry = get_job_registry(app)
    for interrupted_job in job_registry.interrupted_restart_jobs():
        session_id = interrupted_job.session_id or interrupted_job.original_session_id
        if session_id is None:
            await _materialize_restart_failure(
                job_registry,
                interrupted_job,
                reason=(
                    "Backend restart interrupted execution before a session checkpoint "
                    "was available."
                ),
            )
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
            await _materialize_restart_failure(
                job_registry,
                interrupted_job,
                reason="Restart checkpoint discovery failed.",
            )
            continue
        if checkpoint is None:
            await _materialize_restart_failure(
                job_registry,
                interrupted_job,
                reason=(
                    "Backend restart interrupted execution before a valid recovery "
                    "checkpoint was available."
                ),
            )
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


__all__ = ["queue_interrupted_research_run_recoveries"]
