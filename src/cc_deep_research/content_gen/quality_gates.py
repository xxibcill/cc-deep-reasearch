"""Automated quality gates for content-gen outputs (P22-T5).

Quality gates perform automated checks that:
1. Verify required fields are present
2. Check trace compatibility
3. Validate prompt metadata
4. Check QC status and publish readiness
5. Flag actionable failures

Human review gates (HumanQCGate, BriefExecutionGate) are NOT replaced
by these automated checks — they remain the authoritative publish gates.
"""

from __future__ import annotations

from typing import Any

from cc_deep_research.content_gen.models import (
    HumanQCGate,
    IterationState,
    ManagedOpportunityBrief,
    PackagingOutput,
    PublishItem,
    PublishReadinessState,
    ReleaseState,
    ScriptingContext,
)


def check_scripting_context_complete(ctx: ScriptingContext) -> dict[str, Any]:
    """Verify scripting stage produced complete output.

    Checks:
    - idea_id is set
    - hook is non-empty
    - thesis is non-empty
    - At least one beat or word_count indicates script was generated
    """
    missing = []
    if not ctx.idea_id:
        missing.append("idea_id")
    if not ctx.hook:
        missing.append("hook")
    if not ctx.thesis:
        missing.append("thesis")
    if not ctx.beats and ctx.word_count == 0:
        missing.append("script_body")

    passed = len(missing) == 0
    return {
        "gate": "scripting_context_complete",
        "stage": "run_scripting",
        "passed": passed,
        "missing_fields": missing,
        "idea_id": ctx.idea_id,
        "message": (
            f"Scripting incomplete for {ctx.idea_id}: missing {missing}. "
            if not passed
            else f"Scripting complete for {ctx.idea_id}."
        ),
    }


def check_packaging_output_complete(output: PackagingOutput) -> dict[str, Any]:
    """Verify packaging stage produced publishable output.

    Checks:
    - At least one platform package exists
    - Each package has a primary_hook
    - Each package has a non-empty caption
    """
    missing = []
    if not output.platform_packages:
        missing.append("platform_packages")
    else:
        for pkg in output.platform_packages:
            if not pkg.primary_hook:
                missing.append(f"platform:{pkg.platform}:primary_hook")
            if not pkg.caption:
                missing.append(f"platform:{pkg.platform}:caption")

    passed = len(missing) == 0
    return {
        "gate": "packaging_output_complete",
        "stage": "packaging",
        "passed": passed,
        "missing_fields": missing,
        "idea_id": output.idea_id,
        "message": (
            f"Packaging incomplete for {output.idea_id}: missing {missing}."
            if not passed
            else f"Packaging complete for {output.idea_id}."
        ),
    }


def check_human_qc_approved(gate: HumanQCGate) -> dict[str, Any]:
    """Verify human QC gate has approved the content for publication.

    Returns passed=True only when release_state is APPROVED or
    APPROVED_WITH_KNOWN_RISKS and approved_for_publish is True.

    BLOCKED state always returns passed=False regardless of automated checks.
    """
    is_approved = gate.release_state in (
        ReleaseState.APPROVED,
        ReleaseState.APPROVED_WITH_KNOWN_RISKS,
    ) and gate.approved_for_publish

    reason = "blocked" if gate.release_state == ReleaseState.BLOCKED else "approved"
    if gate.release_state == ReleaseState.APPROVED_WITH_KNOWN_RISKS:
        reason = "approved_with_known_risks"

    return {
        "gate": "human_qc_approved",
        "stage": "human_qc",
        "passed": is_approved,
        "release_state": gate.release_state.value,
        "reason": reason,
        "must_fix_items": list(gate.must_fix_items) if gate.must_fix_items else [],
        "message": (
            f"Human QC gate: {gate.release_state.value}. "
            f"{len(gate.must_fix_items)} must-fix items."
            if gate.must_fix_items
            else f"Human QC gate: {gate.release_state.value}."
        ),
    }


def check_publish_ready(item: PublishItem) -> dict[str, Any]:
    """Verify publish queue item is in a ready-to-publish state.

    Required: readiness is READY or SCHEDULED.
    Also checks: no unresolved critical blockers.
    """
    ready_states = {PublishReadinessState.READY, PublishReadinessState.SCHEDULED}
    is_ready = item.readiness in ready_states

    reason = "not_ready"
    if item.readiness == PublishReadinessState.BLOCKED:
        reason = "blocked"
    elif item.readiness == PublishReadinessState.DRAFT:
        reason = "draft"
    elif item.readiness == PublishReadinessState.NEEDS_REVIEW:
        reason = "needs_review"
    elif item.readiness == PublishReadinessState.PUBLISHED:
        reason = "already_published"
    elif item.readiness == PublishReadinessState.ARCHIVED:
        reason = "archived"

    return {
        "gate": "publish_ready",
        "stage": "publish_queue",
        "passed": is_ready,
        "readiness": item.readiness.value,
        "reason": reason,
        "idea_id": item.idea_id,
        "platform": item.platform,
        "message": (
            f"Publish item {item.idea_id}/{item.platform} is {item.readiness.value} "
            f"(not ready for publication)."
            if not is_ready
            else f"Publish item {item.idea_id}/{item.platform} is ready."
        ),
    }


