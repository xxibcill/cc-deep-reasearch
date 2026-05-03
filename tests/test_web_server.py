"""Tests for FastAPI dashboard runtime state."""

from __future__ import annotations

import asyncio

import pytest

from cc_deep_research.event_router import EventRouter
from cc_deep_research.models import ResearchSession
from cc_deep_research.research_runs import (
    ResearchOutputFormat,
    ResearchRunReport,
    ResearchRunRequest,
    ResearchRunResult,
    ResearchRunStatus,
)
from cc_deep_research.research_runs.jobs import (
    ResearchRunJobRegistry,
    ResearchRunJobStatus,
)
from cc_deep_research.web_server import (
    create_app,
    get_event_router,
    get_job_registry,
)


def test_create_app_uses_supplied_runtime_dependencies() -> None:
    """The app should expose one shared router and job registry through helpers."""
    event_router = EventRouter()
    registry = ResearchRunJobRegistry()

    app = create_app(event_router=event_router, job_registry=registry)

    assert get_event_router(app) is event_router
    assert get_job_registry(app) is registry


def test_job_registry_tracks_active_and_completed_runs() -> None:
    """The registry should keep in-process state for queued, running, and finished jobs."""
    registry = ResearchRunJobRegistry()
    request = ResearchRunRequest(query="test query")
    job = registry.create_job(request)

    assert job.status == ResearchRunJobStatus.QUEUED
    assert registry.active_jobs() == [job]

    registry.mark_running(job.run_id, session_id="session-123")
    assert job.status == ResearchRunJobStatus.RUNNING
    assert job.session_id == "session-123"

    result = ResearchRunResult(
        session=ResearchSession(session_id="session-123", query="test query"),
        report=ResearchRunReport(
            format=ResearchOutputFormat.MARKDOWN,
            content="# Report",
            media_type="text/markdown",
        ),
    )
    registry.mark_completed(job.run_id, result=result)

    assert job.status == ResearchRunJobStatus.COMPLETED
    assert job.result == result
    assert registry.active_jobs() == []
    assert registry.completed_jobs() == [job]


@pytest.mark.asyncio
async def test_job_registry_cancel_all_cancels_active_tasks() -> None:
    """Shutdown cleanup should cancel unfinished background tasks."""
    registry = ResearchRunJobRegistry()
    job = registry.create_job(ResearchRunRequest(query="test query"))

    task = asyncio.create_task(asyncio.sleep(60))
    registry.attach_task(job.run_id, task)
    registry.mark_running(job.run_id)

    await registry.cancel_all()

    assert task.cancelled() is True


def test_job_registry_can_mark_run_cancelled() -> None:
    """A single run stop request should be preserved as terminal job state."""
    registry = ResearchRunJobRegistry()
    job = registry.create_job(ResearchRunRequest(query="test query"))

    registry.request_cancel(job.run_id)
    registry.mark_cancelled(job.run_id)

    assert job.stop_requested is True
    assert job.status == ResearchRunStatus.CANCELLED
    assert job.completed_at is not None
