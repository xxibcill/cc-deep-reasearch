"""Brief domain models: managed briefs, execution gates, and revisions."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from .shared import (
    BriefExecutionPolicyMode,
    BriefLifecycleState,
    BriefProvenance,
)
from .pipeline import (
    OperatingPhasePolicy,
)


class BriefRevision(BaseModel):
    """An immutable snapshot of an OpportunityBrief at a point in time."""

    revision_id: str = Field(default_factory=lambda: f"rev__placeholder__")
    brief_id: str = ""
    version: int = 0
    theme: str = ""
    goal: str = ""
    primary_audience_segment: str = ""
    secondary_audience_segments: list[str] = Field(default_factory=list)
    problem_statements: list[str] = Field(default_factory=list)
    content_objective: str = ""
    proof_requirements: list[str] = Field(default_factory=list)
    platform_constraints: list[str] = Field(default_factory=list)
    risk_constraints: list[str] = Field(default_factory=list)
    freshness_rationale: str = ""
    sub_angles: list[str] = Field(default_factory=list)
    research_hypotheses: list[str] = Field(default_factory=list)
    success_criteria: list[str] = Field(default_factory=list)
    expert_take: str = ""
    non_obvious_claims_to_test: list[str] = Field(default_factory=list)
    genericity_risks: list[str] = Field(default_factory=list)
    provenance: BriefProvenance = Field(default=BriefProvenance.GENERATED)
    is_generated: bool = True
    revision_notes: str = ""
    source_pipeline_id: str = ""
    created_at: str = ""


class ManagedOpportunityBrief(BaseModel):
    """A durable, version-aware opportunity brief resource."""

    brief_id: str = Field(default_factory=lambda: f"mbrief__placeholder__")
    title: str = ""
    lifecycle_state: BriefLifecycleState = Field(default=BriefLifecycleState.DRAFT)
    current_revision_id: str = ""
    latest_revision_id: str = ""
    revision_count: int = 0
    provenance: BriefProvenance = Field(default=BriefProvenance.GENERATED)
    created_at: str = ""
    updated_at: str = ""
    revision_history: list[str] = Field(default_factory=list)
    source_brief_id: str = ""
    branch_reason: str = ""
    operating_policies: list[OperatingPhasePolicy] = Field(default_factory=list)
    override_history: list[str] = Field(default_factory=list)

    def head_revision(self, revisions: list[BriefRevision]) -> BriefRevision | None:
        """Return the current head revision from a list of known revisions."""
        if not self.current_revision_id:
            return None
        return next((r for r in revisions if r.revision_id == self.current_revision_id), None)


class ManagedBriefOutput(BaseModel):
    """Container for listing and loading managed briefs."""

    briefs: list[ManagedOpportunityBrief] = Field(default_factory=list)


class PipelineBriefReference(BaseModel):
    """Reference to a managed opportunity brief used by a pipeline run."""

    brief_id: str = Field(default="", description="The managed brief resource ID")
    revision_id: str = Field(default="", description="The specific revision ID this run referenced")
    revision_version: int = Field(default=0, description="Human-readable version number for display")
    snapshot: "OpportunityBrief | None" = Field(default=None, description="Inline brief snapshot for observability")
    lifecycle_state: BriefLifecycleState = Field(default=BriefLifecycleState.DRAFT)
    reference_type: Literal["managed", "inline_fallback", "imported"] = Field(default="managed")
    seeded_from_revision_id: str = Field(default="", description="For seeded runs: revision ID explicitly chosen to seed this run")
    created_at: str = ""
    was_generated_in_run: bool = Field(default=False, description="True if brief was generated in the current pipeline run")

    def is_approved(self) -> bool:
        """Return True if this brief reference was approved at time of use."""
        return self.lifecycle_state == BriefLifecycleState.APPROVED

    def is_draft(self) -> bool:
        """Return True if this brief reference was in draft state at time of use."""
        return self.lifecycle_state == BriefLifecycleState.DRAFT


class BriefExecutionGate(BaseModel):
    """Approval-aware execution gate for brief-controlled pipelines."""

    policy_mode: BriefExecutionPolicyMode = Field(default=BriefExecutionPolicyMode.DEFAULT_APPROVED)
    brief_state_at_start: BriefLifecycleState = Field(default=BriefLifecycleState.DRAFT)
    is_satisfied: bool = Field(default=False)
    warnings: list[str] = Field(default_factory=list)
    error_message: str = ""
    checked_at_stage: int = Field(default=-1)
    was_blocked: bool = Field(default=False)

    def get_gate_status(self) -> str:
        """Return a human-readable gate status for display."""
        if self.was_blocked:
            return f"BLOCKED: {self.error_message}"
        if self.is_satisfied:
            return f"SATISFIED (brief is {self.brief_state_at_start.value})"
        if self.warnings:
            return f"WARNINGS ({len(self.warnings)}): running with {self.brief_state_at_start.value} brief"
        return f"UNKNOWN (brief is {self.brief_state_at_start.value})"

    def requires_approval_for_stage(self, stage_name: str) -> bool:
        """Return True if the given stage requires an approved brief."""
        approval_stages = {
            "build_backlog", "score_ideas", "generate_angles", "build_research_pack",
            "build_argument_map", "run_scripting", "visual_translation",
            "production_brief", "packaging", "human_qc", "publish_queue", "performance_analysis",
        }
        return stage_name in approval_stages

    def check_gate(self, brief_state: BriefLifecycleState, stage_name: str) -> tuple[bool, str]:
        """Check if execution can proceed given the brief state."""
        self.brief_state_at_start = brief_state

        if self.policy_mode == BriefExecutionPolicyMode.ALLOW_ANY:
            self.is_satisfied = True
            return True, "Gate is open (ALLOW_ANY mode)"

        if self.policy_mode == BriefExecutionPolicyMode.ALLOW_DRAFT:
            if brief_state == BriefLifecycleState.APPROVED:
                self.is_satisfied = True
                return True, "Approved brief accepted"
            self.warnings.append(f"Running with {brief_state.value} brief in ALLOW_DRAFT mode")
            self.is_satisfied = True
            return True, f"Gate waived for {brief_state.value} brief"

        # DEFAULT_APPROVED mode
        if brief_state == BriefLifecycleState.APPROVED:
            self.is_satisfied = True
            return True, "Approved brief confirmed"

        if not self.requires_approval_for_stage(stage_name):
            self.is_satisfied = True
            return True, f"Stage {stage_name} does not require approval"

        # Blocked
        self.is_satisfied = False
        self.was_blocked = True
        self.error_message = (
            f"Execution blocked: brief is in '{brief_state.value}' state. "
            f"Stage '{stage_name}' requires an approved brief. "
            f"Please approve the brief before proceeding, or use --brief-policy allow_draft "
            f"to run with draft briefs (not recommended for production)."
        )
        return False, self.error_message


# ---------------------------------------------------------------------------
# Brief models from original module
# ---------------------------------------------------------------------------


class OpportunityBrief(BaseModel):
    """Structured planning artifact (stage 1)."""

    brief_id: str = Field(default_factory=lambda: f"brief__placeholder__")
    theme: str = ""
    goal: str = ""
    primary_audience_segment: str = ""
    secondary_audience_segments: list[str] = Field(default_factory=list)
    problem_statements: list[str] = Field(default_factory=list)
    content_objective: str = ""
    proof_requirements: list[str] = Field(default_factory=list)
    platform_constraints: list[str] = Field(default_factory=list)
    risk_constraints: list[str] = Field(default_factory=list)
    freshness_rationale: str = ""
    sub_angles: list[str] = Field(default_factory=list)
    research_hypotheses: list[str] = Field(default_factory=list)
    success_criteria: list[str] = Field(default_factory=list)
    expert_take: str = ""
    non_obvious_claims_to_test: list[str] = Field(default_factory=list)
    genericity_risks: list[str] = Field(default_factory=list)
    version: int = 1
    is_generated: bool = True
    is_approved: bool = False
    revision_history: list[str] = Field(default_factory=list)


class StrategyReadinessIssue(BaseModel):
    """A single readiness issue found during validation."""

    code: str = ""
    label: str = ""
    severity: Literal["blocking", "warning"] = "warning"
    field_path: str = ""
    detail: str = ""
    suggestion: str = ""


class StrategyReadinessResult(BaseModel):
    """Result of strategy readiness validation."""

    readiness: "StrategyReadiness" = Field(default="incomplete")
    overall_score: float = 0.0
    issues: list[StrategyReadinessIssue] = Field(default_factory=list)
    summary: str = ""

    def blocking_issues(self) -> list[StrategyReadinessIssue]:
        """Return issues that must be resolved before pipeline can run."""
        return [i for i in self.issues if i.severity == "blocking"]

    def warning_issues(self) -> list[StrategyReadinessIssue]:
        """Return issues that are recommended but not blocking."""
        return [i for i in self.issues if i.severity == "warning"]

    def has_blockers(self) -> bool:
        """True if any blocking issues exist."""
        return len(self.blocking_issues()) > 0

    def is_healthy(self) -> bool:
        """True if strategy is in good shape (no blocking issues)."""
        return self.readiness == "healthy"
