"""In-process runtime state for browser-started content-gen pipeline runs."""

from __future__ import annotations

import asyncio
import json
import threading
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path
from typing import TYPE_CHECKING

from cc_deep_research.config import get_default_config_path

if TYPE_CHECKING:
    from cc_deep_research.content_gen.models import PipelineContext


class PipelineRunStatus(StrEnum):
    """Lifecycle states for a pipeline run."""

    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


def _default_pipeline_runs_dir() -> Path:
    """Return the default persistence directory for dashboard pipeline jobs."""
    return get_default_config_path().parent / "content-gen" / "pipelines"


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


class PipelineRunStore:
    """Persist browser-started content-gen pipeline jobs to disk."""

    def __init__(self, path: Path | None = None) -> None:
        self._path = path or _default_pipeline_runs_dir()

    @property
    def path(self) -> Path:
        return self._path

    def load_all(self) -> list[PipelineRunJob]:
        """Load all persisted jobs, oldest first."""
        if not self._path.exists():
            return []

        jobs: list[PipelineRunJob] = []
        for job_path in sorted(self._path.glob("*.json")):
            payload = json.loads(job_path.read_text(encoding="utf-8"))
            jobs.append(self._deserialize_job(payload))

        jobs.sort(key=lambda job: job.created_at)
        return jobs

    def save(self, job: PipelineRunJob) -> None:
        """Persist one job atomically."""
        self._path.mkdir(parents=True, exist_ok=True)
        job_path = self._path / f"{job.pipeline_id}.json"
        tmp_path = job_path.with_suffix(".json.tmp")
        tmp_path.write_text(
            json.dumps(self._serialize_job(job), indent=2),
            encoding="utf-8",
        )
        tmp_path.replace(job_path)

    @staticmethod
    def _serialize_job(job: PipelineRunJob) -> dict[str, object]:
        pipeline_context = None
        if job.pipeline_context is not None:
            pipeline_context = json.loads(job.pipeline_context.model_dump_json())
        return {
            "pipeline_id": job.pipeline_id,
            "theme": job.theme,
            "from_stage": job.from_stage,
            "to_stage": job.to_stage,
            "status": str(job.status),
            "pipeline_context": pipeline_context,
            "error": job.error,
            "created_at": job.created_at.isoformat(),
            "started_at": job.started_at.isoformat() if job.started_at else None,
            "completed_at": job.completed_at.isoformat() if job.completed_at else None,
            "stop_requested": job.stop_requested,
        }

    @staticmethod
    def _deserialize_job(payload: dict[str, object]) -> PipelineRunJob:
        from cc_deep_research.content_gen.models import PipelineContext

        status = PipelineRunStatus(str(payload.get("status", PipelineRunStatus.QUEUED)))
        context_payload = payload.get("pipeline_context")
        job = PipelineRunJob(
            pipeline_id=str(payload.get("pipeline_id", "")),
            theme=str(payload.get("theme", "")),
            from_stage=int(payload.get("from_stage", 0)),
            to_stage=payload.get("to_stage"),
            status=status,
            pipeline_context=(
                PipelineContext.model_validate(context_payload)
                if isinstance(context_payload, dict)
                else None
            ),
            error=str(payload.get("error") or "") or None,
            created_at=datetime.fromisoformat(str(payload.get("created_at"))),
            started_at=(
                datetime.fromisoformat(str(payload.get("started_at")))
                if payload.get("started_at")
                else None
            ),
            completed_at=(
                datetime.fromisoformat(str(payload.get("completed_at")))
                if payload.get("completed_at")
                else None
            ),
        )
        if payload.get("stop_requested"):
            job.cancel_requested.set()
        return job


