"""Data models for the content generation workflow.

Contract Version: 1.4.0

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

from pydantic import BaseModel, Field, field_validator, model_validator

from cc_deep_research.models.search import QueryProvenance

CONTRACT_VERSION = "1.4.0"


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
        contract_version="1.1.0",
        parser_location="agents/research_pack.py::_parse_research_pack",
        output_model="ResearchPack",
        format_notes=(
            "Structured findings/claims/flag blocks reference source_ids from the "
            "prompt-provided source catalog; the model retains backward-compatible "
            "legacy list views for downstream consumers."
        ),
        required_fields=(),
        expected_sections=(
            "findings",
            "claims",
            "counterpoints",
            "uncertainty_flags",
            "assets_needed",
            "research_stop_reason",
        ),
        failure_mode="tolerant",
    ),
    "build_argument_map": ContentGenStageContract(
        stage_name="build_argument_map",
        prompt_module="prompts/argument_map.py",
        contract_version="1.0.0",
        parser_location="agents/argument_map.py::_parse_argument_map",
        output_model="ArgumentMap",
        format_notes=(
            "Scalar thesis fields followed by repeated '---' blocks for proof_anchors, "
            "counterarguments, safe_claims, unsafe_claims, and beat_claim_plan. "
            "Beat and claim records reference explicit proof_id/claim_id identifiers."
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
        ),
        failure_mode="fail_fast",
    ),
    "run_scripting": ContentGenStageContract(
        stage_name="run_scripting",
        prompt_module="prompts/scripting.py",
        contract_version="1.1.0",
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
        contract_version="1.1.0",
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
    status: str = "backlog"  # backlog | selected | runner_up | in_production | published | archived
    latest_score: int | None = None
    latest_recommendation: str = ""
    selection_reasoning: str = ""
    expertise_reason: str = ""
    genericity_risk: str = ""
    proof_gap_note: str = ""
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
    active_candidates: list[PipelineCandidate] = Field(default_factory=list)
    hold: list[str] = Field(default_factory=list)  # idea_ids
    killed: list[str] = Field(default_factory=list)  # idea_ids
    is_degraded: bool = False
    degradation_reason: str = ""

    @model_validator(mode="after")
    def _populate_active_candidates(self) -> ScoringOutput:
        self.active_candidates = _derive_pipeline_candidates(
            selected_idea_id=self.selected_idea_id,
            shortlist=self.shortlist,
            runner_up_idea_ids=self.runner_up_idea_ids,
            existing_candidates=self.active_candidates,
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


class RetrievalMode(StrEnum):
    """Retrieval strategy mode for the planner."""

    BASELINE = "baseline"  # Standard breadth: 6 families, balanced
    DEEP = "deep"  # Widen to cover gaps: additional queries per family
    TARGETED = "targeted"  # Narrow focus: specific evidence gaps
    CONTRARIAN = "contrarian"  # Emphasize counterevidence and pushback


class RetrievalDecision(BaseModel):
    """Single query decision from the retrieval planner."""

    family: str = Field(..., description="Query family label (e.g. proof, contrarian)")
    intent_tags: list[str] = Field(default_factory=list)
    query: str = Field(..., description="The actual search query string")
    mode: RetrievalMode = Field(default=RetrievalMode.BASELINE)
    rationale: str = Field(default="", description="Why this query was chosen")
    priority: int = Field(default=0, description="Higher = more important, runs first")


class RetrievalBudget(BaseModel):
    """Explicit budget for bounding retrieval search volume."""

    max_queries: int = Field(default=6, ge=1, le=50)
    max_sources: int = Field(default=12, ge=1, le=100)
    max_results_per_query: int = Field(default=5, ge=1, le=20)
    stop_if_sources_seen: int | None = Field(default=None, description="Stop early if N sources already collected")
    stop_on_family_count: int | None = Field(
        default=None, description="Stop per family after N queries (for deep mode)"
    )


class RetrievalPlan(BaseModel):
    """Complete retrieval plan from the adaptive planner."""

    decisions: list[RetrievalDecision] = Field(default_factory=list)
    budget: RetrievalBudget = Field(default_factory=RetrievalBudget)
    mode: RetrievalMode = Field(default=RetrievalMode.BASELINE)
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
    unsupported_claims: list[str] = Field(default_factory=list)
    risky_claims: list[str] = Field(default_factory=list)
    required_fact_checks: list[str] = Field(default_factory=list)
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
    evidence_coverage: float = Field(default=0.0, ge=0.0, le=1.0)
    claim_safety: float = Field(default=0.0, ge=0.0, le=1.0)
    originality: float = Field(default=0.0, ge=0.0, le=1.0)
    precision: float = Field(default=0.0, ge=0.0, le=1.0)
    expertise_density: float = Field(default=0.0, ge=0.0, le=1.0)
    critical_issues: list[str] = Field(default_factory=list)
    unsupported_claims: list[str] = Field(default_factory=list)
    evidence_actions_required: list[str] = Field(default_factory=list)
    improvement_suggestions: list[str] = Field(default_factory=list)
    research_gaps_identified: list[str] = Field(default_factory=list)
    rationale: str = ""
    iteration_number: int = 1

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
