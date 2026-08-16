"""Bounded execution controller for automatic research-run recovery."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Callable
from typing import Any, cast

from cc_deep_research.models import ResearchSession
from cc_deep_research.research_runs.jobs import ResearchRunJob
from cc_deep_research.research_runs.models import (
    ResearchRunCancelled,
    ResearchRunRequest,
    ResearchRunResult,
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
    merge_research_session_evidence,
    safe_failure_reason,
)
from cc_deep_research.research_runs.resume import ResearchResumeState

logger = logging.getLogger(__name__)
RECOVERY_FAILURE_MESSAGE = (
    "Research run did not complete; automatic recovery preserved a final report."
)


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


async def finalize_recovery_result_async(
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


async def execute_with_automatic_recovery(
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
            return await finalize_recovery_result_async(
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
                failure_reasons.append(safe_failure_reason("Checkpoint discovery", error))

        if checkpoint is not None:
            recovery_evidence = checkpoint.state
            cancellation_check()
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
                    partial_session = merge_research_session_evidence(
                        partial_session,
                        checkpoint_result.session,
                    )
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
                    return await finalize_recovery_result_async(
                        checkpoint_result,
                        attempts=attempts,
                        failure_reasons=failure_reasons,
                    )

    cancellation_check()
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
        return await finalize_recovery_result_async(
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
        failed_result = await asyncio.to_thread(
            _materialize_terminal_failure,
            service,
            job,
            failure_reasons,
            preserved_session=merge_research_session_evidence(
                partial_session,
                alternate_result.session,
            ),
            recovery_state=recovery_evidence,
        )
        return await finalize_recovery_result_async(
            failed_result,
            attempts=attempts,
            failure_reasons=failure_reasons,
        )

    attempts.append(
        RecoveryAttempt(
            strategy=RecoveryStrategy.ALTERNATE_EXECUTION,
            outcome=RecoveryOutcome.COMPLETED,
            session_id=alternate_result.session_id,
        )
    )
    return await finalize_recovery_result_async(
        alternate_result,
        attempts=attempts,
        failure_reasons=failure_reasons,
    )


__all__ = [
    "RECOVERY_FAILURE_MESSAGE",
    "execute_with_automatic_recovery",
    "finalize_recovery_result_async",
]
