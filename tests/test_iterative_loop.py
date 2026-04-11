"""Tests for targeted revision loop (Task 18)."""

from __future__ import annotations

import pytest

from cc_deep_research.content_gen.iterative_loop import (
    LoopConfig,
    run_evaluation_loop,
)
from cc_deep_research.content_gen.models import (
    BeatRevisionScope,
    IterationState,
    QualityEvaluation,
    RevisionMode,
    RewriteActionType,
    TargetedRevisionPlan,
    TargetedRewriteAction,
)


def _make_plan(
    stable_beats: list[str] | None = None,
    weak_beat_ids: list[str] | None = None,
    full_restart: bool = False,
    actions: list[TargetedRewriteAction] | None = None,
    retrieval_gaps: list[str] | None = None,
    revision_summary: str = "",
) -> TargetedRevisionPlan:
    """Build a TargetedRevisionPlan for testing."""
    stable = [
        BeatRevisionScope(beat_id=b, beat_name=b, is_stable=True)
        for b in (stable_beats or [])
    ]
    weak = [
        BeatRevisionScope(beat_id=b, beat_name=b, is_stable=False, weakness_reason="weak")
        for b in (weak_beat_ids or [])
    ]
    return TargetedRevisionPlan(
        stable_beats=stable,
        weak_beats=weak,
        actions=actions or [],
        full_restart_recommended=full_restart,
        retrieval_gaps=retrieval_gaps or [],
        revision_summary=revision_summary,
    )


def _make_eval(
    *,
    score: float = 0.5,
    passes: bool = False,
    unsupported_claims: list[str] | None = None,
    research_gaps: list[str] | None = None,
    rationale: str = "",
    iteration: int = 1,
    revision_mode: RevisionMode = RevisionMode.NONE,
    targeted_plan: TargetedRevisionPlan | None = None,
) -> QualityEvaluation:
    return QualityEvaluation(
        overall_quality_score=score,
        passes_threshold=passes,
        unsupported_claims=unsupported_claims or [],
        research_gaps_identified=research_gaps or [],
        rationale=rationale,
        iteration_number=iteration,
        revision_mode=revision_mode,
        targeted_revision_plan=targeted_plan,
    )


# ---------------------------------------------------------------------------
# TargetedRevisionPlan helpers
# ---------------------------------------------------------------------------


def test_targeted_revision_plan_stable_beat_ids():
    plan = _make_plan(stable_beats=["beat-A", "beat-B"])
    assert plan.stable_beat_ids() == ["beat-A", "beat-B"]


def test_targeted_revision_plan_weak_beat_ids():
    plan = _make_plan(weak_beat_ids=["beat-C", "beat-D"])
    assert plan.weak_beat_ids() == ["beat-C", "beat-D"]


def test_targeted_revision_plan_has_targeted_actions():
    plan_empty = _make_plan()
    assert plan_empty.has_targeted_actions is False

    plan_with_actions = _make_plan(
        weak_beat_ids=["beat-X"],
        actions=[
            TargetedRewriteAction(
                action_type=RewriteActionType.REWRITE_BEAT,
                beat_id="beat-X",
                beat_name="Beat X",
            )
        ],
    )
    assert plan_with_actions.has_targeted_actions is True


def test_targeted_revision_plan_needs_retrieval():
    plan_no_gaps = _make_plan()
    assert plan_no_gaps.needs_retrieval is False

    plan_with_gaps = _make_plan(retrieval_gaps=["evidence for claim X"])
    assert plan_with_gaps.needs_retrieval is True


# ---------------------------------------------------------------------------
# IterationState.weak_beat_ids property
# ---------------------------------------------------------------------------


def test_iteration_state_weak_beat_ids():
    plan = _make_plan(
        actions=[
            TargetedRewriteAction(
                action_type=RewriteActionType.REWRITE_BEAT,
                beat_id="beat-1",
                beat_name="Beat One",
            ),
            TargetedRewriteAction(
                action_type=RewriteActionType.REFRESH_EVIDENCE,
                beat_id="beat-2",
                beat_name="Beat Two",
            ),
            TargetedRewriteAction(
                action_type=RewriteActionType.QUALIFY_CLAIM,
                beat_id="",  # No beat for qualify
                beat_name="",
            ),
        ]
    )
    state = IterationState(targeted_revision_plan=plan)
    assert state.weak_beat_ids == ["beat-1", "beat-2"]


def test_iteration_state_requires_full_restart():
    plan_no_restart = _make_plan(weak_beat_ids=["beat-A"])
    assert plan_no_restart.full_restart_recommended is False

    plan_restart = _make_plan(full_restart=True)
    assert plan_restart.full_restart_recommended is True

    state_restart = IterationState(targeted_revision_plan=plan_restart)
    assert state_restart.requires_full_restart is True


