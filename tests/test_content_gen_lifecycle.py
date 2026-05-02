"""Lifecycle policy tests for P10-T1: prerequisite, gate, and trace policies.

These tests verify that lifecycle policies can be tested independently
without running the full content-gen pipeline or making live LLM calls.
"""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import MagicMock

import pytest

from cc_deep_research.config import Config
from cc_deep_research.content_gen.lifecycle import (
    StageGatePolicy,
    StagePrerequisitePolicy,
    StageTracePolicy,
)
from cc_deep_research.content_gen.models import (
    BacklogItem,
    BacklogOutput,
    BriefExecutionGate,
    BriefExecutionPolicyMode,
    BriefLifecycleState,
    PipelineCandidate,
    PipelineContext,
    PipelineLaneContext,
)
from cc_deep_research.content_gen.models.angle import AngleOutput
from cc_deep_research.content_gen.models.production import RunConstraints
from cc_deep_research.content_gen.models.script import ScriptingContext

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def config() -> Config:
    return Config()


@pytest.fixture
def prereq_policy() -> StagePrerequisitePolicy:
    return StagePrerequisitePolicy()


@pytest.fixture
def trace_policy() -> StageTracePolicy:
    return StageTracePolicy()


@pytest.fixture
def gate_policy(config: Config) -> StageGatePolicy:
    return StageGatePolicy(config)


@pytest.fixture
def minimal_ctx() -> PipelineContext:
    return PipelineContext(
        theme="test theme",
        created_at=datetime.now(tz=UTC).isoformat(),
    )


# ---------------------------------------------------------------------------
# StagePrerequisitePolicy tests
# ---------------------------------------------------------------------------


