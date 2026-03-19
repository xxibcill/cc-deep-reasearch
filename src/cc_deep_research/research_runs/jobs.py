"""In-process runtime state for browser-started research runs."""

from __future__ import annotations

import asyncio
import threading
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime

from cc_deep_research.research_runs.models import (
    ResearchRunRequest,
    ResearchRunResult,
    ResearchRunStatus,
)


@dataclass(slots=True)
class ResearchRunJob:
    """Mutable state for one active or completed research job."""

    run_id: str
    request: ResearchRunRequest
    status: ResearchRunStatus = ResearchRunStatus.QUEUED
    session_id: str | None = None
    task: asyncio.Task[object] | None = None
    result: ResearchRunResult | None = None
    error: str | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    started_at: datetime | None = None
    completed_at: datetime | None = None
    cancel_requested: threading.Event = field(default_factory=threading.Event, repr=False)

    @property
    def is_active(self) -> bool:
        """Return whether the job is still running in-process."""
        return self.status in {ResearchRunStatus.QUEUED, ResearchRunStatus.RUNNING}

    @property
    def stop_requested(self) -> bool:
        """Return whether an operator has asked to stop the job."""
        return self.cancel_requested.is_set()


class ResearchRunJobRegistry:
    """Process-local registry for browser-started research jobs."""

    def __init__(self) -> None:
        self._jobs: dict[str, ResearchRunJob] = {}
        self._lock = threading.Lock()

    def create_job(
        self,
        request: ResearchRunRequest,
        *,
        run_id: str | None = None,
    ) -> ResearchRunJob:
        """Create and store a queued job entry."""
        job = ResearchRunJob(
            run_id=run_id or self._generate_run_id(),
            request=request,
        )
        with self._lock:
            self._jobs[job.run_id] = job
        return job

    def get_job(self, run_id: str) -> ResearchRunJob | None:
        """Return a stored job by id."""
        with self._lock:
            return self._jobs.get(run_id)

    def list_jobs(self) -> list[ResearchRunJob]:
        """Return all jobs in creation order."""
        with self._lock:
            return list(self._jobs.values())

    def active_jobs(self) -> list[ResearchRunJob]:
        """Return queued and running jobs."""
        return [job for job in self.list_jobs() if job.is_active]

    def completed_jobs(self) -> list[ResearchRunJob]:
        """Return completed and failed jobs."""
        return [job for job in self.list_jobs() if not job.is_active]

    def attach_task(
        self,
        run_id: str,
        task: asyncio.Task[object],
    ) -> ResearchRunJob:
        """Attach the asyncio task that owns execution for a run."""
        job = self._require_job(run_id)
        with self._lock:
            job.task = task
        return job

    def set_session_id(
        self,
        run_id: str,
        *,
        session_id: str,
    ) -> ResearchRunJob:
        """Record the session identifier once the run allocates one."""
        job = self._require_job(run_id)
        with self._lock:
            job.session_id = session_id
        return job

    def mark_running(
        self,
        run_id: str,
        *,
        session_id: str | None = None,
    ) -> ResearchRunJob:
        """Transition a job into the running state."""
        job = self._require_job(run_id)
        with self._lock:
            if job.status == ResearchRunStatus.CANCELLED:
                return job
            job.status = ResearchRunStatus.RUNNING
            job.started_at = datetime.now(UTC)
            if session_id is not None:
                job.session_id = session_id
        return job

    def mark_completed(
        self,
        run_id: str,
        *,
        result: ResearchRunResult,
    ) -> ResearchRunJob:
        """Store the final result for a completed run."""
        job = self._require_job(run_id)
        with self._lock:
            if job.status == ResearchRunStatus.CANCELLED:
                return job
            job.status = ResearchRunStatus.COMPLETED
            job.result = result
            job.session_id = result.session_id
            job.error = None
            job.completed_at = datetime.now(UTC)
        return job

    def mark_failed(
        self,
        run_id: str,
        *,
        error: str,
    ) -> ResearchRunJob:
        """Record a failed run with a safe error message."""
        job = self._require_job(run_id)
        with self._lock:
            if job.status == ResearchRunStatus.CANCELLED:
                return job
            job.status = ResearchRunStatus.FAILED
            job.result = None
            job.error = error
            job.completed_at = datetime.now(UTC)
        return job

    def request_cancel(self, run_id: str) -> ResearchRunJob:
        """Record an operator stop request for a run."""
        job = self._require_job(run_id)
        job.cancel_requested.set()
        return job

    def mark_cancelled(
        self,
        run_id: str,
        *,
        error: str = "Research run was cancelled by the operator.",
    ) -> ResearchRunJob:
        """Store a terminal cancelled state for a run."""
        job = self._require_job(run_id)
        with self._lock:
            job.cancel_requested.set()
            job.status = ResearchRunStatus.CANCELLED
            job.result = None
            job.error = error
            job.completed_at = datetime.now(UTC)
        return job

    async def cancel_all(self) -> None:
        """Cancel every active task owned by the registry."""
        tasks = [
            job.task
            for job in self.active_jobs()
            if job.task is not None and not job.task.done()
        ]
        for job in self.active_jobs():
            self.request_cancel(job.run_id)
        for task in tasks:
            task.cancel()
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)

    def _require_job(self, run_id: str) -> ResearchRunJob:
        """Load a known job or raise a keyed error."""
        job = self.get_job(run_id)
        if job is None:
            raise KeyError(f"Unknown research run: {run_id}")
        return job

    def _generate_run_id(self) -> str:
        """Create a stable local run identifier."""
        return f"run-{uuid.uuid4().hex[:12]}"


ResearchRunJobStatus = ResearchRunStatus


__all__ = [
    "ResearchRunJob",
    "ResearchRunJobRegistry",
    "ResearchRunJobStatus",
]
