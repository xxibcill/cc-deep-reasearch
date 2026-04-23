"""Pipeline context, stage traces, and operating phase models."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, model_validator

from .backlog import PipelineCandidate
from .shared import (
    OperatingPhase,
)


# ---------------------------------------------------------------------------
# Stage-to-phase mapping
# ---------------------------------------------------------------------------

STAGE_TO_PHASE_MAPPING: dict[str, OperatingPhase] = {
    "load_strategy": OperatingPhase.PHASE_01_STRATEGY,
    "plan_opportunity": OperatingPhase.PHASE_02_OPPORTUNITY,
    "build_backlog": OperatingPhase.PHASE_02_OPPORTUNITY,
    "score_ideas": OperatingPhase.PHASE_02_OPPORTUNITY,
    "generate_angles": OperatingPhase.PHASE_02_OPPORTUNITY,
    "build_research_pack": OperatingPhase.PHASE_03_RESEARCH,
    "build_argument_map": OperatingPhase.PHASE_03_RESEARCH,
    "run_scripting": OperatingPhase.PHASE_04_DRAFT,
    "visual_translation": OperatingPhase.PHASE_05_VISUAL,
    "production_brief": OperatingPhase.PHASE_05_VISUAL,
    "packaging": OperatingPhase.PHASE_06_QC,
    "human_qc": OperatingPhase.PHASE_06_QC,
    "publish_queue": OperatingPhase.PHASE_07_PUBLISH,
    "performance_analysis": OperatingPhase.PHASE_07_PUBLISH,
}


# Phase-to-stages mapping: which stages belong to each phase
PHASE_TO_STAGES_MAPPING: dict[OperatingPhase, list[str]] = {
    OperatingPhase.PHASE_01_STRATEGY: ["load_strategy"],
    OperatingPhase.PHASE_02_OPPORTUNITY: [
        "plan_opportunity",
        "build_backlog",
        "score_ideas",
        "generate_angles",
    ],
    OperatingPhase.PHASE_03_RESEARCH: [
        "build_research_pack",
        "build_argument_map",
    ],
    OperatingPhase.PHASE_04_DRAFT: ["run_scripting"],
    OperatingPhase.PHASE_05_VISUAL: [
        "visual_translation",
        "production_brief",
    ],
    OperatingPhase.PHASE_06_QC: ["packaging", "human_qc"],
    OperatingPhase.PHASE_07_PUBLISH: [
        "publish_queue",
        "performance_analysis",
    ],
}


OPERATING_PHASE_LABELS: dict[OperatingPhase, str] = {
    OperatingPhase.PHASE_01_STRATEGY: "Strategy & Setup",
    OperatingPhase.PHASE_02_OPPORTUNITY: "Opportunity & Ideation",
    OperatingPhase.PHASE_03_RESEARCH: "Research & Argument",
    OperatingPhase.PHASE_04_DRAFT: "Draft & Refinement",
    OperatingPhase.PHASE_05_VISUAL: "Visual & Production",
    OperatingPhase.PHASE_06_QC: "QC & Approval",
    OperatingPhase.PHASE_07_PUBLISH: "Publish & Learn",
}


def get_phase_for_stage(stage_name: str) -> OperatingPhase:
    """Return the operating phase for a given pipeline stage."""
    return STAGE_TO_PHASE_MAPPING.get(stage_name, OperatingPhase.PHASE_02_OPPORTUNITY)


def get_stages_for_phase(phase: OperatingPhase) -> list[str]:
    """Return the list of pipeline stages for a given operating phase."""
    return PHASE_TO_STAGES_MAPPING.get(phase, [])


# ---------------------------------------------------------------------------
# Phase governance models
# ---------------------------------------------------------------------------


class PhaseExitCriteria(BaseModel):
    """Exit criteria for completing a phase."""

    description: str = Field(default="", description="Human-readable description of what constitutes phase completion.")
    required_artifacts: list[str] = Field(default_factory=list, description="List of artifact names that must be present to exit the phase.")
    quality_threshold: float | None = Field(default=None, description="Optional quality score threshold to meet before exiting.")


class PhaseSkipCondition(BaseModel):
    """Condition under which a phase can be skipped."""

    reason: str = Field(default="", description="Human-readable reason why the phase can be skipped.")
    requires_manual_override: bool = Field(default=False, description="Whether operator confirmation is required to skip.")
    preserves_quality: bool = Field(default=True, description="Whether skipping this phase preserves output quality.")


class PhaseKillCondition(BaseModel):
    """Condition under which a phase should be terminated early."""

    reason: str = Field(default="", description="Human-readable reason why the phase should be killed.")
    abort_pipeline: bool = Field(default=False, description="Whether killing this phase should abort the entire pipeline.")
    preserve_artifacts: bool = Field(default=True, description="Whether to preserve partial artifacts even when killed.")


class PhaseReuseOpportunity(BaseModel):
    """Opportunity to reuse phase outputs across runs."""

    description: str = Field(default="", description="What can be reused from this phase.")
    reuse_pattern: str = Field(default="", description="How to reuse (e.g., 'cache', 'template', 'reference').")
    ttl_hours: int | None = Field(default=None, description="How long reuse is valid (None = until next strategy update).")


class OperatingPhasePolicy(BaseModel):
    """Typed governance metadata for one operating phase."""

    phase: OperatingPhase = Field(description="Which operating phase this policy governs.")
    phase_label: str = Field(description="Human-readable phase name.")
    owner: str = Field(default="", description="Who is responsible for this phase (role or team).")
    max_turnaround_minutes: int = Field(default=60, description="Expected maximum turnaround time for this phase in minutes.")
    entry_criteria: list[str] = Field(default_factory=list, description="List of conditions that must be true before phase execution.")
    exit_criteria: PhaseExitCriteria = Field(default_factory=PhaseExitCriteria, description="Criteria for successfully completing this phase.")
    skip_conditions: list[PhaseSkipCondition] = Field(default_factory=list, description="Conditions under which this phase can be skipped.")
    kill_conditions: list[PhaseKillCondition] = Field(default_factory=list, description="Conditions under which this phase should be killed.")
    reuse_opportunities: list[PhaseReuseOpportunity] = Field(default_factory=list, description="Opportunities to reuse phase outputs in future runs.")


DEFAULT_PHASE_POLICIES: dict[OperatingPhase, OperatingPhasePolicy] = {
    OperatingPhase.PHASE_01_STRATEGY: OperatingPhasePolicy(
        phase=OperatingPhase.PHASE_01_STRATEGY,
        phase_label="Strategy & Setup",
        owner="content lead",
        max_turnaround_minutes=5,
        entry_criteria=["strategy memory exists"],
        exit_criteria=PhaseExitCriteria(description="Strategy memory loaded and validated", required_artifacts=["strategy"]),
        skip_conditions=[],
        kill_conditions=[
            PhaseKillCondition(reason="Strategy memory is corrupted", abort_pipeline=False, preserve_artifacts=True),
        ],
        reuse_opportunities=[
            PhaseReuseOpportunity(description="Strategy memory persists across all runs", reuse_pattern="persistent_store"),
        ],
    ),
    OperatingPhase.PHASE_02_OPPORTUNITY: OperatingPhasePolicy(
        phase=OperatingPhase.PHASE_02_OPPORTUNITY,
        phase_label="Opportunity & Ideation",
        owner="senior editor",
        max_turnaround_minutes=120,
        entry_criteria=["strategy memory loaded", "theme defined"],
        exit_criteria=PhaseExitCriteria(
            description="At least one scored idea with selected angle",
            required_artifacts=["opportunity_brief", "backlog", "scoring", "angles"],
        ),
        skip_conditions=[
            PhaseSkipCondition(
                reason="Using pre-scored ideas from previous run",
                requires_manual_override=True,
                preserves_quality=True,
            ),
        ],
        kill_conditions=[
            PhaseKillCondition(reason="No ideas score above production threshold", abort_pipeline=False, preserve_artifacts=True),
            PhaseKillCondition(reason="All ideas killed during scoring", abort_pipeline=True, preserve_artifacts=True),
        ],
        reuse_opportunities=[
            PhaseReuseOpportunity(description="Scored backlog can be cached for 24 hours", reuse_pattern="cache", ttl_hours=24),
        ],
    ),
    OperatingPhase.PHASE_03_RESEARCH: OperatingPhasePolicy(
        phase=OperatingPhase.PHASE_03_RESEARCH,
        phase_label="Research & Argument",
        owner="research lead",
        max_turnaround_minutes=180,
        entry_criteria=["angle selected", "opportunity brief approved or in review"],
        exit_criteria=PhaseExitCriteria(
            description="Argument map with proof anchors and beat plan",
            required_artifacts=["research_pack", "argument_map"],
        ),
        skip_conditions=[
            PhaseSkipCondition(
                reason="Using cached research from previous run on same angle",
                requires_manual_override=True,
                preserves_quality=False,
            ),
        ],
        kill_conditions=[
            PhaseKillCondition(reason="Research pack has zero usable claims", abort_pipeline=False, preserve_artifacts=True),
            PhaseKillCondition(reason="All claims flagged as unsafe with no safe alternative", abort_pipeline=True, preserve_artifacts=True),
        ],
        reuse_opportunities=[
            PhaseReuseOpportunity(description="Research pack can be reused within same opportunity", reuse_pattern="cache", ttl_hours=168),
        ],
    ),
    OperatingPhase.PHASE_04_DRAFT: OperatingPhasePolicy(
        phase=OperatingPhase.PHASE_04_DRAFT,
        phase_label="Draft & Refinement",
        owner="script writer",
        max_turnaround_minutes=240,
        entry_criteria=["argument map complete", "beat plan defined"],
        exit_criteria=PhaseExitCriteria(
            description="Final script passed QC with all beats complete",
            required_artifacts=["scripting"],
            quality_threshold=0.7,
        ),
        skip_conditions=[],
        kill_conditions=[
            PhaseKillCondition(reason="Script failed QC after maximum iterations", abort_pipeline=False, preserve_artifacts=True),
            PhaseKillCondition(reason="All beats marked as failed in targeted revision", abort_pipeline=True, preserve_artifacts=True),
        ],
        reuse_opportunities=[
            PhaseReuseOpportunity(description="Stable beats from iterative revision can be preserved", reuse_pattern="template"),
        ],
    ),
    OperatingPhase.PHASE_05_VISUAL: OperatingPhasePolicy(
        phase=OperatingPhase.PHASE_05_VISUAL,
        phase_label="Visual & Production",
        owner="production lead",
        max_turnaround_minutes=60,
        entry_criteria=["script finalized (QC passed or tightened)"],
        exit_criteria=PhaseExitCriteria(
            description="Production brief with location, props, and pickup lines",
            required_artifacts=["visual_plan", "production_brief"],
        ),
        skip_conditions=[
            PhaseSkipCondition(
                reason="Visual plan not needed (audio-only content)",
                requires_manual_override=True,
                preserves_quality=True,
            ),
        ],
        kill_conditions=[
            PhaseKillCondition(reason="Visual plan references missing assets", abort_pipeline=False, preserve_artifacts=True),
        ],
        reuse_opportunities=[
            PhaseReuseOpportunity(description="Production brief templates for recurring shoot setups", reuse_pattern="template"),
        ],
    ),
    OperatingPhase.PHASE_06_QC: OperatingPhasePolicy(
        phase=OperatingPhase.PHASE_06_QC,
        phase_label="QC & Approval",
        owner="quality lead",
        max_turnaround_minutes=30,
        entry_criteria=["production brief complete", "packaging variants generated"],
        exit_criteria=PhaseExitCriteria(
            description="Human QC approved with no blocking must-fix items",
            required_artifacts=["packaging", "qc_gate"],
        ),
        skip_conditions=[],
        kill_conditions=[
            PhaseKillCondition(reason="Human QC blocked with must-fix items not resolved", abort_pipeline=False, preserve_artifacts=True),
        ],
        reuse_opportunities=[
            PhaseReuseOpportunity(description="QC checklist templates for recurring issue patterns", reuse_pattern="template"),
        ],
    ),
    OperatingPhase.PHASE_07_PUBLISH: OperatingPhasePolicy(
        phase=OperatingPhase.PHASE_07_PUBLISH,
        phase_label="Publish & Learn",
        owner="distribution lead",
        max_turnaround_minutes=15,
        entry_criteria=["QC approved"],
        exit_criteria=PhaseExitCriteria(
            description="Publish items scheduled with engagement actions",
            required_artifacts=["publish_items"],
        ),
        skip_conditions=[],
        kill_conditions=[
            PhaseKillCondition(reason="Platform constraints violated by latest changes", abort_pipeline=False, preserve_artifacts=True),
        ],
        reuse_opportunities=[
            PhaseReuseOpportunity(description="Publish scheduling patterns inform future timing", reuse_pattern="learning"),
        ],
    ),
}


def get_phase_policy(phase: OperatingPhase) -> OperatingPhasePolicy:
    """Get the operating policy for a phase."""
    return DEFAULT_PHASE_POLICIES.get(phase, OperatingPhasePolicy(phase=phase, phase_label=phase.value))


# ---------------------------------------------------------------------------
# Stage trace models
# ---------------------------------------------------------------------------


class StageTraceMetadata(BaseModel):
    """Structured metadata for pipeline stage traces."""

    selected_idea_id: str = ""
    selected_angle_id: str = ""
    shortlist_count: int = 0
    option_count: int = 0
    is_degraded: bool = False
    degradation_reason: str = ""
    fact_count: int = 0
    proof_count: int = 0
    claim_count: int = 0
    unsafe_claim_count: int = 0
    cache_reused: bool = False
    step_count: int = 0
    llm_call_count: int = 0
    final_word_count: int = 0
    current_iteration: int = 0
    latest_quality_score: float = 0.0
    should_rerun_research: bool = False
    beats_count: int = 0
    platforms_count: int = 0
    approved: bool = False
    active_candidate_count: int = 0
    parse_mode: str = ""
    fact_risk_decision: str = ""
    progressive_issue_count: int = 0
    checkpoint_count: int = 0


class PipelineStageTrace(BaseModel):
    """Trace record for one completed pipeline stage."""

    stage_index: int
    stage_name: str
    stage_label: str
    phase: OperatingPhase = Field(default="phase_02_opportunity", description="The operating phase this stage belongs to.")
    phase_label: str = Field(default="Opportunity & Ideation", description="Human-readable phase name.")
    policy: OperatingPhasePolicy | None = Field(default=None, description="The operating policy that governed this stage's execution.")
    skip_reason: str = Field(default="", description="Reason for skipping this stage (if status is 'skipped').")
    kill_reason: str = Field(default="", description="Reason for killing this stage early (if status is 'killed').")
    policy_override: str = Field(default="", description="Description of any manual policy override applied to this stage.")
    status: str = "completed"
    started_at: str = ""
    completed_at: str = ""
    duration_ms: int = 0
    input_summary: str = ""
    output_summary: str = ""
    warnings: list[str] = Field(default_factory=list)
    decision_summary: str = ""
    metadata: StageTraceMetadata = Field(default_factory=StageTraceMetadata)


# ---------------------------------------------------------------------------
# Pipeline stage constants
# ---------------------------------------------------------------------------

PIPELINE_STAGES: list[str] = [
    "load_strategy",
    "plan_opportunity",
    "build_backlog",
    "score_ideas",
    "generate_angles",
    "build_research_pack",
    "build_argument_map",
    "run_scripting",
    "visual_translation",
    "production_brief",
    "packaging",
    "human_qc",
    "publish_queue",
    "performance_analysis",
]

PIPELINE_STAGE_LABELS: dict[str, str] = {
    "load_strategy": "Loading strategy memory",
    "plan_opportunity": "Planning opportunity brief",
    "build_backlog": "Building backlog",
    "score_ideas": "Scoring ideas",
    "generate_angles": "Building thesis",
    "build_research_pack": "Building research pack",
    "build_argument_map": "Building argument map",
    "run_scripting": "Running scripting pipeline",
    "visual_translation": "Translating to visuals",
    "production_brief": "Building production brief",
    "packaging": "Generating packaging",
    "human_qc": "Running human QC gate",
    "publish_queue": "Creating publish queue entry",
    "performance_analysis": "Analyzing performance",
}


# ---------------------------------------------------------------------------
# Pipeline context models
# ---------------------------------------------------------------------------


class PipelineLaneContext(BaseModel):
    """Per-idea execution state for one shortlisted production lane."""

    idea_id: str = ""
    role: Literal["primary", "runner_up"] = "primary"
    status: Literal["selected", "runner_up", "in_production", "published"] = "selected"
    last_completed_stage: int = -1
    thesis_artifact: "ThesisArtifact | None" = None
    angles: "AngleOutput | None" = None
    research_pack: "ResearchPack | None" = None
    argument_map: "ArgumentMap | None" = None
    scripting: "ScriptingContext | None" = None
    visual_plan: "VisualPlanOutput | None" = None
    production_brief: "ProductionBrief | None" = None
    execution_brief: "VisualProductionExecutionBrief | None" = None
    packaging: "PackagingOutput | None" = None
    qc_gate: "HumanQCGate | None" = None
    fact_risk_gate: "FactRiskGate | None" = None
    progressive_qc_issues: list["ProgressiveQCIssue"] = Field(default_factory=list)
    progressive_qc_checkpoints: list["ProgressiveQCCheckpoint"] = Field(default_factory=list)
    early_packaging_signals: "EarlyPackagingSignals | None" = None
    derivative_opportunities: list["DerivativeOpportunity"] = Field(default_factory=list)
    draft_decision: "DraftLaneDecision | None" = None
    decision_reason: str = ""
    publish_items: list["PublishItem"] = Field(default_factory=list)


class PipelineContext(BaseModel):
    """Accumulated state through the full 14-stage content pipeline."""

    pipeline_id: str = Field(default_factory=lambda: uuid4().hex[:12])
    theme: str = ""
    created_at: str = ""
    current_stage: int = 0
    strategy: "StrategyMemory | None" = None
    opportunity_brief: "OpportunityBrief | None" = None
    brief_reference: "PipelineBriefReference | None" = None
    run_constraints: "RunConstraints | None" = None
    backlog: "BacklogOutput | None" = None
    scoring: "ScoringOutput | None" = None
    shortlist: list[str] = Field(default_factory=list)
    selected_idea_id: str = ""
    selection_reasoning: str = ""
    runner_up_idea_ids: list[str] = Field(default_factory=list)
    active_candidates: list["PipelineCandidate"] = Field(default_factory=list)
    lane_contexts: list[PipelineLaneContext] = Field(default_factory=list)
    thesis_artifact: "ThesisArtifact | None" = None
    angles: "AngleOutput | None" = None
    research_pack: "ResearchPack | None" = None
    argument_map: "ArgumentMap | None" = None
    fact_risk_gate: "FactRiskGate | None" = None
    scripting: "ScriptingContext | None" = None
    visual_plan: "VisualPlanOutput | None" = None
    production_brief: "ProductionBrief | None" = None
    execution_brief: "VisualProductionExecutionBrief | None" = None
    packaging: "PackagingOutput | None" = None
    qc_gate: "HumanQCGate | None" = None
    publish_items: list["PublishItem"] = Field(default_factory=list)
    publish_item: "PublishItem | None" = None
    performance: "PerformanceAnalysis | None" = None
    iteration_state: "IterationState | None" = None
    stage_traces: list[PipelineStageTrace] = Field(default_factory=list)
    claim_ledger: "ClaimTraceLedger | None" = None
    brief_gate: "BriefExecutionGate | None" = None

    @model_validator(mode="after")
    def _populate_candidate_queue(self) -> PipelineContext:
        if not self.active_candidates and self.selected_idea_id:
            self.active_candidates = [
                PipelineCandidate(
                    idea_id=self.selected_idea_id,
                    role="primary",
                    status="selected",
                )
            ]
        return self


# Import uuid at runtime to avoid top-level import issues
from uuid import uuid4  # noqa: E402

