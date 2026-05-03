"""Targeted revision helpers extracted from legacy_orchestrator.

These helpers decide whether to use targeted vs. full revision mode and
build the feedback strings for the next iteration. They are callable without
importing ContentGenOrchestrator.

Behavior is byte-for-byte equivalent to the original staticmethods.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from cc_deep_research.content_gen.models import RevisionMode

if TYPE_CHECKING:
    from cc_deep_research.content_gen.models import (
        PipelineContext,
        QualityEvaluation,
        TargetedRevisionPlan,
    )


def extract_retrieval_gaps(plan: TargetedRevisionPlan | None) -> list[str]:
    """Extract evidence gaps from a targeted revision plan."""
    if plan is None:
        return []
    gaps = list(plan.retrieval_gaps)
    for action in plan.actions:
        gaps.extend(action.evidence_gaps)
    return gaps


def build_targeted_feedback(quality_eval: QualityEvaluation) -> str:
    """Build feedback string from a targeted revision plan for the next iteration."""
    if quality_eval.targeted_revision_plan is None:
        return ""
    plan = quality_eval.targeted_revision_plan
    parts: list[str] = []

    if plan.revision_summary:
        parts.append(f"Revision: {plan.revision_summary}")

    for action in plan.actions:
        if action.instruction:
            parts.append(f"[{action.beat_name or action.beat_id}] {action.instruction}")
        elif action.weak_claim_ids:
            parts.append(
                f"[{action.beat_name or action.beat_id}] Rewrite needed for claims: {', '.join(action.weak_claim_ids)}"
            )

    if plan.full_restart_recommended:
        parts.append("WARNING: Full restart recommended — targeted revision insufficient.")

    return "\n".join(parts)


def should_use_targeted_mode(quality_eval: QualityEvaluation) -> bool:
    """Decide whether to use targeted or full revision mode."""
    if quality_eval.revision_mode == RevisionMode.FULL:
        return False
    if quality_eval.targeted_revision_plan is None:
        return False
    if quality_eval.targeted_revision_plan.full_restart_recommended:
        return False
    return quality_eval.targeted_revision_plan.has_targeted_actions


def apply_targeted_feedback(ctx: PipelineContext, quality_eval: QualityEvaluation) -> None:
    """Inject targeted revision feedback into scripting context."""
    if not ctx.scripting or not quality_eval.targeted_revision_plan:
        return

    plan = quality_eval.targeted_revision_plan

    targeted_feedback = build_targeted_feedback(quality_eval)
    if not targeted_feedback:
        return

    stable_ids = plan.stable_beat_ids()

    existing = ctx.scripting.research_context or ""
    ctx.scripting.research_context = (
        f"TARGETED REVISION:\n{targeted_feedback}\n\n"
        f"Stable beats (preserve unchanged): {', '.join(stable_ids) if stable_ids else 'none'}\n\n"
        f"{existing}"
    )

    ctx.iteration_state.targeted_revision_plan = plan
    ctx.iteration_state.revision_mode = RevisionMode.TARGETED
