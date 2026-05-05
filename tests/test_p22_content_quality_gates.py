"""Tests for content quality gates (P22-T5)."""

from __future__ import annotations

from cc_deep_research.content_gen.models import (
    HumanQCGate,
    IterationState,
    PackagingOutput,
    PublishItem,
    PublishReadinessState,
    ReleaseState,
    RewriteActionType,
    ScriptingContext,
    TargetedRevisionPlan,
    TargetedRewriteAction,
)
from cc_deep_research.content_gen.models.brief import ManagedOpportunityBrief


class TestQualityGateCheckContracts:
    """P22-T5: Automated checks for content-gen output contracts."""

    def test_scripting_context_required_fields(self) -> None:
        """Scripting context must have required fields for publish readiness."""
        from cc_deep_research.content_gen.quality_gates import check_scripting_context_complete

        # Valid context
        ctx = ScriptingContext(
            idea_id="idea-001",
            hook="Strong hook",
            thesis="Clear thesis",
            beats=[],
            word_count=300,
        )
        result = check_scripting_context_complete(ctx)
        assert result["passed"] is True
        assert result["missing_fields"] == []

        # Missing hook
        ctx_empty = ScriptingContext(idea_id="idea-001", hook="", thesis="Thesis")
        result = check_scripting_context_complete(ctx_empty)
        assert result["passed"] is False
        assert "hook" in result["missing_fields"]

        # Missing thesis
        ctx_no_thesis = ScriptingContext(idea_id="idea-001", hook="Hook", thesis="")
        result = check_scripting_context_complete(ctx_no_thesis)
        assert result["passed"] is False
        assert "thesis" in result["missing_fields"]

    def test_packaging_output_required_fields(self) -> None:
        """Packaging output must have platform packages with captions."""
        from cc_deep_research.content_gen.models import PlatformPackage
        from cc_deep_research.content_gen.quality_gates import check_packaging_output_complete

        valid = PackagingOutput(
            idea_id="idea-001",
            platform_packages=[
                PlatformPackage(platform="youtube", primary_hook="Hook", caption="Caption #test"),
                PlatformPackage(platform="tiktok", primary_hook="Hook", caption="Caption"),
            ],
        )
        result = check_packaging_output_complete(valid)
        assert result["passed"] is True

        # Missing caption
        empty = PackagingOutput(
            idea_id="idea-001",
            platform_packages=[PlatformPackage(platform="youtube", primary_hook="Hook", caption="")],
        )
        result = check_packaging_output_complete(empty)
        assert result["passed"] is False

    def test_human_qc_gate_blocking_check(self) -> None:
        """Human QC gate blocks publish when release_state is BLOCKED."""
        from cc_deep_research.content_gen.quality_gates import check_human_qc_approved

        gate = HumanQCGate(
            review_round=1,
            release_state=ReleaseState.BLOCKED,
            must_fix_items=["Verify claim sourcing", "Fix hook clarity"],
        )
        result = check_human_qc_approved(gate)
        assert result["passed"] is False
        assert result["reason"] == "blocked"
        assert len(result["must_fix_items"]) == 2

        gate_approved = HumanQCGate(
            review_round=1,
            release_state=ReleaseState.APPROVED,
            approved_for_publish=True,
        )
        result = check_human_qc_approved(gate_approved)
        assert result["passed"] is True

        gate_risks = HumanQCGate(
            review_round=1,
            release_state=ReleaseState.APPROVED_WITH_KNOWN_RISKS,
            approved_for_publish=True,
        )
        result = check_human_qc_approved(gate_risks)
        assert result["passed"] is True  # Approved with risks is still approved

    def test_publish_item_readiness_gate(self) -> None:
        """Publish item must be in READY or SCHEDULED state to proceed."""
        from cc_deep_research.content_gen.quality_gates import check_publish_ready

        item_draft = PublishItem(
            idea_id="idea-001",
            platform="youtube",
            readiness=PublishReadinessState.DRAFT,
        )
        result = check_publish_ready(item_draft)
        assert result["passed"] is False
        assert result["reason"] == "draft"

        item_blocked = PublishItem(
            idea_id="idea-001",
            platform="youtube",
            readiness=PublishReadinessState.BLOCKED,
        )
        result = check_publish_ready(item_blocked)
        assert result["passed"] is False

        item_ready = PublishItem(
            idea_id="idea-001",
            platform="youtube",
            readiness=PublishReadinessState.READY,
        )
        result = check_publish_ready(item_ready)
        assert result["passed"] is True

        item_scheduled = PublishItem(
            idea_id="idea-001",
            platform="youtube",
            readiness=PublishReadinessState.SCHEDULED,
        )
        result = check_publish_ready(item_scheduled)
        assert result["passed"] is True

    def test_brief_approval_gate(self) -> None:
        """Brief must be in APPROVED lifecycle state for production."""
        from cc_deep_research.content_gen.models.shared import BriefLifecycleState
        from cc_deep_research.content_gen.quality_gates import check_brief_approved_for_production

        # Approved brief passes
        brief_approved = ManagedOpportunityBrief(
            brief_id="brief-001",
            lifecycle_state=BriefLifecycleState.APPROVED,
            current_revision_id="rev-001",
            latest_revision_id="rev-001",
            revision_count=1,
        )
        result = check_brief_approved_for_production(brief_approved)
        assert result["passed"] is True

        # Draft brief fails by default (no policy override available on brief itself)
        brief_draft = ManagedOpportunityBrief(
            brief_id="brief-002",
            lifecycle_state=BriefLifecycleState.DRAFT,
            current_revision_id="rev-002",
            latest_revision_id="rev-002",
            revision_count=1,
            operating_policies=[],
        )
        result = check_brief_approved_for_production(brief_draft)
        assert result["passed"] is False

        # Archived brief fails
        brief_archived = ManagedOpportunityBrief(
            brief_id="brief-003",
            lifecycle_state=BriefLifecycleState.ARCHIVED,
            current_revision_id="rev-003",
            latest_revision_id="rev-003",
            revision_count=1,
        )
        result = check_brief_approved_for_production(brief_archived)
        assert result["passed"] is False

    def test_iteration_not_stuck_in_loop(self) -> None:
        """Quality gate detects if iterative loop is stuck."""
        from cc_deep_research.content_gen.quality_gates import check_iteration_not_stuck

        # Normal iteration
        iteration = IterationState(
            current_iteration=1,
            max_iterations=3,
            is_converged=False,
        )
        result = check_iteration_not_stuck(iteration)
        assert result["passed"] is True

        # Converged passes
        iteration_converged = IterationState(
            current_iteration=2,
            max_iterations=3,
            is_converged=True,
            convergence_reason="Quality threshold met",
        )
        result = check_iteration_not_stuck(iteration_converged)
        assert result["passed"] is True

        # Max iterations without convergence fails
        iteration_stuck = IterationState(
            current_iteration=3,
            max_iterations=3,
            is_converged=False,
            targeted_revision_plan=TargetedRevisionPlan(
                actions=[
                    TargetedRewriteAction(
                        action_type=RewriteActionType.REWRITE_BEAT,
                        beat_id="beat-001",
                        instruction="Rewrite this beat",
                    ),
                ],
            ),
        )
        result = check_iteration_not_stuck(iteration_stuck)
        assert result["passed"] is False
        assert result["reason"] == "max_iterations_reached"


