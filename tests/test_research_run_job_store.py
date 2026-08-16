"""Tests for crash-safe browser research job persistence."""

from __future__ import annotations

import asyncio
from concurrent.futures import ThreadPoolExecutor

import pytest

from cc_deep_research.models import ResearchSession
from cc_deep_research.research_runs.jobs import (
    PersistentResearchRunJobRegistry,
    ResearchRunJobStore,
)
from cc_deep_research.research_runs.models import (
    ResearchOutputFormat,
    ResearchRunReport,
    ResearchRunRequest,
    ResearchRunResult,
    ResearchRunStatus,
)


def test_persistent_registry_restores_failed_job_and_request(tmp_path) -> None:
    path = tmp_path / "runs"
    registry = PersistentResearchRunJobRegistry(store=ResearchRunJobStore(path))
    job = registry.create_job(ResearchRunRequest(query="expensive research"))
    registry.mark_running(job.run_id, session_id="research-session")
    registry.mark_failed(job.run_id, error="provider failed")

    restored = PersistentResearchRunJobRegistry(store=ResearchRunJobStore(path))
    restored_job = restored.get_job(job.run_id)

    assert restored_job is not None
    assert restored_job.request.query == "expensive research"
    assert restored_job.session_id == "research-session"
    assert restored_job.status == ResearchRunStatus.FAILED
    assert restored_job.error == "provider failed"


def test_persistent_registry_retains_failed_report_metadata(tmp_path) -> None:
    path = tmp_path / "runs"
    registry = PersistentResearchRunJobRegistry(store=ResearchRunJobStore(path))
    request = ResearchRunRequest(query="recoverable report")
    job = registry.create_job(request)
    result = ResearchRunResult(
        session=ResearchSession(
            session_id="failed-with-report",
            query=request.query,
            depth=request.depth,
            metadata={"execution": {"terminal_status": "failed"}},
        ),
        report=ResearchRunReport(
            format=ResearchOutputFormat.MARKDOWN,
            content="# Terminal recovery report",
            media_type="text/markdown",
        ),
    )

    registry.mark_failed(job.run_id, error="recovery exhausted", result=result)

    restored = PersistentResearchRunJobRegistry(store=ResearchRunJobStore(path))
    restored_job = restored.get_job(job.run_id)
    assert restored_job is not None
    assert restored_job.status == ResearchRunStatus.FAILED
    assert restored_job.session_id == "failed-with-report"
    assert restored_job.result_metadata == {
        "session_id": "failed-with-report",
        "report_format": "markdown",
        "report_path": None,
        "artifacts": [],
    }


def test_registry_recovers_process_interrupted_job_as_failed(tmp_path) -> None:
    path = tmp_path / "runs"
    registry = PersistentResearchRunJobRegistry(store=ResearchRunJobStore(path))
    job = registry.create_job(ResearchRunRequest(query="interrupted research"))
    registry.mark_running(job.run_id, session_id="interrupted-session")

    restored = PersistentResearchRunJobRegistry(store=ResearchRunJobStore(path))
    restored_job = restored.get_job(job.run_id)

    assert restored_job is not None
    assert restored_job.status == ResearchRunStatus.FAILED
    assert "interrupted" in (restored_job.error or "").lower()


@pytest.mark.asyncio
async def test_graceful_shutdown_interruption_remains_recoverable(tmp_path) -> None:
    path = tmp_path / "runs"
    registry = PersistentResearchRunJobRegistry(store=ResearchRunJobStore(path))
    job = registry.create_job(ResearchRunRequest(query="resume after deploy"))
    registry.mark_running(job.run_id, session_id="deploy-session")
    task = asyncio.create_task(asyncio.sleep(60))
    registry.attach_task(job.run_id, task)

    await registry.interrupt_all_for_shutdown()

    assert task.cancelled() is True
    assert job.status == ResearchRunStatus.FAILED
    restored = PersistentResearchRunJobRegistry(store=ResearchRunJobStore(path))
    assert [candidate.run_id for candidate in restored.interrupted_restart_jobs()] == [job.run_id]


def test_operator_stop_pending_during_crash_remains_cancelled(tmp_path) -> None:
    path = tmp_path / "runs"
    registry = PersistentResearchRunJobRegistry(store=ResearchRunJobStore(path))
    job = registry.create_job(ResearchRunRequest(query="do not resume me"))
    registry.mark_running(job.run_id, session_id="operator-stopped-session")
    registry.request_cancel(job.run_id)

    restored = PersistentResearchRunJobRegistry(store=ResearchRunJobStore(path))
    restored_job = restored.get_job(job.run_id)

    assert restored_job is not None
    assert restored_job.status == ResearchRunStatus.CANCELLED
    assert restored_job.stop_requested is True
    assert restored.interrupted_restart_jobs() == []


def test_resume_job_has_distinct_identity_and_lineage(tmp_path) -> None:
    registry = PersistentResearchRunJobRegistry(
        store=ResearchRunJobStore(tmp_path / "runs")
    )
    original = registry.create_job(ResearchRunRequest(query="resume me"))
    registry.mark_running(original.run_id, session_id="original-session")
    registry.mark_failed(original.run_id, error="boom")

    resumed = registry.create_resume_job(
        original,
        checkpoint_id="cp-safe",
        idempotency_key="resume-once",
    )
    duplicate = registry.create_resume_job(
        original,
        checkpoint_id="cp-safe",
        idempotency_key="resume-once",
    )

    assert resumed.run_id != original.run_id
    assert duplicate is resumed
    assert resumed.original_run_id == original.run_id
    assert resumed.original_session_id == "original-session"
    assert resumed.resumed_from_checkpoint_id == "cp-safe"
    assert resumed.resume_attempt == 1


def test_registry_finds_jobs_by_session_id(tmp_path) -> None:
    registry = PersistentResearchRunJobRegistry(
        store=ResearchRunJobStore(tmp_path / "runs")
    )
    job = registry.create_job(ResearchRunRequest(query="lookup"))
    registry.set_session_id(job.run_id, session_id="session-lookup")

    assert registry.find_by_session_id("session-lookup") is job


def test_resume_job_for_historical_session_is_idempotent(tmp_path) -> None:
    registry = PersistentResearchRunJobRegistry(
        store=ResearchRunJobStore(tmp_path / "runs")
    )
    request = ResearchRunRequest(query="historical session")

    resumed = registry.create_resume_job_for_session(
        request,
        original_session_id="historical-session",
        checkpoint_id="cp-history",
        idempotency_key="history-once",
    )
    duplicate = registry.create_resume_job_for_session(
        request,
        original_session_id="historical-session",
        checkpoint_id="cp-history",
        idempotency_key="history-once",
    )

    assert duplicate is resumed
    assert resumed.original_run_id is None
    assert resumed.original_session_id == "historical-session"
    assert resumed.resume_attempt == 1


def test_concurrent_resume_reservations_create_one_job(tmp_path) -> None:
    registry = PersistentResearchRunJobRegistry(
        store=ResearchRunJobStore(tmp_path / "runs")
    )
    original = registry.create_job(ResearchRunRequest(query="resume concurrently"))
    registry.mark_running(original.run_id, session_id="concurrent-session")
    registry.mark_failed(original.run_id, error="provider failed")

    def reserve_job():
        return registry.reserve_resume_job(
            original,
            checkpoint_id="cp-concurrent",
            idempotency_key="same-retry",
        )

    with ThreadPoolExecutor(max_workers=2) as executor:
        reservations = list(executor.map(lambda _: reserve_job(), range(2)))

    assert sum(reservation.created for reservation in reservations) == 1
    assert reservations[0].job is reservations[1].job
