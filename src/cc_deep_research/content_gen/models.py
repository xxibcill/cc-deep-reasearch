"""Data models for the content generation workflow.

Contract Version: 1.5.0

This module defines the data contracts for each pipeline stage. Each model
represents the expected output format from its corresponding agent.

When updating prompts, ensure the corresponding parser remains compatible
with the model's fields. Major format changes should bump the CONTRACT_VERSION.
The canonical inventory of prompt/parser contracts lives in
``CONTENT_GEN_STAGE_CONTRACTS`` below.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any, Literal
from uuid import uuid4

from pydantic import BaseModel, Field, computed_field, field_validator, model_validator

from cc_deep_research.models.search import QueryProvenance

CONTRACT_VERSION = "1.8.0"


@dataclass(frozen=True, slots=True)
class ContentGenStageContract:
    """Canonical prompt/parser contract for one prompt-backed stage."""

    stage_name: str
    prompt_module: str
    contract_version: str
    parser_location: str
    output_model: str
    format_notes: str
    required_fields: tuple[str, ...] = ()
    expected_sections: tuple[str, ...] = ()
    failure_mode: Literal["fail_fast", "tolerant", "human_gated"] = "fail_fast"


CONTENT_GEN_STAGE_CONTRACTS: dict[str, ContentGenStageContract] = {
    "plan_opportunity": ContentGenStageContract(
        stage_name="plan_opportunity",
        prompt_module="prompts/opportunity.py",
        contract_version="1.2.0",
        parser_location="agents/opportunity.py::_parse_opportunity_brief (JSON first, legacy fallback)",
        output_model="OpportunityBrief",
        format_notes="JSON output (primary) with structured schema; legacy header+dash text (fallback). parse_mode recorded in trace metadata. P3-T2 adds version/is_generated/is_approved/revision_history tracking.",
        required_fields=(
            "Goal",
            "Primary audience segment",
            "Problem statements",
            "Content objective",
        ),
        expected_sections=(
            "Theme",
            "Secondary audience segments",
            "Proof requirements",
            "Platform constraints",
            "Risk constraints",
            "Freshness rationale",
            "Sub-angles",
            "Research hypotheses",
            "Success criteria",
            "expert_take",
            "non_obvious_claims_to_test",
            "genericity_risks",
        ),
        failure_mode="fail_fast",
    ),
    "build_backlog": ContentGenStageContract(
        stage_name="build_backlog",
        prompt_module="prompts/backlog.py",
        contract_version="1.2.0",
        parser_location="agents/backlog.py::_parse_backlog_items",
        output_model="BacklogOutput",
        format_notes="Repeated '---' blocks with field_name: value pairs.",
        required_fields=("title", "one_line_summary"),
        expected_sections=(
            "category",
            "audience",
            "persona_detail",
            "problem",
            "why_now",
            "hook",
            "content_type",
            "key_message",
            "call_to_action",
            "evidence",
            "risk_level",
            "Rejected ideas",
            "Rejection reasons",
        ),
        failure_mode="tolerant",
    ),
    "score_ideas": ContentGenStageContract(
        stage_name="score_ideas",
        prompt_module="prompts/backlog.py",
        contract_version="1.2.0",
        parser_location="agents/backlog.py::_parse_scores + _derive_selection",
        output_model="ScoringOutput",
        format_notes="Repeated '---' score blocks followed by shortlist summary fields.",
        required_fields=("idea_id",),
        expected_sections=(
            "relevance",
            "novelty",
            "authority_fit",
            "production_ease",
            "evidence_strength",
            "hook_strength",
            "repurposing",
            "total_score",
            "recommendation",
            "reason",
            "shortlist",
            "selected_idea_id",
            "selection_reasoning",
        ),
        failure_mode="tolerant",
    ),
    "generate_angles": ContentGenStageContract(
        stage_name="generate_angles",
        prompt_module="prompts/angle.py",
        contract_version="1.1.0",
        parser_location="agents/angle.py::_parse_angle_options",
        output_model="AngleOutput",
        format_notes="Repeated '---' blocks plus trailing best-angle summary fields.",
        required_fields=(
            "target_audience",
            "viewer_problem",
            "core_promise",
            "primary_takeaway",
        ),
        expected_sections=(
            "lens",
            "format",
            "tone",
            "cta",
            "why_this_version_should_exist",
            "Best angle_id",
            "Selection reasoning",
        ),
        failure_mode="fail_fast",
    ),
    "build_research_pack": ContentGenStageContract(
        stage_name="build_research_pack",
        prompt_module="prompts/research_pack.py",
        contract_version="1.3.0",
        parser_location="agents/research_pack.py::_parse_research_pack",
        output_model="ResearchPack",
        format_notes=(
            "P3-T1: Research depth routing metadata (research_depth_routing, research_mode) "
            "is attached to the pack output for pipeline traceability. "
            "Structured findings/claims/flag blocks reference source_ids from the "
            "prompt-provided source catalog; sources are pre-sorted by quality_rank "
            "and carry authority/directness/freshness signals (Task 16)."
        ),
        required_fields=(),
        expected_sections=(
            "findings",
            "claims",
            "counterpoints",
            "uncertainty_flags",
            "assets_needed",
            "research_stop_reason",
            "research_depth_routing",
            "research_mode",
        ),
        failure_mode="tolerant",
    ),
    "build_argument_map": ContentGenStageContract(
        stage_name="build_argument_map",
        prompt_module="prompts/argument_map.py",
        contract_version="1.1.0",
        parser_location="agents/argument_map.py::_parse_argument_map",
        output_model="ArgumentMap",
        format_notes=(
            "P3-T2: This stage produces the single unified thesis artifact that replaces "
            "the previous separate angle-selection + argument-design flow. "
            "Scalar thesis fields (thesis, audience_belief_to_challenge, core_mechanism) "
            "carry the chosen angle and core claim. Repeated '---' blocks for proof_anchors, "
            "counterarguments, safe_claims, unsafe_claims, and beat_claim_plan provide "
            "the full support structure. The beat_claim_plan is the narrative contract "
            "that seeds scripting directly. Claim ledger linkage is via proof_id cross-reference."
        ),
        required_fields=(
            "thesis",
            "audience_belief_to_challenge",
            "core_mechanism",
            "proof_anchors",
        ),
        expected_sections=(
            "counterarguments",
            "safe_claims",
            "unsafe_claims",
            "beat_claim_plan",
            "what_this_contributes",
            "genericity_flags",
            "differentiation_strategy",
        ),
        failure_mode="fail_fast",
    ),
    "run_scripting": ContentGenStageContract(
        stage_name="run_scripting",
        prompt_module="prompts/scripting.py",
        contract_version="1.2.0",
        parser_location="agents/scripting.py::_STEP_HANDLERS and _extract_* helpers",
        output_model="ScriptingContext",
        format_notes=(
            "Ten step-specific text contracts; step 4 accepts either legacy "
            "'beat: intent' lines or grounded beat blocks with claim/proof ids, "
            "and later drafting steps accept freeform script bodies."
        ),
        required_fields=(
            "Step 1: Topic/Outcome/Audience",
            "Step 2: Angle/Content Type/Core Tension",
            "Step 3: Chosen Structure/Beat List",
            "Step 4: at least one beat intent",
            "Step 5: Best Hook",
            "Step 6: non-empty draft",
        ),
        expected_sections=(
            "Step 7: Revised Script",
            "Step 8: Tightened Script",
            "Step 9: optional visual note annotations",
            "Step 10: QC checks, Weakest parts, Final Script",
        ),
        failure_mode="fail_fast",
    ),
    "visual_translation": ContentGenStageContract(
        stage_name="visual_translation",
        prompt_module="prompts/visual.py",
        contract_version="1.0.0",
        parser_location="agents/visual.py::_parse_beat_visuals",
        output_model="VisualPlanOutput",
        format_notes="Repeated '---' beat blocks plus a trailing visual_refresh_check field.",
        required_fields=("beat", "visual", "visual_refresh_check"),
        expected_sections=(
            "spoken_line",
            "shot_type",
            "a_roll",
            "b_roll",
            "on_screen_text",
            "overlay_or_graphic",
            "prop_or_asset",
            "transition",
            "retention_function",
        ),
        failure_mode="fail_fast",
    ),
    "production_brief": ContentGenStageContract(
        stage_name="production_brief",
        prompt_module="prompts/production.py",
        contract_version="1.0.0",
        parser_location="agents/production.py::_parse_production_brief",
        output_model="ProductionBrief",
        format_notes="Scalar checklist fields plus '-' list sections for production prep.",
        required_fields=(),
        expected_sections=(
            "location",
            "setup",
            "wardrobe",
            "props",
            "assets_to_prepare",
            "audio_checks",
            "battery_checks",
            "storage_checks",
            "pickup_lines_to_capture",
            "backup_plan",
        ),
        failure_mode="tolerant",
    ),
    "packaging": ContentGenStageContract(
        stage_name="packaging",
        prompt_module="prompts/packaging.py",
        contract_version="1.1.0",
        parser_location="agents/packaging.py::_parse_platform_packages",
        output_model="PackagingOutput",
        format_notes="P4-T1: Early packaging signals (target_channel, content_type_hint) added to PlatformPackage. PackagingOutput now includes draft_hooks and early_packaging_signals for channel-aware co-design.",
        required_fields=("platform", "primary_hook", "caption"),
        expected_sections=(
            "alternate_hooks",
            "cover_text",
            "keywords",
            "hashtags",
            "pinned_comment",
            "cta",
            "version_notes",
            "target_channel",
            "content_type_hint",
        ),
        failure_mode="fail_fast",
    ),
    "human_qc": ContentGenStageContract(
        stage_name="human_qc",
        prompt_module="prompts/qc.py",
        contract_version="1.2.0",
        parser_location="agents/qc.py::_parse_qc_gate",
        output_model="HumanQCGate",
        format_notes="Named issue buckets with '-' lists; AI review never sets approval to true.",
        required_fields=("hook_strength",),
        expected_sections=(
            "clarity_issues",
            "factual_issues",
            "visual_issues",
            "audio_issues",
            "caption_issues",
            "unsupported_claims",
            "risky_claims",
            "required_fact_checks",
            "must_fix_items",
        ),
        failure_mode="human_gated",
    ),
    "publish_queue": ContentGenStageContract(
        stage_name="publish_queue",
        prompt_module="prompts/publish.py",
        contract_version="1.0.0",
        parser_location="agents/publish.py::PublishAgent.schedule",
        output_model="PublishItem",
        format_notes="Two scalar fields parsed from each platform-specific publish response.",
        required_fields=(),
        expected_sections=("publish_datetime", "first_30_minute_engagement_plan"),
        failure_mode="tolerant",
    ),
    "performance_analysis": ContentGenStageContract(
        stage_name="performance_analysis",
        prompt_module="prompts/performance.py",
        contract_version="1.1.0",
        parser_location="agents/performance.py::_parse_performance",
        output_model="PerformanceAnalysis",
        format_notes="Named diagnostic sections with '-' lists plus scalar summary fields.",
        required_fields=(),
        expected_sections=(
            "what_worked",
            "what_failed",
            "audience_signals",
            "dropoff_hypotheses",
            "hook_diagnosis",
            "lesson",
            "next_test",
            "follow_up_ideas",
            "backlog_updates",
        ),
        failure_mode="tolerant",
    ),
}


class CoreInputs(BaseModel):
    """Step 1 output: topic, outcome, audience."""

    topic: str
    outcome: str
    audience: str


class AngleDefinition(BaseModel):
    """Step 2 output: angle, content type, core tension."""

    angle: str
    content_type: str
    core_tension: str
    why_it_works: str = ""


class EarlyPackagingSignals(BaseModel):
    """P4-T1: Channel-aware packaging signals captured early to co-design draft with packaging.

    These signals are captured from the angle/channel selection stage and inform
    the packaging generator so hook choices and draft structure can align with
    channel expectations from the start.
    """

    target_channel: str = Field(
        default="",
        description="Primary distribution channel hint (e.g., 'shorts', 'reels', 'feed', 'twitter')",
    )
    content_type: str = Field(
        default="",
        description="Content type hint (e.g., 'contrarian', 'tutorial', 'story', 'insight')",
    )
    tone_hint: str = Field(
        default="",
        description="Tone guidance for packaging (e.g., 'conversational', 'urgent', 'story-driven')",
    )
    format_constraints: list[str] = Field(
        default_factory=list,
        description="Format constraints from channel (e.g., '60s max', 'vertical only', 'no product')",
    )
    cta_hint: str = Field(
        default="",
        description="Call-to-action hint derived from angle or channel best practices",
    )


class DerivativeOpportunity(BaseModel):
    """P4-T2: A reuse or derivative opportunity derived from an approved draft."""

    idea_id: str = Field(default_factory=lambda: f"deriv_{uuid4().hex[:8]}")
    source_idea_id: str = Field(
        default="",
        description="The idea_id of the approved argument this derives from",
    )
    derivative_type: Literal[
        "alternate_hook",
        "quote_card",
        "thread_variant",
        "newsletter_snippet",
        "follow_up_short",
        "clip_reel",
        "cta_variation",
        "audience_variant",
        "platform_adaptation",
    ] = ""
    title: str = ""
    summary: str = Field(
        default="",
        description="Brief description of the derivative opportunity",
    )
    target_channel: str = Field(
        default="",
        description="Recommended channel/platform for this derivative",
    )
    reuse_value: str = Field(
        default="",
        description="Why this derivative is worth producing (e.g., 'high-performing format', 'new audience segment')",
    )
    proof_points_to_reuse: list[str] = Field(
        default_factory=list,
        description="Proof anchor IDs from the source argument that apply here",
    )
    status: Literal["pending", "planned", "in_production", "published"] = "pending"
    created_at: str = ""
    notes: str = ""


class ScriptStructure(BaseModel):
    """Step 3 output: chosen structure and beat list."""

    chosen_structure: str
    why_it_fits: str = ""
    beat_list: list[str]


class BeatIntent(BaseModel):
    """Single beat with name and intent."""

    beat_id: str = ""
    beat_name: str
    intent: str
    claim_ids: list[str] = Field(default_factory=list)
    proof_anchor_ids: list[str] = Field(default_factory=list)
    counterargument_ids: list[str] = Field(default_factory=list)
    transition_note: str = ""


class BeatIntentMap(BaseModel):
    """Step 4 output: all beat intents."""

    beats: list[BeatIntent]


class HookSet(BaseModel):
    """Step 5 output: generated hooks with best selection."""

    hooks: list[str]
    best_hook: str
    best_hook_reason: str


class ScriptVersion(BaseModel):
    """Script text with metadata (used for draft, retention, tightened)."""

    content: str
    word_count: int


class VisualNote(BaseModel):
    """Step 9 output: visual annotation for a beat."""

    beat_name: str
    line: str
    note: str | None = None


class QCCheck(BaseModel):
    """Single QC checklist item."""

    item: str
    passed: bool


class QCResult(BaseModel):
    """Step 10 output: QC review."""

    checks: list[QCCheck]
    weakest_parts: list[str]
    final_script: str


class ScriptingLLMCallTrace(BaseModel):
    """Trace for a single LLM call inside a scripting step."""

    call_index: int
    temperature: float
    system_prompt: str
    user_prompt: str
    raw_response: str
    provider: str
    model: str
    transport: str
    latency_ms: int = 0
    prompt_tokens: int = 0
    completion_tokens: int = 0
    finish_reason: str | None = None


class ScriptingStepTrace(BaseModel):
    """Trace record for one completed scripting step."""

    step_index: int
    step_name: str
    step_label: str
    iteration: int = 1
    llm_calls: list[ScriptingLLMCallTrace] = Field(default_factory=list)
    parsed_output: Any = None


class ScriptingContext(BaseModel):
    """Accumulated state passed through the scripting pipeline.

    Each step enriches the context with its output. Steps can be
    run independently by loading a previously saved context.
    """

    raw_idea: str = ""
    research_context: str = ""
    tone: str = ""
    cta: str = ""
    argument_map: ArgumentMap | None = None
    core_inputs: CoreInputs | None = None
    angle: AngleDefinition | None = None
    structure: ScriptStructure | None = None
    beat_intents: BeatIntentMap | None = None
    hooks: HookSet | None = None
    draft: ScriptVersion | None = None
    retention_revised: ScriptVersion | None = None
    tightened: ScriptVersion | None = None
    annotated_script: ScriptVersion | None = None
    visual_notes: list[VisualNote] | None = None
    qc: QCResult | None = None
    step_traces: list[ScriptingStepTrace] = Field(default_factory=list)
    claim_ledger: ClaimTraceLedger | None = None


class SavedScriptRun(BaseModel):
    """Metadata for a persisted scripting run."""

    run_id: str
    saved_at: str
    raw_idea: str = ""
    word_count: int = 0
    script_path: str
    context_path: str
    result_path: str | None = None
    execution_mode: Literal["single_pass", "iterative"] = "single_pass"
    iterations: ScriptingIterations | None = None


SCRIPTING_STEPS: list[str] = [
    "define_core_inputs",
    "define_angle",
    "choose_structure",
    "define_beat_intents",
    "generate_hooks",
    "draft_script",
    "add_retention_mechanics",
    "tighten",
    "add_visual_notes",
    "run_qc",
]

SCRIPTING_STEP_LABELS: dict[str, str] = {
    "define_core_inputs": "Defining core inputs",
    "define_angle": "Defining angle",
    "choose_structure": "Choosing structure",
    "define_beat_intents": "Defining beat intents",
    "generate_hooks": "Generating hooks",
    "draft_script": "Drafting script",
    "add_retention_mechanics": "Adding retention mechanics",
    "tighten": "Tightening script",
    "add_visual_notes": "Adding visual notes",
    "run_qc": "Running QC",
}


# ---------------------------------------------------------------------------
# Claim Traceability Ledger (Task 17)
# ---------------------------------------------------------------------------


class ClaimTraceStatus(StrEnum):
    """Status of a claim as it travels through the pipeline."""

    SUPPORTED = "supported"  # Has proof anchor backing
    UNSUPPORTED = "unsupported"  # No proof anchor found
    WEAKENED = "weakened"  # Originally supported but proof was dropped
    INTRODUCED_LATE = "introduced_late"  # Added in scripting without prior backing
    DROPPED = "dropped"  # Was in argument map but not in final script
    UNKNOWN = "unknown"  # Cannot be determined


class ClaimTraceStage(StrEnum):
    """Pipeline stage where a claim first appeared."""

    RESEARCH_PACK = "research_pack"  # ResearchClaim in research pack
    ARGUMENT_MAP = "argument_map"  # ArgumentClaim in argument map
    BEAT_PLAN = "beat_plan"  # Claim referenced in beat_claim_plan
    SCRIPTING = "scripting"  # First appeared in script drafting


class ScriptClaimStatement(BaseModel):
    """A single claim/statement made in the final script with traceability."""

    statement_id: str = Field(default_factory=lambda: f"stmt_{uuid4().hex[:8]}")
    text: str = ""  # The actual claim text from the script
    beat_name: str = ""  # Which beat this belongs to
    claim_ids: list[str] = Field(default_factory=list)  # Research claim IDs this traces back to
    proof_anchor_ids: list[str] = Field(default_factory=list)  # Proof anchors used
    status: ClaimTraceStatus = ClaimTraceStatus.UNKNOWN
    status_reason: str = ""  # Why this status was assigned
    source_snippet: str = ""  # Exact text that supports this in research


class ClaimTraceEntry(BaseModel):
    """Single claim's lineage entry in the traceability ledger."""

    claim_id: str = ""  # The canonical claim identifier
    claim_text: str = ""  # The claim text at research stage
    first_seen_stage: ClaimTraceStage = ClaimTraceStage.RESEARCH_PACK
    # Research pack origin
    research_claim_type: ResearchClaimType | None = None
    source_ids: list[str] = Field(default_factory=list)
    # Argument map state
    present_in_argument_map: bool = False
    argument_claim_id: str = ""  # claim_id in ArgumentClaim if present
    supporting_proof_ids: list[str] = Field(default_factory=list)
    # Beat plan state
    present_in_beat_plan: bool = False
    beat_ids: list[str] = Field(default_factory=list)
    # Script state
    present_in_script: bool = False
    script_statement_ids: list[str] = Field(default_factory=list)  # References to ScriptClaimStatement
    # Status tracking
    status: ClaimTraceStatus = ClaimTraceStatus.UNKNOWN
    status_changed_at: str = ""  # ISO timestamp of last status change
    notes: str = ""


