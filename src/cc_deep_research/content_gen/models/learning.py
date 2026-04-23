"""Performance learning and metrics models."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field, computed_field

from .shared import (
    LearningCategory,
    LearningDurability,
    PlanningLearningCategory,
    RuleChangeOperation,
    RuleLifecycleStatus,
    RuleVersionKind,
)


class PerformanceLearning(BaseModel):
    """A single structured learning extracted from performance analysis."""

    learning_id: str = Field(default_factory=lambda: "learn__placeholder__")
    category: LearningCategory = LearningCategory.HOOK_EFFECTIVENESS
    durability: LearningDurability = LearningDurability.TRANSIENT
    observation: str = ""
    implication: str = ""
    guidance: str = ""
    exact_pattern: str = ""
    source_video_ids: list[str] = Field(default_factory=list)
    source_metrics: dict[str, Any] = Field(default_factory=dict)
    evidence_count: int = 0
    baseline_comparison: str = ""
    confidence: float = 0.0
    review_after: str = ""
    operator_reviewed: bool = False
    is_active: bool = True
    superseded_by: str = ""
    created_at: str = ""
    updated_at: str = ""
    platform: str = ""
    content_type: str = ""
    audience_context: str = ""


class PerformanceLearningSet(BaseModel):
    """A set of performance learnings from a single analysis run."""

    video_id: str = ""
    learnings: list[PerformanceLearning] = Field(default_factory=list)
    source_analysis: PerformanceAnalysis | None = None


class PerformanceAnalysis(BaseModel):
    """Post-publish analysis."""

    video_id: str = ""
    metrics: dict[str, Any] = Field(default_factory=dict)
    what_worked: list[str] = Field(default_factory=list)
    what_failed: list[str] = Field(default_factory=list)
    audience_signals: list[str] = Field(default_factory=list)
    dropoff_hypotheses: list[str] = Field(default_factory=list)
    hook_diagnosis: str = ""
    lesson: str = ""
    next_test: str = ""
    follow_up_ideas: list[str] = Field(default_factory=list)
    backlog_updates: list[str] = Field(default_factory=list)
    is_degraded: bool = False
    degradation_reason: str = ""
    opportunity_brief_comparison: str = Field(default="", description="How actual outcomes compared against the original opportunity brief intent")
    brief_success_criteria_results: list[str] = Field(default_factory=list, description="Per-criterion results from opportunity brief")
    brief_hypothesis_results: list[str] = Field(default_factory=list, description="Per-hypothesis results from research hypotheses")


class StrategyPerformanceGuidance(BaseModel):
    """Performance-derived guidance stored in strategy memory."""

    winning_hooks: list[str] = Field(default_factory=list)
    failed_hooks: list[str] = Field(default_factory=list)
    winning_framings: list[str] = Field(default_factory=list)
    failed_framings: list[str] = Field(default_factory=list)
    audience_resonance_notes: list[str] = Field(default_factory=list)
    proof_expectations: list[str] = Field(default_factory=list)
    pending_tests: list[str] = Field(default_factory=list)
    platform_guidance: dict[str, list[str]] = Field(default_factory=dict)


class ContentGenRunMetrics(BaseModel):
    """Performance signals captured for every content-gen run."""

    run_id: str = ""
    brief_id: str = ""
    idea_id: str = ""
    angle_id: str = ""
    idea_score: float = 0.0
    content_type: str = ""
    effort_tier: str = ""
    release_queue_state: str = ""
    phase_1_strategy_ms: int = 0
    phase_2_opportunity_ms: int = 0
    phase_3_research_ms: int = 0
    phase_4_draft_ms: int = 0
    phase_5_visual_ms: int = 0
    phase_6_qc_ms: int = 0
    phase_7_publish_ms: int = 0
    total_cycle_time_ms: int = 0
    release_state: str = "unknown"
    kill_reason: str = ""
    kill_phase: str = ""
    reuse_recommended: bool = False
    derivative_count: int = 0
    approved_with_known_risks: bool = False
    script_word_count: int = 0
    production_asset_count: int = 0
    packaging_variant_count: int = 0
    llm_call_count: int = 0
    estimated_cost_cents: float = 0.0
    view_count: int = 0
    engagement_rate: float = 0.0
    created_at: str = ""
    published_at: str = ""
    analyzed_at: str = ""

    @computed_field(return_type=float)
    @property
    def phase_4_draft_pct(self) -> float:
        if not self.total_cycle_time_ms:
            return 0.0
        return round(self.phase_4_draft_ms / self.total_cycle_time_ms, 4)

    @computed_field(return_type=float)
    @property
    def is_fast_cycle(self) -> float:
        thresholds = {"quick": 300000, "standard": 900000, "deep": 1800000}
        threshold = thresholds.get(self.effort_tier, 900000)
        return 1.0 if self.total_cycle_time_ms < threshold else 0.0

    @computed_field(return_type=bool)
    @property
    def killed(self) -> bool:
        return self.release_state in ("killed_early", "killed_late")


class OperatingFitnessMetrics(BaseModel):
    """Operating fitness metrics for content-gen workflow."""

    avg_cycle_time_ms: float = 0.0
    median_cycle_time_ms: float = 0.0
    p95_cycle_time_ms: float = 0.0
    fastest_cycle_time_ms: int = 0
    slowest_cycle_time_ms: int = 0
    total_ideas_evaluated: int = 0
    ideas_killed_early: int = 0
    ideas_killed_late: int = 0
    ideas_published: int = 0
    ideas_held: int = 0
    ideas_recycled: int = 0

    @computed_field(return_type=float)
    @property
    def kill_rate(self) -> float:
        total = self.total_ideas_evaluated
        if not total:
            return 0.0
        killed = self.ideas_killed_early + self.ideas_killed_late
        return round(killed / total, 4)

    @computed_field(return_type=float)
    @property
    def early_kill_rate(self) -> float:
        total = self.total_ideas_evaluated
        if not total:
            return 0.0
        return round(self.ideas_killed_early / total, 4)

    @computed_field(return_type=float)
    @property
    def late_kill_rate(self) -> float:
        total = self.total_ideas_evaluated
        if not total:
            return 0.0
        return round(self.ideas_killed_late / total, 4)

    @computed_field(return_type=float)
    @property
    def publish_rate(self) -> float:
        total = self.total_ideas_evaluated
        if not total:
            return 0.0
        return round(self.ideas_published / total, 4)

    @computed_field(return_type=float)
    @property
    def reuse_rate(self) -> float:
        held_and_recycled = self.ideas_held + self.ideas_recycled
        if not held_and_recycled:
            return 0.0
        return round(self.ideas_recycled / held_and_recycled, 4)

    reuse_candidates_identified: int = 0
    reuse_candidates_applied: int = 0
    total_estimated_cost_cents: float = 0.0
    avg_cost_per_published: float = 0.0
    avg_cost_per_killed: float = 0.0

    @computed_field(return_type=float)
    @property
    def cost_per_idea(self) -> float:
        total = self.total_ideas_evaluated
        if not total:
            return 0.0
        return round(self.total_estimated_cost_cents / total, 2)

    ideas_per_week: float = 0.0
    published_per_week: float = 0.0
    period_start: str = ""
    period_end: str = ""
    total_runs: int = 0
    rule_churn_rate: float = 0.0
    deprecated_rules_count: int = 0
    new_rules_count: int = 0
    avg_rule_confidence: float = 0.0
    rules_needing_review_count: int = 0
    hook_rule_count: int = 0
    framing_rule_count: int = 0
    scoring_rule_count: int = 0
    packaging_rule_count: int = 0
    other_rule_count: int = 0

    @computed_field(return_type=float)
    @property
    def rule_diversity_ratio(self) -> float:
        non_hook = self.framing_rule_count + self.scoring_rule_count + self.packaging_rule_count + self.other_rule_count
        if not self.hook_rule_count:
            return 2.0 if non_hook else 0.0
        return round(non_hook / self.hook_rule_count, 3)

    @computed_field(return_type=float)
    @property
    def learning_bias_score(self) -> float:
        total = self.hook_rule_count + self.framing_rule_count + self.scoring_rule_count + self.packaging_rule_count + self.other_rule_count
        if not total:
            return 0.0
        hook_share = self.hook_rule_count / total
        expected_hook_share = 0.17
        bias = hook_share - expected_hook_share
        return round(max(0.0, bias), 3)

    @computed_field(return_type=str)
    @property
    def drift_summary(self) -> str:
        parts = []
        if self.rule_churn_rate > 0.5:
            parts.append(f"High rule churn: {self.rule_churn_rate:.1f}/week")
        if self.deprecated_rules_count > 0:
            parts.append(f"{self.deprecated_rules_count} rules deprecated")
        if self.rules_needing_review_count > 0:
            parts.append(f"{self.rules_needing_review_count} rules need review")
        bias = self.learning_bias_score
        if bias > 0.3:
            parts.append("Hook overrepresentation detected")
        elif bias > 0.1:
            parts.append("Slight hook bias")
        if not parts:
            parts.append("Strategy stable")
        return "; ".join(parts)

    def to_summary(self) -> str:
        lines = [
            "Operating Fitness Metrics:",
            f"  Cycle Time: avg={self.avg_cycle_time_ms/1000:.0f}s, median={self.median_cycle_time_ms/1000:.0f}s, p95={self.p95_cycle_time_ms/1000:.0f}s",
            f"  Kill Rate: {self.kill_rate:.1%} (early={self.early_kill_rate:.1%}, late={self.late_kill_rate:.1%})",
            f"  Publish Rate: {self.publish_rate:.1%}",
            f"  Reuse Rate: {self.reuse_rate:.1%}",
            f"  Cost: avg/published=${self.avg_cost_per_published:.2f}, avg/killed=${self.avg_cost_per_killed:.2f}",
            f"  Throughput: {self.published_per_week:.1f} published/week",
            f"  Period: {self.period_start} to {self.period_end}",
        ]
        return "\n".join(lines)


class PlanningLearning(BaseModel):
    """A reusable opportunity-planning pattern extracted from runs."""

    learning_id: str = Field(default_factory=lambda: "planlearn__placeholder__")
    category: PlanningLearningCategory = PlanningLearningCategory.BRIEF_SPECIFICITY
    pattern: str = ""
    implication: str = ""
    guidance: str = ""
    source_brief_ids: list[str] = Field(default_factory=list)
    operator_reviewed: bool = False
    is_active: bool = True
    created_at: str = ""


class PlanningMetrics(BaseModel):
    """Tracking metrics for opportunity planning quality over time."""

    total_briefs: int = 0
    acceptable_briefs: int = 0
    rewritten_briefs: int = 0
    approved_briefs: int = 0
    converted_to_production: int = 0

    @computed_field(return_type=float)
    @property
    def pass_rate(self) -> float:
        if not self.total_briefs:
            return 0.0
        return round(self.acceptable_briefs / self.total_briefs, 3)

    @computed_field(return_type=float)
    @property
    def rewrite_rate(self) -> float:
        if not self.total_briefs:
            return 0.0
        return round(self.rewritten_briefs / self.total_briefs, 3)

    @computed_field(return_type=float)
    @property
    def approval_rate(self) -> float:
        if not self.total_briefs:
            return 0.0
        return round(self.approved_briefs / self.total_briefs, 3)

    @computed_field(return_type=float)
    @property
    def production_conversion_rate(self) -> float:
        if not self.approved_briefs:
            return 0.0
        return round(self.converted_to_production / self.approved_briefs, 3)

    def to_summary(self) -> str:
        lines = [
            "Planning Metrics:",
            f"  Total briefs: {self.total_briefs}",
            f"  Acceptable (passed validation): {self.acceptable_briefs} ({self.pass_rate:.1%})",
            f"  Required rewrite: {self.rewritten_briefs} ({self.rewrite_rate:.1%})",
            f"  Approved: {self.approved_briefs} ({self.approval_rate:.1%})",
            f"  Converted to production: {self.converted_to_production} ({self.production_conversion_rate:.1%})",
        ]
        return "\n".join(lines)


class RuleVersion(BaseModel):
    """A single versioned change to strategy rules."""

    version_id: str = Field(default_factory=lambda: f"rulev_{uuid4().hex[:8]}")
    kind: RuleVersionKind = RuleVersionKind.HOOK
    operation: RuleChangeOperation = RuleChangeOperation.ADDED
    change_summary: str = ""
    previous_value: str = ""
    new_value: str = ""
    source_learning_ids: list[str] = Field(default_factory=list)
    source_content_ids: list[str] = Field(default_factory=list)
    approved_by: str = ""
    created_at: str = ""
    lifecycle_status: RuleLifecycleStatus = RuleLifecycleStatus.PROMOTED
    confidence: float = 0.0
    evidence_count: int = 0
    review_after: str = ""
    review_notes: str = ""


class RuleVersionHistory(BaseModel):
    """Version history for strategy rule changes."""

    versions: list[RuleVersion] = Field(default_factory=list)

    def get_active_rules(self, kind: RuleVersionKind) -> list[str]:
        """Get the current active rules of a given kind, in order of version."""
        active = [
            v for v in self.versions
            if v.kind == kind and v.lifecycle_status == RuleLifecycleStatus.PROMOTED
        ]
        active.sort(key=lambda v: v.created_at)
        return [v.new_value for v in active if v.operation != RuleChangeOperation.REMOVED]


# Import uuid at runtime to avoid top-level import issues
from uuid import uuid4  # noqa: E402

