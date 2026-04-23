"""Pipeline run service: orchestrates pipeline start/stop/resume/status.

This module extracts pipeline orchestration logic from the FastAPI route handlers,
making the logic testable outside of route handlers.

The service is responsible for:
- Creating and tracking pipeline jobs
- Publishing progress events via EventRouter
- Managing job lifecycle (start, stop, cancel, complete, fail)
- Handling seeded backlog item starts
- Preserving WebSocket progress behavior
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from cc_deep_research.config import Config, load_config
from cc_deep_research.content_gen.models import (
    PIPELINE_STAGE_LABELS,
    PIPELINE_STAGES,
    BacklogItem,
    PipelineContext,
    RunConstraints,
)
from cc_deep_research.content_gen.progress import PipelineRunJob, PipelineRunJobRegistry
from cc_deep_research.event_router import EventRouter

if TYPE_CHECKING:
    from cc_deep_research.content_gen.orchestrator import ContentGenOrchestrator


logger = logging.getLogger(__name__)


class PipelineRunServiceError(Exception):
    """Base exception for pipeline run service errors."""


class PipelineNotFoundError(PipelineRunServiceError):
    """Raised when a pipeline is not found."""


class PipelineNotActiveError(PipelineRunServiceError):
    """Raised when an operation requires an active pipeline but it's not active."""


class DuplicateActiveItemError(PipelineRunServiceError):
    """Raised when a backlog item already has an active pipeline."""

    def __init__(self, message: str, pipeline_id: str) -> None:
        super().__init__(message)
        self.pipeline_id = pipeline_id


class ResumeContextError(PipelineRunServiceError):
    """Raised when resume validation fails."""


class _PipelineCancelled(Exception):
    """Internal sentinel to break out of the orchestrator progress loop."""


@dataclass
class PipelineRunResult:
    """Result of a pipeline run operation."""

    pipeline_id: str
    theme: str
    from_stage: int
    to_stage: int | None
    status: str
    current_stage: int
    error: str | None
    created_at: datetime
    started_at: datetime | None
    completed_at: datetime | None


def _job_summary(job: PipelineRunJob) -> dict[str, Any]:
    """Serialize a pipeline job into a JSON-friendly summary."""
    return {
        "pipeline_id": job.pipeline_id,
        "theme": job.theme,
        "from_stage": job.from_stage,
        "to_stage": job.to_stage,
        "status": str(job.status),
        "current_stage": (
            job.pipeline_context.current_stage if job.pipeline_context else job.from_stage
        ),
        "error": job.error,
        "created_at": job.created_at.isoformat(),
        "started_at": job.started_at.isoformat() if job.started_at else None,
        "completed_at": job.completed_at.isoformat() if job.completed_at else None,
    }


