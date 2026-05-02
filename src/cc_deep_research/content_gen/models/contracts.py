"""Pipeline-level contracts and stage metadata."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

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
        prompt_module="prompts/thesis.py",
        contract_version="2.0.0",
        parser_location="agents/thesis.py::_parse_thesis_artifact",
        output_model="ThesisArtifact",
        format_notes=(
            "P3-T2: This stage produces a unified thesis artifact that combines "
            "angle selection with argument design in one pass. The output includes "
            "selected angle fields (target_audience, viewer_problem, core_promise, etc.) "
            "alongside the thesis structure (thesis, audience_belief_to_challenge, "
            "core_mechanism, proof_anchors, safe_claims, beat_claim_plan, etc.). "
            "Repeated '---' blocks for proof_anchors, counterarguments, claims, and beats. "
            "Scalar fields for angle metadata and thesis core."
        ),
        required_fields=(
            "angle_id",
            "target_audience",
            "viewer_problem",
            "core_promise",
            "primary_takeaway",
            "thesis",
            "audience_belief_to_challenge",
            "core_mechanism",
        ),
        expected_sections=(
            "proof_anchors",
            "counterarguments",
            "safe_claims",
            "unsafe_claims",
            "beat_claim_plan",
            "selection_reasoning",
            "what_this_contributes",
            "genericity_flags",
            "differentiation_stategy",
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
            "P3-T2: DEPRECATED - Argument map is now produced as part of ThesisArtifact "
            "in the generate_angles stage. This stage is kept for backward compatibility "
            "and populates argument_map field from thesis_artifact when available. "
            "The unified thesis artifact combines angle selection with argument design."
        ),
        required_fields=(
            "thesis",
            "angle_id",
        ),
        expected_sections=(
            "proof_anchors",
            "counterarguments",
            "claims",
            "beat_plan",
            "evidence_gaps",
        ),
        failure_mode="tolerant",
    ),
    "run_scripting": ContentGenStageContract(
        stage_name="run_scripting",
        prompt_module="prompts/scripting.py",
        contract_version="1.2.0",
        parser_location="agents/scripting.py::_parse_scripting_context",
        output_model="ScriptingContext",
        format_notes=(
            "Unified script output per step. Step 1 emits Topic/Outcome/Audience, "
            "Step 2 emits Angle/Content Type/Core Tension, Step 3 emits Chosen Structure/Beat List, "
            "Step 4 emits grounded beat blocks, Step 5 emits numbered hooks with Best Hook, "
            "Step 6 emits the script body, Steps 7-9 handle retention/tightening/visual notes "
            "with section markers, Step 10 emits Pass/Fail QC checks."
        ),
        required_fields=("idea_id",),
        expected_sections=(
            "Topic",
            "Outcome",
            "Audience",
            "Angle",
            "Chosen Structure",
            "Beat List",
            "Best Hook",
            "Revised Script",
            "Tightened Script",
        ),
        failure_mode="fail_fast",
    ),
    "visual_translation": ContentGenStageContract(
        stage_name="visual_translation",
        prompt_module="prompts/visual.py",
        contract_version="1.0.0",
        parser_location="agents/visual.py::_parse_visual_plan",
        output_model="VisualPlanOutput",
        format_notes="Beat-level visual spec per spoken beat.",
        required_fields=("idea_id",),
        expected_sections=(
            "beat",
            "visual",
            "shot_type",
        ),
        failure_mode="tolerant",
    ),
    "production_brief": ContentGenStageContract(
        stage_name="production_brief",
        prompt_module="prompts/execution_brief.py",
        contract_version="1.0.0",
        parser_location="agents/execution_brief.py::_parse_production_brief",
        output_model="ProductionBrief",
        format_notes="Per-beat production notes.",
        required_fields=("idea_id",),
        expected_sections=(
            "location",
            "setup",
            "wardrobe",
            "props",
        ),
        failure_mode="tolerant",
    ),
    "packaging": ContentGenStageContract(
        stage_name="packaging",
        prompt_module="prompts/packaging.py",
        contract_version="1.1.0",
        parser_location="agents/packaging.py::_parse_packaging_output",
        output_model="PackagingOutput",
        format_notes="Per-platform packaging with hooks, captions, hashtags.",
        required_fields=("idea_id",),
        expected_sections=(
            "platform",
            "primary_hook",
            "caption",
            "hashtags",
        ),
        failure_mode="tolerant",
    ),
    "human_qc": ContentGenStageContract(
        stage_name="human_qc",
        prompt_module="prompts/qc.py",
        contract_version="1.2.0",
        parser_location="agents/qc.py::_parse_qc_gate",
        output_model="HumanQCGate",
        format_notes="Structured QC output with issue categories.",
        required_fields=(),
        expected_sections=(
            "hook_strength",
            "factual_issues",
            "unsupported_claims",
            "must_fix_items",
        ),
        failure_mode="human_gated",
    ),
    "publish_queue": ContentGenStageContract(
        stage_name="publish_queue",
        prompt_module="prompts/next_action.py",
        contract_version="1.0.0",
        parser_location="agents/next_action.py::_parse_publish_item",
        output_model="PublishItem",
        format_notes="Single publish entry per platform.",
        required_fields=("idea_id",),
        expected_sections=(
            "platform",
            "publish_datetime",
            "caption",
        ),
        failure_mode="fail_fast",
    ),
    "performance_analysis": ContentGenStageContract(
        stage_name="performance_analysis",
        prompt_module="prompts/performance.py",
        contract_version="1.1.0",
        parser_location="agents/performance.py::_parse_performance_analysis",
        output_model="PerformanceAnalysis",
        format_notes="Post-publish analysis with lessons and next steps.",
        required_fields=("video_id",),
        expected_sections=(
            "what_worked",
            "what_failed",
            "lesson",
            "next_test",
        ),
        failure_mode="tolerant",
    ),
}