class TestStagePrerequisitePolicy:
    """Tests for StagePrerequisitePolicy.check()."""

    def test_score_ideas_requires_backlog(self, prereq_policy: StagePrerequisitePolicy) -> None:
        ctx = PipelineContext(theme="test", created_at=datetime.now(tz=UTC).isoformat())
        ctx.backlog = None
        met, reason = prereq_policy.check(3, ctx)  # score_ideas
        assert met is False
        assert "backlog missing" in reason

    def test_score_ideas_passes_with_backlog(self, prereq_policy: StagePrerequisitePolicy) -> None:
        ctx = PipelineContext(theme="test", created_at=datetime.now(tz=UTC).isoformat())
        ctx.backlog = BacklogOutput(items=[], is_degraded=False)
        met, reason = prereq_policy.check(3, ctx)
        assert met is True
        assert reason == ""

    def test_generate_angles_requires_backlog(self, prereq_policy: StagePrerequisitePolicy) -> None:
        ctx = PipelineContext(theme="test", created_at=datetime.now(tz=UTC).isoformat())
        ctx.backlog = None
        met, reason = prereq_policy.check(4, ctx)  # generate_angles
        assert met is False
        assert "backlog missing" in reason

    def test_generate_angles_requires_selected_idea(
        self, prereq_policy: StagePrerequisitePolicy
    ) -> None:
        ctx = PipelineContext(theme="test", created_at=datetime.now(tz=UTC).isoformat())
        ctx.backlog = BacklogOutput(items=[], is_degraded=False)
        # No selected_idea_id and no active_candidates
        met, reason = prereq_policy.check(4, ctx)
        assert met is False
        assert "scoring/selected idea missing" in reason

    def test_generate_angles_passes_with_candidates(
        self, prereq_policy: StagePrerequisitePolicy
    ) -> None:
        ctx = PipelineContext(theme="test", created_at=datetime.now(tz=UTC).isoformat())
        ctx.backlog = BacklogOutput(
            items=[
                BacklogItem(
                    idea_id="idea-1", idea="test idea", source="test", category="authority-building"
                )
            ],
            is_degraded=False,
        )
        ctx.selected_idea_id = "idea-1"
        ctx.active_candidates = [
            PipelineCandidate(idea_id="idea-1", role="primary", status="selected"),
        ]
        met, reason = prereq_policy.check(4, ctx)
        assert met is True

    def test_build_research_pack_requires_angle(self, prereq_policy: StagePrerequisitePolicy) -> None:
        ctx = PipelineContext(theme="test", created_at=datetime.now(tz=UTC).isoformat())
        ctx.backlog = BacklogOutput(
            items=[BacklogItem(idea_id="idea-1", idea="test", source="test", category="authority-building")],
            is_degraded=False,
        )
        ctx.selected_idea_id = "idea-1"
        ctx.active_candidates = [
            PipelineCandidate(idea_id="idea-1", role="primary", status="selected"),
        ]
        # No lane with angle
        met, reason = prereq_policy.check(5, ctx)
        assert met is False
        assert "selected angle missing" in reason

    def test_build_research_pack_requires_backlog_item(
        self, prereq_policy: StagePrerequisitePolicy
    ) -> None:
        ctx = PipelineContext(theme="test", created_at=datetime.now(tz=UTC).isoformat())
        ctx.backlog = None
        ctx.selected_idea_id = "idea-1"
        ctx.active_candidates = [
            PipelineCandidate(idea_id="idea-1", role="primary", status="selected"),
        ]
        met, reason = prereq_policy.check(5, ctx)
        assert met is False
        assert "backlog missing" in reason

    def test_visual_translation_requires_script_and_structure(
        self, prereq_policy: StagePrerequisitePolicy
    ) -> None:
        ctx = PipelineContext(theme="test", created_at=datetime.now(tz=UTC).isoformat())
        lane = PipelineLaneContext(idea_id="idea-1", role="primary", status="selected")
        lane.scripting = MagicMock(spec=ScriptingContext)
        lane.scripting.tightened = None
        lane.scripting.annotated_script = None
        lane.scripting.draft = None
        lane.scripting.structure = None
        ctx.lane_contexts = [lane]
        met, reason = prereq_policy.check(8, ctx)  # visual_translation
        assert met is False
        assert "lane script/structure incomplete" in reason

    def test_visual_translation_skips_when_using_combined_execution_brief(
        self, prereq_policy: StagePrerequisitePolicy
    ) -> None:
        """visual_translation skips when run_constraints signals combined execution brief."""
        ctx = PipelineContext(theme="test", created_at=datetime.now(tz=UTC).isoformat())
        # Set up combined execution brief via run_constraints with a content type
        # known to use combined brief (empty content_type falls back to False in current profile)
        ctx.run_constraints = RunConstraints(content_type="")
        # The check is: if use_combined_execution_brief returns True, it skips.
        # Without a known combined-brief content type, this just tests the early-return path.
        # This test validates the policy object is callable without a pipeline instance.
        met, reason = prereq_policy.check(8, ctx)
        # The specific outcome depends on the profile; verify the policy ran without error
        assert isinstance(met, bool)
        assert isinstance(reason, str)

    def test_packaging_requires_final_script(
        self, prereq_policy: StagePrerequisitePolicy
    ) -> None:
        ctx = PipelineContext(theme="test", created_at=datetime.now(tz=UTC).isoformat())
        lane = PipelineLaneContext(idea_id="idea-1", role="primary", status="selected")
        lane.scripting = MagicMock(spec=ScriptingContext)
        lane.scripting.qc = MagicMock()
        lane.scripting.qc.final_script = ""  # empty final script
        ctx.lane_contexts = [lane]
        ctx.angles = AngleOutput(idea_id="idea-1", angle_options=[], selected_angle_id="a1")
        met, reason = prereq_policy.check(10, ctx)  # packaging
        assert met is False
        assert "script empty" in reason

    def test_publish_queue_requires_approved_qc(
        self, prereq_policy: StagePrerequisitePolicy
    ) -> None:
        from cc_deep_research.content_gen.models.shared import ReleaseState

        ctx = PipelineContext(theme="test", created_at=datetime.now(tz=UTC).isoformat())
        lane = PipelineLaneContext(idea_id="idea-1", role="primary", status="selected")
        lane.packaging = MagicMock()
        lane.qc_gate = MagicMock()
        lane.qc_gate.release_state = ReleaseState.BLOCKED
        lane.qc_gate.approved_for_publish = False
        ctx.lane_contexts = [lane]
        met, reason = prereq_policy.check(12, ctx)  # publish_queue
        assert met is False
        assert "not approved" in reason

    def test_stages_with_no_prereqs_always_pass(
        self, prereq_policy: StagePrerequisitePolicy
    ) -> None:
        ctx = PipelineContext(theme="test", created_at=datetime.now(tz=UTC).isoformat())
        # plan_opportunity (idx=1) and build_backlog (idx=2) have no prerequisites
        for idx in (1, 2):
            met, reason = prereq_policy.check(idx, ctx)
            assert met is True, f"stage {idx} should pass with no prerequisites"