class PipelineRunService:
    """Service for managing pipeline runs.

    This service encapsulates pipeline orchestration logic, separating it from
    HTTP route handlers. It manages job lifecycle, progress events, and
    cancellation behavior.

    Args:
        job_registry: Registry for tracking pipeline jobs.
        event_router: Router for publishing progress events.
        pipeline_factory: Factory for creating pipeline orchestrators.
            If None, creates ContentGenOrchestrator instances.
    """

    def __init__(
        self,
        job_registry: PipelineRunJobRegistry,
        event_router: EventRouter,
        pipeline_factory: Callable[[Config], ContentGenOrchestrator] | None = None,
    ) -> None:
        self._job_registry = job_registry
        self._event_router = event_router
        self._pipeline_factory = pipeline_factory or self._default_pipeline_factory

    def _default_pipeline_factory(self, config: Config) -> ContentGenOrchestrator:
        from cc_deep_research.content_gen.orchestrator import ContentGenOrchestrator

        return ContentGenOrchestrator(config)

    # -------------------------------------------------------------------------
    # Public API
    # -------------------------------------------------------------------------

    def list_pipelines(self) -> list[dict[str, Any]]:
        """List all pipeline jobs."""
        jobs = self._job_registry.list_jobs()
        return [_job_summary(job) for job in jobs]

    def get_pipeline_status(self, pipeline_id: str) -> dict[str, Any] | None:
        """Get the status of a pipeline.

        Returns None if the pipeline is not found.
        """
        job = self._job_registry.get_job(pipeline_id)
        if job is None:
            return None
        result = _job_summary(job)
        if job.pipeline_context is not None:
            import json

            result["context"] = json.loads(job.pipeline_context.model_dump_json())
        return result

    def stop_pipeline(self, pipeline_id: str) -> dict[str, Any]:
        """Request cancellation of an active pipeline.

        Raises:
            PipelineNotFoundError: If the pipeline does not exist.
            PipelineNotActiveError: If the pipeline is not currently active.
        """
        job = self._job_registry.get_job(pipeline_id)
        if job is None:
            raise PipelineNotFoundError(f"Pipeline not found: {pipeline_id}")
        if not job.is_active:
            raise PipelineNotActiveError(f"Pipeline is not active: {pipeline_id}")
        self._job_registry.request_cancel(pipeline_id)
        return {"pipeline_id": pipeline_id, "status": "cancelling"}

    def start_pipeline(
        self,
        theme: str,
        *,
        from_stage: int = 0,
        to_stage: int | None = None,
        run_constraints: RunConstraints | None = None,
    ) -> PipelineRunResult:
        """Start a new pipeline run.

        Args:
            theme: The research/theme for the pipeline.
            from_stage: Stage to start from (default 0).
            to_stage: Stage to end at (default last stage).
            run_constraints: Optional run constraints.

        Returns:
            PipelineRunResult with the created job details.
        """
        config = load_config()
        end = to_stage if to_stage is not None else len(PIPELINE_STAGES) - 1

        job = self._job_registry.create_job(
            theme=theme,
            from_stage=from_stage,
            to_stage=end,
        )

        self._start_pipeline_task(job, config, run_constraints=run_constraints)
        return self._job_to_result(job)

    def resume_pipeline(
        self,
        pipeline_id: str,
        *,
        from_stage: int = 0,
    ) -> PipelineRunResult:
        """Resume a completed or failed pipeline.

        Args:
            pipeline_id: ID of the pipeline to resume.
            from_stage: Stage to resume from.

        Raises:
            PipelineNotFoundError: If the pipeline does not exist.
            PipelineNotActiveError: If the pipeline is currently active.
            ResumeContextError: If the pipeline has no saved context or
                validation fails.
        """
        job = self._job_registry.get_job(pipeline_id)
        if job is None:
            raise PipelineNotFoundError(f"Pipeline not found: {pipeline_id}")
        if job.is_active:
            raise PipelineNotActiveError(f"Pipeline is already active: {pipeline_id}")

        ctx = job.pipeline_context
        if ctx is None:
            raise ResumeContextError("No saved context to resume")

        config = load_config()
        end = job.to_stage if job.to_stage is not None else len(PIPELINE_STAGES) - 1


        orch = self._pipeline_factory(config)
        resume_error = orch.validate_resume_context(from_stage=from_stage, ctx=ctx)
        if resume_error:
            raise ResumeContextError(resume_error)

        # Create a distinct job for each resume attempt so concurrent retries
        # cannot overwrite one another in the registry.
        new_job = self._job_registry.create_resume_job(
            pipeline_id,
            theme=job.theme,
            from_stage=from_stage,
            to_stage=end,
        )
        # Clone the context so the original failed job's snapshot stays stable
        # while the resumed run mutates its own copy.
        self._job_registry.update_context(new_job.pipeline_id, ctx.model_copy(deep=True))

        self._start_resume_pipeline_task(new_job, config, ctx, orch)
        return self._job_to_result(new_job)

    def start_from_backlog_item(
        self,
        item: BacklogItem,
    ) -> PipelineRunResult:
        """Start a pipeline seeded from a backlog item.

        This starts the pipeline at stage 4 (generate_angles) with a
        seeded context containing the backlog item as the primary candidate.

        Args:
            item: The backlog item to start from.

        Raises:
            DuplicateActiveItemError: If the backlog item already has an active pipeline.
        """
        # Check for duplicate active run
        for job in self._job_registry.active_jobs():
            if (
                job.pipeline_context is not None
                and job.pipeline_context.selected_idea_id == item.idea_id
            ):
                raise DuplicateActiveItemError(
                    "Backlog item is already in an active pipeline",
                    pipeline_id=job.pipeline_id,
                )

        config = load_config()
        end = len(PIPELINE_STAGES) - 1
        theme = item.source_theme or item.title or item.idea

        job = self._job_registry.create_job(
            theme=theme,
            from_stage=4,
            to_stage=end,
        )

        # Build seeded context with the single backlog item as primary candidate
        ctx = self._build_seeded_context_from_backlog_item(job.pipeline_id, item)
        self._job_registry.update_context(job.pipeline_id, ctx)

        self._start_backlog_item_pipeline_task(job, config, ctx)
        return self._job_to_result(job)

    # -------------------------------------------------------------------------
    # Internal helpers
    # -------------------------------------------------------------------------

    def _start_pipeline_task(
        self,
        job: PipelineRunJob,
        config: Config,
        *,
        run_constraints: RunConstraints | None = None,
    ) -> None:
        """Start the asyncio task for a new pipeline run."""

        async def _run() -> None:
            orch = self._pipeline_factory(config)
            self._job_registry.mark_running(job.pipeline_id)

            def _progress(stage_idx: int, label: str) -> None:
                if job.stop_requested:
                    raise _PipelineCancelled(job.pipeline_id)
                asyncio.get_running_loop().create_task(
                    self._event_router.publish(
                        job.pipeline_id,
                        {
                            "type": "pipeline_stage_started",
                            "stage_index": stage_idx,
                            "stage_label": label,
                            "timestamp": datetime.now(UTC).isoformat(),
                        },
                    )
                )

            def _stage_completed(stage_idx: int, status: str, detail: str, stage_ctx) -> None:
                self._job_registry.update_context(job.pipeline_id, stage_ctx)
                serialized_context = stage_ctx.model_dump(mode="json")

                if status == "failed":
                    asyncio.get_running_loop().create_task(
                        self._event_router.publish(
                            job.pipeline_id,
                            {
                                "type": "pipeline_stage_failed",
                                "stage_index": stage_idx,
                                "stage_label": PIPELINE_STAGE_LABELS.get(
                                    PIPELINE_STAGES[stage_idx], ""
                                ),
                                "error": detail,
                                "context": serialized_context,
                                "timestamp": datetime.now(UTC).isoformat(),
                            },
                        )
                    )
                elif status == "skipped":
                    asyncio.get_running_loop().create_task(
                        self._event_router.publish(
                            job.pipeline_id,
                            {
                                "type": "pipeline_stage_skipped",
                                "stage_index": stage_idx,
                                "stage_label": PIPELINE_STAGE_LABELS.get(
                                    PIPELINE_STAGES[stage_idx], ""
                                ),
                                "reason": detail,
                                "context": serialized_context,
                                "timestamp": datetime.now(UTC).isoformat(),
                            },
                        )
                    )
                else:
                    asyncio.get_running_loop().create_task(
                        self._event_router.publish(
                            job.pipeline_id,
                            {
                                "type": "pipeline_stage_completed",
                                "stage_index": stage_idx,
                                "stage_status": status,
                                "stage_detail": detail,
                                "context": serialized_context,
                                "timestamp": datetime.now(UTC).isoformat(),
                            },
                        )
                    )

            try:
                ctx = await orch.run_full_pipeline(
                    job.theme,
                    from_stage=job.from_stage,
                    to_stage=job.to_stage,
                    progress_callback=_progress,
                    stage_completed_callback=_stage_completed,
                    run_constraints=run_constraints,
                )

                self._job_registry.update_context(job.pipeline_id, ctx)
                self._job_registry.mark_completed(job.pipeline_id, context=ctx)

                await self._event_router.publish(
                    job.pipeline_id,
                    {
                        "type": "pipeline_completed",
                        "current_stage": ctx.current_stage,
                        "timestamp": datetime.now(UTC).isoformat(),
                    },
                )
            except _PipelineCancelled:
                self._job_registry.mark_cancelled(job.pipeline_id)
                await self._event_router.publish(
                    job.pipeline_id,
                    {"type": "pipeline_cancelled", "timestamp": datetime.now(UTC).isoformat()},
                )
            except Exception as exc:
                logger.exception("Pipeline %s failed", job.pipeline_id)
                self._job_registry.mark_failed(job.pipeline_id, error=str(exc))
                await self._event_router.publish(
                    job.pipeline_id,
                    {
                        "type": "pipeline_error",
                        "error": str(exc),
                        "timestamp": datetime.now(UTC).isoformat(),
                    },
                )

        task = asyncio.create_task(_run())
        self._job_registry.attach_task(job.pipeline_id, task)

    def _start_resume_pipeline_task(
        self,
        job: PipelineRunJob,
        config: Config,
        initial_context: PipelineContext,
        orch: ContentGenOrchestrator,
    ) -> None:
        """Start the asyncio task for a resumed pipeline run."""

        async def _run() -> None:
            self._job_registry.mark_running(job.pipeline_id)

            def _progress(stage_idx: int, label: str) -> None:
                if job.stop_requested:
                    raise _PipelineCancelled(job.pipeline_id)
                asyncio.get_running_loop().create_task(
                    self._event_router.publish(
                        job.pipeline_id,
                        {
                            "type": "pipeline_stage_started",
                            "stage_index": stage_idx,
                            "stage_label": label,
                            "timestamp": datetime.now(UTC).isoformat(),
                        },
                    )
                )

            def _stage_completed(stage_idx: int, status: str, detail: str, stage_ctx) -> None:
                # Clone the context so the registry never holds a reference to the
                # orchestrator's live object (which is mutated between callback invocations).
                self._job_registry.update_context(
                    job.pipeline_id, stage_ctx.model_copy(deep=True)
                )
                serialized_context = stage_ctx.model_dump(mode="json")

                if status == "failed":
                    asyncio.get_running_loop().create_task(
                        self._event_router.publish(
                            job.pipeline_id,
                            {
                                "type": "pipeline_stage_failed",
                                "stage_index": stage_idx,
                                "stage_label": PIPELINE_STAGE_LABELS.get(
                                    PIPELINE_STAGES[stage_idx], ""
                                ),
                                "error": detail,
                                "context": serialized_context,
                                "timestamp": datetime.now(UTC).isoformat(),
                            },
                        )
                    )
                elif status == "skipped":
                    asyncio.get_running_loop().create_task(
                        self._event_router.publish(
                            job.pipeline_id,
                            {
                                "type": "pipeline_stage_skipped",
                                "stage_index": stage_idx,
                                "stage_label": PIPELINE_STAGE_LABELS.get(
                                    PIPELINE_STAGES[stage_idx], ""
                                ),
                                "reason": detail,
                                "context": serialized_context,
                                "timestamp": datetime.now(UTC).isoformat(),
                            },
                        )
                    )
                else:
                    asyncio.get_running_loop().create_task(
                        self._event_router.publish(
                            job.pipeline_id,
                            {
                                "type": "pipeline_stage_completed",
                                "stage_index": stage_idx,
                                "stage_status": status,
                                "stage_detail": detail,
                                "context": serialized_context,
                                "timestamp": datetime.now(UTC).isoformat(),
                            },
                        )
                    )

            try:
                result_ctx = await orch.run_full_pipeline(
                    job.theme,
                    from_stage=job.from_stage,
                    to_stage=job.to_stage,
                    initial_context=initial_context,
                    progress_callback=_progress,
                    stage_completed_callback=_stage_completed,
                )
                self._job_registry.update_context(job.pipeline_id, result_ctx)
                self._job_registry.mark_completed(job.pipeline_id, context=result_ctx)
                await self._event_router.publish(
                    job.pipeline_id,
                    {"type": "pipeline_completed", "timestamp": datetime.now(UTC).isoformat()},
                )
            except _PipelineCancelled:
                self._job_registry.mark_cancelled(job.pipeline_id)
            except Exception as exc:
                logger.exception("Pipeline %s resume failed", job.pipeline_id)
                self._job_registry.mark_failed(job.pipeline_id, error=str(exc))

        task = asyncio.create_task(_run())
        self._job_registry.attach_task(job.pipeline_id, task)

    def _start_backlog_item_pipeline_task(
        self,
        job: PipelineRunJob,
        config: Config,
        initial_context: PipelineContext,
    ) -> None:
        """Start the asyncio task for a backlog-item-seeded pipeline run."""

        async def _run() -> None:

            orch = self._pipeline_factory(config)
            self._job_registry.mark_running(job.pipeline_id)

            def _progress(stage_idx: int, label: str) -> None:
                if job.stop_requested:
                    raise _PipelineCancelled(job.pipeline_id)
                asyncio.get_running_loop().create_task(
                    self._event_router.publish(
                        job.pipeline_id,
                        {
                            "type": "pipeline_stage_started",
                            "stage_index": stage_idx,
                            "stage_label": label,
                            "timestamp": datetime.now(UTC).isoformat(),
                        },
                    )
                )

            def _stage_completed(stage_idx: int, status: str, detail: str, stage_ctx) -> None:
                self._job_registry.update_context(job.pipeline_id, stage_ctx)
                serialized_context = stage_ctx.model_dump(mode="json")

                if status == "failed":
                    asyncio.get_running_loop().create_task(
                        self._event_router.publish(
                            job.pipeline_id,
                            {
                                "type": "pipeline_stage_failed",
                                "stage_index": stage_idx,
                                "stage_label": PIPELINE_STAGE_LABELS.get(
                                    PIPELINE_STAGES[stage_idx], ""
                                ),
                                "error": detail,
                                "context": serialized_context,
                                "timestamp": datetime.now(UTC).isoformat(),
                            },
                        )
                    )
                elif status == "skipped":
                    asyncio.get_running_loop().create_task(
                        self._event_router.publish(
                            job.pipeline_id,
                            {
                                "type": "pipeline_stage_skipped",
                                "stage_index": stage_idx,
                                "stage_label": PIPELINE_STAGE_LABELS.get(
                                    PIPELINE_STAGES[stage_idx], ""
                                ),
                                "reason": detail,
                                "context": serialized_context,
                                "timestamp": datetime.now(UTC).isoformat(),
                            },
                        )
                    )
                else:
                    asyncio.get_running_loop().create_task(
                        self._event_router.publish(
                            job.pipeline_id,
                            {
                                "type": "pipeline_stage_completed",
                                "stage_index": stage_idx,
                                "stage_status": status,
                                "stage_detail": detail,
                                "context": serialized_context,
                                "timestamp": datetime.now(UTC).isoformat(),
                            },
                        )
                    )

            try:
                result_ctx = await orch.run_full_pipeline(
                    initial_context.theme,
                    from_stage=4,
                    to_stage=job.to_stage,
                    initial_context=initial_context,
                    progress_callback=_progress,
                    stage_completed_callback=_stage_completed,
                )
                self._job_registry.update_context(job.pipeline_id, result_ctx)
                self._job_registry.mark_completed(job.pipeline_id, context=result_ctx)
                await self._event_router.publish(
                    job.pipeline_id,
                    {
                        "type": "pipeline_completed",
                        "current_stage": result_ctx.current_stage,
                        "timestamp": datetime.now(UTC).isoformat(),
                    },
                )
            except _PipelineCancelled:
                self._job_registry.mark_cancelled(job.pipeline_id)
                await self._event_router.publish(
                    job.pipeline_id,
                    {"type": "pipeline_cancelled", "timestamp": datetime.now(UTC).isoformat()},
                )
            except Exception as exc:
                logger.exception("Pipeline %s failed", job.pipeline_id)
                self._job_registry.mark_failed(job.pipeline_id, error=str(exc))
                await self._event_router.publish(
                    job.pipeline_id,
                    {
                        "type": "pipeline_error",
                        "error": str(exc),
                        "timestamp": datetime.now(UTC).isoformat(),
                    },
                )

        task = asyncio.create_task(_run())
        self._job_registry.attach_task(job.pipeline_id, task)

    def _build_seeded_context_from_backlog_item(
        self, pipeline_id: str, item: BacklogItem
    ) -> PipelineContext:
        """Build a minimal valid PipelineContext seeded from one backlog item.

        The context is seeded so that the orchestrator can start at generate_angles
        (stage 4) without needing upstream scoring or backlog regeneration.
        """
        from cc_deep_research.content_gen.models import (
            BacklogOutput,
            PipelineCandidate,
        )
        from cc_deep_research.content_gen.storage import StrategyStore

        strategy = StrategyStore().load()

        return PipelineContext(
            pipeline_id=pipeline_id,
            theme=item.source_theme or item.title or item.idea,
            created_at=datetime.now(tz=UTC).isoformat(),
            current_stage=4,
            strategy=strategy,
            backlog=BacklogOutput(items=[item]),
            selected_idea_id=item.idea_id,
            shortlist=[item.idea_id],
            selection_reasoning=(
                item.selection_reasoning
                if item.selection_reasoning
                else "Started explicitly by operator from backlog."
            ),
            runner_up_idea_ids=[],
            active_candidates=[
                PipelineCandidate(
                    idea_id=item.idea_id,
                    role="primary",
                    status="selected",
                )
            ],
        )

    def _job_to_result(self, job: PipelineRunJob) -> PipelineRunResult:
        """Convert a PipelineRunJob to a PipelineRunResult."""
        return PipelineRunResult(
            pipeline_id=job.pipeline_id,
            theme=job.theme,
            from_stage=job.from_stage,
            to_stage=job.to_stage,
            status=str(job.status),
            current_stage=(
                job.pipeline_context.current_stage if job.pipeline_context else job.from_stage
            ),
            error=job.error,
            created_at=job.created_at,
            started_at=job.started_at,
            completed_at=job.completed_at,
        )


__all__ = [
    "PipelineRunService",
    "PipelineRunServiceError",
    "PipelineNotFoundError",
    "PipelineNotActiveError",
    "DuplicateActiveItemError",
    "ResumeContextError",
    "PipelineRunResult",
]
