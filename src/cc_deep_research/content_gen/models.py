"""Data models for the content generation workflow."""

from __future__ import annotations

from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field


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


class SavedScriptRun(BaseModel):
    """Metadata for a persisted scripting run."""

    run_id: str
    saved_at: str
    raw_idea: str = ""
    word_count: int = 0
    script_path: str
    context_path: str


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
# Pipeline stage 1: Backlog builder
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


class BacklogOutput(BaseModel):
    """Output of the backlog builder stage."""

    items: list[BacklogItem] = Field(default_factory=list)
    rejected_count: int = 0
    rejection_reasons: list[str] = Field(default_factory=list)


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
    hold: list[str] = Field(default_factory=list)  # idea_ids
    killed: list[str] = Field(default_factory=list)  # idea_ids


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
    backlog: BacklogOutput | None = None
    scoring: ScoringOutput | None = None
    angles: AngleOutput | None = None
    research_pack: ResearchPack | None = None
    scripting: ScriptingContext | None = None
    visual_plan: VisualPlanOutput | None = None
    production_brief: ProductionBrief | None = None
    packaging: PackagingOutput | None = None
    qc_gate: HumanQCGate | None = None
    publish_item: PublishItem | None = None
    performance: PerformanceAnalysis | None = None


# ---------------------------------------------------------------------------
# Pipeline stage definitions
# ---------------------------------------------------------------------------


PIPELINE_STAGES: list[str] = [
    "load_strategy",
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
