"""Tests for PipelineRunService.

These tests verify the public boundary of PipelineRunService:
- Successful pipeline run
- Cancellation behavior
- Duplicate active item detection
- Resume from saved context

These tests do not require real LLM, search, or network access.
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from cc_deep_research.config import Config
from cc_deep_research.content_gen.backlog_service import BacklogItem
from cc_deep_research.content_gen.models import (
    PIPELINE_STAGES,
    PipelineContext,
)
from cc_deep_research.content_gen.pipeline_run_service import (
    DuplicateActiveItemError,
    PipelineNotActiveError,
    PipelineNotFoundError,
    PipelineRunResult,
    PipelineRunService,
    ResumeContextError,
)
from cc_deep_research.content_gen.progress import (
    PipelineRunJobRegistry,
    PipelineRunStatus,
)
from cc_deep_research.event_router import EventRouter

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


class MockPipelineFactory:
    """Fake pipeline factory for testing."""

    def __init__(self, config: Config) -> None:
        self.config = config
        self.validate_resume_context_called = False
        self.run_full_pipeline_calls: list[dict[str, Any]] = []

    def __call__(self, config: Config) -> MockPipelineFactory:
        """Allow factory to be used as a factory."""
        return self

    def validate_resume_context(self, *, from_stage: int, ctx: PipelineContext) -> str | None:
        """Return None to indicate resume is valid."""
        self.validate_resume_context_called = True
        return None

    async def run_full_pipeline(
        self,
        theme: str,
        *,
        from_stage: int = 0,
        to_stage: int | None = None,
        initial_context: PipelineContext | None = None,
        progress_callback=None,
        stage_completed_callback=None,
        run_constraints=None,
    ) -> PipelineContext:
        """Fake run_full_pipeline that returns a minimal context."""
        self.run_full_pipeline_calls.append({
            "theme": theme,
            "from_stage": from_stage,
            "to_stage": to_stage,
            "initial_context": initial_context,
        })

        # Simulate progress callbacks
        if progress_callback:
            for i in range(from_stage, (to_stage or len(PIPELINE_STAGES) - 1) + 1):
                progress_callback(i, PIPELINE_STAGES[i])
                await asyncio.sleep(0)

        # Create a result context
        result_ctx = PipelineContext(
            pipeline_id=initial_context.pipeline_id if initial_context else "test-pipeline",
            theme=theme,
            created_at=datetime.now(tz=UTC).isoformat(),
            current_stage=to_stage if to_stage is not None else len(PIPELINE_STAGES) - 1,
        )

        if stage_completed_callback:
            for i in range(from_stage, (to_stage or len(PIPELINE_STAGES) - 1) + 1):
                stage_completed_callback(i, "completed", "done", result_ctx)

        return result_ctx


@pytest.fixture
def config() -> Config:
    return Config()


@pytest.fixture
def mock_pipeline_factory(config: Config) -> MockPipelineFactory:
    return MockPipelineFactory(config)


@pytest.fixture
def event_router() -> MagicMock:
    """Mock EventRouter that tracks published events."""
    router = MagicMock(spec=EventRouter)
    router.publish = AsyncMock()
    return router


@pytest.fixture
def job_registry(tmp_path: Any) -> PipelineRunJobRegistry:
    """Create a job registry with a temporary path."""
    return PipelineRunJobRegistry(path=tmp_path)


@pytest.fixture
def service(
    job_registry: PipelineRunJobRegistry,
    event_router: MagicMock,
    mock_pipeline_factory: MockPipelineFactory,
) -> PipelineRunService:
    """Create a PipelineRunService with mocked dependencies."""
    return PipelineRunService(
        job_registry=job_registry,
        event_router=event_router,
        pipeline_factory=mock_pipeline_factory,
    )


# ---------------------------------------------------------------------------
# Helper to mock asyncio.create_task
# ---------------------------------------------------------------------------


class FakeTask:
    """A fake asyncio.Task that tracks if it was cancelled."""

    def __init__(self, coro: Any) -> None:
        self._coro = coro
        self.done_called = False
        self.cancelled_called = False

    def done(self) -> bool:
        return self.done_called

    def cancel(self) -> None:
        self.cancelled_called = True


def mock_create_task(coro: Any, *, name: str | None = None) -> FakeTask:
    """Mock asyncio.create_task that captures the coroutine."""
    return FakeTask(coro)


# ---------------------------------------------------------------------------
# Tests for list_pipelines
# ---------------------------------------------------------------------------


def test_list_pipelines_empty(service: PipelineRunService) -> None:
    """Service returns empty list when no pipelines exist."""
    result = service.list_pipelines()
    assert result == []


def test_list_pipelines_returns_all_jobs(
    service: PipelineRunService,
    job_registry: PipelineRunJobRegistry,
) -> None:
    """Service returns all pipeline jobs."""
    # Create a few jobs directly in registry
    job_registry.create_job("theme1", from_stage=0, to_stage=5)
    job_registry.create_job("theme2", from_stage=2, to_stage=10)

    result = service.list_pipelines()
    assert len(result) == 2
    themes = {r["theme"] for r in result}
    assert themes == {"theme1", "theme2"}


# ---------------------------------------------------------------------------
# Tests for get_pipeline_status
# ---------------------------------------------------------------------------


def test_get_pipeline_status_not_found(
    service: PipelineRunService,
) -> None:
    """Service returns None for non-existent pipeline."""
    result = service.get_pipeline_status("nonexistent")
    assert result is None


def test_get_pipeline_status_returns_job(
    service: PipelineRunService,
    job_registry: PipelineRunJobRegistry,
) -> None:
    """Service returns pipeline status with context."""
    job = job_registry.create_job("test theme", from_stage=0, to_stage=5)

    result = service.get_pipeline_status(job.pipeline_id)
    assert result is not None
    assert result["pipeline_id"] == job.pipeline_id
    assert result["theme"] == "test theme"
    assert result["status"] == str(PipelineRunStatus.QUEUED)


def test_get_pipeline_status_includes_context(
    service: PipelineRunService,
    job_registry: PipelineRunJobRegistry,
) -> None:
    """Service includes pipeline context when available."""
    job = job_registry.create_job("test theme", from_stage=0, to_stage=5)
    ctx = PipelineContext(
        pipeline_id=job.pipeline_id,
        theme="test theme",
        created_at=datetime.now(tz=UTC).isoformat(),
        current_stage=3,
    )
    job_registry.update_context(job.pipeline_id, ctx)

    result = service.get_pipeline_status(job.pipeline_id)
    assert result is not None
    assert "context" in result
    assert result["context"]["current_stage"] == 3


# ---------------------------------------------------------------------------
# Tests for stop_pipeline
# ---------------------------------------------------------------------------


def test_stop_pipeline_not_found(
    service: PipelineRunService,
) -> None:
    """Service raises PipelineNotFoundError for non-existent pipeline."""
    with pytest.raises(PipelineNotFoundError):
        service.stop_pipeline("nonexistent")


def test_stop_pipeline_not_active(
    service: PipelineRunService,
    job_registry: PipelineRunJobRegistry,
) -> None:
    """Service raises PipelineNotActiveError for completed pipeline."""
    job = job_registry.create_job("test theme", from_stage=0, to_stage=5)
    # Manually set to completed
    job.status = PipelineRunStatus.COMPLETED

    with pytest.raises(PipelineNotActiveError):
        service.stop_pipeline(job.pipeline_id)


def test_stop_pipeline_success(
    service: PipelineRunService,
    job_registry: PipelineRunJobRegistry,
) -> None:
    """Service successfully requests cancellation for active pipeline."""
    job = job_registry.create_job("test theme", from_stage=0, to_stage=5)
    job.status = PipelineRunStatus.RUNNING

    result = service.stop_pipeline(job.pipeline_id)
    assert result["pipeline_id"] == job.pipeline_id
    assert result["status"] == "cancelling"

    # Verify cancel was requested on the job
    updated_job = job_registry.get_job(job.pipeline_id)
    assert updated_job is not None
    assert updated_job.stop_requested is True


# ---------------------------------------------------------------------------
# Tests for start_pipeline
# ---------------------------------------------------------------------------


@patch("asyncio.create_task", mock_create_task)
@patch("asyncio.create_task", mock_create_task)
def test_start_pipeline_returns_result(
    service: PipelineRunService,
    event_router: MagicMock,
    mock_pipeline_factory: MockPipelineFactory,
) -> None:
    """Service starts a new pipeline and returns result synchronously."""
    result = service.start_pipeline("test theme", from_stage=0, to_stage=3)

    assert isinstance(result, PipelineRunResult)
    assert result.theme == "test theme"
    assert result.from_stage == 0
    assert result.to_stage == 3
    assert result.status == str(PipelineRunStatus.QUEUED)


@patch("asyncio.create_task", mock_create_task)
def test_start_pipeline_creates_job_in_registry(
    service: PipelineRunService,
    job_registry: PipelineRunJobRegistry,
) -> None:
    """Service creates a job in the registry."""
    result = service.start_pipeline("test theme", from_stage=0, to_stage=3)

    job = job_registry.get_job(result.pipeline_id)
    assert job is not None
    assert job.theme == "test theme"


@patch("asyncio.create_task", mock_create_task)
def test_start_pipeline_attaches_task(
    service: PipelineRunService,
    job_registry: PipelineRunJobRegistry,
) -> None:
    """Service attaches an asyncio task to the job."""
    result = service.start_pipeline("test theme", from_stage=0, to_stage=3)

    job = job_registry.get_job(result.pipeline_id)
    assert job is not None
    assert job.task is not None


# ---------------------------------------------------------------------------
# Tests for resume_pipeline
# ---------------------------------------------------------------------------


def test_resume_pipeline_not_found(
    service: PipelineRunService,
) -> None:
    """Service raises PipelineNotFoundError for non-existent pipeline."""
    with pytest.raises(PipelineNotFoundError):
        service.resume_pipeline("nonexistent", from_stage=0)


def test_resume_pipeline_already_active(
    service: PipelineRunService,
    job_registry: PipelineRunJobRegistry,
) -> None:
    """Service raises PipelineNotActiveError for active pipeline."""
    job = job_registry.create_job("test theme", from_stage=0, to_stage=5)
    job.status = PipelineRunStatus.RUNNING

    with pytest.raises(PipelineNotActiveError):
        service.resume_pipeline(job.pipeline_id, from_stage=0)


def test_resume_pipeline_no_context(
    service: PipelineRunService,
    job_registry: PipelineRunJobRegistry,
) -> None:
    """Service raises ResumeContextError when no saved context."""
    job = job_registry.create_job("test theme", from_stage=0, to_stage=5)
    job.status = PipelineRunStatus.FAILED

    with pytest.raises(ResumeContextError, match="No saved context"):
        service.resume_pipeline(job.pipeline_id, from_stage=0)


@patch("asyncio.create_task", mock_create_task)
def test_resume_pipeline_success(
    service: PipelineRunService,
    job_registry: PipelineRunJobRegistry,
    mock_pipeline_factory: MockPipelineFactory,
) -> None:
    """Service successfully resumes a completed pipeline."""
    # Create and complete a pipeline
    original_job = job_registry.create_job("test theme", from_stage=0, to_stage=5)
    ctx = PipelineContext(
        pipeline_id=original_job.pipeline_id,
        theme="test theme",
        created_at=datetime.now(tz=UTC).isoformat(),
        current_stage=3,
    )
    job_registry.update_context(original_job.pipeline_id, ctx)
    job_registry.mark_completed(original_job.pipeline_id, context=ctx)

    # Resume from stage 3
    result = service.resume_pipeline(original_job.pipeline_id, from_stage=3)

    assert isinstance(result, PipelineRunResult)
    assert result.theme == "test theme"
    assert result.from_stage == 3
    assert result.pipeline_id != original_job.pipeline_id  # New job created


@patch("asyncio.create_task", mock_create_task)
def test_resume_pipeline_creates_new_job(
    service: PipelineRunService,
    job_registry: PipelineRunJobRegistry,
    mock_pipeline_factory: MockPipelineFactory,
) -> None:
    """Resume creates a distinct job for each resume attempt."""
    original_job = job_registry.create_job("test theme", from_stage=0, to_stage=5)
    ctx = PipelineContext(
        pipeline_id=original_job.pipeline_id,
        theme="test theme",
        created_at=datetime.now(tz=UTC).isoformat(),
        current_stage=3,
    )
    job_registry.update_context(original_job.pipeline_id, ctx)
    job_registry.mark_completed(original_job.pipeline_id, context=ctx)

    result1 = service.resume_pipeline(original_job.pipeline_id, from_stage=3)
    result2 = service.resume_pipeline(original_job.pipeline_id, from_stage=3)

    # Each resume should create a distinct job
    assert result1.pipeline_id != result2.pipeline_id
    assert result1.pipeline_id.startswith(original_job.pipeline_id)
    assert result2.pipeline_id.startswith(original_job.pipeline_id)


# ---------------------------------------------------------------------------
# Tests for start_from_backlog_item
# ---------------------------------------------------------------------------


def test_start_from_backlog_item_duplicate_active(
    service: PipelineRunService,
    job_registry: PipelineRunJobRegistry,
) -> None:
    """Service raises DuplicateActiveItemError when item already has active pipeline."""
    # Create an active job with a selected idea
    job = job_registry.create_job("test theme", from_stage=0, to_stage=5)
    job.status = PipelineRunStatus.RUNNING
    ctx = PipelineContext(
        pipeline_id=job.pipeline_id,
        theme="test theme",
        created_at=datetime.now(tz=UTC).isoformat(),
        current_stage=0,
        selected_idea_id="idea-123",
    )
    job_registry.update_context(job.pipeline_id, ctx)

    # Try to start from the same idea
    item = BacklogItem(
        idea_id="idea-123",
        idea="Test idea",
        title="Test title",
    )

    with pytest.raises(DuplicateActiveItemError) as exc_info:
        service.start_from_backlog_item(item)

    assert exc_info.value.pipeline_id == job.pipeline_id


@patch("asyncio.create_task", mock_create_task)
def test_start_from_backlog_item_success(
    service: PipelineRunService,
    job_registry: PipelineRunJobRegistry,
) -> None:
    """Service successfully starts from a backlog item."""
    item = BacklogItem(
        idea_id="idea-456",
        idea="Another idea",
        title="Another title",
        source_theme="parent theme",
    )

    result = service.start_from_backlog_item(item)

    assert isinstance(result, PipelineRunResult)
    assert result.theme == "parent theme"
    assert result.from_stage == 4  # Starts at generate_angles
    assert result.to_stage == len(PIPELINE_STAGES) - 1

    # Verify job was created
    job = job_registry.get_job(result.pipeline_id)
    assert job is not None
    assert job.from_stage == 4


@patch("asyncio.create_task", mock_create_task)
def test_start_from_backlog_item_seeds_context(
    service: PipelineRunService,
    job_registry: PipelineRunJobRegistry,
) -> None:
    """Service seeds context with the backlog item as primary candidate."""
    item = BacklogItem(
        idea_id="idea-789",
        idea="Test idea",
        title="Test title",
        source_theme="parent theme",
    )

    result = service.start_from_backlog_item(item)

    job = job_registry.get_job(result.pipeline_id)
    assert job is not None
    assert job.pipeline_context is not None
    assert job.pipeline_context.selected_idea_id == "idea-789"
    assert job.pipeline_context.current_stage == 4


# ---------------------------------------------------------------------------
# Tests for cancellation behavior
# ---------------------------------------------------------------------------


@patch("asyncio.create_task", mock_create_task)
def test_cancellation_stops_pipeline(
    service: PipelineRunService,
    job_registry: PipelineRunJobRegistry,
    event_router: MagicMock,
    mock_pipeline_factory: MockPipelineFactory,
) -> None:
    """Verify cancellation is observable in tests."""
    # Start a pipeline
    result = service.start_pipeline("test theme", from_stage=0, to_stage=10)

    # Request cancellation
    cancel_result = service.stop_pipeline(result.pipeline_id)
    assert cancel_result["status"] == "cancelling"

    # Verify the job has stop_requested set
    job = job_registry.get_job(result.pipeline_id)
    assert job is not None
    assert job.stop_requested is True


# ---------------------------------------------------------------------------
# Tests for response payload compatibility
# ---------------------------------------------------------------------------


def test_job_summary_has_required_fields(
    service: PipelineRunService,
    job_registry: PipelineRunJobRegistry,
) -> None:
    """Verify job summary has all required fields for backward compatibility."""
    job = job_registry.create_job("test theme", from_stage=2, to_stage=8)

    result = service.get_pipeline_status(job.pipeline_id)

    assert result is not None
    # Required fields per acceptance criteria
    assert "pipeline_id" in result
    assert "theme" in result
    assert "from_stage" in result
    assert "to_stage" in result
    assert "status" in result
    assert "current_stage" in result
    assert "error" in result
    assert "created_at" in result
    assert "started_at" in result
    assert "completed_at" in result


@patch("asyncio.create_task", mock_create_task)
def test_pipeline_run_result_fields(
    service: PipelineRunService,
) -> None:
    """Verify PipelineRunResult has all required fields."""
    result = service.start_pipeline("test theme", from_stage=1, to_stage=7)

    assert result.pipeline_id is not None
    assert result.theme == "test theme"
    assert result.from_stage == 1
    assert result.to_stage == 7
    assert result.status == str(PipelineRunStatus.QUEUED)
    assert result.current_stage == 1
    assert result.error is None
    assert result.created_at is not None
    assert result.started_at is None
    assert result.completed_at is None


@patch("asyncio.create_task", mock_create_task)
def test_resume_pipeline_validates_context(
    service: PipelineRunService,
    job_registry: PipelineRunJobRegistry,
    mock_pipeline_factory: MockPipelineFactory,
) -> None:
    """Resume validates context before proceeding."""
    original_job = job_registry.create_job("test theme", from_stage=0, to_stage=5)
    ctx = PipelineContext(
        pipeline_id=original_job.pipeline_id,
        theme="test theme",
        created_at=datetime.now(tz=UTC).isoformat(),
        current_stage=3,
    )
    job_registry.update_context(original_job.pipeline_id, ctx)
    job_registry.mark_completed(original_job.pipeline_id, context=ctx)

    # Validate that validate_resume_context was called on the mock
    service.resume_pipeline(original_job.pipeline_id, from_stage=3)
    assert mock_pipeline_factory.validate_resume_context_called
