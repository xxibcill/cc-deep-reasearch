"""In-process runtime state for browser-started content-gen pipeline runs."""

from __future__ import annotations

import asyncio
import threading
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from cc_deep_research.content_gen.models import PipelineContext


class PipelineRunStatus(StrEnum):
    """Lifecycle states for a pipeline run."""

    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass(slots=True)
class PipelineRunJob:
    """Mutable state for one active or completed content-gen pipeline run."""

    pipeline_id: str
    theme: str
    from_stage: int = 0
    to_stage: int | None = None
    status: PipelineRunStatus = PipelineRunStatus.QUEUED
    pipeline_context: PipelineContext | None = None
    task: asyncio.Task[object] | None = None
    error: str | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    started_at: datetime | None = None
    completed_at: datetime | None = None
    cancel_requested: threading.Event = field(default_factory=threading.Event, repr=False)

    @property
    def is_active(self) -> bool:
        """Return whether the job is still running in-process."""
        return self.status in {PipelineRunStatus.QUEUED, PipelineRunStatus.RUNNING}

    @property
    def stop_requested(self) -> bool:
        """Return whether an operator has asked to stop the job."""
        return self.cancel_requested.is_set()


class PipelineRunJobRegistry:
    """Process-local registry for browser-started content-gen pipeline runs."""

    DEFAULT_MAX_COMPLETED_JOBS = 50

    def __init__(
        self,
        *,
        max_completed_jobs: int | None = None,
    ) -> None:
        self._jobs: dict[str, PipelineRunJob] = {}
        self._lock = threading.Lock()
        self._max_completed_jobs = max_completed_jobs or self.DEFAULT_MAX_COMPLETED_JOBS

    def create_job(
        self,
        theme: str,
        *,
        from_stage: int = 0,
        to_stage: int | None = None,
        pipeline_id: str | None = None,
    ) -> PipelineRunJob:
        """Create and store a queued job entry."""
        self.cleanup_old_jobs()
        job = PipelineRunJob(
            pipeline_id=pipeline_id or self._generate_pipeline_id(),
            theme=theme,
            from_stage=from_stage,
            to_stage=to_stage,
        )
        with self._lock:
            self._jobs[job.pipeline_id] = job
        return job

    def get_job(self, pipeline_id: str) -> PipelineRunJob | None:
        """Return a stored job by id."""
        with self._lock:
            return self._jobs.get(pipeline_id)

    def list_jobs(self) -> list[PipelineRunJob]:
        """Return all jobs in creation order."""
        with self._lock:
            return list(self._jobs.values())

    def active_jobs(self) -> list[PipelineRunJob]:
        """Return queued and running jobs."""
        return [job for job in self.list_jobs() if job.is_active]

    def completed_jobs(self) -> list[PipelineRunJob]:
        """Return completed and failed jobs."""
        return [job for job in self.list_jobs() if not job.is_active]

    def attach_task(
        self,
        pipeline_id: str,
        task: asyncio.Task[object],
    ) -> PipelineRunJob:
        """Attach the asyncio task that owns execution for a run."""
        job = self._require_job(pipeline_id)
        with self._lock:
            job.task = task
        return job

    def mark_running(self, pipeline_id: str) -> PipelineRunJob:
        """Transition a job into the running state."""
        job = self._require_job(pipeline_id)
        with self._lock:
            if job.status == PipelineRunStatus.CANCELLED:
                return job
            job.status = PipelineRunStatus.RUNNING
            job.started_at = datetime.now(UTC)
        return job

    def mark_completed(
        self,
        pipeline_id: str,
        *,
        context: PipelineContext,
    ) -> PipelineRunJob:
        """Store the final context for a completed run."""
        job = self._require_job(pipeline_id)
        with self._lock:
            if job.status == PipelineRunStatus.CANCELLED:
                return job
            job.status = PipelineRunStatus.COMPLETED
            job.pipeline_context = context
            job.error = None
            job.completed_at = datetime.now(UTC)
        return job

    def mark_failed(
        self,
        pipeline_id: str,
        *,
        error: str,
    ) -> PipelineRunJob:
        """Record a failed run with a safe error message."""
        job = self._require_job(pipeline_id)
        with self._lock:
            if job.status == PipelineRunStatus.CANCELLED:
                return job
            job.status = PipelineRunStatus.FAILED
            job.error = error
            job.completed_at = datetime.now(UTC)
        return job

    def request_cancel(self, pipeline_id: str) -> PipelineRunJob:
        """Record an operator stop request for a run."""
        job = self._require_job(pipeline_id)
        job.cancel_requested.set()
        return job

    def mark_cancelled(
        self,
        pipeline_id: str,
        *,
        error: str = "Pipeline run was cancelled by the operator.",
    ) -> PipelineRunJob:
        """Store a terminal cancelled state for a run."""
        job = self._require_job(pipeline_id)
        with self._lock:
            job.cancel_requested.set()
            job.status = PipelineRunStatus.CANCELLED
            job.error = error
            job.completed_at = datetime.now(UTC)
        return job

    def update_context(
        self,
        pipeline_id: str,
        context: PipelineContext,
    ) -> PipelineRunJob:
        """Update the pipeline context after a stage completes."""
        job = self._require_job(pipeline_id)
        with self._lock:
            job.pipeline_context = context
        return job

    async def cancel_all(self) -> None:
        """Cancel every active task owned by the registry."""
        tasks = [
            job.task for job in self.active_jobs() if job.task is not None and not job.task.done()
        ]
        for job in self.active_jobs():
            self.request_cancel(job.pipeline_id)
        for task in tasks:
            task.cancel()
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)

    def cleanup_old_jobs(self) -> int:
        """Remove oldest completed/failed jobs exceeding max retention.

        Returns:
            Number of jobs removed.
        """
        if self._max_completed_jobs <= 0:
            return 0

        with self._lock:
            completed = [
                (pid, job)
                for pid, job in self._jobs.items()
                if not job.is_active and job.completed_at is not None
            ]
            completed.sort(key=lambda x: x[1].completed_at or datetime.min)

            excess = len(completed) - self._max_completed_jobs
            if excess <= 0:
                return 0

            removed = 0
            for pid, _ in completed[:excess]:
                del self._jobs[pid]
                removed += 1
            return removed

    def _require_job(self, pipeline_id: str) -> PipelineRunJob:
        """Load a known job or raise a keyed error."""
        job = self.get_job(pipeline_id)
        if job is None:
            raise KeyError(f"Unknown pipeline run: {pipeline_id}")
        return job

    def _generate_pipeline_id(self) -> str:
        """Create a stable local pipeline identifier."""
        return f"cgp-{uuid.uuid4().hex[:12]}"


__all__ = [
    "PipelineRunJob",
    "PipelineRunJobRegistry",
    "PipelineRunStatus",
]
