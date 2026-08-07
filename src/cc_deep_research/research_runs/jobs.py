"""In-process runtime state for browser-started research runs."""

from __future__ import annotations

import asyncio
import json
import threading
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from cc_deep_research.config import get_default_config_path
from cc_deep_research.persistence import atomic_write_json
from cc_deep_research.research_runs.models import (
    ResearchRunRequest,
    ResearchRunResult,
    ResearchRunStatus,
)


def _default_research_runs_dir() -> Path:
    """Return the durable store for browser-started research jobs."""
    return get_default_config_path().parent / "research-runs"


@dataclass(slots=True)
class ResearchRunJob:
    """Mutable state for one active or completed research job."""

    run_id: str
    request: ResearchRunRequest
    status: ResearchRunStatus = ResearchRunStatus.QUEUED
    session_id: str | None = None
    task: asyncio.Task[object] | None = None
    result: ResearchRunResult | None = None
    result_metadata: dict[str, Any] | None = None
    error: str | None = None
    original_run_id: str | None = None
    original_session_id: str | None = None
    resumed_from_checkpoint_id: str | None = None
    resume_attempt: int = 0
    idempotency_key: str | None = None
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

    def _job_changed(self, job: ResearchRunJob) -> None:
        """Handle a durable job-state mutation."""
        return None

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
        self._job_changed(job)
        return job

    def create_resume_job(
        self,
        original: ResearchRunJob,
        *,
        checkpoint_id: str,
        idempotency_key: str | None = None,
    ) -> ResearchRunJob:
        """Create one child job without mutating the original failed run."""
        with self._lock:
            if idempotency_key:
                duplicate = next(
                    (
                        job
                        for job in self._jobs.values()
                        if job.idempotency_key == idempotency_key
                        and job.original_run_id == original.run_id
                    ),
                    None,
                )
                if duplicate is not None:
                    return duplicate

            previous_attempts = [
                job.resume_attempt
                for job in self._jobs.values()
                if job.original_run_id == original.run_id
            ]
            job = ResearchRunJob(
                run_id=self._generate_run_id(),
                request=original.request.model_copy(deep=True),
                original_run_id=original.run_id,
                original_session_id=original.session_id,
                resumed_from_checkpoint_id=checkpoint_id,
                resume_attempt=max(previous_attempts, default=0) + 1,
                idempotency_key=idempotency_key,
            )
            self._jobs[job.run_id] = job
        self._job_changed(job)
        return job

    def find_by_session_id(self, session_id: str) -> ResearchRunJob | None:
        """Return the most recently created job attached to a session."""
        matches = [job for job in self.list_jobs() if job.session_id == session_id]
        return matches[-1] if matches else None

    def create_resume_job_for_session(
        self,
        request: ResearchRunRequest,
        *,
        original_session_id: str,
        checkpoint_id: str,
        original_run_id: str | None = None,
        idempotency_key: str | None = None,
    ) -> ResearchRunJob:
        """Create a child job for a durable session without a registry parent."""
        with self._lock:
            if idempotency_key:
                duplicate = next(
                    (
                        job
                        for job in self._jobs.values()
                        if job.idempotency_key == idempotency_key
                        and job.original_session_id == original_session_id
                    ),
                    None,
                )
                if duplicate is not None:
                    return duplicate
            previous_attempts = [
                job.resume_attempt
                for job in self._jobs.values()
                if job.original_session_id == original_session_id
            ]
            job = ResearchRunJob(
                run_id=self._generate_run_id(),
                request=request.model_copy(deep=True),
                original_run_id=original_run_id,
                original_session_id=original_session_id,
                resumed_from_checkpoint_id=checkpoint_id,
                resume_attempt=max(previous_attempts, default=0) + 1,
                idempotency_key=idempotency_key,
            )
            self._jobs[job.run_id] = job
        self._job_changed(job)
        return job

    def find_active_resume(
        self,
        *,
        original_session_id: str,
        checkpoint_id: str,
    ) -> ResearchRunJob | None:
        """Return an active resume attempt for one durable checkpoint."""
        return next(
            (
                job
                for job in self.active_jobs()
                if job.original_session_id == original_session_id
                and job.resumed_from_checkpoint_id == checkpoint_id
            ),
            None,
        )

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
        self._job_changed(job)
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
        self._job_changed(job)
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
            job.result_metadata = {
                "session_id": result.session_id,
                "report_format": result.report.format.value,
                "report_path": str(result.report.path) if result.report.path else None,
                "artifacts": [
                    {
                        "kind": artifact.kind.value,
                        "path": str(artifact.path),
                        "media_type": artifact.media_type,
                    }
                    for artifact in result.artifacts
                ],
            }
            job.session_id = result.session_id
            job.error = None
            job.completed_at = datetime.now(UTC)
        self._job_changed(job)
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
        self._job_changed(job)
        return job

    def request_cancel(self, run_id: str) -> ResearchRunJob:
        """Record an operator stop request for a run."""
        job = self._require_job(run_id)
        job.cancel_requested.set()
        self._job_changed(job)
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
        self._job_changed(job)
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