class TestQualityGateActionableMessages:
    """P22-T5: Quality gate failures provide actionable messages."""

    def test_actionable_message_format(self) -> None:
        """Gate failures identify the broken stage and field."""
        from cc_deep_research.content_gen.quality_gates import check_scripting_context_complete

        ctx = ScriptingContext(idea_id="idea-001", hook="", thesis="")
        result = check_scripting_context_complete(ctx)
        assert result["gate"] == "scripting_context_complete"
        # Missing fields are listed
        missing = result["missing_fields"]
        assert "hook" in missing or "thesis" in missing

    def test_gate_failure_identifies_stage(self) -> None:
        """Each gate failure clearly identifies which stage failed."""
        from cc_deep_research.content_gen.quality_gates import check_human_qc_approved

        gate = HumanQCGate(
            review_round=1,
            release_state=ReleaseState.BLOCKED,
            must_fix_items=["Fix this"],
        )
        result = check_human_qc_approved(gate)
        assert "stage" in result
        assert result["stage"] == "human_qc"


class TestHumanReviewGatesSeparateFromAutomated:
    """P22-T5: Human review gates are not bypassed by automated checks."""

    def test_human_qc_gate_not_automatically_approved(self) -> None:
        """Automated gates never auto-approve human QC decisions."""
        from cc_deep_research.content_gen.quality_gates import check_human_qc_approved

        gate = HumanQCGate(
            review_round=1,
            release_state=ReleaseState.BLOCKED,
            approved_for_publish=False,
        )
        result = check_human_qc_approved(gate)
        # Even with all automated checks passing, BLOCKED state remains
        assert result["passed"] is False

    def test_automated_gates_supplement_not_replace_human_review(self) -> None:
        """Automated checks provide context; human review remains the gate."""
        from cc_deep_research.content_gen.quality_gates import check_scripting_context_complete

        # Script could be structurally complete but still need human QC
        ctx = ScriptingContext(
            idea_id="idea-001",
            hook="Valid hook",
            thesis="Clear thesis",
            beats=[],
            word_count=300,
        )
        result = check_scripting_context_complete(ctx)
        assert result["passed"] is True
        # But this doesn't mean it's approved for publish — human QC still required