class ClaimTraceLedger(BaseModel):
    """Ledger tracking all claims and their lineage through the pipeline.

    Machine-readable claim traceability that answers "where did this claim come from?"
    for any major script assertion.
    """

    entries: list[ClaimTraceEntry] = Field(default_factory=list)
    script_claims: list[ScriptClaimStatement] = Field(default_factory=list)
    unsupported_script_claims: list[str] = Field(default_factory=list)  # statement_ids of unsupported claims
    introduced_late_claims: list[str] = Field(default_factory=list)  # claim_ids introduced in scripting
    dropped_claims: list[str] = Field(default_factory=list)  # claim_ids present in argument map but not script
    weakened_claims: list[str] = Field(default_factory=list)  # claim_ids that lost proof support

    def get_claim(self, claim_id: str) -> ClaimTraceEntry | None:
        """Get trace entry by claim_id."""
        return next((e for e in self.entries if e.claim_id == claim_id), None)

    def get_script_claim(self, statement_id: str) -> ScriptClaimStatement | None:
        """Get script claim statement by statement_id."""
        return next((s for s in self.script_claims if s.statement_id == statement_id), None)

    def claims_needing_attention(self) -> list[ClaimTraceEntry]:
        """Return all claims with problematic statuses."""
        return [
            e
            for e in self.entries
            if e.status
            in (
                ClaimTraceStatus.UNSUPPORTED,
                ClaimTraceStatus.INTRODUCED_LATE,
                ClaimTraceStatus.WEAKENED,
                ClaimTraceStatus.DROPPED,
            )
        ]

    def unsupported_claims_for_qc(self) -> list[str]:
        """Return human-readable list of unsupported claims for QC review."""
        result: list[str] = []
        for entry in self.entries:
            if entry.status == ClaimTraceStatus.INTRODUCED_LATE:
                result.append(f"LATE: {entry.claim_text}")
            elif entry.status == ClaimTraceStatus.UNSUPPORTED:
                result.append(f"UNSUPPORTED: {entry.claim_text}")
            elif entry.status == ClaimTraceStatus.WEAKENED:
                result.append(f"WEAKENED: {entry.claim_text}")
            elif entry.status == ClaimTraceStatus.DROPPED:
                result.append(f"DROPPED: {entry.claim_text}")
        return result

    def to_summary(self) -> str:
        """Generate human-readable traceability summary."""
        lines = ["Claim Traceability Summary:"]
        lines.append(f"  Total tracked claims: {len(self.entries)}")
        lines.append(f"  Script statements: {len(self.script_claims)}")
        if self.unsupported_script_claims:
            lines.append(f"  Unsupported in script: {len(self.unsupported_script_claims)}")
        if self.introduced_late_claims:
            lines.append(f"  Introduced late: {len(self.introduced_late_claims)}")
        if self.dropped_claims:
            lines.append(f"  Dropped from argument map: {len(self.dropped_claims)}")
        if self.weakened_claims:
            lines.append(f"  Weakened (lost proof): {len(self.weakened_claims)}")
        return "\n".join(lines)


def _build_claim_ledger_from_research_pack(
    research_pack: ResearchPack | None,
) -> ClaimTraceLedger:
    """Initialize ledger entries from research pack claims."""
    if research_pack is None:
        return ClaimTraceLedger()

    ledger = ClaimTraceLedger()
    for claim in research_pack.claims:
        entry = ClaimTraceEntry(
            claim_id=claim.claim_id,
            claim_text=claim.claim,
            first_seen_stage=ClaimTraceStage.RESEARCH_PACK,
            research_claim_type=claim.claim_type,
            source_ids=list(claim.source_ids),
            status=ClaimTraceStatus.SUPPORTED if claim.source_ids else ClaimTraceStatus.UNSUPPORTED,
        )
        ledger.entries.append(entry)

    return ledger


def _update_ledger_from_argument_map(
    ledger: ClaimTraceLedger,
    argument_map: ArgumentMap | None,
) -> ClaimTraceLedger:
    """Update ledger entries with argument map state."""
    if argument_map is None:
        return ledger

    # Index existing entries by claim text for matching
    claim_text_to_id: dict[str, str] = {e.claim_text: e.claim_id for e in ledger.entries}

    for arg_claim in argument_map.safe_claims:
        if arg_claim.claim in claim_text_to_id:
            # Update existing entry
            entry = ledger.get_claim(claim_text_to_id[arg_claim.claim])
            if entry:
                entry.present_in_argument_map = True
                entry.argument_claim_id = arg_claim.claim_id
                entry.supporting_proof_ids = list(arg_claim.supporting_proof_ids)
                # Check if still has proof
                if not arg_claim.supporting_proof_ids:
                    entry.status = ClaimTraceStatus.UNSUPPORTED
        else:
            # New claim first seen in argument map
            entry = ClaimTraceEntry(
                claim_id=arg_claim.claim_id,
                claim_text=arg_claim.claim,
                first_seen_stage=ClaimTraceStage.ARGUMENT_MAP,
                present_in_argument_map=True,
                argument_claim_id=arg_claim.claim_id,
                supporting_proof_ids=list(arg_claim.supporting_proof_ids),
                status=ClaimTraceStatus.SUPPORTED if arg_claim.supporting_proof_ids else ClaimTraceStatus.UNSUPPORTED,
            )
            ledger.entries.append(entry)
            claim_text_to_id[arg_claim.claim] = arg_claim.claim_id

    # Process beat_claim_plan
    for beat in argument_map.beat_claim_plan:
        for claim_id in beat.claim_ids:
            entry = ledger.get_claim(claim_id)
            if entry:
                entry.present_in_beat_plan = True
                if beat.beat_id not in entry.beat_ids:
                    entry.beat_ids.append(beat.beat_id)
            else:
                # Claim referenced in beat plan but not in our ledger - should not happen
                # but handle gracefully by creating entry
                entry = ClaimTraceEntry(
                    claim_id=claim_id,
                    claim_text="",
                    first_seen_stage=ClaimTraceStage.BEAT_PLAN,
                    present_in_beat_plan=True,
                    beat_ids=[beat.beat_id],
                    status=ClaimTraceStatus.UNKNOWN,
                )
                ledger.entries.append(entry)

    return ledger


# ---------------------------------------------------------------------------
# Pipeline stage 0: Persistent strategy memory
# ---------------------------------------------------------------------------


class AudienceSegment(BaseModel):
    """Target audience segment."""

    name: str
    description: str
    pain_points: list[str] = Field(default_factory=list)


class ContentExample(BaseModel):
    """Past content example (winner or loser)."""

    title: str
    why_it_worked_or_failed: str = ""
    metrics_snapshot: dict[str, Any] = Field(default_factory=dict)


class ExpertFramework(BaseModel):
    """Reusable lens or framework that signals creator expertise."""

    name: str = ""
    summary: str = ""


class ContrarianBelief(BaseModel):
    """A viewpoint that challenges common but weak industry advice."""

    belief: str = ""
    rationale: str = ""


class ProofRule(BaseModel):
    """A durable rule for how evidence should be used in content."""

    rule: str = ""
    rationale: str = ""


# ---------------------------------------------------------------------------
# Task 20: Performance Learning (referenced by StrategyMemory)
# ---------------------------------------------------------------------------


class LearningDurability(StrEnum):
    """Whether a learning is a durable default or a one-run observation."""

    DURABLE = "durable"  # Should influence future strategy by default
    EXPERIMENTAL = "experimental"  # One-run observation, operator-gated
    REJECTED = "rejected"  # Explicitly failed approach, not worth retrying


class LearningCategory(StrEnum):
    """Category of performance learning."""

    HOOK = "hook"  # Hook/opening performance
    FRAME = "frame"  # Content framing or angle
    AUDIENCE = "audience"  # Audience resonance signals
    PROOF = "proof"  # Evidence or proof requirements
    FORMAT = "format"  # Content format or structure
    PACING = "pacing"  # Pacing or retention
    CTA = "cta"  # Call-to-action effectiveness
    PACKAGING = "packaging"  # Thumbnail, title, caption
    PLATFORM = "platform"  # Platform-specific lesson


class PerformanceLearning(BaseModel):
    """A single structured learning extracted from performance analysis.

    Transforms raw performance observations into actionable guidance
    that can be stored in strategy memory and used by downstream stages.
    """

    learning_id: str = Field(default_factory=lambda: f"learn_{uuid4().hex[:8]}")
    category: LearningCategory = LearningCategory.HOOK
    durability: LearningDurability = LearningDurability.EXPERIMENTAL
    # What was observed
    observation: str = ""
    # Why it matters
    implication: str = ""
    # What to do differently
    guidance: str = ""
    # Which video(s) this came from
    source_video_ids: list[str] = Field(default_factory=list)
    # Original performance metrics that prompted this learning
    source_metrics: dict[str, Any] = Field(default_factory=dict)
    # Whether this learning has been reviewed by an operator
    operator_reviewed: bool = False
    # Whether this learning is currently active (vs. superseded or rejected)
    is_active: bool = True
    # What superseded this learning, if any
    superseded_by: str = ""
    # When this learning was created
    created_at: str = ""
    # When this learning was last updated
    updated_at: str = ""
    # Which platform this applies to (empty = cross-platform)
    platform: str = ""


class PerformanceLearningSet(BaseModel):
    """A set of performance learnings from a single analysis run.

    Produced immediately after PerformanceAnalysis and before any
    persistence decision is made.
    """

    video_id: str = ""
    learnings: list[PerformanceLearning] = Field(default_factory=list)
    # The source analysis this was derived from
    source_analysis: PerformanceAnalysis | None = None


class StrategyPerformanceGuidance(BaseModel):
    """Performance-derived guidance stored in strategy memory.

    This is the durable, operator-reviewed subset of learnings that
    influences future content strategy. Stored in StrategyMemory.
    """

    # Winning hook patterns
    winning_hooks: list[str] = Field(default_factory=list)
    # Failed hook patterns to avoid
    failed_hooks: list[str] = Field(default_factory=list)
    # Winning framing patterns
    winning_framings: list[str] = Field(default_factory=list)
    # Failed framing patterns
    failed_framings: list[str] = Field(default_factory=list)
    # Audience resonance notes (what resonated and why)
    audience_resonance_notes: list[str] = Field(default_factory=list)
    # Updated proof expectations (what level of evidence performed)
    proof_expectations: list[str] = Field(default_factory=list)
    # A/B test results (what to test next)
    pending_tests: list[str] = Field(default_factory=list)
    # Platform-specific learnings, keyed by platform
    platform_guidance: dict[str, list[str]] = Field(default_factory=dict)


