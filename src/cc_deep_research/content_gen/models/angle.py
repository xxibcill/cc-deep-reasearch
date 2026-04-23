"""Angle and thesis stage models."""

from __future__ import annotations

from pydantic import BaseModel, Field


class CoreInputs(BaseModel):
    """Shared inputs that persist across all stages."""

    theme: str = ""
    goal: str = ""
    primary_audience_segment: str = ""
    secondary_audience_segments: list[str] = Field(default_factory=list)


class AngleDefinition(BaseModel):
    """Angle definition within an angle option."""

    angle_id: str = ""
    angle_name: str = ""
    target_audience: str = ""
    viewer_problem: str = ""
    core_promise: str = ""
    primary_takeaway: str = ""
    key_hooks: list[str] = Field(default_factory=list)


class EarlyPackagingSignals(BaseModel):
    """Early packaging signals captured from angle/channel stage."""

    target_channel: str = ""
    content_type: str = ""
    tone: str = ""
    hook_style: str = ""
    differentiation_hint: str = ""


class DerivativeOpportunity(BaseModel):
    """A derivative reuse opportunity extracted from a draft."""

    opportunity_id: str = ""
    derivative_type: str = ""
    description: str = ""
    source_idea_id: str = ""
    priority: str = ""


class AngleOption(BaseModel):
    """Single angle option within AngleOutput."""

    angle_id: str
    angle_name: str = ""
    target_audience: str = ""
    viewer_problem: str = ""
    core_promise: str = ""
    primary_takeaway: str = ""
    thesis: str = ""
    audience_belief_to_challenge: str = ""
    core_mechanism: str = ""
    proof_anchors: list[str] = Field(default_factory=list)
    counterarguments: list[str] = Field(default_factory=list)
    safe_claims: list[str] = Field(default_factory=list)
    unsafe_claims: list[str] = Field(default_factory=list)
    beat_plan: list[str] = Field(default_factory=list)
    selection_reasoning: str = ""
    what_this_contributes: str = ""
    genericity_flags: list[str] = Field(default_factory=list)
    differentiation_strategy: str = ""
    channel_hint: str = ""


class AngleOutput(BaseModel):
    """Output of the angle generation stage."""

    idea_id: str = ""
    options: list[AngleOption] = Field(default_factory=list)
    selected_angle_id: str = ""
    selection_reasoning: str = ""


class BeatIntent(BaseModel):
    """Intent and structure for a single beat."""

    beat_id: str = ""
    beat_type: str = ""
    intent: str = ""
    key_points: list[str] = Field(default_factory=list)
    evidence_needs: list[str] = Field(default_factory=list)
    talking_duration_seconds: int = 0


class BeatIntentMap(BaseModel):
    """Map of all beats with their intent and evidence needs."""

    beats: list[BeatIntent] = Field(default_factory=list)


class HookSet(BaseModel):
    """Set of hook variants for a script."""

    primary_hook: str = ""
    hook_variants: list[str] = Field(default_factory=list)


class CtAVariants(BaseModel):
    """CTA variant options."""

    primary_cta: str = ""
    cta_variants: list[str] = Field(default_factory=list)


class ThesisArtifact(BaseModel):
    """P3-T2: Unified thesis artifact combining angle selection with argument design.

    This is the output of the generate_angles stage (previously produced separately
    by AngleOutput and ArgumentMap). It combines angle selection with thesis
    structure, proof anchors, and beat plan.
    """

    # Identity
    idea_id: str = ""
    angle_id: str = ""

    # Angle fields (from P2 angle selection)
    angle_name: str = ""
    target_audience: str = ""
    viewer_problem: str = ""
    core_promise: str = ""
    primary_takeaway: str = ""

    # Thesis core
    thesis: str = ""
    audience_belief_to_challenge: str = ""
    core_mechanism: str = ""

    # Argument structure
    proof_anchors: list[str] = Field(default_factory=list)
    counterarguments: list[str] = Field(default_factory=list)
    safe_claims: list[str] = Field(default_factory=list)
    unsafe_claims: list[str] = Field(default_factory=list)

    # Beat structure
    beat_plan: list[str] = Field(
        default_factory=list,
        description="Ordered list of beat topics/claims that form the story arc",
    )
    beat_intent_map: BeatIntentMap | None = None

    # Evidence tracking
    evidence_anchors: list[str] = Field(
        default_factory=list,
        description="Source IDs of evidence supporting proof anchors",
    )
    missing_evidence: list[str] = Field(
        default_factory=list,
        description="Claims without sufficient evidence",
    )

    # Selection metadata
    selection_reasoning: str = ""
    what_this_contributes: str = ""
    differentiation_strategy: str = ""

    # P3-T3: Generic framing detection
    genericity_flags: list[str] = Field(default_factory=list)

    # P4-T1: Early packaging signals
    early_packaging_signals: EarlyPackagingSignals | None = None

    # P4-T2: Derivative opportunities
    derivative_opportunities: list[DerivativeOpportunity] = Field(default_factory=list)

    # P4-T3: Claim trace reference
    claim_ledger: "ClaimTraceLedger | None" = None

    def get_beats(self) -> list[str]:
        """Return the beat plan as a list of strings."""
        return self.beat_plan


class StrategyMemory(BaseModel):
    """Long-term strategy memory guiding content decisions.

    Loaded once per theme and used across all stages to ensure
    consistency and quality bar.
    """

    theme: str = ""
    niche: str = ""
    pillars: list[str] = Field(default_factory=list)
    audience_segments: list[str] = Field(default_factory=list)
    proof_standards: list[str] = Field(default_factory=list)
    differentiation_gaps: list[str] = Field(default_factory=list)
    common_objections: list[str] = Field(default_factory=list)
    voice_guide: str = ""
    hook_library: list[str] = Field(default_factory=list)
    content_type_examples: list[str] = Field(default_factory=list)
    content_type_profiles: dict[str, str] = Field(default_factory=dict)