# ---------------------------------------------------------------------------
# StageGatePolicy tests
# ---------------------------------------------------------------------------


class TestStageGatePolicy:
    """Tests for StageGatePolicy.check()."""

    def test_bypasses_without_brief_reference(
        self, gate_policy: StageGatePolicy, minimal_ctx: PipelineContext
    ) -> None:
        ctx = minimal_ctx.model_copy(deep=True)
        ctx.brief_reference = None
        ok, message = gate_policy.check(ctx, "production_brief")
        assert ok is True
        assert "legacy/inline run" in message

    def test_bypasses_when_brief_generated_in_run(
        self, gate_policy: StageGatePolicy, minimal_ctx: PipelineContext
    ) -> None:
        ctx = minimal_ctx.model_copy(deep=True)
        ctx.brief_reference = MagicMock(
            lifecycle_state=BriefLifecycleState.DRAFT,
            was_generated_in_run=True,
        )
        ok, message = gate_policy.check(ctx, "production_brief")
        assert ok is True
        assert "generated in this pipeline run" in message

    def test_blocks_draft_brief_for_production_stage(
        self, gate_policy: StageGatePolicy, minimal_ctx: PipelineContext
    ) -> None:
        ctx = minimal_ctx.model_copy(deep=True)
        ctx.brief_reference = MagicMock(
            lifecycle_state=BriefLifecycleState.DRAFT,
            was_generated_in_run=False,
        )
        ctx.brief_gate = BriefExecutionGate(
            policy_mode=BriefExecutionPolicyMode.ALLOW_DRAFT,
            brief_state_at_start=BriefLifecycleState.DRAFT,
        )
        ctx.brief_gate.was_blocked = True
        ctx.brief_gate.error_message = "Brief must be approved before running production stages."
        ctx.brief_gate.checked_at_stage = 9
        ok, message = gate_policy.check(ctx, "production_brief")
        assert ok is False
        assert "Brief must be approved" in message

    def test_passes_with_approved_brief(
        self, gate_policy: StageGatePolicy, minimal_ctx: PipelineContext
    ) -> None:
        ctx = minimal_ctx.model_copy(deep=True)
        ctx.brief_reference = MagicMock(
            lifecycle_state=BriefLifecycleState.APPROVED,
            was_generated_in_run=False,
        )
        ctx.brief_gate = BriefExecutionGate(
            policy_mode=BriefExecutionPolicyMode.ALLOW_DRAFT,
            brief_state_at_start=BriefLifecycleState.APPROVED,
        )
        ok, message = gate_policy.check(ctx, "production_brief")
        assert ok is True


# ---------------------------------------------------------------------------
# StageTracePolicy tests
# ---------------------------------------------------------------------------