class StrategyMemory(BaseModel):
    """Persistent strategy memory (spec stage 0).

    Stored on disk and loaded at pipeline start to keep the AI
    consistent across runs.
    """

    niche: str = ""
    content_pillars: list[str] = Field(default_factory=list)
    audience_segments: list[AudienceSegment] = Field(default_factory=list)
    tone_rules: list[str] = Field(default_factory=list)
    offer_cta_rules: list[str] = Field(default_factory=list)
    platforms: list[str] = Field(default_factory=list)
    forbidden_claims: list[str] = Field(default_factory=list)
    proof_standards: list[str] = Field(default_factory=list)
    signature_frameworks: list[ExpertFramework] = Field(default_factory=list)
    contrarian_beliefs: list[ContrarianBelief] = Field(default_factory=list)
    proof_rules: list[ProofRule] = Field(default_factory=list)
    banned_tropes: list[str] = Field(default_factory=list)
    expertise_edge: str = ""
    past_winners: list[ContentExample] = Field(default_factory=list)
    past_losers: list[ContentExample] = Field(default_factory=list)
    # Task 20: Performance-derived guidance
    performance_guidance: StrategyPerformanceGuidance = Field(default_factory=StrategyPerformanceGuidance)

    @field_validator("signature_frameworks", mode="before")
    @classmethod
    def _coerce_signature_frameworks(cls, value: Any) -> Any:
        if not isinstance(value, list):
            return value
        return [
            item if not isinstance(item, str) else {"name": item}
            for item in value
        ]

    @field_validator("contrarian_beliefs", mode="before")
    @classmethod
    def _coerce_contrarian_beliefs(cls, value: Any) -> Any:
        if not isinstance(value, list):
            return value
        return [
            item if not isinstance(item, str) else {"belief": item}
            for item in value
        ]

    @field_validator("proof_rules", mode="before")
    @classmethod
    def _coerce_proof_rules(cls, value: Any) -> Any:
        if not isinstance(value, list):
            return value
        return [
            item if not isinstance(item, str) else {"rule": item}
            for item in value
        ]


# ---------------------------------------------------------------------------
# Pipeline stage 1: Opportunity planning
# ---------------------------------------------------------------------------


class OpportunityBrief(BaseModel):
    """Structured planning artifact (stage 1).

    Turns a raw theme into a focused editorial contract that guides
    backlog generation and later scoring.
    """

    brief_id: str = Field(default_factory=lambda: f"brief_{uuid4().hex[:8]}")
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
    # P3-T2: Version tracking
    version: int = 1
    # P3-T2: Source tracking — original generated vs operator-revised
    is_generated: bool = True  # True = AI-generated, False = operator-created or heavily edited
    # P3-T2: Revision state
    is_approved: bool = False
    # P3-T2: Revision history
    revision_history: list[str] = Field(
        default_factory=list,
        description="Change log entries describing what was revised",
    )


# ---------------------------------------------------------------------------
# Phase 01 - Run Constraints (per-run variables)
# ---------------------------------------------------------------------------


class EffortTier(StrEnum):
    """Effort/complexity tier for a content run.

    This determines how much iteration and refinement the pipeline applies.
    """

    QUICK = "quick"  # Minimal iteration, fast turnaround
    STANDARD = "standard"  # Normal iteration, standard quality bar
    DEEP = "deep"  # Full iteration, highest quality bar


# P2-T3: Content-type branching profiles
class ContentTypeProfile(BaseModel):
    """Depth profile for one content type.

    Determines how much research, drafting, production, and packaging
    depth is required. Each stage respects the profile's skip conditions.
    """

    profile_key: str = ""  # e.g., "short_form", "newsletter", "article"
    research_depth: Literal["none", "light", "standard", "deep"] = "standard"
    drafting_depth: Literal["outline", "draft", "polished"] = "draft"
    production_depth: Literal["minimal", "standard", "premium"] = "standard"
    packaging_depth: Literal["minimal", "standard", "full"] = "standard"
    skip_stages: list[str] = Field(
        default_factory=list,
        description="Stage names to skip for this content type",
    )
    required_artifacts: list[str] = Field(
        default_factory=list,
        description="Stage outputs that must be present for this type",
    )