# ---------------------------------------------------------------------------
# RevisionMode enum
# ---------------------------------------------------------------------------


def test_revision_mode_values():
    assert RevisionMode.FULL == "full"
    assert RevisionMode.TARGETED == "targeted"
    assert RevisionMode.NONE == "none"


# ---------------------------------------------------------------------------
# QualityEvaluation with targeted revision plan
# ---------------------------------------------------------------------------


def test_quality_evaluation_with_targeted_plan():
    plan = _make_plan(
        stable_beats=["beat-A"],
        weak_beat_ids=["beat-B"],
    )
    eval = _make_eval(
        score=0.6,
        revision_mode=RevisionMode.TARGETED,
        targeted_plan=plan,
    )
    assert eval.revision_mode == RevisionMode.TARGETED
    assert eval.targeted_revision_plan is not None
    assert eval.targeted_revision_plan.stable_beat_ids() == ["beat-A"]
    assert eval.targeted_revision_plan.weak_beat_ids() == ["beat-B"]


# ---------------------------------------------------------------------------
# Orchestrator helper methods
# ---------------------------------------------------------------------------

from cc_deep_research.content_gen.orchestrator import ContentGenOrchestrator


def test_extract_retrieval_gaps_empty():
    gaps = ContentGenOrchestrator._extract_retrieval_gaps(None)
    assert gaps == []


def test_extract_retrieval_gaps_from_plan():
    plan = _make_plan(
        retrieval_gaps=["gap-A", "gap-B"],
        actions=[
            TargetedRewriteAction(
                action_type=RewriteActionType.REFRESH_EVIDENCE,
                beat_id="beat-X",
                evidence_gaps=["gap-C"],
            )
        ],
    )
    gaps = ContentGenOrchestrator._extract_retrieval_gaps(plan)
    assert "gap-A" in gaps
    assert "gap-B" in gaps
    assert "gap-C" in gaps


def test_build_targeted_feedback_with_actions():
    plan = _make_plan(
        revision_summary="Fix the second beat",
        weak_beat_ids=["beat-2"],
        actions=[
            TargetedRewriteAction(
                action_type=RewriteActionType.REWRITE_BEAT,
                beat_id="beat-2",
                beat_name="Second Beat",
                instruction="Rewrite this beat with better proof",
            )
        ],
    )
    eval = _make_eval(targeted_plan=plan)
    feedback = ContentGenOrchestrator._build_targeted_feedback(eval)
    assert "Second Beat" in feedback
    assert "Rewrite this beat with better proof" in feedback


def test_build_targeted_feedback_with_weak_claims():
    plan = _make_plan(
        actions=[
            TargetedRewriteAction(
                action_type=RewriteActionType.REWRITE_BEAT,
                beat_id="beat-2",
                beat_name="Second Beat",
                weak_claim_ids=["claim-A", "claim-B"],
                instruction="",  # no explicit instruction
            )
        ],
    )
    eval = _make_eval(targeted_plan=plan)
    feedback = ContentGenOrchestrator._build_targeted_feedback(eval)
    assert "Second Beat" in feedback
    assert "Rewrite needed" in feedback


def test_build_targeted_feedback_full_restart_warning():
    plan = _make_plan(
        revision_summary="Script is fundamentally broken",
        full_restart=True,
    )
    eval = _make_eval(targeted_plan=plan)
    feedback = ContentGenOrchestrator._build_targeted_feedback(eval)
    assert "Full restart recommended" in feedback


def test_should_use_targeted_mode_true():
    plan = _make_plan(
        actions=[
            TargetedRewriteAction(
                action_type=RewriteActionType.REWRITE_BEAT,
                beat_id="beat-1",
            )
        ],
    )
    eval = _make_eval(revision_mode=RevisionMode.TARGETED, targeted_plan=plan)
    assert ContentGenOrchestrator._should_use_targeted_mode(eval) is True


def test_should_use_targeted_mode_false_when_full_mode():
    plan = _make_plan(actions=[TargetedRewriteAction(action_type=RewriteActionType.REWRITE_BEAT, beat_id="beat-1")])
    eval = _make_eval(revision_mode=RevisionMode.FULL, targeted_plan=plan)
    assert ContentGenOrchestrator._should_use_targeted_mode(eval) is False


def test_should_use_targeted_mode_false_when_no_plan():
    eval = _make_eval(revision_mode=RevisionMode.TARGETED, targeted_plan=None)
    assert ContentGenOrchestrator._should_use_targeted_mode(eval) is False


def test_should_use_targeted_mode_false_when_full_restart_recommended():
    plan = _make_plan(full_restart=True, actions=[TargetedRewriteAction(action_type=RewriteActionType.REWRITE_BEAT, beat_id="beat-1")])
    eval = _make_eval(revision_mode=RevisionMode.TARGETED, targeted_plan=plan)
    assert ContentGenOrchestrator._should_use_targeted_mode(eval) is False


