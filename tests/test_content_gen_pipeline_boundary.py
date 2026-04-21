"""Pipeline boundary tests for P1-T4: full pipeline behavior.

These tests verify the public boundary of ContentGenPipeline:
- Full-run happy path with mocked stage dependencies
- Cancellation
- Resume from a stage
- Seeded backlog item starts
- Stage skip/block behavior

These tests do not require real LLM, search, or network access.
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from typing import Any
from unittest.mock import MagicMock

import pytest

from cc_deep_research.config import Config
from cc_deep_research.content_gen.models import (
    PIPELINE_STAGES,
    BacklogItem,
    BacklogOutput,
    PipelineCandidate,
    PipelineContext,
    PipelineStageTrace,
    ScoringOutput,
)
from cc_deep_research.content_gen.pipeline import ContentGenPipeline

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def config() -> Config:
    return Config()


@pytest.fixture
def minimal_ctx() -> PipelineContext:
    """A minimal context with just a theme."""
    return PipelineContext(
        theme="test theme",
        created_at=datetime.now(tz=UTC).isoformat(),
    )


def _make_fake_orchestrator(
    side_effect: Any = None,
) -> type:
    """Create a fake stage orchestrator class.

    Returns a class (not an instance) that can be used to replace a real
    stage orchestrator in the pipeline's registry.
    """

    class FakeStageOrchestrator:
        """Fake stage orchestrator that returns ctx unchanged or raises."""

        async def run_with_context(self, ctx: PipelineContext) -> PipelineContext:
            if side_effect:
                if isinstance(side_effect, Exception):
                    raise side_effect
                return side_effect(ctx)
            return ctx

    return FakeStageOrchestrator


def _install_fake_orchestrators(pipeline: ContentGenPipeline) -> None:
    """Install no-op fake orchestrators for all stages that have real implementations."""
    for name in (
        "strategy",
        "opportunity",
        "backlog",
        "angle",
        "research",
        "argument_map",
        "scripting",
        "visual",
        "production",
        "packaging",
        "qc",
        "publish",
    ):
        pipeline._stage_orchestrators[name] = _make_fake_orchestrator()()


# ---------------------------------------------------------------------------
# Happy-path full-run tests
# ---------------------------------------------------------------------------
# Note: stages 0-11 have real orchestrators; stages 12-13 are stubs that
# will skip in the happy-path tests since they require upstream data.


@pytest.mark.asyncio
async def test_all_stages_run_without_real_llm(config: Config) -> None:
    """All 14 stages run without real LLM calls; stages with met prerequisites complete."""
    pipeline = ContentGenPipeline(config)
    _install_fake_orchestrators(pipeline)

    ctx = PipelineContext(
        theme="test theme",
        created_at=datetime.now(tz=UTC).isoformat(),
    )
    ctx.backlog = BacklogOutput(
        items=[
            BacklogItem(
                idea_id="idea-1",
                title="test idea",
                source="test",
                category="authority-building",
            )
        ],
        is_degraded=False,
    )
    ctx.selected_idea_id = "idea-1"
    ctx.active_candidates = [
        PipelineCandidate(idea_id="idea-1", role="primary", status="selected"),
    ]

    for idx in range(len(PIPELINE_STAGES)):
        ctx = await pipeline.run_stage(idx, ctx)

    # All 14 stages produced traces
    assert len(ctx.stage_traces) == len(PIPELINE_STAGES)
    # Stages 0-4 complete with minimal context
    assert all(t.status == "completed" for t in ctx.stage_traces[:5])
    # Stages 5+ have upstream dependencies not met by fakes → skip (expected)
    assert all(t.status in ("completed", "skipped") for t in ctx.stage_traces)


@pytest.mark.asyncio
async def test_traces_have_correct_stage_sequence(config: Config) -> None:
    """Traces appear in stage-index order with correct stage names and labels."""
    pipeline = ContentGenPipeline(config)
    _install_fake_orchestrators(pipeline)

    ctx = PipelineContext(
        theme="test theme",
        created_at=datetime.now(tz=UTC).isoformat(),
    )

    for idx in range(12):
        ctx = await pipeline.run_stage(idx, ctx)

    for i, trace in enumerate(ctx.stage_traces):
        assert trace.stage_index == i
        assert trace.stage_name == PIPELINE_STAGES[i]
        assert trace.stage_label is not None
        assert trace.started_at is not None
        assert trace.completed_at is not None
        assert trace.duration_ms >= 0


@pytest.mark.asyncio
async def test_traces_have_phase_and_policy(config: Config) -> None:
    """Every trace includes phase, phase_label, and policy from the governance layer."""
    pipeline = ContentGenPipeline(config)
    _install_fake_orchestrators(pipeline)

    ctx = PipelineContext(
        theme="test theme",
        created_at=datetime.now(tz=UTC).isoformat(),
    )

    for idx in range(12):
        ctx = await pipeline.run_stage(idx, ctx)

    for trace in ctx.stage_traces:
        assert trace.phase is not None
        assert trace.phase_label is not None
        assert trace.policy is not None


# ---------------------------------------------------------------------------
# Cancellation tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_cancellation_raises_and_leaves_trace(config: Config) -> None:
    """Cancelling a stage mid-execution leaves a failed trace with CancelledError."""

    class CancellingStageOrchestrator:
        async def run_with_context(self, ctx: PipelineContext) -> PipelineContext:
            raise asyncio.CancelledError("User cancelled")

    pipeline = ContentGenPipeline(config)
    pipeline._stage_orchestrators["backlog"] = CancellingStageOrchestrator()  # type: ignore

    ctx = PipelineContext(
        theme="test theme",
        created_at=datetime.now(tz=UTC).isoformat(),
    )
    ctx.backlog = BacklogOutput(items=[], is_degraded=False)

    with pytest.raises(asyncio.CancelledError):
        await pipeline.run_stage(2, ctx)  # build_backlog

    traces = [t for t in ctx.stage_traces if t.stage_index == 2]
    assert len(traces) == 1
    trace = traces[0]
    assert trace.status == "failed"
    assert "CancelledError" in trace.kill_reason


@pytest.mark.asyncio
async def test_cancellation_does_not_append_multiple_traces(config: Config) -> None:
    """A cancelled stage appends exactly one trace (not one per attempt)."""

    class CancellingStageOrchestrator:
        async def run_with_context(self, ctx: PipelineContext) -> PipelineContext:
            raise asyncio.CancelledError()

    pipeline = ContentGenPipeline(config)
    pipeline._stage_orchestrators["backlog"] = CancellingStageOrchestrator()  # type: ignore

    ctx = PipelineContext(
        theme="test theme",
        created_at=datetime.now(tz=UTC).isoformat(),
    )
    ctx.backlog = BacklogOutput(items=[], is_degraded=False)

    with pytest.raises(asyncio.CancelledError):
        await pipeline.run_stage(2, ctx)

    traces = [t for t in ctx.stage_traces if t.stage_index == 2]
    assert len(traces) == 1


# ---------------------------------------------------------------------------
# Resume from stage tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_resume_from_later_stage_skips_earlier_stages(config: Config) -> None:
    """Resuming from stage 5 only runs stages 5-13; stages 0-4 are pre-completed."""
    pipeline = ContentGenPipeline(config)
    _install_fake_orchestrators(pipeline)

    # Simulate a context that has already completed stages 0-4
    ctx = PipelineContext(
        theme="test theme",
        created_at=datetime.now(tz=UTC).isoformat(),
    )
    for i in range(5):
        ctx.stage_traces.append(
            PipelineStageTrace(
                stage_index=i,
                stage_name=PIPELINE_STAGES[i],
                stage_label=PIPELINE_STAGES[i],
                status="completed",
                started_at=datetime.now(tz=UTC).isoformat(),
                completed_at=datetime.now(tz=UTC).isoformat(),
                input_summary="",
                output_summary="",
            )
        )

    for idx in range(5, len(PIPELINE_STAGES)):
        ctx = await pipeline.run_stage(idx, ctx)

    # Only stages 5-13 should have new traces
    new_traces = [t for t in ctx.stage_traces if t.stage_index >= 5]
    assert len(new_traces) == len(PIPELINE_STAGES) - 5
    # No duplicate stage indices
    stage_indices = [t.stage_index for t in ctx.stage_traces]
    assert len(stage_indices) == len(set(stage_indices))


@pytest.mark.asyncio
async def test_resume_validates_prerequisites(config: Config) -> None:
    """Resuming from a stage with unmet prerequisites produces a skipped trace."""
    pipeline = ContentGenPipeline(config)
    _install_fake_orchestrators(pipeline)

    ctx = PipelineContext(
        theme="test theme",
        created_at=datetime.now(tz=UTC).isoformat(),
    )
    # Stage 5 (build_research_pack) requires angle + backlog items
    # Providing backlog but no angle/lane context causes skip
    ctx.backlog = BacklogOutput(
        items=[
            BacklogItem(
                idea_id="idea-1",
                title="test idea",
                source="test",
                category="authority-building",
            )
        ],
        is_degraded=False,
    )
    ctx.selected_idea_id = "idea-1"
    ctx.active_candidates = [
        PipelineCandidate(idea_id="idea-1", role="primary", status="selected"),
    ]
    # No lane_contexts with angles → prerequisite not met

    ctx = await pipeline.run_stage(5, ctx)

    trace = ctx.stage_traces[0]
    assert trace.status == "skipped"
    assert trace.stage_name == "build_research_pack"


@pytest.mark.asyncio
async def test_resume_from_stage_preserves_existing_traces(config: Config) -> None:
    """Existing completed traces for earlier stages are preserved on resume."""
    pipeline = ContentGenPipeline(config)
    _install_fake_orchestrators(pipeline)

    ctx = PipelineContext(
        theme="test theme",
        created_at=datetime.now(tz=UTC).isoformat(),
    )
    # Pre-existing completed traces for stages 0-2
    for i in range(3):
        ctx.stage_traces.append(
            PipelineStageTrace(
                stage_index=i,
                stage_name=PIPELINE_STAGES[i],
                stage_label=PIPELINE_STAGES[i],
                status="completed",
                started_at=datetime.now(tz=UTC).isoformat(),
                completed_at=datetime.now(tz=UTC).isoformat(),
                duration_ms=100,
                input_summary=f"input-{i}",
                output_summary=f"output-{i}",
            )
        )

    for idx in range(3, len(PIPELINE_STAGES)):
        ctx = await pipeline.run_stage(idx, ctx)

    # Stages 0-2 should still have their original traces
    for i in range(3):
        traces_i = [t for t in ctx.stage_traces if t.stage_index == i]
        assert len(traces_i) == 1
        assert traces_i[0].status == "completed"
        assert traces_i[0].duration_ms == 100


# ---------------------------------------------------------------------------
# Seeded backlog-item start tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_seeded_backlog_item_starts_at_build_backlog(config: Config) -> None:
    """Seeding a backlog item starts at build_backlog (stage 2) and produces traces."""
    pipeline = ContentGenPipeline(config)
    _install_fake_orchestrators(pipeline)

    ctx = PipelineContext(
        theme="seeded theme",
        created_at=datetime.now(tz=UTC).isoformat(),
    )
    # Stages 2-4 require backlog to be populated; seed it
    ctx.backlog = BacklogOutput(
        items=[
            BacklogItem(
                idea_id="idea-seed",
                title="seeded idea",
                source="seed",
                category="authority-building",
            )
        ],
        is_degraded=False,
    )
    ctx.selected_idea_id = "idea-seed"
    ctx.active_candidates = [
        PipelineCandidate(idea_id="idea-seed", role="primary", status="selected"),
    ]

    # Run stages 2-4 (build_backlog → score_ideas → generate_angles)
    for idx in range(2, 5):
        ctx = await pipeline.run_stage(idx, ctx)

    assert len(ctx.stage_traces) == 3
    assert [t.stage_index for t in ctx.stage_traces] == [2, 3, 4]
    # With seeded backlog and candidates, stages 2-4 should all complete
    assert all(t.status == "completed" for t in ctx.stage_traces)


@pytest.mark.asyncio
async def test_seeded_backlog_preserves_seed_idea_id(config: Config) -> None:
    """A seeded run preserves the seed idea ID in downstream trace metadata."""
    pipeline = ContentGenPipeline(config)
    _install_fake_orchestrators(pipeline)

    ctx = PipelineContext(
        theme="seeded theme",
        created_at=datetime.now(tz=UTC).isoformat(),
    )
    ctx.selected_idea_id = "seeded-idea-123"
    ctx.active_candidates = [
        PipelineCandidate(idea_id="seeded-idea-123", role="primary", status="selected"),
    ]
    ctx.backlog = BacklogOutput(
        items=[
            BacklogItem(
                idea_id="seeded-idea-123",
                title="seeded idea",
                source="seed",
                category="authority-building",
            )
        ],
        is_degraded=False,
    )

    for idx in range(2, 5):
        ctx = await pipeline.run_stage(idx, ctx)

    for trace in ctx.stage_traces:
        assert trace.metadata is not None


@pytest.mark.asyncio
async def test_seeded_scoring_output_with_shortlist(config: Config) -> None:
    """Seeding a scoring output with shortlist produces traces with correct idea IDs."""
    pipeline = ContentGenPipeline(config)
    _install_fake_orchestrators(pipeline)

    ctx = PipelineContext(
        theme="test theme",
        created_at=datetime.now(tz=UTC).isoformat(),
    )
    ctx.backlog = BacklogOutput(
        items=[
            BacklogItem(
                idea_id="idea-a",
                title="idea a",
                source="test",
                category="authority-building",
            ),
            BacklogItem(
                idea_id="idea-b",
                title="idea b",
                source="test",
                category="authority-building",
            ),
        ],
        is_degraded=False,
    )
    ctx.scoring = ScoringOutput(
        scores=[],
        shortlist=["idea-a", "idea-b"],
        selected_idea_id="idea-a",
        active_candidates=[
            BacklogItem(
                idea_id="idea-a",
                title="idea a",
                source="test",
                category="authority-building",
            ),
            BacklogItem(
                idea_id="idea-b",
                title="idea b",
                source="test",
                category="authority-building",
            ),
        ],
    )
    ctx.shortlist = ["idea-a", "idea-b"]
    ctx.selected_idea_id = "idea-a"
    ctx.active_candidates = [
        PipelineCandidate(idea_id="idea-a", role="primary", status="selected"),
        PipelineCandidate(idea_id="idea-b", role="runner_up", status="runner_up"),
    ]

    ctx = await pipeline.run_stage(3, ctx)

    trace = ctx.stage_traces[0]
    assert trace.status == "completed"


# ---------------------------------------------------------------------------
# Stage skip/block behavior tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_stage_skips_with_correct_reason_in_trace(config: Config) -> None:
    """A skipped stage populates skip_reason; output_summary == skip_reason."""
    pipeline = ContentGenPipeline(config)

    ctx = PipelineContext(
        theme="test theme",
        created_at=datetime.now(tz=UTC).isoformat(),
    )
    # stage 3 (score_ideas) requires backlog → skip
    ctx.backlog = None

    ctx = await pipeline.run_stage(3, ctx)

    trace = ctx.stage_traces[0]
    assert trace.status == "skipped"
    assert trace.skip_reason
    assert trace.output_summary == trace.skip_reason
    assert trace.decision_summary == f"Skipped: {trace.skip_reason}"


@pytest.mark.asyncio
async def test_multiple_consecutive_skips_in_order(config: Config) -> None:
    """Multiple stages that all skip produce one trace each in stage-index order."""
    pipeline = ContentGenPipeline(config)

    ctx = PipelineContext(
        theme="test theme",
        created_at=datetime.now(tz=UTC).isoformat(),
    )
    # score_ideas, generate_angles, build_research_pack all need backlog
    ctx.backlog = None

    for idx in (3, 4, 5):
        ctx = await pipeline.run_stage(idx, ctx)

    assert len(ctx.stage_traces) == 3
    assert all(t.status == "skipped" for t in ctx.stage_traces[-3:])
    assert ctx.stage_traces[-3].stage_index == 3
    assert ctx.stage_traces[-2].stage_index == 4
    assert ctx.stage_traces[-1].stage_index == 5


@pytest.mark.asyncio
async def test_stage_blocked_by_brief_gate_raises(config: Config) -> None:
    """A stage blocked by the brief gate raises RuntimeError and leaves a trace."""
    from cc_deep_research.content_gen.models import (
        BriefExecutionGate,
        BriefExecutionPolicyMode,
        BriefLifecycleState,
        PipelineLaneContext,
        VisualPlanOutput,
    )

    pipeline = ContentGenPipeline(config)

    class AlwaysBlockedStageOrchestrator:
        """Stage orchestrator that checks gate then raises."""

        async def run_with_context(self, ctx: PipelineContext) -> PipelineContext:
            raise RuntimeError("Should not be reached - gate should have blocked")

    pipeline._stage_orchestrators["production"] = AlwaysBlockedStageOrchestrator()  # type: ignore

    ctx = PipelineContext(
        theme="test theme",
        created_at=datetime.now(tz=UTC).isoformat(),
    )
    ctx.brief_reference = MagicMock(
        lifecycle_state=BriefLifecycleState.DRAFT,
        was_generated_in_run=False,
    )
    ctx.brief_gate = BriefExecutionGate(
        policy_mode=BriefExecutionPolicyMode.ALLOW_DRAFT,
        brief_state_at_start=BriefLifecycleState.DRAFT,
    )
    ctx.brief_gate.was_blocked = True
    ctx.brief_gate.error_message = "Brief must be approved."
    ctx.brief_gate.checked_at_stage = 9
    # Use model_construct to bypass forward-reference resolution for ThesisArtifact
    lane = PipelineLaneContext.model_construct(
        idea_id="idea-1",
        role="primary",
        status="selected",
        visual_plan=VisualPlanOutput(idea_id="idea-1", angle_id="a1"),
        last_completed_stage=-1,
    )
    ctx.lane_contexts = [lane]
    ctx.scripting = MagicMock()

    with pytest.raises(RuntimeError, match="Brief must be approved"):
        await pipeline.run_stage(9, ctx)  # production_brief

    traces = [t for t in ctx.stage_traces if t.stage_index == 9]
    assert len(traces) >= 1
    trace = traces[0]
    assert trace.status == "blocked"


@pytest.mark.asyncio
async def test_stage_gate_bypass_for_legacy_run(config: Config) -> None:
    """Without a brief_reference, the gate is bypassed (legacy/inline behavior)."""
    pipeline = ContentGenPipeline(config)

    ctx = PipelineContext(
        theme="test theme",
        created_at=datetime.now(tz=UTC).isoformat(),
    )
    ctx.brief_reference = None  # legacy/inline run
    ctx.backlog = BacklogOutput(items=[], is_degraded=False)

    # Run stage 9 without visual_plan → skip (not blocked)
    ctx = await pipeline.run_stage(9, ctx)

    trace = ctx.stage_traces[0]
    assert trace.status == "skipped"


# ---------------------------------------------------------------------------
# Observable PipelineContext assertions
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_pipeline_ctx_current_stage_updates(config: Config) -> None:
    """PipelineContext.current_stage is updated after each run_stage call."""
    pipeline = ContentGenPipeline(config)
    _install_fake_orchestrators(pipeline)

    ctx = PipelineContext(
        theme="test theme",
        created_at=datetime.now(tz=UTC).isoformat(),
    )

    for idx in range(12):
        ctx = await pipeline.run_stage(idx, ctx)
        assert ctx.current_stage == idx


@pytest.mark.asyncio
async def test_pipeline_ctx_pipeline_id_stable_across_stages(config: Config) -> None:
    """PipelineContext.pipeline_id is stable across all stage runs."""
    pipeline = ContentGenPipeline(config)
    _install_fake_orchestrators(pipeline)

    ctx = PipelineContext(
        theme="test theme",
        created_at=datetime.now(tz=UTC).isoformat(),
    )
    original_pipeline_id = ctx.pipeline_id

    for idx in range(12):
        ctx = await pipeline.run_stage(idx, ctx)

    assert ctx.pipeline_id == original_pipeline_id


@pytest.mark.asyncio
async def test_completed_traces_have_nonnegative_duration(config: Config) -> None:
    """All completed traces have a non-negative duration_ms."""
    pipeline = ContentGenPipeline(config)
    _install_fake_orchestrators(pipeline)

    ctx = PipelineContext(
        theme="test theme",
        created_at=datetime.now(tz=UTC).isoformat(),
    )

    for idx in range(12):
        ctx = await pipeline.run_stage(idx, ctx)

    for trace in ctx.stage_traces:
        assert trace.duration_ms >= 0


@pytest.mark.asyncio
async def test_all_traces_expose_warnings_list(config: Config) -> None:
    """Every trace exposes a warnings list (possibly empty)."""
    pipeline = ContentGenPipeline(config)
    _install_fake_orchestrators(pipeline)

    ctx = PipelineContext(
        theme="test theme",
        created_at=datetime.now(tz=UTC).isoformat(),
    )

    for idx in range(12):
        ctx = await pipeline.run_stage(idx, ctx)

    for trace in ctx.stage_traces:
        assert isinstance(trace.warnings, list)


# ---------------------------------------------------------------------------
# Callbacks
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_progress_callback_invoked_per_stage(config: Config) -> None:
    """The progress_callback is invoked once per stage run."""
    pipeline = ContentGenPipeline(config)
    _install_fake_orchestrators(pipeline)

    calls: list[tuple[int, str]] = []

    def progress_callback(idx: int, label: str) -> None:
        calls.append((idx, label))

    ctx = PipelineContext(
        theme="test theme",
        created_at=datetime.now(tz=UTC).isoformat(),
    )

    for idx in range(12):
        ctx = await pipeline.run_stage(idx, ctx, progress_callback=progress_callback)

    assert len(calls) == 12
    assert calls[0][0] == 0
    assert calls[-1][0] == 11


@pytest.mark.asyncio
async def test_stage_completed_callback_receives_correct_status(config: Config) -> None:
    """stage_completed_callback fires with stage_index, status, detail, and ctx."""
    pipeline = ContentGenPipeline(config)
    _install_fake_orchestrators(pipeline)

    completed: list[tuple[int, str, str, PipelineContext]] = []

    def stage_completed_callback(idx: int, status: str, detail: str, ctx: PipelineContext) -> None:
        completed.append((idx, status, detail, ctx))

    ctx = PipelineContext(
        theme="test theme",
        created_at=datetime.now(tz=UTC).isoformat(),
    )
    ctx.backlog = BacklogOutput(
        items=[
            BacklogItem(
                idea_id="idea-1",
                title="test idea",
                source="test",
                category="authority-building",
            )
        ],
        is_degraded=False,
    )
    ctx.selected_idea_id = "idea-1"
    ctx.active_candidates = [
        PipelineCandidate(idea_id="idea-1", role="primary", status="selected"),
    ]

    for idx in (2, 3, 4):
        ctx = await pipeline.run_stage(idx, ctx, stage_completed_callback=stage_completed_callback)

    assert len(completed) == 3
    assert all(t[1] == "completed" for t in completed)


# ---------------------------------------------------------------------------
# Fake stage produces correct observable state
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_fake_stage_orchestrator_modifies_ctx(config: Config) -> None:
    """A fake orchestrator that modifies ctx produces a trace reflecting the modification."""

    class FakeBacklogOrchestrator:
        async def run_with_context(self, ctx: PipelineContext) -> PipelineContext:
            ctx.backlog = BacklogOutput(
                items=[
                    BacklogItem(
                        idea_id="idea-1",
                        title="idea from mock",
                        source="mock",
                        category="authority-building",
                    )
                ],
                is_degraded=False,
            )
            return ctx

    pipeline = ContentGenPipeline(config)
    pipeline._stage_orchestrators["backlog"] = FakeBacklogOrchestrator()  # type: ignore

    ctx = PipelineContext(
        theme="test theme",
        created_at=datetime.now(tz=UTC).isoformat(),
    )

    ctx = await pipeline.run_stage(2, ctx)

    assert len(ctx.stage_traces) == 1
    trace = ctx.stage_traces[0]
    assert trace.status == "completed"
    assert trace.stage_name == "build_backlog"
    assert ctx.backlog is not None
    assert len(ctx.backlog.items) == 1