# P2-T3: Known content type profiles
CONTENT_TYPE_PROFILES: dict[str, ContentTypeProfile] = {
    "short_form_video": ContentTypeProfile(
        profile_key="short_form_video",
        research_depth="standard",
        drafting_depth="polished",
        production_depth="standard",
        packaging_depth="standard",
        skip_stages=[],
        required_artifacts=["research_pack", "script", "visual_plan", "packaging"],
    ),
    "newsletter": ContentTypeProfile(
        profile_key="newsletter",
        research_depth="light",
        drafting_depth="draft",
        production_depth="minimal",
        packaging_depth="minimal",
        skip_stages=["visual_translation", "production_brief"],
        required_artifacts=["research_pack", "script", "packaging"],
    ),
    "article": ContentTypeProfile(
        profile_key="article",
        research_depth="deep",
        drafting_depth="polished",
        production_depth="minimal",
        packaging_depth="minimal",
        skip_stages=["visual_translation", "production_brief"],
        required_artifacts=["research_pack", "argument_map", "script", "packaging"],
    ),
    "webinar": ContentTypeProfile(
        profile_key="webinar",
        research_depth="deep",
        drafting_depth="polished",
        production_depth="premium",
        packaging_depth="full",
        skip_stages=[],
        required_artifacts=["research_pack", "argument_map", "script", "visual_plan", "production_brief", "packaging"],
    ),
    "launch_asset": ContentTypeProfile(
        profile_key="launch_asset",
        research_depth="standard",
        drafting_depth="polished",
        production_depth="premium",
        packaging_depth="full",
        skip_stages=[],
        required_artifacts=["research_pack", "angle", "script", "visual_plan", "production_brief", "packaging"],
    ),
    "thread": ContentTypeProfile(
        profile_key="thread",
        research_depth="light",
        drafting_depth="draft",
        production_depth="minimal",
        packaging_depth="minimal",
        skip_stages=["visual_translation", "production_brief"],
        required_artifacts=["research_pack", "script", "packaging"],
    ),
    "carousel": ContentTypeProfile(
        profile_key="carousel",
        research_depth="standard",
        drafting_depth="polished",
        production_depth="standard",
        packaging_depth="standard",
        skip_stages=["production_brief"],
        required_artifacts=["research_pack", "script", "visual_plan", "packaging"],
    ),
    "短视频": ContentTypeProfile(
        profile_key="短视频",
        research_depth="standard",
        drafting_depth="polished",
        production_depth="standard",
        packaging_depth="standard",
        skip_stages=[],
        required_artifacts=["research_pack", "script", "visual_plan", "packaging"],
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

    # Content type for this run (e.g., "short-form video", "carousel", "thread")
    content_type: str = Field(
        default="",
        description="The content format for this run.",
    )
    # Effort/complexity tier
    effort_tier: EffortTier = Field(
        default=EffortTier.STANDARD,
        description="Effort tier determining iteration depth and SLA.",
    )
    # Who owns this run (role or name)
    owner: str = Field(
        default="",
        description="Who is responsible for this content run.",
    )
    # Channel or platform goal for this run
    channel_goal: str = Field(
        default="",
        description="Primary channel or distribution goal for this content.",
    )
    # Success target for this specific run
    success_target: str = Field(
        default="",
        description="What success looks like for this content cycle.",
    )
    # Target platform(s) for this run (overrides strategy default)
    target_platforms: list[str] = Field(
        default_factory=list,
        description="Specific platforms to optimize for (empty = use strategy defaults).",
    )
    # Whether to use iterative drafting (for deep tier)
    use_iterative_loop: bool = Field(
        default=True,
        description="Whether to enable iterative drafting with quality evaluation.",
    )
    # Maximum iterations allowed (None = use config default)
    max_iterations: int | None = Field(
        default=None,
        description="Override for max iterations (None = use config default).",
    )


# ---------------------------------------------------------------------------
# Pipeline stage 2: Backlog builder
# ---------------------------------------------------------------------------


class IdeaCoreFields(BaseModel):
    """Identity and editorial framing for one backlog item."""

    category: Literal["", "trend-responsive", "evergreen", "authority-building"] = ""
    title: str = ""
    one_line_summary: str = ""
    raw_idea: str = ""
    constraints: str = ""
    source_theme: str = ""
    why_now: str = ""


class AudienceProblemFitFields(BaseModel):
    """Who the item targets and what tension it resolves."""

    audience: str = ""
    persona_detail: str = ""
    problem: str = ""
    emotional_driver: str = ""
    urgency_level: Literal["", "low", "medium", "high"] = ""


class ContentExecutionFields(BaseModel):
    """Fields that make the idea directly producible."""

    content_type: str = ""
    format_duration: str = ""
    hook: str = ""
    key_message: str = ""
    call_to_action: str = ""


class ValidationLayerFields(BaseModel):
    """Signals that determine whether the idea is credible and differentiated."""

    evidence: str = ""
    proof_gap_note: str = ""
    expertise_reason: str = ""
    genericity_risk: str = ""
    source: str = ""


class PrioritizationFields(BaseModel):
    """Selection and queueing metadata for backlog operations."""

    risk_level: Literal["low", "medium", "high"] = "medium"
    priority_score: float = 0.0
    impact_score: int | None = Field(default=None, ge=1, le=5)
    urgency_score: int | None = Field(default=None, ge=1, le=5)
    evidence_score: int | None = Field(default=None, ge=1, le=5)
    conversion_score: int | None = Field(default=None, ge=1, le=5)
    production_effort: int | None = Field(default=None, ge=1, le=5)
    latest_score: int | None = None
    latest_recommendation: Literal["", "produce_now", "hold", "kill"] = ""
    selection_reasoning: str = ""
    status: Literal["captured", "backlog", "selected", "archived"] = "backlog"
    production_status: Literal["idle", "in_production", "ready_to_publish"] = "idle"


class BacklogItem(
    IdeaCoreFields,
    AudienceProblemFitFields,
    ContentExecutionFields,
    ValidationLayerFields,
    PrioritizationFields,
):
    """Single backlog idea with legacy field compatibility."""

    idea_id: str = Field(default_factory=lambda: uuid4().hex[:8])
    source_pipeline_id: str = ""
    created_at: str = ""
    updated_at: str = ""
    last_scored_at: str = ""
    # P2-T1: Reference back to the opportunity brief that generated this idea
    opportunity_brief_id: str = Field(
        default="",
        description="ID of the OpportunityBrief that this idea traces back to",
    )

    @model_validator(mode="before")
    @classmethod
    def _normalize_legacy_fields(cls, raw: Any) -> Any:
        if not isinstance(raw, dict):
            return raw

        data = dict(raw)
        # Handle legacy field names (map to current canonical names)
        if data.get("idea") and "title" not in data:
            data["title"] = str(data["idea"])
        if data.get("potential_hook") and "hook" not in data:
            data["hook"] = str(data["potential_hook"])

        legacy_status = str(data.get("status") or "").strip()
        if not data.get("production_status"):
            if legacy_status == "in_production":
                data["production_status"] = "in_production"
            elif legacy_status == "published":
                data["production_status"] = "ready_to_publish"
        if legacy_status in {"runner_up", "in_production", "published"}:
            data["status"] = "backlog"

        component_keys = (
            "impact_score",
            "urgency_score",
            "evidence_score",
            "conversion_score",
            "production_effort",
        )
        if not data.get("priority_score") and all(data.get(key) is not None for key in component_keys):
            effort_score = max(1, min(5, 6 - int(data["production_effort"])))
            weighted = (
                int(data["impact_score"]) * 0.30
                + int(data["urgency_score"]) * 0.20
                + int(data["evidence_score"]) * 0.20
                + int(data["conversion_score"]) * 0.20
                + effort_score * 0.10
            )
            data["priority_score"] = round((weighted / 5) * 100, 1)

        return data

    @model_validator(mode="after")
    def _sync_legacy_fields(self) -> BacklogItem:
        canonical_title = self.title.strip() or self.one_line_summary.strip()
        canonical_summary = self.one_line_summary.strip() or canonical_title
        canonical_hook = self.hook.strip()

        self.title = canonical_title
        self.one_line_summary = canonical_summary
        self.hook = canonical_hook
        if self.status == "captured" and self.title.strip():
            self.status = "backlog"
        if self.status == "backlog" and self.raw_idea.strip() and not self.title.strip():
            self.status = "captured"
        return self

    def __getattr__(self, name: str) -> str:
        if name == "idea":
            return self.title
        if name == "potential_hook":
            return self.hook
        raise AttributeError(f"'{type(self).__name__}' object has no attribute '{name}'")

    @computed_field(return_type=str)
    @property
    def idea(self) -> str:
        """Legacy serialized alias for title."""
        return self.title

    @computed_field(return_type=str)
    @property
    def potential_hook(self) -> str:
        """Legacy serialized alias for hook."""
        return self.hook

    def __setattr__(self, name: str, value: str) -> None:
        if name == "idea":
            object.__setattr__(self, "title", value)
            return
        if name == "potential_hook":
            object.__setattr__(self, "hook", value)
            return
        super().__setattr__(name, value)


class BacklogOutput(BaseModel):
    """Output of the backlog builder stage."""

    items: list[BacklogItem] = Field(default_factory=list)
    rejected_count: int = 0
    rejection_reasons: list[str] = Field(default_factory=list)
    is_degraded: bool = False
    degradation_reason: str = ""


# ---------------------------------------------------------------------------
# Pipeline stage 2: Idea scorer
# ---------------------------------------------------------------------------


class IdeaScores(BaseModel):
    """Scores for a single idea (spec stage 2)."""

    idea_id: str
    relevance: int = Field(default=0, ge=1, le=5)
    novelty: int = Field(default=0, ge=1, le=5)
    authority_fit: int = Field(default=0, ge=1, le=5)
    production_ease: int = Field(default=0, ge=1, le=5)
    evidence_strength: int = Field(default=0, ge=1, le=5)
    hook_strength: int = Field(default=0, ge=1, le=5)
    repurposing: int = Field(default=0, ge=1, le=5)
    opportunity_fit: int = Field(default=1, ge=1, le=5, description="How well this idea fits opportunity brief constraints")
    # P2-T2: Effort and ROI gates
    effort_tier: EffortTier = Field(
        default=EffortTier.STANDARD,
        description="Estimated effort/complexity tier for producing this idea",
    )
    expected_upside: int = Field(
        default=3,
        ge=1,
        le=5,
        description="Expected upside potential (1-5) — used for ROI gate",
    )
    kill_reason: str = Field(
        default="",
        description="Why this idea was recommended for kill (fast-fail rationale)",
    )
    total_score: int = 0
    recommendation: str = "hold"  # produce_now | hold | kill
    reason: str = ""
    opportunity_fit_reason: str = Field(
        default="",
        description="Brief explanation of how this idea satisfies the opportunity brief",
    )


class ScoringOutput(BaseModel):
    """Output of the idea scorer stage."""

    scores: list[IdeaScores] = Field(default_factory=list)
    produce_now: list[str] = Field(default_factory=list)  # idea_ids
    shortlist: list[str] = Field(default_factory=list)  # ranked idea_ids
    selected_idea_id: str = ""
    selection_reasoning: str = ""
    runner_up_idea_ids: list[str] = Field(default_factory=list)
    active_candidates: list[PipelineCandidate] = Field(default_factory=list)
    hold: list[str] = Field(default_factory=list)  # idea_ids
    killed: list[str] = Field(default_factory=list)  # idea_ids
    reuse_recommended: list[str] = Field(
        default_factory=list,
        description="idea_ids of hold ideas that are recommended for future reuse when conditions improve",
    )
    # P2-T2: Effort distribution summary across scored ideas
    effort_summary: dict[str, int] = Field(
        default_factory=dict,
        description="Count of ideas per effort tier: {'quick': N, 'standard': N, 'deep': N}",
    )
    # P2-T3: Content-type profile that applies to all ideas in this scoring run
    content_type_profile: str = Field(
        default="",
        description="Profile key (e.g., 'short_form_video') derived from RunConstraints.content_type",
    )
    is_degraded: bool = False
    degradation_reason: str = ""

    @model_validator(mode="after")
    def _populate_active_candidates(self) -> ScoringOutput:
        self.active_candidates = _derive_pipeline_candidates(
            selected_idea_id=self.selected_idea_id,
            shortlist=self.shortlist,
            runner_up_idea_ids=self.runner_up_idea_ids,
            existing_candidates=self.active_candidates,
            content_type_profile=self.content_type_profile,
        )
        if not self.runner_up_idea_ids:
            self.runner_up_idea_ids = [
                candidate.idea_id for candidate in self.active_candidates if candidate.role == "runner_up"
            ]
        if not self.selected_idea_id:
            primary = next(
                (candidate.idea_id for candidate in self.active_candidates if candidate.role == "primary"),
                "",
            )
            if primary:
                self.selected_idea_id = primary
        return self


class PipelineCandidate(BaseModel):
    """One active candidate lane in the small editorial queue."""

    idea_id: str
    role: Literal["primary", "runner_up"] = "primary"
    status: Literal["selected", "runner_up", "in_production", "published"] = "selected"
    # P2-T3: Content-type profile for this lane
    content_type_profile: str = Field(
        default="",
        description="Profile key for branching decisions in this lane",
    )


# ---------------------------------------------------------------------------
# Pipeline stage 3: Angle generator
# ---------------------------------------------------------------------------


class AngleOption(BaseModel):
    """Single editorial angle (spec stage 3)."""

    angle_id: str = Field(default_factory=lambda: uuid4().hex[:8])
    target_audience: str = ""
    viewer_problem: str = ""
    core_promise: str = ""
    primary_takeaway: str = ""
    lens: str = ""
    format: str = ""
    tone: str = ""
    cta: str = ""
    why_this_version_should_exist: str = ""
    # Task 19: Differentiation and genericity
    differentiation_summary: str = Field(
        default="",
        description="Why this angle is distinct from the baseline market framing for this topic",
    )
    genericity_risks: list[str] = Field(
        default_factory=list,
        description="Known failure modes: clichéd framing, interchangeable takeaways, generic advice",
    )
    market_framing_challenged: str = Field(
        default="",
        description="What common/repeated market framing this angle reframes or contradicts",
    )


class AngleOutput(BaseModel):
    """Output of the angle generator stage."""

    idea_id: str = ""
    angle_options: list[AngleOption] = Field(default_factory=list)
    selected_angle_id: str = ""
    selection_reasoning: str = ""


# ---------------------------------------------------------------------------
# Pipeline stage 4: Research pack builder
# ---------------------------------------------------------------------------


class ResearchConfidence(StrEnum):
    """Coarse confidence bucket for research evidence."""

    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    UNKNOWN = "unknown"


class ResearchFindingType(StrEnum):
    """Structured qualitative finding categories."""

    AUDIENCE_INSIGHT = "audience_insight"
    COMPETITOR_OBSERVATION = "competitor_observation"
    EXAMPLE = "example"
    CASE_STUDY = "case_study"
    GAP_TO_EXPLOIT = "gap_to_exploit"


class ResearchClaimType(StrEnum):
    """Structured claim categories for downstream scripting."""

    KEY_FACT = "key_fact"
    PROOF_POINT = "proof_point"


class ResearchFlagType(StrEnum):
    """Risk or uncertainty flag categories."""

    VERIFICATION_REQUIRED = "verification_required"
    UNSAFE_OR_UNCERTAIN = "unsafe_or_uncertain"


class ResearchSeverity(StrEnum):
    """Severity bucket for research risks."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class SourceAuthority(StrEnum):
    """Authority level of a source.

    - PRIMARY: Official docs, original research, government data, first-party reports
    - SECONDARY: News analysis, industry reports, expert commentary
    - TERTIARY: Summaries, aggregations, secondary references, social posts
    - UNKNOWN: Cannot be determined from available metadata
    """

    PRIMARY = "primary"
    SECONDARY = "secondary"
    TERTIARY = "tertiary"
    UNKNOWN = "unknown"


class EvidenceDirectness(StrEnum):
    """How directly the source supports a specific claim or finding.

    - DIRECT: Original data, first-hand accounts, official statements
    - INDIRECT: Analysis, interpretation, second-hand reporting
    - ANECDOTAL: Personal accounts, unsourced claims, general observations
    - UNKNOWN: Cannot be determined
    """

    DIRECT = "direct"
    INDIRECT = "indirect"
    ANECDOTAL = "anecdotal"
    UNKNOWN = "unknown"


class SourceFreshness(StrEnum):
    """Freshness of the source relative to current date.

    - CURRENT: Within last 6 months (highly relevant for fast-moving topics)
    - RECENT: Within last 2 years (standard relevance window)
    - STALE: Older than 2 years (may still be valuable for foundational facts)
    - UNKNOWN: No date information available
    """

    CURRENT = "current"
    RECENT = "recent"
    STALE = "stale"
    UNKNOWN = "unknown"


class RetrievalMode(StrEnum):
    """Retrieval strategy mode for the planner."""

    BASELINE = "baseline"  # Standard breadth: 6 families, balanced
    DEEP = "deep"  # Widen to cover gaps: additional queries per family
    TARGETED = "targeted"  # Narrow focus: specific evidence gaps
    CONTRARIAN = "contrarian"  # Emphasize counterevidence and pushback


class ResearchDepthTier(StrEnum):
    """Research depth investment level tied to upside and claim risk.

    P3-T1: Routes research time and validation depth to expected upside
    and fact risk of the idea instead of using one default level.
    """

    LIGHT = "light"  # Minimal search, fast turnaround — low-upside or low-risk ideas
    STANDARD = "standard"  # Normal search depth — medium-upside ideas
    DEEP = "deep"  # Expanded search, more sources — high-upside or high-risk ideas
    OVERRIDE = "override"  # Operator-specified depth, bypasses ROI routing


class ResearchDepthRouting(BaseModel):
    """P3-T1: Routing decision for research depth with traceability."""

    tier: ResearchDepthTier = Field(
        default=ResearchDepthTier.STANDARD,
        description="The depth tier assigned to this research run",
    )
    routing_basis: str = Field(
        default="",
        description="Why this tier was selected: 'effort_tier', 'expected_upside', 'claim_risk', 'operator_override'",
    )
    effort_tier_source: str = Field(
        default="",
        description="The EffortTier value from scoring that influenced routing",
    )
    expected_upside_source: int = Field(
        default=0,
        ge=0,
        le=5,
        description="The expected_upside score from scoring (0 means unknown/not yet scored)",
    )
    claim_risk_signals: list[str] = Field(
        default_factory=list,
        description="Identified risk signals that bumped tier: 'high_dispute', 'no_sources', 'weak_evidence', etc.",
    )
    operator_override: bool = Field(
        default=False,
        description="True when operator explicitly overrode the ROI-based routing",
    )
    override_reason: str = Field(
        default="",
        description="Operator's stated reason for override",
    )


# ---------------------------------------------------------------------------
# P3-T3: Early Fact-Risk And Uncertainty Gate
# ---------------------------------------------------------------------------


class ClaimStatus(StrEnum):
    """P3-T3: Classification of a claim's support status."""

    SUPPORTED = "supported"  # Has proof anchor backing from research
    WEAK = "weak"  # Has some evidence but not strong enough for confident delivery
    MISSING = "missing"  # Claim made but no supporting proof found
    DISPUTED = "disputed"  # Counterevidence or conflicting sources exist
    ACCEPTABLE_WITH_DISCLOSURE = "acceptable_with_disclosure"  # Known uncertainty but operator-approved


class FactRiskDecision(StrEnum):
    """P3-T3: Gate decision for an idea's path through the pipeline."""

    APPROVED = "approved"  # All critical claims supported, can proceed to drafting
    HOLD = "hold"  # Significant unsupported claims — hold for proof before drafting
    KILL = "kill"  # Critical claims disputed or missing — kill before drafting
    PROCEED_WITH_UNCERTAINTY = "proceed_with_uncertainty"  # Known uncertainty acceptable with disclosure


class FactRiskGate(BaseModel):
    """P3-T3: Early gate output after thesis artifact, before drafting.

    Classifies all claims and makes a pipeline routing decision.
    Stops unsupported ideas before drafting starts.
    """

    idea_id: str = ""
    angle_id: str = ""
    thesis: str = ""

    # P3-T3: Per-claim classification
    claim_statuses: list[ClaimStatus] = Field(
        default_factory=list,
        description="Status of each major claim in the thesis",
    )

    # P3-T3: Aggregate counts for review
    supported_claims: list[str] = Field(
        default_factory=list,
        description="claim_ids or claim texts that are fully supported",
    )
    weak_claims: list[str] = Field(
        default_factory=list,
        description="claim_ids or claim texts with partial but insufficient evidence",
    )
    missing_claims: list[str] = Field(
        default_factory=list,
        description="claim_ids or claim texts with no supporting evidence",
    )
    disputed_claims: list[str] = Field(
        default_factory=list,
        description="claim_ids or claim texts with conflicting evidence",
    )
    acceptable_uncertainty_claims: list[str] = Field(
        default_factory=list,
        description="claim_ids or claim texts approved for delivery with known uncertainty",
    )

    # P3-T3: Gate decision
    decision: FactRiskDecision = FactRiskDecision.HOLD

    # P3-T3: Reason for the decision
    decision_reason: str = Field(
        default="",
        description="Why this decision was made — key evidence or risk factors",
    )

    # P3-T3: What must be resolved before the hold can be cleared
    hold_resolution_requirements: list[str] = Field(
        default_factory=list,
        description="What must be proven or clarified before moving to drafting",
    )

    # P3-T3: When proceeding with known uncertainty, what disclosure is required
    required_disclosure: str = Field(
        default="",
        description="What the script must include as qualified/uncertain delivery",
    )

    # P3-T3: Known-uncertainty rules for this idea/angle
    # When operator explicitly allows delivery with known gaps
    uncertainty_policy: str = Field(
        default="",
        description="The policy that governs when delivery with uncertainty is acceptable",
    )

    # P3-T3: Trace of which proof anchors were checked and their status
    proof_check_results: list[str] = Field(
        default_factory=list,
        description="Human-readable trace of which proof anchors were verified",
    )


class FactRiskGateResult(BaseModel):
    """P3-T3: Result of a single idea's fact-risk gate evaluation."""

    idea_id: str
    decision: FactRiskDecision
    decision_reason: str
    supported_count: int = 0
    weak_count: int = 0
    missing_count: int = 0
    disputed_count: int = 0
    hold_resolution_requirements: list[str] = Field(default_factory=list)
    required_disclosure: str = ""
    uncertainty_policy: str = ""


class FactRiskGateOutput(BaseModel):
    """P3-T3: Collection of gate decisions for all ideas in a scoring run."""

    gates: list[FactRiskGate] = Field(default_factory=list)
    # Aggregate summary across all gated ideas
    total_approved: int = 0
    total_held: int = 0
    total_killed: int = 0
    total_proceed_with_uncertainty: int = 0


class RetrievalDecision(BaseModel):
    """Single query decision from the retrieval planner."""

    family: str = Field(..., description="Query family label (e.g. proof, contrarian)")
    intent_tags: list[str] = Field(default_factory=list)
    query: str = Field(..., description="The actual search query string")
    mode: RetrievalMode = Field(default=RetrievalMode.BASELINE)
    rationale: str = Field(default="", description="Why this query was chosen")
    priority: int = Field(default=0, description="Higher = more important, runs first")


class RetrievalBudget(BaseModel):
    """Explicit budget for bounding retrieval search volume.

    P3-T1: Core budget fields are used for all tiers; tier-specific overrides
    are applied by the planner based on the ResearchDepthRouting decision.
    """

    max_queries: int = Field(default=6, ge=1, le=50)
    max_sources: int = Field(default=12, ge=1, le=100)
    max_results_per_query: int = Field(default=5, ge=1, le=20)
    stop_if_sources_seen: int | None = Field(default=None, description="Stop early if N sources already collected")
    stop_on_family_count: int | None = Field(
        default=None, description="Stop per family after N queries (for deep mode)"
    )
    # P3-T1: Tier-specific overrides — these replace the base fields when the tier is set
    # Format: tier_name -> (max_queries, max_sources)
    tier_overrides: dict[str, tuple[int, int]] = Field(
        default_factory=lambda: {
            "light": (3, 6),
            "standard": (6, 12),
            "deep": (12, 24),
        },
        description="Per-tier query and source budget overrides",
    )
    # P3-T1: Time budget in seconds — used for display and enforcement
    time_budget_seconds: int = Field(
        default=120,
        ge=30,
        le=600,
        description="Estimated time budget for this research run",
    )


class RetrievalPlan(BaseModel):
    """Complete retrieval plan from the adaptive planner."""

    decisions: list[RetrievalDecision] = Field(default_factory=list)
    budget: RetrievalBudget = Field(default_factory=RetrievalBudget)
    mode: RetrievalMode = Field(default=RetrievalMode.BASELINE)
    # P3-T1: Research depth routing for the pipeline
    research_depth_routing: ResearchDepthRouting | None = Field(
        default=None,
        description="Routing decision that determines depth tier and time budget",
    )
    research_hypotheses: list[str] = Field(default_factory=list)
    coverage_notes: list[str] = Field(default_factory=list)
    is_complete: bool = Field(default=False)

    @property
    def total_queries(self) -> int:
        return len(self.decisions)

    @property
    def families_used(self) -> set[str]:
        return {d.family for d in self.decisions}


class ResearchSource(BaseModel):
    """Normalized source record retained from search retrieval."""

    source_id: str = Field(default_factory=lambda: f"src_{uuid4().hex[:8]}")
    url: str = ""
    title: str = ""
    provider: str = ""
    query: str = ""
    query_family: str = "baseline"
    intent_tags: list[str] = Field(default_factory=list)
    published_date: str | None = None
    snippet: str = ""
    query_provenance: list[QueryProvenance] = Field(default_factory=list)
    source_metadata: dict[str, Any] = Field(default_factory=dict)
    # Source quality metadata (Task 16)
    source_authority: SourceAuthority = SourceAuthority.UNKNOWN
    evidence_directness: EvidenceDirectness = EvidenceDirectness.UNKNOWN
    source_freshness: SourceFreshness = SourceFreshness.UNKNOWN
    quality_rank: float | None = Field(default=None, description="Computed quality rank (higher = stronger evidence)")

    @model_validator(mode="after")
    def _sync_query_provenance(self) -> ResearchSource:
        if not self.query_provenance and self.query:
            self.query_provenance = [
                QueryProvenance(
                    query=self.query,
                    family=self.query_family or "baseline",
                    intent_tags=list(self.intent_tags),
                )
            ]
        elif self.query_provenance:
            first_entry = self.query_provenance[0]
            if not self.query:
                self.query = first_entry.query
            if not self.query_family:
                self.query_family = first_entry.family
            if not self.intent_tags:
                self.intent_tags = list(first_entry.intent_tags)
        return self


class ResearchFinding(BaseModel):
    """Qualitative observation that can still be tied back to sources."""

    finding_id: str = Field(default_factory=lambda: f"finding_{uuid4().hex[:8]}")
    finding_type: ResearchFindingType = ResearchFindingType.AUDIENCE_INSIGHT
    summary: str = ""
    source_ids: list[str] = Field(default_factory=list)
    confidence: ResearchConfidence = ResearchConfidence.UNKNOWN
    evidence_note: str = ""


class ResearchClaim(BaseModel):
    """Concrete claim that should later be mapped into beats and proofs."""

    claim_id: str = Field(default_factory=lambda: f"claim_{uuid4().hex[:8]}")
    claim_type: ResearchClaimType = ResearchClaimType.KEY_FACT
    claim: str = ""
    source_ids: list[str] = Field(default_factory=list)
    confidence: ResearchConfidence = ResearchConfidence.UNKNOWN
    mechanism: str = ""


class ResearchCounterpoint(BaseModel):
    """Counterevidence or caveat that keeps the script intellectually honest."""

    counterpoint_id: str = Field(default_factory=lambda: f"counter_{uuid4().hex[:8]}")
    summary: str = ""
    why_it_matters: str = ""
    source_ids: list[str] = Field(default_factory=list)
    confidence: ResearchConfidence = ResearchConfidence.UNKNOWN


class ResearchUncertaintyFlag(BaseModel):
    """Claim-level uncertainty that should constrain scripting and QC."""

    flag_id: str = Field(default_factory=lambda: f"flag_{uuid4().hex[:8]}")
    flag_type: ResearchFlagType = ResearchFlagType.VERIFICATION_REQUIRED
    claim: str = ""
    reason: str = ""
    severity: ResearchSeverity = ResearchSeverity.MEDIUM
    source_ids: list[str] = Field(default_factory=list)


class ResearchPack(BaseModel):
    """Compact research pack (spec stage 4)."""

    idea_id: str = ""
    angle_id: str = ""
    supporting_sources: list[ResearchSource] = Field(default_factory=list)
    findings: list[ResearchFinding] = Field(default_factory=list)
    claims: list[ResearchClaim] = Field(default_factory=list)
    counterpoints: list[ResearchCounterpoint] = Field(default_factory=list)
    uncertainty_flags: list[ResearchUncertaintyFlag] = Field(default_factory=list)
    audience_insights: list[str] = Field(default_factory=list)
    competitor_observations: list[str] = Field(default_factory=list)
    key_facts: list[str] = Field(default_factory=list)
    proof_points: list[str] = Field(default_factory=list)
    examples: list[str] = Field(default_factory=list)
    case_studies: list[str] = Field(default_factory=list)
    gaps_to_exploit: list[str] = Field(default_factory=list)
    assets_needed: list[str] = Field(default_factory=list)
    claims_requiring_verification: list[str] = Field(default_factory=list)
    unsafe_or_uncertain_claims: list[str] = Field(default_factory=list)
    research_stop_reason: str = ""
    is_degraded: bool = False
    degradation_reason: str = ""
    # P3-T1: Research depth routing metadata (which tier was used and why)
    research_depth_routing: ResearchDepthRouting | None = Field(
        default=None,
        description="Depth routing decision for this research run",
    )
    # P3-T1: Retrieval mode used (baseline, deep, targeted, contrarian)
    research_mode: str = Field(
        default="",
        description="RetrievalMode string used for this research run",
    )

    @model_validator(mode="after")
    def _sync_structured_and_legacy_views(self) -> ResearchPack:
        self.supporting_sources = _dedupe_research_sources(self.supporting_sources)

        has_structured_records = any(
            (
                self.findings,
                self.claims,
                self.counterpoints,
                self.uncertainty_flags,
            )
        )
        if not has_structured_records:
            self.findings = _legacy_findings_from_research_pack(self)
            self.claims = _legacy_claims_from_research_pack(self)
            self.uncertainty_flags = _legacy_uncertainty_flags_from_research_pack(self)

        if self.findings or self.claims or self.uncertainty_flags:
            self.audience_insights = _summaries_for_finding_type(
                self.findings,
                ResearchFindingType.AUDIENCE_INSIGHT,
            )
            self.competitor_observations = _summaries_for_finding_type(
                self.findings,
                ResearchFindingType.COMPETITOR_OBSERVATION,
            )
            self.examples = _summaries_for_finding_type(
                self.findings,
                ResearchFindingType.EXAMPLE,
            )
            self.case_studies = _summaries_for_finding_type(
                self.findings,
                ResearchFindingType.CASE_STUDY,
            )
            self.gaps_to_exploit = _summaries_for_finding_type(
                self.findings,
                ResearchFindingType.GAP_TO_EXPLOIT,
            )
            self.key_facts = _summaries_for_claim_type(
                self.claims,
                ResearchClaimType.KEY_FACT,
            )
            self.proof_points = _summaries_for_claim_type(
                self.claims,
                ResearchClaimType.PROOF_POINT,
            )
            self.claims_requiring_verification = _claims_for_flag_type(
                self.uncertainty_flags,
                ResearchFlagType.VERIFICATION_REQUIRED,
            )
            self.unsafe_or_uncertain_claims = _claims_for_flag_type(
                self.uncertainty_flags,
                ResearchFlagType.UNSAFE_OR_UNCERTAIN,
            )
        return self


# ---------------------------------------------------------------------------
# Pipeline stage 5: Argument map builder
# ---------------------------------------------------------------------------


class ArgumentProofAnchor(BaseModel):
    """A piece of evidence or mechanism support that later beats can cite."""

    proof_id: str = Field(default_factory=lambda: f"proof_{uuid4().hex[:8]}")
    summary: str = ""
    source_ids: list[str] = Field(default_factory=list)
    usage_note: str = ""


class ArgumentCounterargument(BaseModel):
    """Credible pushback and the response the script should hold ready."""

    counterargument_id: str = Field(default_factory=lambda: f"counter_{uuid4().hex[:8]}")
    counterargument: str = ""
    response: str = ""
    response_proof_ids: list[str] = Field(default_factory=list)


class ArgumentClaim(BaseModel):
    """A claim candidate that can be safe to state or marked off-limits."""

    claim_id: str = Field(default_factory=lambda: f"claim_{uuid4().hex[:8]}")
    claim: str = ""
    supporting_proof_ids: list[str] = Field(default_factory=list)
    note: str = ""


class ArgumentBeatClaim(BaseModel):
    """Beat-level plan that ties the narrative to validated proof and claims."""

    beat_id: str = Field(default_factory=lambda: f"beat_{uuid4().hex[:8]}")
    beat_name: str = ""
    goal: str = ""
    claim_ids: list[str] = Field(default_factory=list)
    proof_anchor_ids: list[str] = Field(default_factory=list)
    counterargument_ids: list[str] = Field(default_factory=list)
    transition_note: str = ""


class ArgumentMap(BaseModel):
    """Bridge artifact between research synthesis and script drafting."""

    idea_id: str = ""
    angle_id: str = ""
    thesis: str = ""
    audience_belief_to_challenge: str = ""
    core_mechanism: str = ""
    proof_anchors: list[ArgumentProofAnchor] = Field(default_factory=list)
    counterarguments: list[ArgumentCounterargument] = Field(default_factory=list)
    safe_claims: list[ArgumentClaim] = Field(default_factory=list)
    unsafe_claims: list[ArgumentClaim] = Field(default_factory=list)
    beat_claim_plan: list[ArgumentBeatClaim] = Field(default_factory=list)
    # Task 19: Differentiation — what this angle contributes beyond standard advice
    what_this_contributes: str = Field(
        default="",
        description="What the selected angle contributes beyond consensus or standard advice",
    )
    genericity_flags: list[str] = Field(
        default_factory=list,
        description="Specific generic or clichéd framings this script must avoid",
    )
    differentiation_stategy: str = Field(
        default="",
        description="The editorial strategy for standing out from market-standard content on this topic",
    )

    @model_validator(mode="after")
    def _validate_references(self) -> ArgumentMap:
        proof_ids = _ensure_unique_ids(
            self.proof_anchors,
            id_attr="proof_id",
            label="proof_anchors",
        )
        counterargument_ids = _ensure_unique_ids(
            self.counterarguments,
            id_attr="counterargument_id",
            label="counterarguments",
        )
        claim_ids = _ensure_unique_ids(
            [*self.safe_claims, *self.unsafe_claims],
            id_attr="claim_id",
            label="claims",
        )
        _ensure_unique_ids(
            self.beat_claim_plan,
            id_attr="beat_id",
            label="beat_claim_plan",
        )

        for claim in [*self.safe_claims, *self.unsafe_claims]:
            _ensure_known_ids(
                claim.supporting_proof_ids,
                valid_ids=proof_ids,
                label=f"claim '{claim.claim_id}' supporting_proof_ids",
            )

        for counterargument in self.counterarguments:
            _ensure_known_ids(
                counterargument.response_proof_ids,
                valid_ids=proof_ids,
                label=f"counterargument '{counterargument.counterargument_id}' response_proof_ids",
            )

        for beat in self.beat_claim_plan:
            _ensure_known_ids(
                beat.claim_ids,
                valid_ids=claim_ids,
                label=f"beat '{beat.beat_id}' claim_ids",
            )
            _ensure_known_ids(
                beat.proof_anchor_ids,
                valid_ids=proof_ids,
                label=f"beat '{beat.beat_id}' proof_anchor_ids",
            )
            _ensure_known_ids(
                beat.counterargument_ids,
                valid_ids=counterargument_ids,
                label=f"beat '{beat.beat_id}' counterargument_ids",
            )

        return self


def _dedupe_research_sources(sources: list[ResearchSource]) -> list[ResearchSource]:
    deduped: list[ResearchSource] = []
    seen: set[tuple[str, str]] = set()
    for source in sources:
        key = (source.source_id, source.url)
        if key in seen:
            continue
        seen.add(key)
        deduped.append(source)
    return deduped


def _ensure_unique_ids(items: list[BaseModel], *, id_attr: str, label: str) -> set[str]:
    ids: set[str] = set()
    for item in items:
        item_id = str(getattr(item, id_attr, "")).strip()
        if not item_id:
            continue
        if item_id in ids:
            msg = f"{label} contains duplicate identifier '{item_id}'"
            raise ValueError(msg)
        ids.add(item_id)
    return ids


def _ensure_known_ids(referenced_ids: list[str], *, valid_ids: set[str], label: str) -> None:
    unknown_ids = sorted({item_id for item_id in referenced_ids if item_id and item_id not in valid_ids})
    if unknown_ids:
        msg = f"{label} references unknown identifiers: {', '.join(unknown_ids)}"
        raise ValueError(msg)


def _summaries_for_finding_type(
    findings: list[ResearchFinding],
    finding_type: ResearchFindingType,
) -> list[str]:
    return [finding.summary for finding in findings if finding.finding_type == finding_type and finding.summary]


def _summaries_for_claim_type(
    claims: list[ResearchClaim],
    claim_type: ResearchClaimType,
) -> list[str]:
    return [claim.claim for claim in claims if claim.claim_type == claim_type and claim.claim]


def _claims_for_flag_type(
    flags: list[ResearchUncertaintyFlag],
    flag_type: ResearchFlagType,
) -> list[str]:
    return [flag.claim for flag in flags if flag.flag_type == flag_type and flag.claim]


def _legacy_findings_from_research_pack(research_pack: ResearchPack) -> list[ResearchFinding]:
    findings: list[ResearchFinding] = []
    legacy_sections = (
        (ResearchFindingType.AUDIENCE_INSIGHT, research_pack.audience_insights),
        (ResearchFindingType.COMPETITOR_OBSERVATION, research_pack.competitor_observations),
        (ResearchFindingType.EXAMPLE, research_pack.examples),
        (ResearchFindingType.CASE_STUDY, research_pack.case_studies),
        (ResearchFindingType.GAP_TO_EXPLOIT, research_pack.gaps_to_exploit),
    )
    for finding_type, entries in legacy_sections:
        for summary in entries:
            if summary:
                findings.append(
                    ResearchFinding(
                        finding_type=finding_type,
                        summary=summary,
                    )
                )
    return findings


def _legacy_claims_from_research_pack(research_pack: ResearchPack) -> list[ResearchClaim]:
    claims: list[ResearchClaim] = []
    legacy_sections = (
        (ResearchClaimType.KEY_FACT, research_pack.key_facts),
        (ResearchClaimType.PROOF_POINT, research_pack.proof_points),
    )
    for claim_type, entries in legacy_sections:
        for claim in entries:
            if claim:
                claims.append(
                    ResearchClaim(
                        claim_type=claim_type,
                        claim=claim,
                    )
                )
    return claims


def _legacy_uncertainty_flags_from_research_pack(
    research_pack: ResearchPack,
) -> list[ResearchUncertaintyFlag]:
    flags: list[ResearchUncertaintyFlag] = []
    legacy_sections = (
        (
            ResearchFlagType.VERIFICATION_REQUIRED,
            ResearchSeverity.MEDIUM,
            research_pack.claims_requiring_verification,
        ),
        (
            ResearchFlagType.UNSAFE_OR_UNCERTAIN,
            ResearchSeverity.HIGH,
            research_pack.unsafe_or_uncertain_claims,
        ),
    )
    for flag_type, severity, entries in legacy_sections:
        for claim in entries:
            if claim:
                flags.append(
                    ResearchUncertaintyFlag(
                        flag_type=flag_type,
                        claim=claim,
                        severity=severity,
                    )
                )
    return flags


# ---------------------------------------------------------------------------
# Pipeline stage 6: Visual translation
# ---------------------------------------------------------------------------


class BeatVisual(BaseModel):
    """Per-beat visual plan (spec stage 6)."""

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
    visual_refresh_check: str = ""  # pass if every 1-3 beats has meaningful change


# ---------------------------------------------------------------------------
# Pipeline stage 7: Production brief
# ---------------------------------------------------------------------------


class ProductionBrief(BaseModel):
    """Production planning output (spec stage 7)."""

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


# ---------------------------------------------------------------------------
# Pipeline stage 8: Packaging generator
# ---------------------------------------------------------------------------


class PlatformPackage(BaseModel):
    """Per-platform packaging (spec stage 8)."""

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
    # P4-T1: Channel-aware packaging signals
    target_channel: str = Field(
        default="",
        description="Target channel/format hint (e.g., 'shorts', 'reels', 'feed') that guided this packaging",
    )
    content_type_hint: str = Field(
        default="",
        description="Content type that guided this packaging (e.g., 'contrarian', 'tutorial', 'story')",
    )


class PackagingOutput(BaseModel):
    """Output of the packaging generator stage."""

    idea_id: str = ""
    platform_packages: list[PlatformPackage] = Field(default_factory=list)
    # P4-T1: Early packaging signals captured from hook/angle stage
    # These guide packaging generation before the full script is written
    draft_hooks: list[str] = Field(
        default_factory=list,
        description="Hook candidates considered during scripting, passed forward for packaging selection",
    )
    early_packaging_signals: EarlyPackagingSignals | None = Field(
        default=None,
        description="Channel format, content type, and target signals captured early to co-design draft with packaging",
    )


# ---------------------------------------------------------------------------
# Pipeline stage 9: Human QC gate
# ---------------------------------------------------------------------------


class HumanQCGate(BaseModel):
    """Human-gateable QC output (spec stage 9).

    approved_for_publish defaults to False. Only a human can set it to True.
    """

    review_round: int = 1
    hook_strength: str = ""  # strong | adequate | weak
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
    # P2-T3: Success criteria evaluation from opportunity brief
    success_criteria_results: list[str] = Field(
        default_factory=list,
        description="Per-criterion evaluation: whether each planned success criterion is met or unmet",
    )


# ---------------------------------------------------------------------------
# Targeted Revision (Task 18)
# ---------------------------------------------------------------------------


class BeatRevisionScope(BaseModel):
    """Identifies a specific beat or claim group that needs repair."""

    beat_id: str = ""
    beat_name: str = ""
    # Claim IDs within this beat that are weak or unsupported
    weak_claim_ids: list[str] = Field(default_factory=list)
    # Which proof anchors are missing or stale for this beat
    missing_proof_ids: list[str] = Field(default_factory=list)
    # Why this beat is weak
    weakness_reason: str = ""
    # Stable — True means this beat passed QC and should not be touched
    is_stable: bool = False


class RewriteActionType(StrEnum):
    """The type of repair action for a targeted revision."""

    REWRITE_BEAT = "rewrite_beat"  # Rewrite the beat content (severe issues)
    REFRESH_EVIDENCE = "refresh_evidence"  # Update evidence only, keep structure
    QUALIFY_CLAIM = "qualify_claim"  # Soften a claim instead of proving it
    REMOVE_CLAIM = "remove_claim"  # Drop the claim entirely
    ADD_COUNTERARGUMENT = "add_counterargument"  # Add counterargument coverage


class TargetedRewriteAction(BaseModel):
    """A single repair action targeting a specific beat or claim."""

    action_id: str = Field(default_factory=lambda: f"rewrite_{uuid4().hex[:8]}")
    action_type: RewriteActionType
    beat_id: str = ""
    beat_name: str = ""
    # For rewrite_beat / refresh_evidence
    weak_claim_ids: list[str] = Field(default_factory=list)
    # For refresh_evidence — which proof anchors are missing
    missing_proof_ids: list[str] = Field(default_factory=list)
    # For qualify_claim / remove_claim
    target_claim_text: str = ""
    target_claim_id: str = ""
    # Instructions for the LLM doing the repair
    instruction: str = ""
    # Evidence gaps — passed to retrieval for targeted research
    evidence_gaps: list[str] = Field(default_factory=list)
    priority: int = Field(default=0, ge=0, le=10)  # Higher = more urgent


class TargetedRevisionPlan(BaseModel):
    """A surgical revision plan targeting only weak beats and claims.

    Produced by the quality evaluator when the script has localized issues
    rather than pervasive failure. Allows the loop to repair specific beats
    without rebuilding the entire script.
    """

    revision_id: str = Field(default_factory=lambda: f"rev_{uuid4().hex[:8]}")
    # Beats that passed QC and should be preserved unchanged
    stable_beats: list[BeatRevisionScope] = Field(default_factory=list)
    # Beats that need repair
    weak_beats: list[BeatRevisionScope] = Field(default_factory=list)
    # Individual repair actions
    actions: list[TargetedRewriteAction] = Field(default_factory=list)
    # Short summary of what changed
    revision_summary: str = ""
    # When True, the script is too broken for targeted repair — do full restart
    full_restart_recommended: bool = False
    # If True, this plan replaces the existing script; if False, it patches it
    is_patch: bool = True
    # Evidence gaps requiring targeted retrieval
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


class RevisionMode(StrEnum):
    """Revision strategy for the iterative loop."""

    FULL = "full"  # Re-run all content stages with broad feedback
    TARGETED = "targeted"  # Surgical repair of specific weak beats only
    NONE = "none"  # No revision needed — script is acceptable


# ---------------------------------------------------------------------------
# Pipeline stage 10: Publish queue
# ---------------------------------------------------------------------------


class QualityEvaluation(BaseModel):
    """Result of the quality evaluator agent.

    Assesses the complete content package after each iteration to decide
    whether to stop iterating or continue improving.
    """

    overall_quality_score: float = Field(default=0.0, ge=0.0, le=1.0)
    passes_threshold: bool = False
    evidence_coverage: float = Field(default=0.0, ge=0.0, le=1.0)
    claim_safety: float = Field(default=0.0, ge=0.0, le=1.0)
    originality: float = Field(default=0.0, ge=0.0, le=1.0)
    precision: float = Field(default=0.0, ge=0.0, le=1.0)
    expertise_density: float = Field(default=0.0, ge=0.0, le=1.0)
    # Task 19: Generic framing / undifferentiated content detection
    genericity: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
        description="Degree to which the content sounds like everyone else — high = generic, low = distinctive",
    )
    critical_issues: list[str] = Field(default_factory=list)
    unsupported_claims: list[str] = Field(default_factory=list)
    evidence_actions_required: list[str] = Field(default_factory=list)
    improvement_suggestions: list[str] = Field(default_factory=list)
    research_gaps_identified: list[str] = Field(default_factory=list)
    # Task 19: Explicit genericity/cliché flags
    cliche_flags: list[str] = Field(
        default_factory=list,
        description="Specific clichéd framings or interchangeable talking points detected in the script",
    )
    interchangeable_take_flags: list[str] = Field(
        default_factory=list,
        description="Content that sounds like everyone else's take on this topic",
    )
    rationale: str = ""
    iteration_number: int = 1
    # Task 18: structured repair plan for targeted revision
    targeted_revision_plan: TargetedRevisionPlan | None = None
    revision_mode: RevisionMode = RevisionMode.NONE

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
    revision_mode: RevisionMode = RevisionMode.FULL
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


class ScriptingIterationSummary(BaseModel):
    """Compact quality summary for one scripting iteration."""

    iteration: int = Field(default=1, ge=1)
    score: float = Field(default=0.0, ge=0.0, le=1.0)
    passes: bool = False


class ScriptingIterations(BaseModel):
    """Saved iteration summary for iterative scripting runs."""

    count: int = Field(default=1, ge=1)
    max_iterations: int = Field(default=1, ge=1)
    converged: bool = False
    quality_history: list[ScriptingIterationSummary] = Field(default_factory=list)


class ScriptingRunResult(BaseModel):
    """Full saved response for a standalone scripting run."""

    run_id: str | None = None
    raw_idea: str = ""
    script: str = ""
    word_count: int = 0
    context: ScriptingContext
    execution_mode: Literal["single_pass", "iterative"] = "single_pass"
    iterations: ScriptingIterations | None = None


class DraftLaneDecision(StrEnum):
    """P4-T3: Draft lane decision for publish-now vs hold-for-proof path."""

    PUBLISH_NOW = "publish_now"  # Publish with known uncertainty, fast path
    HOLD_FOR_PROOF = "hold_for_proof"  # Hold for stronger proof before publishing
    RECYCLE_FOR_REUSE = "recycle_for_reuse"  # Recycle to backlog for derivative/reuse
    KILL = "kill"  # Abandon this draft


class PublishItem(BaseModel):
    """Single publish queue entry (spec stage 10)."""

    idea_id: str = ""
    platform: str = ""
    publish_datetime: str = ""  # ISO 8601
    asset_version: str = ""
    caption_version: str = ""
    pinned_comment: str = ""
    cross_post_targets: list[str] = Field(default_factory=list)
    first_30_minute_engagement_plan: str = ""
    status: str = "scheduled"  # scheduled | published
    # P4-T3: Publish-now vs hold decision tracking
    draft_decision: DraftLaneDecision | None = Field(
        default=None,
        description="The draft lane decision that led to this publish item",
    )
    decision_reason: str = Field(
        default="",
        description="Why this decision was made (uncertainty status, risk level, etc.)",
    )
    claim_status_summary: str = Field(
        default="",
        description="Summary of claim status at time of decision (e.g., '3 supported, 1 weak')",
    )


class PipelineLaneContext(BaseModel):
    """Per-idea execution state for one shortlisted production lane."""

    idea_id: str = ""
    role: Literal["primary", "runner_up"] = "primary"
    status: Literal["selected", "runner_up", "in_production", "published"] = "selected"
    last_completed_stage: int = -1
    angles: AngleOutput | None = None
    research_pack: ResearchPack | None = None
    argument_map: ArgumentMap | None = None
    scripting: ScriptingContext | None = None
    visual_plan: VisualPlanOutput | None = None
    production_brief: ProductionBrief | None = None
    packaging: PackagingOutput | None = None
    qc_gate: HumanQCGate | None = None
    # P3-T3: Early fact-risk gate decision (after thesis, before drafting)
    fact_risk_gate: FactRiskGate | None = Field(
        default=None,
        description="Early gate output after thesis artifact, before drafting",
    )
    # P4-T1: Early packaging signals captured from angle/channel stage
    early_packaging_signals: EarlyPackagingSignals | None = Field(
        default=None,
        description="Channel format, content type, and target signals captured early to co-design draft with packaging",
    )
    # P4-T2: Derivative and reuse opportunities from approved draft
    derivative_opportunities: list[DerivativeOpportunity] = Field(
        default_factory=list,
        description="Reuse and derivative opportunities extracted from this draft",
    )
    # P4-T3: Publish-now vs hold-for-proof decision
    draft_decision: DraftLaneDecision | None = Field(
        default=None,
        description="Draft lane decision: publish now, hold for proof, recycle for reuse, or kill",
    )
    decision_reason: str = Field(
        default="",
        description="Why the draft decision was made (uncertainty status, risk level, etc.)",
    )
    publish_items: list[PublishItem] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Pipeline stage 11: Performance analyst
# ---------------------------------------------------------------------------


class PerformanceAnalysis(BaseModel):
    """Post-publish analysis (spec stage 11)."""

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
    # P2-T3: Opportunity brief comparison results
    opportunity_brief_comparison: str = Field(
        default="",
        description="How the actual outcomes compared against the original opportunity brief intent",
    )
    brief_success_criteria_results: list[str] = Field(
        default_factory=list,
        description="Per-criterion results: whether each planned success criterion was met or unmet",
    )
    brief_hypothesis_results: list[str] = Field(
        default_factory=list,
        description="Per-hypothesis results: whether each planned research hypothesis was supported or contradicted",
    )


# ---------------------------------------------------------------------------
# Phase 03 - Learning Store and Planning Metrics (P3-T3)
# ---------------------------------------------------------------------------


class PlanningLearningCategory(StrEnum):
    """Category of opportunity planning learning."""

    BRIEF_SPECIFICITY = "brief_specificity"  # How specific vs generic the brief was
    AUDIENCE_DEFINITION = "audience_definition"  # How well audience was defined
    HYPOTHESIS_QUALITY = "hypothesis_quality"  # Quality of research hypotheses
    SUCCESS_CRITERIA = "success_criteria"  # How measurable the criteria were
    PROOF_REQUIREMENTS = "proof_requirements"  # How actionable proof requirements were
    SUB_ANGLE_DISTINCTION = "sub_angle_distinction"  # How distinct sub-angles were


class PlanningLearning(BaseModel):
    """A reusable opportunity-planning pattern extracted from runs.

    Stores validated lessons that can influence future planning.
    """

    learning_id: str = Field(default_factory=lambda: f"planlearn_{uuid4().hex[:8]}")
    category: PlanningLearningCategory = PlanningLearningCategory.BRIEF_SPECIFICITY
    # What pattern was observed
    pattern: str = ""
    # Why it matters for planning quality
    implication: str = ""
    # What to do differently in future briefs
    guidance: str = ""
    # Which brief(s) this learning came from
    source_brief_ids: list[str] = Field(default_factory=list)
    # Whether this learning has been operator-reviewed
    operator_reviewed: bool = False
    # Whether this learning is currently active
    is_active: bool = True
    # When this learning was created
    created_at: str = ""


class PlanningMetrics(BaseModel):
    """Tracking metrics for opportunity planning quality over time.

    These metrics help operators understand whether planning is improving.
    """

    total_briefs: int = 0
    acceptable_briefs: int = 0  # Passed quality validation
    rewritten_briefs: int = 0  # Required at least one revision
    approved_briefs: int = 0  # Passed operator review
    converted_to_production: int = 0  # Successfully produced content

    @computed_field(return_type=float)
    @property
    def pass_rate(self) -> float:
        """Brief acceptance rate."""
        if not self.total_briefs:
            return 0.0
        return round(self.acceptable_briefs / self.total_briefs, 3)

    @computed_field(return_type=float)
    @property
    def rewrite_rate(self) -> float:
        """Rate of briefs needing revision."""
        if not self.total_briefs:
            return 0.0
        return round(self.rewritten_briefs / self.total_briefs, 3)

    @computed_field(return_type=float)
    @property
    def approval_rate(self) -> float:
        """Rate of briefs passing operator review."""
        if not self.total_briefs:
            return 0.0
        return round(self.approved_briefs / self.total_briefs, 3)

    @computed_field(return_type=float)
    @property
    def production_conversion_rate(self) -> float:
        """Rate of approved briefs that went to production."""
        if not self.approved_briefs:
            return 0.0
        return round(self.converted_to_production / self.approved_briefs, 3)

    def to_summary(self) -> str:
        """Human-readable metrics summary."""
        lines = [
            "Planning Metrics:",
            f"  Total briefs: {self.total_briefs}",
            f"  Acceptable (passed validation): {self.acceptable_briefs} ({self.pass_rate:.1%})",
            f"  Required rewrite: {self.rewritten_briefs} ({self.rewrite_rate:.1%})",
            f"  Approved: {self.approved_briefs} ({self.approval_rate:.1%})",
            f"  Converted to production: {self.converted_to_production} ({self.production_conversion_rate:.1%})",
        ]
        return "\n".join(lines)


# ---------------------------------------------------------------------------
# Pipeline stage tracing
# ---------------------------------------------------------------------------


class StageTraceMetadata(BaseModel):
    """Structured metadata for pipeline stage traces.

    Provides typed fields for data that would otherwise be embedded
    in prose strings, enabling better UI rendering and filtering.
    """

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
    parse_mode: str = ""  # "json" | "legacy" — which parse path succeeded


class PipelineStageTrace(BaseModel):
    """Trace record for one completed pipeline stage."""

    stage_index: int
    stage_name: str
    stage_label: str
    # P1-T1: Operating phase this stage belongs to
    # Uses string default to avoid forward reference issue; Pydantic coerces to OperatingPhase
    phase: OperatingPhase = Field(
        default="phase_02_opportunity",
        description="The operating phase this stage belongs to.",
    )
    phase_label: str = Field(
        default="Opportunity & Ideation",
        description="Human-readable phase name.",
    )
    # P1-T2: Policy fields that governed this stage
    policy: OperatingPhasePolicy | None = Field(
        default=None,
        description="The operating policy that governed this stage's execution.",
    )
    # P1-T2: Skip/kill decision reason if stage was skipped or killed
    skip_reason: str = Field(
        default="",
        description="Reason for skipping this stage (if status is 'skipped').",
    )
    kill_reason: str = Field(
        default="",
        description="Reason for killing this stage early (if status is 'killed').",
    )
    # P1-T2: Override record if policy was manually overridden
    policy_override: str = Field(
        default="",
        description="Description of any manual policy override applied to this stage.",
    )
    status: str = "completed"  # completed | skipped | failed | blocked
    started_at: str = ""
    completed_at: str = ""
    duration_ms: int = 0
    input_summary: str = ""
    output_summary: str = ""
    warnings: list[str] = Field(default_factory=list)
    decision_summary: str = ""
    metadata: StageTraceMetadata = Field(default_factory=StageTraceMetadata)


# ---------------------------------------------------------------------------
# Full pipeline context
# ---------------------------------------------------------------------------


class PipelineContext(BaseModel):
    """Accumulated state through the full 14-stage content pipeline.

    Each stage enriches the context with its output. Stages can be
    run independently by loading a previously saved context. The
    existing ScriptingContext sits inside as the ``scripting`` field.
    """

    pipeline_id: str = Field(default_factory=lambda: uuid4().hex[:12])
    theme: str = ""
    created_at: str = ""
    current_stage: int = 0

    strategy: StrategyMemory | None = None
    opportunity_brief: OpportunityBrief | None = None
    # P2-T1: Managed brief reference for controlled handoff between planning and execution
    brief_reference: PipelineBriefReference | None = Field(
        default=None,
        description="Reference to the managed brief resource and revision used by this run.",
    )
    # P1-T3: Per-run constraints that change each content cycle
    run_constraints: RunConstraints | None = Field(
        default=None,
        description="Per-run constraint variables (content type, effort tier, owner, channel goal, success target).",
    )
    backlog: BacklogOutput | None = None
    scoring: ScoringOutput | None = None
    shortlist: list[str] = Field(default_factory=list)
    selected_idea_id: str = ""
    selection_reasoning: str = ""
    runner_up_idea_ids: list[str] = Field(default_factory=list)
    active_candidates: list[PipelineCandidate] = Field(default_factory=list)
    lane_contexts: list[PipelineLaneContext] = Field(default_factory=list)
    angles: AngleOutput | None = None
    research_pack: ResearchPack | None = None
    argument_map: ArgumentMap | None = None
    scripting: ScriptingContext | None = None
    visual_plan: VisualPlanOutput | None = None
    production_brief: ProductionBrief | None = None
    packaging: PackagingOutput | None = None
    qc_gate: HumanQCGate | None = None
    publish_items: list[PublishItem] = Field(default_factory=list)
    publish_item: PublishItem | None = None
    performance: PerformanceAnalysis | None = None
    iteration_state: IterationState | None = None
    stage_traces: list[PipelineStageTrace] = Field(default_factory=list)
    claim_ledger: ClaimTraceLedger | None = None
    # P2-T2: Approval-aware execution gate for brief-controlled pipelines
    brief_gate: BriefExecutionGate | None = Field(
        default=None,
        description="Gate that enforces brief approval requirements for downstream stages.",
    )

    @model_validator(mode="after")
    def _populate_candidate_queue(self) -> PipelineContext:
        lane_candidates = _derive_candidates_from_lane_contexts(self.lane_contexts)
        legacy_primary_idea_id = _derive_legacy_primary_idea_id(self)
        shortlist = self.shortlist or (self.scoring.shortlist if self.scoring else []) or [
            candidate.idea_id for candidate in lane_candidates
        ] or ([legacy_primary_idea_id] if legacy_primary_idea_id else [])
        runner_up_idea_ids = self.runner_up_idea_ids or (
            self.scoring.runner_up_idea_ids if self.scoring else []
        ) or [candidate.idea_id for candidate in lane_candidates if candidate.role == "runner_up"]
        selected_idea_id = self.selected_idea_id or (
            self.scoring.selected_idea_id if self.scoring else ""
        ) or next(
            (candidate.idea_id for candidate in lane_candidates if candidate.role == "primary"),
            "",
        ) or legacy_primary_idea_id
        existing_candidates = self.active_candidates or (
            self.scoring.active_candidates if self.scoring else []
        ) or lane_candidates or (
            [PipelineCandidate(idea_id=legacy_primary_idea_id, role="primary", status="selected")]
            if legacy_primary_idea_id
            else []
        )
        self.active_candidates = _derive_pipeline_candidates(
            selected_idea_id=selected_idea_id,
            shortlist=shortlist,
            runner_up_idea_ids=runner_up_idea_ids,
            existing_candidates=existing_candidates,
        )
        legacy_primary_publish_items = self.publish_items or ([self.publish_item] if self.publish_item is not None else [])
        self.lane_contexts = _derive_lane_contexts(
            candidates=self.active_candidates,
            existing_lane_contexts=self.lane_contexts,
            primary_angles=self.angles,
            primary_research_pack=self.research_pack,
            primary_argument_map=self.argument_map,
            primary_scripting=self.scripting,
            primary_visual_plan=self.visual_plan,
            primary_production_brief=self.production_brief,
            primary_packaging=self.packaging,
            primary_qc_gate=self.qc_gate,
            primary_publish_items=legacy_primary_publish_items,
        )
        if not self.selected_idea_id:
            primary = next(
                (candidate.idea_id for candidate in self.active_candidates if candidate.role == "primary"),
                "",
            )
            if primary:
                self.selected_idea_id = primary
        if not self.runner_up_idea_ids:
            self.runner_up_idea_ids = [
                candidate.idea_id for candidate in self.active_candidates if candidate.role == "runner_up"
            ]
        primary_lane = next(
            (lane for lane in self.lane_contexts if lane.role == "primary"),
            self.lane_contexts[0] if self.lane_contexts else None,
        )
        if primary_lane is not None:
            self.angles = primary_lane.angles
            self.research_pack = primary_lane.research_pack
            self.argument_map = primary_lane.argument_map
            self.scripting = primary_lane.scripting
            self.visual_plan = primary_lane.visual_plan
            self.production_brief = primary_lane.production_brief
            self.packaging = primary_lane.packaging
            self.qc_gate = primary_lane.qc_gate
            self.publish_items = list(primary_lane.publish_items)
            self.publish_item = self.publish_items[0] if self.publish_items else None
        else:
            if not self.publish_items and self.publish_item is not None:
                self.publish_items = [self.publish_item]
            if self.publish_item is None and self.publish_items:
                self.publish_item = self.publish_items[0]
        return self


_ACTIVE_CANDIDATE_LIMIT = 2


def _derive_pipeline_candidates(
    *,
    selected_idea_id: str = "",
    shortlist: list[str] | None = None,
    runner_up_idea_ids: list[str] | None = None,
    existing_candidates: list[PipelineCandidate] | None = None,
    content_type_profile: str = "",
) -> list[PipelineCandidate]:
    primary_id = selected_idea_id.strip()
    if not primary_id and existing_candidates:
        primary_id = next(
            (candidate.idea_id for candidate in existing_candidates if candidate.role == "primary"),
            "",
        )
    if not primary_id and shortlist:
        primary_id = next((idea_id for idea_id in shortlist if idea_id), "")

    ordered_ids: list[str] = []
    for idea_id in [primary_id, *(shortlist or []), *(runner_up_idea_ids or [])]:
        if idea_id and idea_id not in ordered_ids:
            ordered_ids.append(idea_id)

    if not ordered_ids:
        return []

    primary_status = "selected"
    if existing_candidates:
        primary_status = next(
            (
                candidate.status
                for candidate in existing_candidates
                if candidate.idea_id == primary_id and candidate.role == "primary"
            ),
            primary_status,
        )

    candidates = [
        PipelineCandidate(
            idea_id=primary_id or ordered_ids[0],
            role="primary",
            status=primary_status if primary_status in {"selected", "in_production", "published"} else "selected",
            content_type_profile=content_type_profile,
        )
    ]

    for idea_id in ordered_ids:
        if idea_id == candidates[0].idea_id:
            continue
        candidates.append(
            PipelineCandidate(
                idea_id=idea_id,
                role="runner_up",
                status="runner_up",
                content_type_profile=content_type_profile,
            )
        )
        if len(candidates) >= _ACTIVE_CANDIDATE_LIMIT:
            break

    return candidates


def _derive_candidates_from_lane_contexts(
    lane_contexts: list[PipelineLaneContext] | None,
) -> list[PipelineCandidate]:
    if not lane_contexts:
        return []

    ordered_lanes = sorted(
        (lane for lane in lane_contexts if lane.idea_id),
        key=lambda lane: (0 if lane.role == "primary" else 1, lane.idea_id),
    )
    return [
        PipelineCandidate(
            idea_id=lane.idea_id,
            role=lane.role,
            status=lane.status,
        )
        for lane in ordered_lanes[:_ACTIVE_CANDIDATE_LIMIT]
    ]


def _derive_lane_contexts(
    *,
    candidates: list[PipelineCandidate],
    existing_lane_contexts: list[PipelineLaneContext] | None = None,
    primary_angles: AngleOutput | None = None,
    primary_research_pack: ResearchPack | None = None,
    primary_argument_map: ArgumentMap | None = None,
    primary_scripting: ScriptingContext | None = None,
    primary_visual_plan: VisualPlanOutput | None = None,
    primary_production_brief: ProductionBrief | None = None,
    primary_packaging: PackagingOutput | None = None,
    primary_qc_gate: HumanQCGate | None = None,
    primary_publish_items: list[PublishItem] | None = None,
) -> list[PipelineLaneContext]:
    existing_by_id = {
        lane.idea_id: lane for lane in (existing_lane_contexts or []) if lane.idea_id
    }
    lane_contexts: list[PipelineLaneContext] = []

    for candidate in candidates:
        lane = existing_by_id.get(candidate.idea_id)
        if lane is None:
            lane = PipelineLaneContext(
                idea_id=candidate.idea_id,
                role=candidate.role,
                status=candidate.status,
            )
        else:
            lane = lane.model_copy(
                update={
                    "role": candidate.role,
                    "status": candidate.status,
                }
            )

        if candidate.role == "primary":
            lane = lane.model_copy(
                update={
                    "angles": lane.angles or primary_angles,
                    "research_pack": lane.research_pack or primary_research_pack,
                    "argument_map": lane.argument_map or primary_argument_map,
                    "scripting": lane.scripting or primary_scripting,
                    "visual_plan": lane.visual_plan or primary_visual_plan,
                    "production_brief": lane.production_brief or primary_production_brief,
                    "packaging": lane.packaging or primary_packaging,
                    "qc_gate": lane.qc_gate or primary_qc_gate,
                    "publish_items": lane.publish_items or list(primary_publish_items or []),
                }
            )

        lane_contexts.append(lane)

    return lane_contexts


def _derive_legacy_primary_idea_id(ctx: PipelineContext) -> str:
    for idea_id in (
        getattr(ctx.angles, "idea_id", ""),
        getattr(ctx.research_pack, "idea_id", ""),
        getattr(ctx.argument_map, "idea_id", ""),
        getattr(ctx.visual_plan, "idea_id", ""),
        getattr(ctx.production_brief, "idea_id", ""),
        getattr(ctx.packaging, "idea_id", ""),
        getattr(ctx.publish_item, "idea_id", ""),
        ctx.publish_items[0].idea_id if ctx.publish_items else "",
    ):
        if idea_id:
            return idea_id
    return ""


# ---------------------------------------------------------------------------
# Pipeline stage definitions
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
    "generate_angles": "Generating angles",
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
# Backlog AI Triage (batch operations)
# ---------------------------------------------------------------------------


class TriageOperationKind(str):
    """Kinds of batch triage proposals."""

    BATCH_ENRICH = "batch_enrich"
    BATCH_REFRAME = "batch_reframe"
    DEDUPE_RECOMMENDATION = "dedupe_recommendation"
    ARCHIVE_RECOMMENDATION = "archive_recommendation"
    PRIORITY_RECOMMENDATION = "priority_recommendation"


class TriageOperation(BaseModel):
    """A single triage operation proposed by the batch triage agent."""

    kind: Literal[
        "batch_enrich",
        "batch_reframe",
        "dedupe_recommendation",
        "archive_recommendation",
        "priority_recommendation",
    ]
    idea_ids: list[str] = Field(default_factory=list)
    reason: str = ""
    fields: dict[str, Any] = Field(default_factory=dict)
    preferred_idea_id: str | None = None  # for dedupe: which item to keep


class TriageResponse(BaseModel):
    """Structured response from the batch triage agent."""

    reply_markdown: str
    proposals: list[TriageOperation] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    mentioned_idea_ids: list[str] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Managed Brief Domain (Phase 01 - Persistent Brief)
# ---------------------------------------------------------------------------


class BriefLifecycleState(StrEnum):
    """Lifecycle states for a managed opportunity brief.

    draft       - Initial state; AI-generated or operator-created, not yet approved.
    approved    - Reviewed and approved; ready to drive backlog generation.
    superseded  - Replaced by a newer approved brief (rare; for long-running campaigns).
    archived    - No longer active; retained for audit trail.
    """

    DRAFT = "draft"
    APPROVED = "approved"
    SUPERSEDED = "superseded"
    ARCHIVED = "archived"


class BriefProvenance(StrEnum):
    """How a brief entered the managed brief system.

    generated      - Created by the AI pipeline (stage 1 output).
    imported       - Hydrated from a legacy saved PipelineContext payload.
    cloned         - Copied from an existing managed brief for reuse.
    branched       - Created as a derivative for a different theme/channel.
    operator_created - Manually authored by an operator.
    """

    GENERATED = "generated"
    IMPORTED = "imported"
    CLONED = "cloned"
    BRANCHED = "branched"
    OPERATOR_CREATED = "operator_created"


# ---------------------------------------------------------------------------
# Phase 02 - Pipeline Brief Reference
# ---------------------------------------------------------------------------


class PipelineBriefReference(BaseModel):
    """Reference to a managed opportunity brief used by a pipeline run.

    This establishes an explicit, auditable link between a pipeline run and
    the specific managed brief revision it used. The snapshot field preserves
    the brief content for portability and inspection even if the managed brief
    later changes.

    Design principles
    ------------------
    - The reference is authoritative: if set, downstream work should prefer
      the managed brief revision over any inline snapshot.
    - The snapshot is for observability: it lets operators inspect what the
      run actually used without loading the managed brief store.
    - Revision pinning is explicit: a run always records which revision_id it
      used, preventing silent rebinding to newer heads during resume.
    """

    brief_id: str = Field(
        default="",
        description="The managed brief resource ID (e.g. 'mbrief_abc123').",
    )
    revision_id: str = Field(
        default="",
        description="The specific revision ID this run referenced.",
    )
    revision_version: int = Field(
        default=0,
        description="Human-readable version number for display (e.g. 3 for 'v3').",
    )
    # Snapshot of the brief content at the time of reference for portability
    snapshot: OpportunityBrief | None = Field(
        default=None,
        description="Inline brief snapshot for observability and portability.",
    )
    # Lifecycle state at the time this reference was created
    lifecycle_state: BriefLifecycleState = Field(
        default=BriefLifecycleState.DRAFT,
        description="Brief lifecycle state at time of pipeline run.",
    )
    # Source of this reference
    reference_type: Literal["managed", "inline_fallback", "imported"] = Field(
        default="managed",
        description="Whether this run was started from managed brief, inline payload, or legacy import.",
    )
    # For resume/clone flows: which brief revision was explicitly selected
    seeded_from_revision_id: str = Field(
        default="",
        description="For seeded runs: the revision ID that was explicitly chosen to seed this run.",
    )
    created_at: str = Field(
        default="",
        description="ISO timestamp when this reference was created.",
    )
    # P2-T2: Whether this brief was generated in the same pipeline run
    # If True, gate will not block since the brief is being actively developed
    was_generated_in_run: bool = Field(
        default=False,
        description="True if this brief was generated in the current pipeline run.",
    )

    def is_approved(self) -> bool:
        """Return True if this brief reference was approved at time of use."""
        return self.lifecycle_state == BriefLifecycleState.APPROVED

    def is_draft(self) -> bool:
        """Return True if this brief reference was in draft state at time of use."""
        return self.lifecycle_state == BriefLifecycleState.DRAFT


class BriefRevision(BaseModel):
    """An immutable snapshot of an OpportunityBrief at a point in time.

    Each revision captures the full editorial state plus provenance metadata
    for that specific revision. Revisions are never modified after creation.
    """

    revision_id: str = Field(
        default_factory=lambda: f"rev_{uuid4().hex[:10]}",
        description="Unique identifier for this specific revision.",
    )
    brief_id: str = Field(
        description="The managed brief resource this revision belongs to.",
    )
    version: int = Field(
        description="Monotonically increasing version number within the brief.",
    )
    # Full snapshot of OpportunityBrief content at this revision
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
    # Provenance
    provenance: BriefProvenance = Field(
        default=BriefProvenance.GENERATED,
        description="How this revision was created.",
    )
    # Source tracking (original generated vs operator-edited)
    is_generated: bool = Field(
        default=True,
        description="True = AI-generated content, False = operator-created or heavily edited.",
    )
    # Revision metadata
    revision_notes: str = Field(
        default="",
        description="Human-readable description of what changed in this revision.",
    )
    source_pipeline_id: str = Field(
        default="",
        description="Pipeline ID that generated this revision, if applicable.",
    )
    created_at: str = Field(
        default="",
        description="ISO timestamp when this revision was created.",
    )


class ManagedOpportunityBrief(BaseModel):
    """A durable, version-aware opportunity brief resource.

    This is the canonical persisted shape for an opportunity brief, separated
    from any single pipeline run. It tracks lifecycle state, maintains a revision
    history, and owns the current head pointer.

    Design principles
    ------------------
    - Immutable revisions: each BriefRevision is append-only and never modified.
    - Current head: ``current_revision_id`` points to the active revision.
    - Lifecycle is on the resource, not individual revisions.
    - Provenance tracks how the first revision entered the system.
    """

    brief_id: str = Field(
        default_factory=lambda: f"mbrief_{uuid4().hex[:8]}",
        description="Stable resource identifier, unique across the system.",
    )
    title: str = Field(
        default="",
        description="Short human-readable title for the brief.",
    )
    # Lifecycle
    lifecycle_state: BriefLifecycleState = Field(
        default=BriefLifecycleState.DRAFT,
        description="Current lifecycle state of this brief resource.",
    )
    # Revision tracking
    current_revision_id: str = Field(
        default="",
        description="ID of the currently active revision (head).",
    )
    latest_revision_id: str = Field(
        default="",
        description="ID of the most recently created revision (may differ from current_revision_id during review).",
    )
    revision_count: int = Field(
        default=0,
        description="Total number of revisions this brief has had.",
    )
    # Provenance of the first revision
    provenance: BriefProvenance = Field(
        default=BriefProvenance.GENERATED,
        description="How the initial brief entered the system.",
    )
    # Timestamps - set by service layer when persisting
    created_at: str = Field(
        default="",
        description="ISO timestamp when this brief resource was first created.",
    )
    updated_at: str = Field(
        default="",
        description="ISO timestamp when this brief or its head revision was last modified.",
    )
    # Human-readable change log (revision summaries)
    revision_history: list[str] = Field(
        default_factory=list,
        description="Change log entries describing what was revised.",
    )
    # Lineage tracking for branched/cloned briefs
    source_brief_id: str = Field(
        default="",
        description="The brief_id this was branched or cloned from, if any.",
    )
    branch_reason: str = Field(
        default="",
        description="Why this brief was branched (e.g., 'different channel', 'experiment').",
    )

    def head_revision(self, revisions: list[BriefRevision]) -> BriefRevision | None:
        """Return the current head revision from a list of known revisions."""
        if not self.current_revision_id:
            return None
        return next((r for r in revisions if r.revision_id == self.current_revision_id), None)


class ManagedBriefOutput(BaseModel):
    """Container for listing and loading managed briefs."""

    briefs: list[ManagedOpportunityBrief] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Phase 02 - Brief Execution Gates
# ---------------------------------------------------------------------------


class BriefExecutionPolicyMode(StrEnum):
    """Policy modes for brief approval gates.

    These modes control whether downstream execution can proceed based on
    the brief's lifecycle state at pipeline start.

    DEFAULT_APPROVED    - Only approved briefs can proceed past planning.
                          Draft briefs are blocked with a clear error.
    ALLOW_DRAFT         - Draft briefs can proceed through all stages.
                          Warnings are issued but execution continues.
    ALLOW_ANY           - Any brief state can proceed. No gates, no warnings.
                          Use for development and debugging only.
    """

    DEFAULT_APPROVED = "default_approved"  # Default for production
    ALLOW_DRAFT = "allow_draft"  # For internal iterations
    ALLOW_ANY = "allow_any"  # For development/debugging


class BriefExecutionGate(BaseModel):
    """Approval-aware execution gate for brief-controlled pipelines.

    This gate is checked at pipeline start and at key stage transitions
    to enforce brief approval requirements. It provides explicit,
    operator-visible signals about the brief state used for each run.

    Design principles
    ------------------
    - Gate is checked at pipeline initialization, not just at stage transitions.
    - Warnings surface at the start so operators know what state they're using.
    - Errors are clear and actionable, not silently ignored.
    - Policy modes are few and explicit to avoid hidden surprises.
    """

    # Current policy mode
    policy_mode: BriefExecutionPolicyMode = Field(
        default=BriefExecutionPolicyMode.DEFAULT_APPROVED,
        description="Current gate enforcement policy.",
    )
    # Brief state at pipeline start
    brief_state_at_start: BriefLifecycleState = Field(
        default=BriefLifecycleState.DRAFT,
        description="Brief lifecycle state when the pipeline was initialized.",
    )
    # Whether the gate has been satisfied for this run
    is_satisfied: bool = Field(
        default=False,
        description="True if the current brief state satisfies the policy requirements.",
    )
    # Warning messages for operator visibility
    warnings: list[str] = Field(
        default_factory=list,
        description="Warning messages when running with non-approved brief.",
    )
    # Error message if gate failed
    error_message: str = Field(
        default="",
        description="Error message if the gate blocked execution.",
    )
    # Stage index where gate was checked
    checked_at_stage: int = Field(
        default=-1,
        description="Stage index where the gate was last checked.",
    )
    # Whether execution was blocked by this gate
    was_blocked: bool = Field(
        default=False,
        description="True if execution was blocked by this gate.",
    )

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
        """Return True if the given stage requires an approved brief.

        Stages before build_backlog (planning stages) don't require approval.
        Stages from build_backlog onward should use approved briefs in
        DEFAULT_APPROVED mode.
        """
        approval_stages = {
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
        }
        return stage_name in approval_stages

    def check_gate(self, brief_state: BriefLifecycleState, stage_name: str) -> tuple[bool, str]:
        """Check if execution can proceed given the brief state.

        Args:
            brief_state: Current brief lifecycle state.
            stage_name: Name of the current pipeline stage.

        Returns:
            Tuple of (can_proceed, message) where:
            - can_proceed is True if execution can continue
            - message is a human-readable reason for the decision
        """
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
# Phase 01 - Seven-Phase Operating Model
# ---------------------------------------------------------------------------


class OperatingPhase(StrEnum):
    """Canonical seven-phase operating model for content generation.

    This replaces the 14-stage view with a compressed, operator-friendly
    grouping that aligns with how teams actually think about content work.
    """

    PHASE_01_STRATEGY = "phase_01_strategy"
    PHASE_02_OPPORTUNITY = "phase_02_opportunity"
    PHASE_03_RESEARCH = "phase_03_research"
    PHASE_04_DRAFT = "phase_04_draft"
    PHASE_05_VISUAL = "phase_05_visual"
    PHASE_06_QC = "phase_06_qc"
    PHASE_07_PUBLISH = "phase_07_publish"


OPERATING_PHASE_LABELS: dict[OperatingPhase, str] = {
    OperatingPhase.PHASE_01_STRATEGY: "Strategy & Setup",
    OperatingPhase.PHASE_02_OPPORTUNITY: "Opportunity & Ideation",
    OperatingPhase.PHASE_03_RESEARCH: "Research & Argument",
    OperatingPhase.PHASE_04_DRAFT: "Draft & Refinement",
    OperatingPhase.PHASE_05_VISUAL: "Visual & Production",
    OperatingPhase.PHASE_06_QC: "QC & Approval",
    OperatingPhase.PHASE_07_PUBLISH: "Publish & Learn",
}


# Stage-to-phase mapping: which phase each of the 14 pipeline stages belongs to
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


def get_phase_for_stage(stage_name: str) -> OperatingPhase:
    """Return the operating phase for a given pipeline stage."""
    return STAGE_TO_PHASE_MAPPING.get(stage_name, OperatingPhase.PHASE_02_OPPORTUNITY)


def get_stages_for_phase(phase: OperatingPhase) -> list[str]:
    """Return the list of pipeline stages for a given operating phase."""
    return PHASE_TO_STAGES_MAPPING.get(phase, [])


class PhaseExitCriteria(BaseModel):
    """Exit criteria for completing a phase."""

    description: str = Field(
        default="",
        description="Human-readable description of what constitutes phase completion.",
    )
    required_artifacts: list[str] = Field(
        default_factory=list,
        description="List of artifact names that must be present to exit the phase.",
    )
    quality_threshold: float | None = Field(
        default=None,
        description="Optional quality score threshold to meet before exiting.",
    )


class PhaseSkipCondition(BaseModel):
    """Condition under which a phase can be skipped."""

    reason: str = Field(
        default="",
        description="Human-readable reason why the phase can be skipped.",
    )
    requires_manual_override: bool = Field(
        default=False,
        description="Whether operator confirmation is required to skip.",
    )
    preserves_quality: bool = Field(
        default=True,
        description="Whether skipping this phase preserves output quality.",
    )


class PhaseKillCondition(BaseModel):
    """Condition under which a phase should be terminated early."""

    reason: str = Field(
        default="",
        description="Human-readable reason why the phase should be killed.",
    )
    abort_pipeline: bool = Field(
        default=False,
        description="Whether killing this phase should abort the entire pipeline.",
    )
    preserve_artifacts: bool = Field(
        default=True,
        description="Whether to preserve partial artifacts even when killed.",
    )


class PhaseReuseOpportunity(BaseModel):
    """Opportunity to reuse phase outputs across runs."""

    description: str = Field(
        default="",
        description="What can be reused from this phase.",
    )
    reuse_pattern: str = Field(
        default="",
        description="How to reuse (e.g., 'cache', 'template', 'reference').",
    )
    ttl_hours: int | None = Field(
        default=None,
        description="How long reuse is valid (None = until next strategy update).",
    )


class OperatingPhasePolicy(BaseModel):
    """Typed governance metadata for one operating phase.

    This model captures the explicit workflow rules that were previously
    only documented in prose, making them machine-readable and
    enforceable in traces and managed briefs.
    """

    phase: OperatingPhase = Field(
        description="Which operating phase this policy governs.",
    )
    phase_label: str = Field(
        description="Human-readable phase name.",
    )
    owner: str = Field(
        default="",
        description="Who is responsible for this phase (role or team).",
    )
    # SLA: max turnaround time in minutes
    max_turnaround_minutes: int = Field(
        default=60,
        description="Expected maximum turnaround time for this phase in minutes.",
    )
    # Entry criteria: what must be true before this phase starts
    entry_criteria: list[str] = Field(
        default_factory=list,
        description="List of conditions that must be true before phase execution.",
    )
    # Exit criteria: what must be true before moving to next phase
    exit_criteria: PhaseExitCriteria = Field(
        default_factory=PhaseExitCriteria,
        description="Criteria for successfully completing this phase.",
    )
    # Skip conditions: when this phase can be bypassed
    skip_conditions: list[PhaseSkipCondition] = Field(
        default_factory=list,
        description="Conditions under which this phase can be skipped.",
    )
    # Kill conditions: when this phase should terminate early
    kill_conditions: list[PhaseKillCondition] = Field(
        default_factory=list,
        description="Conditions under which this phase should be killed.",
    )
    # Reuse opportunities: how outputs can be leveraged
    reuse_opportunities: list[PhaseReuseOpportunity] = Field(
        default_factory=list,
        description="Opportunities to reuse phase outputs in future runs.",
    )


# Default operating phase policies
DEFAULT_PHASE_POLICIES: dict[OperatingPhase, OperatingPhasePolicy] = {
    OperatingPhase.PHASE_01_STRATEGY: OperatingPhasePolicy(
        phase=OperatingPhase.PHASE_01_STRATEGY,
        phase_label="Strategy & Setup",
        owner="content lead",
        max_turnaround_minutes=5,
        entry_criteria=["strategy memory exists"],
        exit_criteria=PhaseExitCriteria(
            description="Strategy memory loaded and validated",
            required_artifacts=["strategy"],
        ),
        skip_conditions=[],
        kill_conditions=[
            PhaseKillCondition(
                reason="Strategy memory is corrupted",
                abort_pipeline=False,
                preserve_artifacts=True,
            ),
        ],
        reuse_opportunities=[
            PhaseReuseOpportunity(
                description="Strategy memory persists across all runs",
                reuse_pattern="persistent_store",
            ),
        ],
    ),
    OperatingPhase.PHASE_02_OPPORTUNITY: OperatingPhasePolicy(
        phase=OperatingPhase.PHASE_02_OPPORTUNITY,
        phase_label="Opportunity & Ideation",
        owner="senior editor",
        max_turnaround_minutes=120,
        entry_criteria=[
            "strategy memory loaded",
            "theme defined",
        ],
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
            PhaseKillCondition(
                reason="No ideas score above production threshold",
                abort_pipeline=False,
                preserve_artifacts=True,
            ),
            PhaseKillCondition(
                reason="All ideas killed during scoring",
                abort_pipeline=True,
                preserve_artifacts=True,
            ),
        ],
        reuse_opportunities=[
            PhaseReuseOpportunity(
                description="Scored backlog can be cached for 24 hours",
                reuse_pattern="cache",
                ttl_hours=24,
            ),
        ],
    ),
    OperatingPhase.PHASE_03_RESEARCH: OperatingPhasePolicy(
        phase=OperatingPhase.PHASE_03_RESEARCH,
        phase_label="Research & Argument",
        owner="research lead",
        max_turnaround_minutes=180,
        entry_criteria=[
            "angle selected",
            "opportunity brief approved or in review",
        ],
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
            PhaseKillCondition(
                reason="Research pack has zero usable claims",
                abort_pipeline=False,
                preserve_artifacts=True,
            ),
            PhaseKillCondition(
                reason="All claims flagged as unsafe with no safe alternative",
                abort_pipeline=True,
                preserve_artifacts=True,
            ),
        ],
        reuse_opportunities=[
            PhaseReuseOpportunity(
                description="Research pack can be reused within same opportunity",
                reuse_pattern="cache",
                ttl_hours=168,  # 1 week
            ),
        ],
    ),
    OperatingPhase.PHASE_04_DRAFT: OperatingPhasePolicy(
        phase=OperatingPhase.PHASE_04_DRAFT,
        phase_label="Draft & Refinement",
        owner="script writer",
        max_turnaround_minutes=240,
        entry_criteria=[
            "argument map complete",
            "beat plan defined",
        ],
        exit_criteria=PhaseExitCriteria(
            description="Final script passed QC with all beats complete",
            required_artifacts=["scripting"],
            quality_threshold=0.7,
        ),
        skip_conditions=[],
        kill_conditions=[
            PhaseKillCondition(
                reason="Script failed QC after maximum iterations",
                abort_pipeline=False,
                preserve_artifacts=True,
            ),
            PhaseKillCondition(
                reason="All beats marked as failed in targeted revision",
                abort_pipeline=True,
                preserve_artifacts=True,
            ),
        ],
        reuse_opportunities=[
            PhaseReuseOpportunity(
                description="Stable beats from iterative revision can be preserved",
                reuse_pattern="template",
            ),
        ],
    ),
    OperatingPhase.PHASE_05_VISUAL: OperatingPhasePolicy(
        phase=OperatingPhase.PHASE_05_VISUAL,
        phase_label="Visual & Production",
        owner="production lead",
        max_turnaround_minutes=60,
        entry_criteria=[
            "script finalized (QC passed or tightened)",
        ],
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
            PhaseKillCondition(
                reason="Visual plan references missing assets",
                abort_pipeline=False,
                preserve_artifacts=True,
            ),
        ],
        reuse_opportunities=[
            PhaseReuseOpportunity(
                description="Production brief templates for recurring shoot setups",
                reuse_pattern="template",
            ),
        ],
    ),
    OperatingPhase.PHASE_06_QC: OperatingPhasePolicy(
        phase=OperatingPhase.PHASE_06_QC,
        phase_label="QC & Approval",
        owner="quality lead",
        max_turnaround_minutes=30,
        entry_criteria=[
            "production brief complete",
            "packaging variants generated",
        ],
        exit_criteria=PhaseExitCriteria(
            description="Human QC approved with no blocking must-fix items",
            required_artifacts=["packaging", "qc_gate"],
        ),
        skip_conditions=[],
        kill_conditions=[
            PhaseKillCondition(
                reason="Human QC blocked with must-fix items not resolved",
                abort_pipeline=False,
                preserve_artifacts=True,
            ),
        ],
        reuse_opportunities=[
            PhaseReuseOpportunity(
                description="QC checklist templates for recurring issue patterns",
                reuse_pattern="template",
            ),
        ],
    ),
    OperatingPhase.PHASE_07_PUBLISH: OperatingPhasePolicy(
        phase=OperatingPhase.PHASE_07_PUBLISH,
        phase_label="Publish & Learn",
        owner="distribution lead",
        max_turnaround_minutes=15,
        entry_criteria=[
            "QC approved",
        ],
        exit_criteria=PhaseExitCriteria(
            description="Publish items scheduled with engagement actions",
            required_artifacts=["publish_items"],
        ),
        skip_conditions=[],
        kill_conditions=[
            PhaseKillCondition(
                reason="Platform constraints violated by latest changes",
                abort_pipeline=False,
                preserve_artifacts=True,
            ),
        ],
        reuse_opportunities=[
            PhaseReuseOpportunity(
                description="Publish scheduling patterns inform future timing",
                reuse_pattern="learning",
            ),
        ],
    ),
}


def get_phase_policy(phase: OperatingPhase) -> OperatingPhasePolicy:
    """Get the operating policy for a phase."""
    return DEFAULT_PHASE_POLICIES.get(phase, OperatingPhasePolicy(phase=phase, phase_label=phase.value))