# ---------------------------------------------------------------------------
# Loop behavior tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_loop_with_targeted_revision_plan():
    """Loop passes targeted revision plan through iterations correctly."""
    iterations_received: list[IterationState] = []

    async def producer(feedback: str) -> str:
        return "artifact"

    async def evaluator(artifact: str, iteration: int, prev: str) -> QualityEvaluation:
        if iteration == 1:
            plan = _make_plan(
                weak_beat_ids=["beat-2"],
                actions=[
                    TargetedRewriteAction(
                        action_type=RewriteActionType.REWRITE_BEAT,
                        beat_id="beat-2",
                        beat_name="Second Beat",
                        instruction="Rewrite beat 2",
                    )
                ],
            )
            return _make_eval(
                score=0.65,
                revision_mode=RevisionMode.TARGETED,
                targeted_plan=plan,
                iteration=iteration,
            )
        return _make_eval(
            score=0.85,
            passes=True,
            revision_mode=RevisionMode.NONE,
            iteration=iteration,
        )

    result = await run_evaluation_loop(
        producer=producer,
        evaluator=evaluator,
        config=LoopConfig(max_iterations=3),
    )

    # Two iterations: first had targeted plan, second passed threshold
    assert len(result.iteration_state.quality_history) == 2
    assert result.iteration_state.quality_history[0].revision_mode == RevisionMode.TARGETED
    assert result.iteration_state.quality_history[0].targeted_revision_plan is not None
    assert result.iteration_state.quality_history[1].passes_threshold is True


@pytest.mark.asyncio
async def test_targeted_revision_preserves_stable_beats():
    """Verifies that targeted revision plan correctly identifies stable beats."""
    plan = _make_plan(
        stable_beats=["beat-A", "beat-B"],
        weak_beat_ids=["beat-C"],
        actions=[
            TargetedRewriteAction(
                action_type=RewriteActionType.REFRESH_EVIDENCE,
                beat_id="beat-C",
                beat_name="Third Beat",
                instruction="Refresh evidence for third beat",
            )
        ],
    )

    state = IterationState(
        targeted_revision_plan=plan,
        revision_mode=RevisionMode.TARGETED,
    )

    # Stable beats should be marked and preserved
    assert plan.stable_beat_ids() == ["beat-A", "beat-B"]
    assert plan.weak_beat_ids() == ["beat-C"]
    assert state.weak_beat_ids == ["beat-C"]
    assert state.requires_full_restart is False


@pytest.mark.asyncio
async def test_loop_converges_on_targeted_pass():
    """Targeted mode still triggers convergence when score passes threshold."""
    call_count = 0

    async def producer(feedback: str) -> str:
        nonlocal call_count
        call_count += 1
        return f"artifact-{call_count}"

    async def evaluator(artifact: str, iteration: int, prev: str) -> QualityEvaluation:
        if iteration == 1:
            plan = _make_plan(
                weak_beat_ids=["beat-X"],
                actions=[TargetedRewriteAction(action_type=RewriteActionType.REWRITE_BEAT, beat_id="beat-X", instruction="Fix")],
            )
            return _make_eval(score=0.7, revision_mode=RevisionMode.TARGETED, targeted_plan=plan, iteration=iteration)
        return _make_eval(score=0.82, passes=True, revision_mode=RevisionMode.NONE, iteration=iteration)

    result = await run_evaluation_loop(
        producer=producer,
        evaluator=evaluator,
        config=LoopConfig(max_iterations=5),
    )

    # Should converge after 2 iterations
    assert len(result.iteration_state.quality_history) == 2
    assert result.iteration_state.is_converged


# ---------------------------------------------------------------------------
# Regression: localized revisions preserve unrelated high-quality beats
# ---------------------------------------------------------------------------


def test_beat_revision_scope_stable_flag():
    stable = BeatRevisionScope(beat_id="beat-1", beat_name="First Beat", is_stable=True, weakness_reason="")
    weak = BeatRevisionScope(beat_id="beat-2", beat_name="Second Beat", is_stable=False, weakness_reason="No proof")

    assert stable.is_stable is True
    assert stable.weakness_reason == ""
    assert weak.is_stable is False
    assert weak.weakness_reason == "No proof"


def test_beat_revision_scope_claim_tracking():
    scope = BeatRevisionScope(
        beat_id="beat-3",
        beat_name="Third Beat",
        weak_claim_ids=["claim-A", "claim-B"],
        missing_proof_ids=["proof-1"],
        is_stable=False,
    )
    assert scope.weak_claim_ids == ["claim-A", "claim-B"]
    assert scope.missing_proof_ids == ["proof-1"]
