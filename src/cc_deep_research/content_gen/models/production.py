"""Production and visual stage models."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, model_validator

from .angle import EarlyPackagingSignals
from .shared import (
    DraftLaneDecision,
    EffortTier,
    MissingAssetDecision,
    ReleaseState,
    RevisionMode,
    RewriteActionType,
    VisualComplexity,
)


class BeatVisual(BaseModel):
    """Per-beat visual plan."""

    beat: str = ""
    spoken_line: str = ""
    visual: str = ""
    shot_type: str = ""
    a_roll: str = ""
    b_roll: str = ""
    on_screen_text: str = ""
    overlay_or_graphic: str = ""
    prop_or_asset: str = ""
    transition: str = ""
    retention_function: str = ""


class VisualPlanOutput(BaseModel):
    """Output of the visual translation stage."""

    idea_id: str = ""
    angle_id: str = ""
    visual_plan: list[BeatVisual] = Field(default_factory=list)
    visual_refresh_check: str = ""


class ProductionBrief(BaseModel):
    """Production planning output."""

    idea_id: str = ""
    location: str = ""
    setup: str = ""
    wardrobe: str = ""
    props: list[str] = Field(default_factory=list)
    assets_to_prepare: list[str] = Field(default_factory=list)
    audio_checks: list[str] = Field(default_factory=list)
    battery_checks: list[str] = Field(default_factory=list)
    storage_checks: list[str] = Field(default_factory=list)
    pickup_lines_to_capture: list[str] = Field(default_factory=list)
    backup_plan: str = ""
    is_degraded: bool = False
    degradation_reason: str = ""


class AssetFallback(BaseModel):
    """A fallback option for a missing asset or dependency."""

    asset_name: str = Field(description="Name of the asset that might be missing")
    fallback_option: str = Field(description="What to use instead")
    decision: MissingAssetDecision = Field(
        default=MissingAssetDecision.DOWNGRADE,
        description="How to handle if this asset is unavailable",
    )
    decision_note: str = Field(
        default="",
        description="Why this decision was made",
    )


class VisualProductionExecutionBrief(BaseModel):
    """Combined execution brief for formats that use use_combined_execution_brief=True."""

    idea_id: str = ""
    beat_visuals: list[BeatVisual] = Field(default_factory=list)
    location: str = ""
    location_fallback: str = ""
    setup: str = ""
    wardrobe: str = ""
    props: list[str] = Field(default_factory=list)
    prop_fallbacks: list[str] = Field(default_factory=list)
    assets_to_prepare: list[str] = Field(default_factory=list)
    existing_assets: list[str] = Field(default_factory=list)
    asset_reuse_plan: str = ""
    audio_checks: list[str] = Field(default_factory=list)
    battery_checks: list[str] = Field(default_factory=list)
    storage_checks: list[str] = Field(default_factory=list)
    pickup_lines_to_capture: list[str] = Field(default_factory=list)
    visual_fallbacks: list[str] = Field(default_factory=list)
    backup_plan: str = ""
    missing_asset_decisions: list[AssetFallback] = Field(default_factory=list)
    owner: str = ""
    shoot_constraints: str = ""
    planning_depth: Literal["light", "standard", "rich"] = "standard"
    visual_complexity_used: VisualComplexity = Field(
        default=VisualComplexity.STANDARD,
    )
    is_degraded: bool = False
    degradation_reason: str = ""


class PlatformPackage(BaseModel):
    """Per-platform packaging."""

    platform: str = ""
    primary_hook: str = ""
    alternate_hooks: list[str] = Field(default_factory=list)
    cover_text: str = ""
    caption: str = ""
    keywords: list[str] = Field(default_factory=list)
    hashtags: list[str] = Field(default_factory=list)
    pinned_comment: str = ""
    cta: str = ""
    version_notes: str = ""
    target_channel: str = ""
    content_type_hint: str = ""


class PackagingOutput(BaseModel):
    """Output of the packaging generator stage."""

    idea_id: str = ""
    platform_packages: list[PlatformPackage] = Field(default_factory=list)
    draft_hooks: list[str] = Field(default_factory=list)
    early_packaging_signals: EarlyPackagingSignals | None = None


class HumanQCGate(BaseModel):
    """Human-gateable QC output."""

    review_round: int = 1
    hook_strength: str = ""
    clarity_issues: list[str] = Field(default_factory=list)
    factual_issues: list[str] = Field(default_factory=list)
    visual_issues: list[str] = Field(default_factory=list)
    audio_issues: list[str] = Field(default_factory=list)
    caption_issues: list[str] = Field(default_factory=list)
    unsupported_claims: list[str] = Field(default_factory=list)
    risky_claims: list[str] = Field(default_factory=list)
    required_fact_checks: list[str] = Field(default_factory=list)
    must_fix_items: list[str] = Field(default_factory=list)
    approved_for_publish: bool = False
    success_criteria_results: list[str] = Field(default_factory=list)
    release_state: ReleaseState = Field(
        default="blocked",
    )
    override_actor: str = ""
    override_reason: str = ""
    override_timestamp: str = ""
    issue_origin_summary: list[str] = Field(default_factory=list)


class BeatRevisionScope(BaseModel):
    """Identifies a specific beat or claim group that needs repair."""

    beat_id: str = ""
    beat_name: str = ""
    weak_claim_ids: list[str] = Field(default_factory=list)
    missing_proof_ids: list[str] = Field(default_factory=list)
    weakness_reason: str = ""
    is_stable: bool = False


class TargetedRewriteAction(BaseModel):
    """A single repair action targeting a specific beat or claim."""

    action_id: str = Field(default_factory=lambda: f"rewrite_{uuid4().hex[:8]}")
    action_type: RewriteActionType
    beat_id: str = ""
    beat_name: str = ""
    weak_claim_ids: list[str] = Field(default_factory=list)
    missing_proof_ids: list[str] = Field(default_factory=list)
    target_claim_text: str = ""
    target_claim_id: str = ""
    instruction: str = ""
    evidence_gaps: list[str] = Field(default_factory=list)
    priority: int = Field(default=0, ge=0, le=10)


class TargetedRevisionPlan(BaseModel):
    """A surgical revision plan targeting only weak beats and claims."""

    revision_id: str = Field(default_factory=lambda: f"rev_{uuid4().hex[:8]}")
    stable_beats: list[BeatRevisionScope] = Field(default_factory=list)
    weak_beats: list[BeatRevisionScope] = Field(default_factory=list)
    actions: list[TargetedRewriteAction] = Field(default_factory=list)
    revision_summary: str = ""
    full_restart_recommended: bool = False
    is_patch: bool = True
    retrieval_gaps: list[str] = Field(default_factory=list)

    @property
    def has_targeted_actions(self) -> bool:
        return bool(self.actions)

    @property
    def needs_retrieval(self) -> bool:
        return bool(self.retrieval_gaps)

    def stable_beat_ids(self) -> list[str]:
        return [b.beat_id for b in self.stable_beats]

    def weak_beat_ids(self) -> list[str]:
        return [b.beat_id for b in self.weak_beats]


class QualityEvaluation(BaseModel):
    """Result of the quality evaluator agent."""

    overall_quality_score: float = Field(default=0.0, ge=0.0, le=1.0)
    passes_threshold: bool = False
    evidence_coverage: float = Field(default=0.0, ge=0.0, le=1.0)
    claim_safety: float = Field(default=0.0, ge=0.0, le=1.0)
    originality: float = Field(default=0.0, ge=0.0, le=1.0)
    precision: float = Field(default=0.0, ge=0.0, le=1.0)
    expertise_density: float = Field(default=0.0, ge=0.0, le=1.0)
    genericity: float = Field(default=0.0, ge=0.0, le=1.0)
    critical_issues: list[str] = Field(default_factory=list)
    unsupported_claims: list[str] = Field(default_factory=list)
    evidence_actions_required: list[str] = Field(default_factory=list)
    improvement_suggestions: list[str] = Field(default_factory=list)
    research_gaps_identified: list[str] = Field(default_factory=list)
    cliche_flags: list[str] = Field(default_factory=list)
    interchangeable_take_flags: list[str] = Field(default_factory=list)
    rationale: str = ""
    iteration_number: int = 1
    targeted_revision_plan: TargetedRevisionPlan | None = None
    revision_mode: RevisionMode = Field(default="none")

    @property
    def has_blocking_claim_issues(self) -> bool:
        """Return true when the script still contains unsupported or unsafe claims."""
        return bool(self.unsupported_claims)


class IterationState(BaseModel):
    """State tracking for the iterative content generation loop."""

    current_iteration: int = Field(default=1, ge=1)
    max_iterations: int = Field(default=3, ge=1)
    quality_history: list[QualityEvaluation] = Field(default_factory=list)
    latest_feedback: str = ""
    is_converged: bool = False
    convergence_reason: str = ""
    should_rerun_research: bool = False
    revision_mode: RevisionMode = "full"
    targeted_revision_plan: TargetedRevisionPlan | None = None

    @property
    def weak_beat_ids(self) -> list[str]:
        """Return beat IDs that failed quality check and need targeted revision."""
        if self.targeted_revision_plan is None:
            return []
        return [
            action.beat_id
            for action in self.targeted_revision_plan.actions
            if action.action_type in {"rewrite_beat", "refresh_evidence"}
        ]

    @property
    def requires_full_restart(self) -> bool:
        """Return True when the script is fundamentally broken and full restart is cleaner."""
        if self.targeted_revision_plan is None:
            return False
        return self.targeted_revision_plan.full_restart_recommended


class PublishItem(BaseModel):
    """Single publish queue entry."""

    idea_id: str = ""
    platform: str = ""
    publish_datetime: str = ""
    asset_version: str = ""
    caption_version: str = ""
    pinned_comment: str = ""
    cross_post_targets: list[str] = Field(default_factory=list)
    first_30_minute_engagement_plan: str = ""
    status: str = "scheduled"
    draft_decision: DraftLaneDecision | None = None
    decision_reason: str = ""
    claim_status_summary: str = ""
    override_actor: str = ""
    override_reason: str = ""
    override_timestamp: str = ""


class ContentTypeProfile(BaseModel):
    """Depth profile for one content type.

    Determines how much research, drafting, production, and packaging
    depth is required. Each stage respects the profile's skip conditions.
    """

    profile_key: str = ""
    research_depth: Literal["none", "light", "standard", "deep"] = "standard"
    drafting_depth: Literal["outline", "draft", "polished"] = "draft"
    production_depth: Literal["minimal", "standard", "premium"] = "standard"
    visual_complexity: VisualComplexity = VisualComplexity.STANDARD
    packaging_depth: Literal["minimal", "standard", "full"] = "standard"
    use_combined_execution_brief: bool = False
    skip_stages: list[str] = Field(
        default_factory=list,
        description="Stage names to skip for this content type",
    )
    required_artifacts: list[str] = Field(
        default_factory=list,
        description="Stage outputs that must be present for this type",
    )


CONTENT_TYPE_PROFILES: dict[str, ContentTypeProfile] = {
    "short_form_video": ContentTypeProfile(
        profile_key="short_form_video",
        research_depth="standard",
        drafting_depth="polished",
        production_depth="standard",
        visual_complexity=VisualComplexity.STANDARD,
        packaging_depth="standard",
        use_combined_execution_brief=False,
        skip_stages=[],
        required_artifacts=["research_pack", "script", "visual_plan", "production_brief", "packaging"],
    ),
    "newsletter": ContentTypeProfile(
        profile_key="newsletter",
        research_depth="light",
        drafting_depth="draft",
        production_depth="minimal",
        visual_complexity=VisualComplexity.MINIMAL,
        packaging_depth="minimal",
        use_combined_execution_brief=True,
        skip_stages=["visual_translation", "production_brief"],
        required_artifacts=["research_pack", "script", "packaging"],
    ),
    "article": ContentTypeProfile(
        profile_key="article",
        research_depth="deep",
        drafting_depth="polished",
        production_depth="minimal",
        visual_complexity=VisualComplexity.MINIMAL,
        packaging_depth="minimal",
        use_combined_execution_brief=True,
        skip_stages=["visual_translation", "production_brief"],
        required_artifacts=["research_pack", "argument_map", "script", "packaging"],
    ),
    "webinar": ContentTypeProfile(
        profile_key="webinar",
        research_depth="deep",
        drafting_depth="polished",
        production_depth="premium",
        visual_complexity=VisualComplexity.DYNAMIC,
        packaging_depth="full",
        use_combined_execution_brief=False,
        skip_stages=[],
        required_artifacts=["research_pack", "argument_map", "script", "visual_plan", "production_brief", "packaging"],
    ),
    "launch_asset": ContentTypeProfile(
        profile_key="launch_asset",
        research_depth="standard",
        drafting_depth="polished",
        production_depth="premium",
        visual_complexity=VisualComplexity.DYNAMIC,
        packaging_depth="full",
        use_combined_execution_brief=False,
        skip_stages=[],
        required_artifacts=["research_pack", "angle", "script", "visual_plan", "production_brief", "packaging"],
    ),
    "thread": ContentTypeProfile(
        profile_key="thread",
        research_depth="light",
        drafting_depth="draft",
        production_depth="minimal",
        visual_complexity=VisualComplexity.MINIMAL,
        packaging_depth="minimal",
        use_combined_execution_brief=True,
        skip_stages=["visual_translation", "production_brief"],
        required_artifacts=["research_pack", "script", "packaging"],
    ),
    "carousel": ContentTypeProfile(
        profile_key="carousel",
        research_depth="standard",
        drafting_depth="polished",
        production_depth="standard",
        visual_complexity=VisualComplexity.SIMPLE,
        packaging_depth="standard",
        use_combined_execution_brief=True,
        skip_stages=["production_brief"],
        required_artifacts=["research_pack", "script", "visual_plan", "packaging"],
    ),
    "短视频": ContentTypeProfile(
        profile_key="短视频",
        research_depth="standard",
        drafting_depth="polished",
        production_depth="standard",
        visual_complexity=VisualComplexity.STANDARD,
        packaging_depth="standard",
        use_combined_execution_brief=False,
        skip_stages=[],
        required_artifacts=["research_pack", "script", "visual_plan", "production_brief", "packaging"],
    ),
}


def get_content_type_profile(content_type: str) -> ContentTypeProfile:
    """Resolve content type string to profile, with fallback to short_form_video."""
    return CONTENT_TYPE_PROFILES.get(content_type, CONTENT_TYPE_PROFILES.get("short_form_video"))


class RunConstraints(BaseModel):
    """Per-run constraint variables that change each content cycle.

    These fields capture the run-specific decisions that would otherwise
    be embedded in the opportunity brief. Separating them makes strategy
    truly evergreen and allows operators to set content type and effort
    tier before opportunity scoring begins.

    Strategy memory provides the durable defaults; RunConstraints provides
    the per-run overrides.
    """

    content_type: str = Field(
        default="",
        description="The content format for this run.",
    )
    effort_tier: EffortTier = Field(
        default=EffortTier.STANDARD,
        description="Effort tier determining iteration depth and SLA.",
    )
    owner: str = Field(
        default="",
        description="Who is responsible for this content run.",
    )
    channel_goal: str = Field(
        default="",
        description="Primary channel or distribution goal for this content.",
    )
    success_target: str = Field(
        default="",
        description="What success looks like for this content cycle.",
    )
    target_platforms: list[str] = Field(
        default_factory=list,
        description="Specific platforms to optimize for (empty = use strategy defaults).",
    )
    use_iterative_loop: bool = Field(
        default=True,
        description="Whether to enable iterative drafting with quality evaluation.",
    )
    max_iterations: int | None = Field(
        default=None,
        description="Override for max iterations (None = use config default).",
    )
    research_depth_override: Literal["", "light", "standard", "deep"] = Field(
        default="",
        description="Optional operator-selected research depth that overrides ROI-based routing.",
    )
    research_override_reason: str = Field(
        default="",
        description="Why the operator overrode the default research depth routing.",
    )

    @model_validator(mode="after")
    def validate_content_type(self) -> RunConstraints:
        """Warn and fall back if content_type is not a known profile."""
        if self.content_type and self.content_type not in CONTENT_TYPE_PROFILES:
            import logging

            logger = logging.getLogger(__name__)
            logger.warning(
                "Unknown content_type %r, falling back to short_form_video. "
                "Known types: %s",
                self.content_type,
                ", ".join(sorted(CONTENT_TYPE_PROFILES.keys())),
            )
            self.content_type = "short_form_video"
        return self


# Import uuid at runtime to avoid top-level import issues in this module
from uuid import uuid4  # noqa: E402