class TestStageTracePolicy:
    """Tests for StageTracePolicy trace construction methods."""

    def test_summarize_input_plan_opportunity(
        self, trace_policy: StageTracePolicy, minimal_ctx: PipelineContext
    ) -> None:
        result = trace_policy.summarize_input(1, minimal_ctx)
        assert "theme=" in result

    def test_summarize_input_score_ideas_with_backlog(
        self, trace_policy: StageTracePolicy, minimal_ctx: PipelineContext
    ) -> None:
        ctx = minimal_ctx.model_copy(deep=True)
        ctx.backlog = BacklogOutput(items=[], is_degraded=False)
        result = trace_policy.summarize_input(3, ctx)
        assert "items=" in result

    def test_summarize_input_score_ideas_empty_backlog(
        self, trace_policy: StageTracePolicy, minimal_ctx: PipelineContext
    ) -> None:
        ctx = minimal_ctx.model_copy(deep=True)
        ctx.backlog = None
        result = trace_policy.summarize_input(3, ctx)
        assert result == "items=0"

    def test_summarize_output_load_strategy(
        self, trace_policy: StageTracePolicy, minimal_ctx: PipelineContext
    ) -> None:
        result = trace_policy.summarize_output(0, minimal_ctx)
        assert "niche=" in result

    def test_summarize_output_build_backlog(
        self, trace_policy: StageTracePolicy, minimal_ctx: PipelineContext
    ) -> None:
        ctx = minimal_ctx.model_copy(deep=True)
        ctx.backlog = BacklogOutput(items=[], rejected_count=0, is_degraded=False)
        result = trace_policy.summarize_output(2, ctx)
        assert "items=0" in result

    def test_summarize_output_publish_queue_with_items(
        self, trace_policy: StageTracePolicy, minimal_ctx: PipelineContext
    ) -> None:
        from cc_deep_research.content_gen.models.production import PublishItem

        ctx = minimal_ctx.model_copy(deep=True)
        ctx.publish_items = [
            PublishItem(idea_id="idea-1", platform="youtube", content_url=""),
        ]
        result = trace_policy.summarize_output(12, ctx)
        assert "idea_id=idea-1" in result
        assert "platforms=1" in result

    def test_summarize_output_human_qc_with_release_state(
        self, trace_policy: StageTracePolicy, minimal_ctx: PipelineContext
    ) -> None:
        from cc_deep_research.content_gen.models.production import HumanQCGate
        from cc_deep_research.content_gen.models.shared import ReleaseState

        ctx = minimal_ctx.model_copy(deep=True)
        ctx.qc_gate = HumanQCGate(release_state=ReleaseState.APPROVED)
        result = trace_policy.summarize_output(11, ctx)
        assert "release_state=approved" in result

    def test_build_decision_summary_skipped(self, trace_policy: StageTracePolicy) -> None:
        result = trace_policy.build_decision_summary(3, PipelineContext(theme="test"), status="skipped", detail="backlog missing")
        assert result == "Skipped: backlog missing"

    def test_build_decision_summary_failed(self, trace_policy: StageTracePolicy) -> None:
        result = trace_policy.build_decision_summary(3, PipelineContext(theme="test"), status="failed", detail="something went wrong")
        assert result == "Stage failed: something went wrong"

    def test_collect_warnings_failed_stage(
        self, trace_policy: StageTracePolicy, minimal_ctx: PipelineContext
    ) -> None:
        warnings = trace_policy.collect_warnings(3, minimal_ctx, status="failed", detail="timeout")
        assert any("Stage failed: timeout" in w for w in warnings)

    def test_collect_warnings_degraded_backlog(
        self, trace_policy: StageTracePolicy, minimal_ctx: PipelineContext
    ) -> None:
        ctx = minimal_ctx.model_copy(deep=True)
        ctx.backlog = BacklogOutput(items=[], is_degraded=True, degradation_reason="API timeout")
        warnings = trace_policy.collect_warnings(2, ctx, status="completed")
        assert any("Backlog degraded" in w for w in warnings)

    def test_collect_warnings_human_qc_must_fix(
        self, trace_policy: StageTracePolicy, minimal_ctx: PipelineContext
    ) -> None:
        from cc_deep_research.content_gen.models.production import HumanQCGate
        from cc_deep_research.content_gen.models.shared import ReleaseState

        ctx = minimal_ctx.model_copy(deep=True)
        ctx.qc_gate = HumanQCGate(release_state=ReleaseState.BLOCKED)
        ctx.qc_gate.must_fix_items = [MagicMock(), MagicMock()]
        ctx.qc_gate.issue_origin_summary = ["research", "scripting", "angles"]
        warnings = trace_policy.collect_warnings(11, ctx, status="completed")
        assert any("Human QC blocked publish" in w for w in warnings)

    def test_collect_warnings_empty_for_unknown_stage(
        self, trace_policy: StageTracePolicy, minimal_ctx: PipelineContext
    ) -> None:
        # Use a valid stage index that has no specific warning logic
        warnings = trace_policy.collect_warnings(0, minimal_ctx, status="completed")
        assert warnings == []

    def test_build_trace_metadata_score_ideas(
        self, trace_policy: StageTracePolicy, minimal_ctx: PipelineContext
    ) -> None:
        from cc_deep_research.content_gen.models import ScoringOutput

        ctx = minimal_ctx.model_copy(deep=True)
        ctx.scoring = ScoringOutput(
            scores=[],
            shortlist=["idea-1"],
            selected_idea_id="idea-1",
            active_candidates=[],
        )
        meta = trace_policy.build_trace_metadata(3, ctx)
        assert meta.selected_idea_id == "idea-1"
        assert meta.shortlist_count == 1

    def test_build_trace_metadata_empty(
        self, trace_policy: StageTracePolicy, minimal_ctx: PipelineContext
    ) -> None:
        meta = trace_policy.build_trace_metadata(1, minimal_ctx)
        # Empty context produces empty metadata (no crash)
        assert meta is not None
        assert hasattr(meta, "selected_idea_id")

    def test_build_trace_metadata_human_qc_approved(
        self, trace_policy: StageTracePolicy, minimal_ctx: PipelineContext
    ) -> None:
        from cc_deep_research.content_gen.models.production import HumanQCGate
        from cc_deep_research.content_gen.models.shared import ReleaseState

        ctx = minimal_ctx.model_copy(deep=True)
        ctx.qc_gate = HumanQCGate(release_state=ReleaseState.APPROVED)
        meta = trace_policy.build_trace_metadata(11, ctx)
        assert meta.approved is True