class ResearchRunJobStore:
    """Persist browser research jobs as independently replaceable JSON files."""

    def __init__(self, path: Path | None = None) -> None:
        self._path = path or _default_research_runs_dir()

    @property
    def path(self) -> Path:
        return self._path

    def load_all(self) -> list[ResearchRunJob]:
        """Load persisted jobs in creation order, skipping corrupt records."""
        if not self._path.exists():
            return []
        jobs: list[ResearchRunJob] = []
        for job_path in sorted(self._path.glob("*.json")):
            try:
                payload = json.loads(job_path.read_text(encoding="utf-8"))
                jobs.append(self._deserialize_job(payload))
            except (json.JSONDecodeError, OSError, TypeError, ValueError):
                continue
        return sorted(jobs, key=lambda job: job.created_at)

    def save(self, job: ResearchRunJob) -> None:
        """Persist one job atomically without serializing its live task handle."""
        atomic_write_json(
            self._path / f"{job.run_id}.json",
            self._serialize_job(job),
        )

    @staticmethod
    def _serialize_job(job: ResearchRunJob) -> dict[str, Any]:
        return {
            "run_id": job.run_id,
            "request": job.request.model_dump(mode="json"),
            "status": job.status.value,
            "session_id": job.session_id,
            "result_metadata": job.result_metadata,
            "error": job.error,
            "original_run_id": job.original_run_id,
            "original_session_id": job.original_session_id,
            "resumed_from_checkpoint_id": job.resumed_from_checkpoint_id,
            "resume_attempt": job.resume_attempt,
            "idempotency_key": job.idempotency_key,
            "created_at": job.created_at.isoformat(),
            "started_at": job.started_at.isoformat() if job.started_at else None,
            "completed_at": job.completed_at.isoformat() if job.completed_at else None,
            "stop_requested": job.stop_requested,
        }

    @staticmethod
    def _deserialize_job(payload: dict[str, Any]) -> ResearchRunJob:
        job = ResearchRunJob(
            run_id=str(payload["run_id"]),
            request=ResearchRunRequest.model_validate(payload["request"]),
            status=ResearchRunStatus(str(payload.get("status", ResearchRunStatus.QUEUED))),
            session_id=str(payload["session_id"]) if payload.get("session_id") else None,
            result_metadata=(
                dict(payload["result_metadata"])
                if isinstance(payload.get("result_metadata"), dict)
                else None
            ),
            error=str(payload["error"]) if payload.get("error") else None,
            original_run_id=(
                str(payload["original_run_id"]) if payload.get("original_run_id") else None
            ),
            original_session_id=(
                str(payload["original_session_id"])
                if payload.get("original_session_id")
                else None
            ),
            resumed_from_checkpoint_id=(
                str(payload["resumed_from_checkpoint_id"])
                if payload.get("resumed_from_checkpoint_id")
                else None
            ),
            resume_attempt=int(payload.get("resume_attempt", 0)),
            idempotency_key=(
                str(payload["idempotency_key"]) if payload.get("idempotency_key") else None
            ),
            created_at=datetime.fromisoformat(str(payload["created_at"])),
            started_at=(
                datetime.fromisoformat(str(payload["started_at"]))
                if payload.get("started_at")
                else None
            ),
            completed_at=(
                datetime.fromisoformat(str(payload["completed_at"]))
                if payload.get("completed_at")
                else None
            ),
        )
        if payload.get("stop_requested"):
            job.cancel_requested.set()
        return job


