"""Data models for the content generation workflow.

Contract Version: 1.0.0

This module defines the data contracts for each pipeline stage. Each model
represents the expected output format from its corresponding agent.

When updating prompts, ensure the corresponding parser remains compatible
with the model's fields. Major format changes should bump the CONTRACT_VERSION.
The canonical inventory of prompt/parser contracts lives in
``CONTENT_GEN_STAGE_CONTRACTS`` below.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal
from uuid import uuid4

from pydantic import BaseModel, Field

CONTRACT_VERSION = "1.0.0"


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
        contract_version="1.0.0",
        parser_location="agents/opportunity.py::_parse_opportunity_brief",
        output_model="OpportunityBrief",
        format_notes="Header-based scalar fields plus '-' list sections.",
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
        ),
        failure_mode="fail_fast",
    ),
    "build_backlog": ContentGenStageContract(
        stage_name="build_backlog",
        prompt_module="prompts/backlog.py",
        contract_version="1.0.0",
        parser_location="agents/backlog.py::_parse_backlog_items",
        output_model="BacklogOutput",
        format_notes="Repeated '---' blocks with field_name: value pairs.",
        required_fields=("idea",),
        expected_sections=(
            "category",
            "audience",
            "problem",
            "source",
            "why_now",
            "potential_hook",
            "content_type",
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
        contract_version="1.0.0",
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
        contract_version="1.0.0",
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
        contract_version="1.0.0",
        parser_location="agents/research_pack.py::_parse_research_pack",
        output_model="ResearchPack",
        format_notes="Named list sections with a trailing research_stop_reason field.",
        required_fields=(),
        expected_sections=(
            "audience_insights",
            "competitor_observations",
            "key_facts",
            "proof_points",
            "examples",
            "case_studies",
            "gaps_to_exploit",
            "assets_needed",
            "claims_requiring_verification",
            "unsafe_or_uncertain_claims",
            "research_stop_reason",
        ),
        failure_mode="tolerant",
    ),
    "run_scripting": ContentGenStageContract(
        stage_name="run_scripting",
        prompt_module="prompts/scripting.py",
        contract_version="1.0.0",
        parser_location="agents/scripting.py::_STEP_HANDLERS and _extract_* helpers",
        output_model="ScriptingContext",
        format_notes="Ten step-specific text contracts; some steps require exact headers, later drafting steps accept freeform script bodies.",
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
        contract_version="1.0.0",
        parser_location="agents/packaging.py::_parse_platform_packages",
        output_model="PackagingOutput",
        format_notes="Repeated '---' platform blocks with scalar fields and '-' list sections.",
        required_fields=("platform", "primary_hook", "caption"),
        expected_sections=(
            "alternate_hooks",
            "cover_text",
            "keywords",
            "hashtags",
            "pinned_comment",
            "cta",
            "version_notes",
        ),
        failure_mode="fail_fast",
    ),
    "human_qc": ContentGenStageContract(
        stage_name="human_qc",
        prompt_module="prompts/qc.py",
        contract_version="1.0.0",
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
        contract_version="1.0.0",
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


class ScriptStructure(BaseModel):
    """Step 3 output: chosen structure and beat list."""

    chosen_structure: str
    why_it_fits: str = ""
    beat_list: list[str]


class BeatIntent(BaseModel):
    """Single beat with name and intent."""

    beat_name: str
    intent: str


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
    past_winners: list[ContentExample] = Field(default_factory=list)
    past_losers: list[ContentExample] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Pipeline stage 1: Opportunity planning
# ---------------------------------------------------------------------------


class OpportunityBrief(BaseModel):
    """Structured planning artifact (stage 1).

    Turns a raw theme into a focused editorial contract that guides
    backlog generation and later scoring.
    """

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


# ---------------------------------------------------------------------------
# Pipeline stage 2: Backlog builder
# ---------------------------------------------------------------------------


class BacklogItem(BaseModel):
    """Single backlog idea (spec stage 1 output)."""

    idea_id: str = Field(default_factory=lambda: uuid4().hex[:8])
    category: str = ""  # trend-responsive | evergreen | authority-building
    idea: str = ""
    audience: str = ""
    problem: str = ""
    source: str = ""
    why_now: str = ""
    potential_hook: str = ""
    content_type: str = ""
    evidence: str = ""
    risk_level: str = "medium"  # low | medium | high
    priority_score: float = 0.0
    status: str = "backlog"  # backlog | selected | in_production | published | archived
    latest_score: int | None = None
    latest_recommendation: str = ""
    selection_reasoning: str = ""
    source_theme: str = ""
    source_pipeline_id: str = ""
    created_at: str = ""
    updated_at: str = ""
    last_scored_at: str = ""


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
    total_score: int = 0
    recommendation: str = "hold"  # produce_now | hold | kill
    reason: str = ""


class ScoringOutput(BaseModel):
    """Output of the idea scorer stage."""

    scores: list[IdeaScores] = Field(default_factory=list)
    produce_now: list[str] = Field(default_factory=list)  # idea_ids
    shortlist: list[str] = Field(default_factory=list)  # ranked idea_ids
    selected_idea_id: str = ""
    selection_reasoning: str = ""
    runner_up_idea_ids: list[str] = Field(default_factory=list)
    hold: list[str] = Field(default_factory=list)  # idea_ids
    killed: list[str] = Field(default_factory=list)  # idea_ids
    is_degraded: bool = False
    degradation_reason: str = ""


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


class AngleOutput(BaseModel):
    """Output of the angle generator stage."""

    idea_id: str = ""
    angle_options: list[AngleOption] = Field(default_factory=list)
    selected_angle_id: str = ""
    selection_reasoning: str = ""


# ---------------------------------------------------------------------------
# Pipeline stage 4: Research pack builder
# ---------------------------------------------------------------------------


class ResearchPack(BaseModel):
    """Compact research pack (spec stage 4)."""

    idea_id: str = ""
    angle_id: str = ""
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


class PackagingOutput(BaseModel):
    """Output of the packaging generator stage."""

    idea_id: str = ""
    platform_packages: list[PlatformPackage] = Field(default_factory=list)


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
    must_fix_items: list[str] = Field(default_factory=list)
    approved_for_publish: bool = False


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
    hook_quality: float = Field(default=0.0, ge=0.0, le=1.0)
    content_clarity: float = Field(default=0.0, ge=0.0, le=1.0)
    factual_accuracy: float = Field(default=0.0, ge=0.0, le=1.0)
    audience_alignment: float = Field(default=0.0, ge=0.0, le=1.0)
    production_readiness: float = Field(default=0.0, ge=0.0, le=1.0)
    critical_issues: list[str] = Field(default_factory=list)
    improvement_suggestions: list[str] = Field(default_factory=list)
    research_gaps_identified: list[str] = Field(default_factory=list)
    rationale: str = ""
    iteration_number: int = 1


class IterationState(BaseModel):
    """State tracking for the iterative content generation loop."""

    current_iteration: int = Field(default=1, ge=1)
    max_iterations: int = Field(default=3, ge=1)
    quality_history: list[QualityEvaluation] = Field(default_factory=list)
    latest_feedback: str = ""
    is_converged: bool = False
    convergence_reason: str = ""
    should_rerun_research: bool = False


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


class PipelineStageTrace(BaseModel):
    """Trace record for one completed pipeline stage."""

    stage_index: int
    stage_name: str
    stage_label: str
    status: str = "completed"  # completed | skipped | failed
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
    """Accumulated state through the full 12-stage content pipeline.

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
    backlog: BacklogOutput | None = None
    scoring: ScoringOutput | None = None
    shortlist: list[str] = Field(default_factory=list)
    selected_idea_id: str = ""
    selection_reasoning: str = ""
    runner_up_idea_ids: list[str] = Field(default_factory=list)
    angles: AngleOutput | None = None
    research_pack: ResearchPack | None = None
    scripting: ScriptingContext | None = None
    visual_plan: VisualPlanOutput | None = None
    production_brief: ProductionBrief | None = None
    packaging: PackagingOutput | None = None
    qc_gate: HumanQCGate | None = None
    publish_item: PublishItem | None = None
    performance: PerformanceAnalysis | None = None
    iteration_state: IterationState | None = None
    stage_traces: list[PipelineStageTrace] = Field(default_factory=list)


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
    "run_scripting": "Running scripting pipeline",
    "visual_translation": "Translating to visuals",
    "production_brief": "Building production brief",
    "packaging": "Generating packaging",
    "human_qc": "Running human QC gate",
    "publish_queue": "Creating publish queue entry",
    "performance_analysis": "Analyzing performance",
}