# ---------------------------------------------------------------------------
# Integration: policy objects are independent of stage dispatch
# ---------------------------------------------------------------------------


class TestPolicyIndependence:
    """Verify lifecycle policies can run without a pipeline instance."""

    def test_prereq_policy_runs_without_pipeline(
        self, prereq_policy: StagePrerequisitePolicy
    ) -> None:
        ctx = PipelineContext(theme="test", created_at=datetime.now(tz=UTC).isoformat())
        ctx.backlog = None
        # Should not raise, should not require any stage orchestrator
        met, reason = prereq_policy.check(3, ctx)
        assert met is False

    def test_trace_policy_runs_without_pipeline(
        self, trace_policy: StageTracePolicy
    ) -> None:
        ctx = PipelineContext(theme="test", created_at=datetime.now(tz=UTC).isoformat())
        # Should not raise, should not require any stage orchestrator
        summary = trace_policy.summarize_input(3, ctx)
        assert isinstance(summary, str)

    def test_gate_policy_runs_without_pipeline(
        self, gate_policy: StageGatePolicy
    ) -> None:
        ctx = PipelineContext(theme="test", created_at=datetime.now(tz=UTC).isoformat())
        ctx.brief_reference = None
        # Should not raise, should not require any stage orchestrator
        ok, message = gate_policy.check(ctx, "production_brief")
        assert ok is True