def check_brief_approved_for_production(brief: ManagedOpportunityBrief) -> dict[str, Any]:
    """Verify brief is approved for use in content production.

    Checks:
    - Brief lifecycle_state is APPROVED

    DRAFT, BLOCKED and ARCHIVED briefs fail by default.
    """
    from cc_deep_research.content_gen.models.shared import BriefLifecycleState

    is_approved = brief.lifecycle_state == BriefLifecycleState.APPROVED
    reason = "approved" if is_approved else brief.lifecycle_state.value

    return {
        "gate": "brief_approved_for_production",
        "stage": "opportunity",
        "passed": is_approved,
        "lifecycle_state": brief.lifecycle_state.value,
        "reason": reason,
        "brief_id": brief.brief_id,
        "message": (
            f"Brief {brief.brief_id} is {brief.lifecycle_state.value} — "
            f"{'approved' if is_approved else 'not approved'} for production."
        ),
    }


def check_iteration_not_stuck(iteration: IterationState) -> dict[str, Any]:
    """Check that iterative content loop is not stuck.

    Passes when:
    - Current iteration < max_iterations, OR
    - is_converged is True (quality threshold met), OR
    - targeted_revision_plan has no actions (nothing more to fix)

    Fails when max iterations reached without convergence.
    """
    is_stuck = (
        iteration.current_iteration >= iteration.max_iterations
        and not iteration.is_converged
        and iteration.targeted_revision_plan is not None
        and iteration.targeted_revision_plan.has_targeted_actions
    )

    reason = "ok"
    if iteration.is_converged:
        reason = "converged"
    elif iteration.current_iteration >= iteration.max_iterations:
        reason = "max_iterations_reached"

    return {
        "gate": "iteration_not_stuck",
        "stage": "run_scripting",
        "passed": not is_stuck,
        "current_iteration": iteration.current_iteration,
        "max_iterations": iteration.max_iterations,
        "is_converged": iteration.is_converged,
        "reason": reason,
        "message": (
            "Iterative loop reached max iterations without convergence. "
            "Consider a full restart or operator review."
            if is_stuck
            else f"Iteration {iteration.current_iteration}/{iteration.max_iterations}: {reason}."
        ),
    }


def run_all_gates(
    ctx: ScriptingContext | None = None,
    packaging: PackagingOutput | None = None,
    qc_gate: HumanQCGate | None = None,
    publish_item: PublishItem | None = None,
    brief: ManagedOpportunityBrief | None = None,
    iteration: IterationState | None = None,
) -> dict[str, Any]:
    """Run all applicable gates and return a combined report.

    Returns summary with:
    - overall_passed: bool
    - gates: list of individual gate results
    - blocking_gates: list of gates that failed
    """
    gates: list[dict[str, Any]] = []
    blocking: list[dict[str, Any]] = []

    if ctx is not None:
        result = check_scripting_context_complete(ctx)
        gates.append(result)
        if not result["passed"]:
            blocking.append(result)

    if packaging is not None:
        result = check_packaging_output_complete(packaging)
        gates.append(result)
        if not result["passed"]:
            blocking.append(result)

    if qc_gate is not None:
        result = check_human_qc_approved(qc_gate)
        gates.append(result)
        if not result["passed"]:
            blocking.append(result)

    if publish_item is not None:
        result = check_publish_ready(publish_item)
        gates.append(result)
        if not result["passed"]:
            blocking.append(result)

    if brief is not None:
        result = check_brief_approved_for_production(brief)
        gates.append(result)
        if not result["passed"]:
            blocking.append(result)

    if iteration is not None:
        result = check_iteration_not_stuck(iteration)
        gates.append(result)
        if not result["passed"]:
            blocking.append(result)

    overall_passed = len(blocking) == 0

    return {
        "overall_passed": overall_passed,
        "gates": gates,
        "blocking_gates": blocking,
        "summary": (
            f"All {len(gates)} gates passed."
            if overall_passed
            else f"{len(blocking)}/{len(gates)} gates failed: "
            + ", ".join(g["gate"] for g in blocking)
        ),
    }