class PersistentResearchRunJobRegistry(ResearchRunJobRegistry):
    """Research job registry that survives dashboard process restarts."""

    _RECOVERY_ERROR = (
        "Research run was interrupted by a backend restart. "
        "Resume from the latest valid checkpoint."
    )

    def __init__(self, *, store: ResearchRunJobStore | None = None) -> None:
        super().__init__()
        self._store = store or ResearchRunJobStore()
        self._restore_jobs()

    def _job_changed(self, job: ResearchRunJob) -> None:
        """Persist every durable mutation through the base registry hook."""
        self._store.save(job)

    def _restore_jobs(self) -> None:
        for job in self._store.load_all():
            if job.status in {ResearchRunStatus.QUEUED, ResearchRunStatus.RUNNING}:
                job.cancel_requested.clear()
                job.status = ResearchRunStatus.FAILED
                job.error = self._RECOVERY_ERROR
                job.completed_at = datetime.now(UTC)
            self._jobs[job.run_id] = job
            self._job_changed(job)


ResearchRunJobStatus = ResearchRunStatus


@dataclass(slots=True)
class BackgroundJob:
    """Mutable state for a generic dashboard background job."""

    job_id: str
    kind: str
    metadata: dict[str, Any] = field(default_factory=dict)
    status: str = "queued"
    task: asyncio.Task[object] | None = None
    result: dict[str, Any] | None = None
    error: str | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    started_at: datetime | None = None
    completed_at: datetime | None = None

    @property
    def is_active(self) -> bool:
        """Return whether the job is still running in-process."""
        return self.status in {"queued", "running"}


class BackgroundJobRegistry:
    """Process-local registry for generic dashboard background jobs."""

    def __init__(self) -> None:
        self._jobs: dict[str, BackgroundJob] = {}
        self._lock = threading.Lock()

    def create_job(
        self,
        kind: str,
        *,
        metadata: dict[str, Any] | None = None,
        job_id: str | None = None,
    ) -> BackgroundJob:
        """Create and store a queued generic job."""
        job = BackgroundJob(
            job_id=job_id or self._generate_job_id(kind),
            kind=kind,
            metadata=metadata or {},
        )
        with self._lock:
            self._jobs[job.job_id] = job
        return job

    def get_job(self, job_id: str) -> BackgroundJob | None:
        """Return a stored generic job by id."""
        with self._lock:
            return self._jobs.get(job_id)

    def list_jobs(self) -> list[BackgroundJob]:
        """Return all generic jobs in creation order."""
        with self._lock:
            return list(self._jobs.values())

    def active_jobs(self) -> list[BackgroundJob]:
        """Return queued and running generic jobs."""
        return [job for job in self.list_jobs() if job.is_active]

    def attach_task(self, job_id: str, task: asyncio.Task[object]) -> BackgroundJob:
        """Attach the asyncio task that owns execution for a generic job."""
        job = self._require_job(job_id)
        with self._lock:
            job.task = task
        return job

    def mark_running(self, job_id: str) -> BackgroundJob:
        """Transition a generic job into the running state."""
        job = self._require_job(job_id)
        with self._lock:
            job.status = "running"
            job.started_at = datetime.now(UTC)
        return job

    def mark_completed(self, job_id: str, *, result: dict[str, Any]) -> BackgroundJob:
        """Store the final result for a completed generic job."""
        job = self._require_job(job_id)
        with self._lock:
            job.status = "completed"
            job.result = result
            job.error = None
            job.completed_at = datetime.now(UTC)
        return job

    def mark_failed(self, job_id: str, *, error: str) -> BackgroundJob:
        """Record a failed generic job with a safe error message."""
        job = self._require_job(job_id)
        with self._lock:
            job.status = "failed"
            job.result = None
            job.error = error
            job.completed_at = datetime.now(UTC)
        return job

    async def cancel_all(self) -> None:
        """Cancel every active generic task owned by the registry."""
        tasks = [
            job.task
            for job in self.active_jobs()
            if job.task is not None and not job.task.done()
        ]
        for task in tasks:
            task.cancel()
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
        for job in self.active_jobs():
            self.mark_failed(job.job_id, error="Background job was cancelled during shutdown.")

    def _require_job(self, job_id: str) -> BackgroundJob:
        """Load a known generic job or raise a keyed error."""
        job = self.get_job(job_id)
        if job is None:
            raise KeyError(f"Unknown background job: {job_id}")
        return job

    def _generate_job_id(self, kind: str) -> str:
        """Create a stable local background job identifier."""
        normalized_kind = kind.replace(".", "-").replace("_", "-")
        return f"job-{normalized_kind}-{uuid.uuid4().hex[:12]}"


__all__ = [
    "BackgroundJob",
    "BackgroundJobRegistry",
    "PersistentResearchRunJobRegistry",
    "ResearchRunJob",
    "ResearchRunJobRegistry",
    "ResearchRunJobStatus",
    "ResearchRunJobStore",
]