class PipelineRunJobRegistry:
    """Process-local registry for browser-started content-gen pipeline runs."""

    _RECOVERY_ERROR = "Pipeline run was interrupted before completion. Resume from the saved context."

    def __init__(
        self,
        *,
        store: PipelineRunStore | None = None,
        path: Path | None = None,
    ) -> None:
        self._store = store or PipelineRunStore(path)
        self._jobs: dict[str, PipelineRunJob] = {}
        self._lock = threading.Lock()
        self._restore_jobs()

    def create_job(
        self,
        theme: str,
        *,
        from_stage: int = 0,
        to_stage: int | None = None,
        pipeline_id: str | None = None,
    ) -> PipelineRunJob:
        """Create and store a queued job entry."""
        with self._lock:
            resolved_pipeline_id = pipeline_id or self._generate_pipeline_id()
            if resolved_pipeline_id in self._jobs:
                raise ValueError(f"Pipeline run already exists: {resolved_pipeline_id}")

            job = PipelineRunJob(
                pipeline_id=resolved_pipeline_id,
                theme=theme,
                from_stage=from_stage,
                to_stage=to_stage,
            )
            self._jobs[job.pipeline_id] = job
            self._persist_job(job)
        return job

    def create_resume_job(
        self,
        source_pipeline_id: str,
        theme: str,
        *,
        from_stage: int = 0,
        to_stage: int | None = None,
    ) -> PipelineRunJob:
        """Create a distinct job entry for a resumed pipeline run."""
        with self._lock:
            pipeline_id = self._generate_resume_pipeline_id(source_pipeline_id)
            while pipeline_id in self._jobs:
                pipeline_id = self._generate_resume_pipeline_id(source_pipeline_id)

            job = PipelineRunJob(
                pipeline_id=pipeline_id,
                theme=theme,
                from_stage=from_stage,
                to_stage=to_stage,
            )
            self._jobs[job.pipeline_id] = job
            self._persist_job(job)
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
            self._persist_job(job)
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
            self._persist_job(job)
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
            self._persist_job(job)
        return job

    def request_cancel(self, pipeline_id: str) -> PipelineRunJob:
        """Record an operator stop request for a run."""
        job = self._require_job(pipeline_id)
        with self._lock:
            job.cancel_requested.set()
            self._persist_job(job)
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
            self._persist_job(job)
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
            self._persist_job(job)
        return job

    async def cancel_all(self) -> None:
        """Cancel every active task owned by the registry."""
        tasks = [
            job.task
            for job in self.active_jobs()
            if job.task is not None and not job.task.done()
        ]
        for job in self.active_jobs():
            self.request_cancel(job.pipeline_id)
        for task in tasks:
            task.cancel()
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)

    def _require_job(self, pipeline_id: str) -> PipelineRunJob:
        """Load a known job or raise a keyed error."""
        job = self.get_job(pipeline_id)
        if job is None:
            raise KeyError(f"Unknown pipeline run: {pipeline_id}")
        return job

    def _generate_pipeline_id(self) -> str:
        """Create a stable local pipeline identifier."""
        return f"cgp-{uuid.uuid4().hex[:12]}"

    def _generate_resume_pipeline_id(self, source_pipeline_id: str) -> str:
        """Create a stable identifier for a resumed pipeline run."""
        return f"{source_pipeline_id}-resume-{uuid.uuid4().hex[:8]}"

    def _persist_job(self, job: PipelineRunJob) -> None:
        self._store.save(job)

    def _restore_jobs(self) -> None:
        for job in self._store.load_all():
            recovered = self._recover_interrupted_job(job)
            self._jobs[recovered.pipeline_id] = recovered
            self._persist_job(recovered)

    def _recover_interrupted_job(self, job: PipelineRunJob) -> PipelineRunJob:
        if job.status not in {PipelineRunStatus.QUEUED, PipelineRunStatus.RUNNING}:
            return job

        job.cancel_requested.clear()
        job.status = PipelineRunStatus.FAILED
        job.error = self._RECOVERY_ERROR
        job.completed_at = datetime.now(UTC)
        return job


__all__ = [
    "PipelineRunJob",
    "PipelineRunJobRegistry",
    "PipelineRunStatus",
    "PipelineRunStore",
]
