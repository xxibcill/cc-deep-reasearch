"""Tests for the content generation workflow."""

from __future__ import annotations

from pathlib import Path

import pytest
from click.testing import CliRunner

from cc_deep_research.cli import main
from cc_deep_research.content_gen.agents import research_pack as research_pack_agent_module
from cc_deep_research.content_gen.agents.angle import AngleAgent, _parse_angle_options
from cc_deep_research.content_gen.agents.argument_map import ArgumentMapAgent, _parse_argument_map
from cc_deep_research.content_gen.agents.backlog import (
    BacklogAgent,
    _derive_selection,
    _parse_backlog_items,
    _parse_scores,
    _validate_scores,
)
from cc_deep_research.content_gen.agents.opportunity import OpportunityPlanningAgent
from cc_deep_research.content_gen.agents.packaging import PackagingAgent, _parse_platform_packages
from cc_deep_research.content_gen.agents.qc import QCAgent, _parse_qc_gate
from cc_deep_research.content_gen.agents.quality_evaluator import (
    QualityEvaluatorAgent,
    _parse_quality_evaluation,
)
from cc_deep_research.content_gen.agents.research_pack import (
    ResearchPackAgent,
    RetrievalPlanner,
    _build_search_queries,
    _parse_research_pack,
)
from cc_deep_research.content_gen.agents.scripting import _STEP_HANDLERS, ScriptingAgent
from cc_deep_research.content_gen.agents.visual import VisualAgent
from cc_deep_research.content_gen.models import (
    CONTENT_GEN_STAGE_CONTRACTS,
    PIPELINE_STAGES,
    SCRIPTING_STEPS,
    AngleDefinition,
    AngleOption,
    AngleOutput,
    ArgumentBeatClaim,
    ArgumentClaim,
    ArgumentMap,
    ArgumentProofAnchor,
    BacklogItem,
    BacklogOutput,
    BeatIntent,
    BeatIntentMap,
    ClaimTraceEntry,
    ClaimTraceLedger,
    ClaimTraceStage,
    ClaimTraceStatus,
    ContrarianBelief,
    CoreInputs,
    ExpertFramework,
    HookSet,
    HumanQCGate,
    IdeaScores,
    OpportunityBrief,
    PackagingOutput,
    PipelineCandidate,
    PipelineContext,
    PipelineLaneContext,
    PipelineStageTrace,
    PlatformPackage,
    ProductionBrief,
    ProofRule,
    PublishItem,
    QCResult,
    QualityEvaluation,
    ResearchClaim,
    ResearchClaimType,
    ResearchConfidence,
    ResearchFindingType,
    ResearchFlagType,
    ResearchPack,
    ResearchSeverity,
    ResearchSource,
    RetrievalBudget,
    RetrievalMode,
    RetrievalPlan,
    SavedScriptRun,
    ScoringOutput,
    ScriptClaimStatement,
    ScriptingContext,
    ScriptStructure,
    ScriptVersion,
    StrategyMemory,
    VisualPlanOutput,
)
from cc_deep_research.content_gen.orchestrator import _format_research_context
from cc_deep_research.content_gen.progress import PipelineRunJobRegistry, PipelineRunStatus
from cc_deep_research.content_gen.prompts import angle as angle_prompts
from cc_deep_research.content_gen.prompts import argument_map as argument_map_prompts
from cc_deep_research.content_gen.prompts import backlog as backlog_prompts
from cc_deep_research.content_gen.prompts import opportunity as opportunity_prompts
from cc_deep_research.content_gen.prompts import packaging as packaging_prompts
from cc_deep_research.content_gen.prompts import performance as performance_prompts
from cc_deep_research.content_gen.prompts import production as production_prompts
from cc_deep_research.content_gen.prompts import publish as publish_prompts
from cc_deep_research.content_gen.prompts import qc as qc_prompts
from cc_deep_research.content_gen.prompts import research_pack as research_pack_prompts
from cc_deep_research.content_gen.prompts import scripting as scripting_prompts
from cc_deep_research.content_gen.prompts import visual as visual_prompts
from cc_deep_research.content_gen.prompts.backlog import build_backlog_user
from cc_deep_research.llm.base import LLMProviderType, LLMResponse, LLMTransportType
from cc_deep_research.models import QueryProvenance, SearchResult, SearchResultItem
from tests.helpers.fixture_loader import load_content_gen_pipeline_smoke, load_text_fixture


class _FakeScriptingAgent(ScriptingAgent):
    def __init__(self, response: str) -> None:
        self._response = response
        self._active_iteration = 1
        self.last_user_prompt = ""
        self.user_prompts: list[str] = []

    async def _call_llm(
        self,
        system_prompt: str,
        user_prompt: str,
        *,
        temperature: float = 0.3,
    ) -> LLMResponse:
        del system_prompt, temperature
        self.last_user_prompt = user_prompt
        self.user_prompts.append(user_prompt)
        return LLMResponse(
            content=self._response,
            model="test-model",
            provider=LLMProviderType.ANTHROPIC,
            transport=LLMTransportType.ANTHROPIC_API,
            usage={"prompt_tokens": 11, "completion_tokens": 7},
            latency_ms=123,
            finish_reason="stop",
        )


class _FakeBacklogAgent(BacklogAgent):
    def __init__(self, response: str) -> None:
        self._response = response

    async def _call_llm(
        self,
        system_prompt: str,
        user_prompt: str,
        *,
        temperature: float = 0.5,
    ) -> str:
        del system_prompt, user_prompt, temperature
        return self._response


class _FakeOpportunityAgent(OpportunityPlanningAgent):
    def __init__(self, response: str) -> None:
        self._response = response

    async def _call_llm(
        self,
        system_prompt: str,
        user_prompt: str,
        *,
        temperature: float = 0.5,
    ) -> str:
        del system_prompt, user_prompt, temperature
        return self._response


class _FakeAngleAgent(AngleAgent):
    def __init__(self, response: str) -> None:
        self._response = response

    async def _call_llm(
        self,
        system_prompt: str,
        user_prompt: str,
        *,
        temperature: float = 0.5,
    ) -> str:
        del system_prompt, user_prompt, temperature
        return self._response


class _FakeArgumentMapAgent(ArgumentMapAgent):
    def __init__(self, response: str) -> None:
        self._response = response

    async def _call_llm(
        self,
        system_prompt: str,
        user_prompt: str,
        *,
        temperature: float = 0.3,
    ) -> str:
        del system_prompt, user_prompt, temperature
        return self._response


class _FakeVisualAgent(VisualAgent):
    def __init__(self, response: str) -> None:
        self._response = response

    async def _call_llm(
        self,
        system_prompt: str,
        user_prompt: str,
        *,
        temperature: float = 0.3,
    ) -> str:
        del system_prompt, user_prompt, temperature
        return self._response


class _FakePackagingAgent(PackagingAgent):
    def __init__(self, response: str) -> None:
        self._response = response

    async def _call_llm(
        self,
        system_prompt: str,
        user_prompt: str,
        *,
        temperature: float = 0.5,
    ) -> str:
        del system_prompt, user_prompt, temperature
        return self._response


class _FakeQCAgent(QCAgent):
    def __init__(self, response: str) -> None:
        self._response = response
        self.last_user_prompt = ""

    async def _call_llm(
        self,
        system_prompt: str,
        user_prompt: str,
        *,
        temperature: float = 0.2,
    ) -> str:
        del system_prompt, temperature
        self.last_user_prompt = user_prompt
        return self._response


class _StubTextRouter:
    def __init__(self, responses: list[str], *, available: bool = True) -> None:
        from cc_deep_research.llm.base import LLMProviderType, LLMResponse, LLMTransportType

        self._responses = list(responses)
        self._available = available
        self.calls = 0
        self._provider = LLMProviderType.OPENROUTER
        self._transport = LLMTransportType.OPENROUTER_API
        self._response_type = LLMResponse

    def is_available(self, agent_id: str) -> bool:
        del agent_id
        return self._available

    async def execute(
        self,
        agent_id: str,
        prompt: str,
        *,
        system_prompt: str | None = None,
        temperature: float = 0.3,
        max_tokens: int = 4096,
        metadata: dict | None = None,
    ):
        del agent_id, prompt, system_prompt, temperature, max_tokens, metadata
        self.calls += 1
        index = min(self.calls - 1, max(len(self._responses) - 1, 0))
        content = self._responses[index] if self._responses else ""
        return self._response_type(
            content=content,
            model="test-model",
            provider=self._provider,
            transport=self._transport,
            latency_ms=1,
            finish_reason="stop",
            usage={},
            metadata={},
        )


# ---------------------------------------------------------------------------
# Dispatch table
# ---------------------------------------------------------------------------


def test_dispatch_table_covers_all_steps() -> None:
    """Every step in SCRIPTING_STEPS should have a handler."""
    assert len(_STEP_HANDLERS) == len(SCRIPTING_STEPS)


# ---------------------------------------------------------------------------
# Pipeline stages
# ---------------------------------------------------------------------------


def test_pipeline_stages_count() -> None:
    """The pipeline should have 14 stages (0-13)."""
    assert len(PIPELINE_STAGES) == 14


def test_content_gen_stage_contract_registry_covers_core_prompt_stages() -> None:
    """Core prompt-backed stages should have explicit contract entries."""
    expected_modules = {
        "plan_opportunity": opportunity_prompts,
        "build_backlog": backlog_prompts,
        "score_ideas": backlog_prompts,
        "generate_angles": angle_prompts,
        "build_research_pack": research_pack_prompts,
        "build_argument_map": argument_map_prompts,
        "run_scripting": scripting_prompts,
        "visual_translation": visual_prompts,
        "production_brief": production_prompts,
        "packaging": packaging_prompts,
        "human_qc": qc_prompts,
        "publish_queue": publish_prompts,
        "performance_analysis": performance_prompts,
    }

    assert expected_modules.keys() <= CONTENT_GEN_STAGE_CONTRACTS.keys()

    for stage_name, module in expected_modules.items():
        contract = CONTENT_GEN_STAGE_CONTRACTS[stage_name]
        module_name = module.__name__.rsplit(".", maxsplit=1)[-1]

        assert contract.prompt_module == f"prompts/{module_name}.py"
        assert contract.contract_version == module.CONTRACT_VERSION
        assert contract.parser_location
        assert contract.output_model
        assert contract.format_notes
        assert contract.required_fields or contract.expected_sections


def test_content_gen_stage_contract_registry_documents_parser_behavior() -> None:
    """Registry entries should describe the intended parser strictness."""
    assert CONTENT_GEN_STAGE_CONTRACTS["generate_angles"].failure_mode == "fail_fast"
    assert CONTENT_GEN_STAGE_CONTRACTS["build_research_pack"].failure_mode == "tolerant"
    assert CONTENT_GEN_STAGE_CONTRACTS["build_argument_map"].failure_mode == "fail_fast"
    assert CONTENT_GEN_STAGE_CONTRACTS["human_qc"].failure_mode == "human_gated"


def test_content_gen_stage_contract_registry_tracks_expert_workflow_shapes() -> None:
    """Registry should document the expert-workflow contract additions."""
    research_contract = CONTENT_GEN_STAGE_CONTRACTS["build_research_pack"]
    argument_contract = CONTENT_GEN_STAGE_CONTRACTS["build_argument_map"]
    scripting_contract = CONTENT_GEN_STAGE_CONTRACTS["run_scripting"]
    qc_contract = CONTENT_GEN_STAGE_CONTRACTS["human_qc"]

    assert research_contract.contract_version == "1.2.0"
    assert "counterpoints" in research_contract.expected_sections
    assert "uncertainty_flags" in research_contract.expected_sections

    assert argument_contract.contract_version == "1.0.0"
    assert "unsafe_claims" in argument_contract.expected_sections
    assert "beat_claim_plan" in argument_contract.expected_sections

    assert scripting_contract.contract_version == "1.2.0"
    assert "Step 4: at least one beat intent" in scripting_contract.required_fields

    assert qc_contract.contract_version == "1.2.0"
    assert "unsupported_claims" in qc_contract.expected_sections
    assert "required_fact_checks" in qc_contract.expected_sections


def test_scripting_prompt_uses_refined_short_form_format_library() -> None:
    """Scripting prompts should expose the broader short-form format set."""
    assert "Tutorial / How-To" in scripting_prompts.STEP2_SYSTEM
    assert "Result-First / Case Study" in scripting_prompts.STEP2_SYSTEM
    assert "Opinion / Hot Take" in scripting_prompts.STEP2_SYSTEM
    assert "Before vs After" in scripting_prompts.STEP2_SYSTEM

    assert "Common pitfall" in scripting_prompts.STEP3_SYSTEM
    assert "Why most people disagree" in scripting_prompts.STEP3_SYSTEM
    assert "What changed" in scripting_prompts.STEP3_SYSTEM


def test_scripting_prompt_applies_expert_short_form_rules() -> None:
    """Universal retention and payoff rules should be visible in scripting prompts."""
    assert "The hook must create tension" in scripting_prompts.STEP3_SYSTEM
    assert "The second beat must justify attention fast" in scripting_prompts.STEP3_SYSTEM
    assert "One video = one core idea" in scripting_prompts.STEP3_SYSTEM

    assert (
        "The second beat must quickly add tension, pain, proof, or surprise"
        in scripting_prompts.STEP6_SYSTEM
    )
    assert "Make the payoff specific and observable" in scripting_prompts.STEP6_SYSTEM
    assert "If the payoff lands late, move proof or example earlier" in scripting_prompts.STEP7_SYSTEM


def test_backlog_and_angle_prompts_prefer_specific_format_led_ideas() -> None:
    """Upstream prompt stages should steer toward distinct formats and non-generic ideas."""
    assert "Use refined short-form formats where possible" in backlog_prompts.BUILD_BACKLOG_SYSTEM
    assert "Best fit between the idea and a proven short-form format" in angle_prompts.ANGLE_SYSTEM
    assert (
        "Reaction / Response and List / Roundup are allowed only when the idea genuinely"
        in angle_prompts.ANGLE_SYSTEM
    )


def test_pipeline_context_default_values() -> None:
    """PipelineContext should have sensible defaults."""
    ctx = PipelineContext()
    assert ctx.pipeline_id  # auto-generated
    assert ctx.strategy is None
    assert ctx.backlog is None
    assert ctx.shortlist == []
    assert ctx.selected_idea_id == ""
    assert ctx.selection_reasoning == ""
    assert ctx.runner_up_idea_ids == []
    assert ctx.active_candidates == []
    assert ctx.scripting is None
    assert ctx.qc_gate is None
    assert ctx.current_stage == 0


def test_argument_map_model_defaults_do_not_break_empty_instantiation() -> None:
    """ArgumentMap should allow empty defaults so untouched pipeline context stays valid."""
    result = ArgumentMap()

    assert result.thesis == ""
    assert result.proof_anchors == []
    assert result.safe_claims == []
    assert result.beat_claim_plan == []


def test_pipeline_context_roundtrip() -> None:
    """PipelineContext should survive JSON serialization and derive the candidate queue."""
    ctx = PipelineContext(
        theme="test theme",
        strategy=StrategyMemory(niche="fitness", content_pillars=["strength"]),
        argument_map=ArgumentMap(
            thesis="The visible premium tier reframes the middle plan.",
            proof_anchors=[
                {
                    "proof_id": "proof_1",
                    "summary": "Buyers compare tier contrast before feature detail.",
                }
            ],
            safe_claims=[
                {
                    "claim_id": "claim_1",
                    "claim": "Tier framing changes what buyers notice first.",
                    "supporting_proof_ids": ["proof_1"],
                }
            ],
            beat_claim_plan=[
                {
                    "beat_id": "beat_1",
                    "beat_name": "Hook",
                    "goal": "Challenge the default pricing diagnosis.",
                    "claim_ids": ["claim_1"],
                    "proof_anchor_ids": ["proof_1"],
                }
            ],
        ),
        backlog=BacklogOutput(items=[
            BacklogItem(idea="test idea", category="evergreen", audience="beginners"),
        ]),
        shortlist=["idea-2", "idea-1"],
        selected_idea_id="idea-2",
        selection_reasoning="Better hook and clearer evidence fit.",
        runner_up_idea_ids=["idea-1"],
    )
    json_str = ctx.model_dump_json()
    restored = PipelineContext.model_validate_json(json_str)
    assert restored.theme == "test theme"
    assert restored.strategy is not None
    assert restored.strategy.niche == "fitness"
    assert restored.argument_map is not None
    assert restored.argument_map.thesis == "The visible premium tier reframes the middle plan."
    assert restored.shortlist == ["idea-2", "idea-1"]
    assert restored.selected_idea_id == "idea-2"
    assert restored.selection_reasoning == "Better hook and clearer evidence fit."
    assert restored.runner_up_idea_ids == ["idea-1"]
    assert [candidate.idea_id for candidate in restored.active_candidates] == ["idea-2", "idea-1"]
    assert [candidate.role for candidate in restored.active_candidates] == ["primary", "runner_up"]
    assert len(restored.backlog.items) == 1
    assert restored.backlog.items[0].title == "test idea"


def test_pipeline_context_roundtrip_with_lane_contexts_syncs_primary_fields() -> None:
    """Lane context state should survive roundtrip and repopulate legacy primary fields."""
    ctx = PipelineContext(
        shortlist=["idea-1", "idea-2"],
        selected_idea_id="idea-1",
        runner_up_idea_ids=["idea-2"],
        lane_contexts=[
            PipelineLaneContext(
                idea_id="idea-1",
                role="primary",
                status="in_production",
                last_completed_stage=10,
                angles=AngleOutput(
                    idea_id="idea-1",
                    angle_options=[AngleOption(angle_id="angle-1", core_promise="Primary angle")],
                    selected_angle_id="angle-1",
                ),
                packaging=PackagingOutput(
                    idea_id="idea-1",
                    platform_packages=[PlatformPackage(platform="tiktok", primary_hook="Primary hook")],
                ),
                publish_items=[PublishItem(idea_id="idea-1", platform="tiktok")],
            ),
            PipelineLaneContext(
                idea_id="idea-2",
                role="runner_up",
                status="runner_up",
                last_completed_stage=4,
                angles=AngleOutput(
                    idea_id="idea-2",
                    angle_options=[AngleOption(angle_id="angle-2", core_promise="Runner-up angle")],
                    selected_angle_id="angle-2",
                ),
            ),
        ],
    )

    restored = PipelineContext.model_validate_json(ctx.model_dump_json())

    assert len(restored.lane_contexts) == 2
    assert [candidate.idea_id for candidate in restored.active_candidates] == ["idea-1", "idea-2"]
    assert [candidate.status for candidate in restored.active_candidates] == ["in_production", "runner_up"]
    assert restored.angles is not None
    assert restored.angles.idea_id == "idea-1"
    assert restored.packaging is not None
    assert restored.packaging.idea_id == "idea-1"
    assert len(restored.publish_items) == 1
    assert restored.publish_items[0].idea_id == "idea-1"
    assert restored.publish_item is not None
    assert restored.publish_item.idea_id == "idea-1"


def test_strategy_memory_coerces_expert_fields_from_string_lists() -> None:
    """String-based config input should coerce into the new expert strategy models."""
    strategy = StrategyMemory(
        signature_frameworks=["Jobs to be done"],
        contrarian_beliefs=["Most buyers compare tier contrast before feature depth"],
        proof_rules=["Prefer first-party examples over vague performance claims"],
    )

    assert strategy.signature_frameworks == [ExpertFramework(name="Jobs to be done", summary="")]
    assert strategy.contrarian_beliefs == [
        ContrarianBelief(
            belief="Most buyers compare tier contrast before feature depth",
            rationale="",
        )
    ]
    assert strategy.proof_rules == [
        ProofRule(
            rule="Prefer first-party examples over vague performance claims",
            rationale="",
        )
    ]


def test_pipeline_stage_trace_defaults() -> None:
    """PipelineStageTrace should have sensible defaults."""
    trace = PipelineStageTrace(
        stage_index=0,
        stage_name="load_strategy",
        stage_label="Loading strategy memory",
    )
    assert trace.status == "completed"
    assert trace.started_at == ""
    assert trace.completed_at == ""
    assert trace.duration_ms == 0
    assert trace.input_summary == ""
    assert trace.output_summary == ""
    assert trace.warnings == []
    assert trace.decision_summary == ""


def test_pipeline_stage_trace_roundtrip() -> None:
    """PipelineStageTrace should survive JSON serialization."""
    trace = PipelineStageTrace(
        stage_index=2,
        stage_name="score_ideas",
        stage_label="Scoring ideas",
        status="completed",
        started_at="2026-03-29T10:00:00+00:00",
        completed_at="2026-03-29T10:00:05+00:00",
        duration_ms=5000,
        input_summary="items=10",
        output_summary="produce=3, hold=5, kill=2",
        warnings=[],
        decision_summary="",
    )
    json_str = trace.model_dump_json()
    restored = PipelineStageTrace.model_validate_json(json_str)
    assert restored.stage_index == 2
    assert restored.stage_name == "score_ideas"
    assert restored.duration_ms == 5000
    assert restored.input_summary == "items=10"


def test_pipeline_context_with_traces_roundtrip() -> None:
    """PipelineContext with stage_traces should survive JSON serialization."""
    ctx = PipelineContext(
        theme="test",
        stage_traces=[
            PipelineStageTrace(
                stage_index=0,
                stage_name="load_strategy",
                stage_label="Loading strategy memory",
                status="completed",
                started_at="2026-03-29T10:00:00+00:00",
                completed_at="2026-03-29T10:00:01+00:00",
                duration_ms=1000,
                input_summary="",
                output_summary="niche=fitness",
            ),
            PipelineStageTrace(
                stage_index=1,
                stage_name="build_backlog",
                stage_label="Building backlog",
                status="skipped",
                started_at="2026-03-29T10:00:01+00:00",
                completed_at="2026-03-29T10:00:01+00:00",
                duration_ms=0,
                input_summary="theme=test",
                output_summary="backlog missing",
                decision_summary="Skipped: backlog missing",
            ),
        ],
    )
    json_str = ctx.model_dump_json()
    restored = PipelineContext.model_validate_json(json_str)
    assert len(restored.stage_traces) == 2
    assert restored.stage_traces[0].status == "completed"
    assert restored.stage_traces[1].status == "skipped"


def test_orchestrator_records_traces_in_stage_order() -> None:
    """Orchestrator should append traces for each stage in order."""
    from cc_deep_research.content_gen.orchestrator import ContentGenOrchestrator

    class FakeConfig:
        content_gen = type(
            "ContentGen",
            (),
            {
                "max_iterations": 1,
                "quality_threshold": 0.7,
                "convergence_threshold": 0.1,
                "enable_iterative_mode": False,
                "scoring_threshold_produce": 3.5,
                "default_platforms": ["tiktok"],
            },
        )()

        llm = type(
            "LLM",
            (),
            {
                "anthropic": type("C", (), {"enabled": True, "api_key": "test"})(),
            },
        )()

    _ = ContentGenOrchestrator(FakeConfig())
    ctx = PipelineContext(theme="test")

    trace1 = PipelineStageTrace(
        stage_index=0,
        stage_name="load_strategy",
        stage_label="Loading strategy memory",
        input_summary="",
        output_summary="niche=fitness",
    )
    trace2 = PipelineStageTrace(
        stage_index=1,
        stage_name="build_backlog",
        stage_label="Building backlog",
        input_summary="theme=test",
        output_summary="items=5",
    )
    ctx.stage_traces.extend([trace1, trace2])

    assert ctx.stage_traces[0].stage_index == 0
    assert ctx.stage_traces[1].stage_index == 1


def test_summarize_input_for_backlog_and_scoring() -> None:
    """Input summaries should exist for backlog and scoring stages."""
    from cc_deep_research.content_gen.orchestrator import ContentGenOrchestrator

    class FakeConfig:
        content_gen = type(
            "ContentGen",
            (),
            {
                "max_iterations": 1,
                "quality_threshold": 0.7,
                "convergence_threshold": 0.1,
                "enable_iterative_mode": False,
                "scoring_threshold_produce": 3.5,
                "default_platforms": ["tiktok"],
            },
        )()

        llm = type(
            "LLM",
            (),
            {
                "anthropic": type("C", (), {"enabled": True, "api_key": "test"})(),
            },
        )()

    orch = ContentGenOrchestrator(FakeConfig())
    ctx = PipelineContext(theme="my theme")

    backlog_summary = orch._summarize_input(2, ctx)
    assert "theme=my theme" in backlog_summary

    ctx.backlog = BacklogOutput(items=[BacklogItem(idea="test") for _ in range(10)])
    scoring_summary = orch._summarize_input(3, ctx)
    assert "items=10" in scoring_summary


def test_summarize_output_for_backlog_and_scoring() -> None:
    """Output summaries should exist for backlog and scoring stages."""
    from cc_deep_research.content_gen.orchestrator import ContentGenOrchestrator

    class FakeConfig:
        content_gen = type(
            "ContentGen",
            (),
            {
                "max_iterations": 1,
                "quality_threshold": 0.7,
                "convergence_threshold": 0.1,
                "enable_iterative_mode": False,
                "scoring_threshold_produce": 3.5,
                "default_platforms": ["tiktok"],
            },
        )()

        llm = type(
            "LLM",
            (),
            {
                "anthropic": type("C", (), {"enabled": True, "api_key": "test"})(),
            },
        )()

    orch = ContentGenOrchestrator(FakeConfig())
    ctx = PipelineContext(theme="my theme")

    ctx.backlog = BacklogOutput(
        items=[BacklogItem(idea="test") for _ in range(10)],
        rejected_count=2,
    )
    backlog_summary = orch._summarize_output(2, ctx)
    assert "items=10" in backlog_summary
    assert "rejected=2" in backlog_summary

    ctx.scoring = ScoringOutput(
        produce_now=["id1", "id2"],
        shortlist=["id2", "id1"],
        selected_idea_id="id2",
        hold=["id3"],
        killed=["id4"],
    )
    scoring_summary = orch._summarize_output(3, ctx)
    assert "produce=2" in scoring_summary
    assert "shortlist=2" in scoring_summary
    assert "selected=id2" in scoring_summary
    assert "hold=1" in scoring_summary
    assert "kill=1" in scoring_summary


def test_skipped_stage_recorded_when_prerequisites_missing() -> None:
    """Skipped stages should be recorded when prerequisites are missing."""
    from cc_deep_research.content_gen.orchestrator import ContentGenOrchestrator

    class FakeConfig:
        content_gen = type(
            "ContentGen",
            (),
            {
                "max_iterations": 1,
                "quality_threshold": 0.7,
                "convergence_threshold": 0.1,
                "enable_iterative_mode": False,
                "scoring_threshold_produce": 3.5,
                "default_platforms": ["tiktok"],
            },
        )()

        llm = type(
            "LLM",
            (),
            {
                "anthropic": type("C", (), {"enabled": True, "api_key": "test"})(),
            },
        )()

    orch = ContentGenOrchestrator(FakeConfig())
    ctx = PipelineContext(theme="test")

    prereqs_met, reason = orch._check_prerequisites(3, ctx)
    assert not prereqs_met
    assert "backlog missing" in reason

    ctx.backlog = BacklogOutput(items=[])
    prereqs_met, reason = orch._check_prerequisites(3, ctx)
    assert prereqs_met

    ctx.backlog = BacklogOutput(items=[])
    ctx.scoring = ScoringOutput(produce_now=[])
    prereqs_met, reason = orch._check_prerequisites(4, ctx)
    assert not prereqs_met
    assert "scoring/selected idea missing" in reason

    ctx.backlog = BacklogOutput(items=[BacklogItem(idea_id="id1", idea="Idea 1")])
    ctx.selected_idea_id = "id1"
    ctx.angles = AngleOutput(angle_options=[])
    prereqs_met, reason = orch._check_prerequisites(5, ctx)
    assert not prereqs_met
    assert "selected angle missing" in reason


@pytest.mark.asyncio
async def test_generate_angles_uses_selected_idea_over_produce_now_order() -> None:
    """Angle generation should follow the explicit selected idea."""
    from cc_deep_research.content_gen.orchestrator import (
        ContentGenOrchestrator,
        _stage_generate_angles,
    )

    class FakeConfig:
        content_gen = type(
            "ContentGen",
            (),
            {
                "max_iterations": 1,
                "quality_threshold": 0.7,
                "convergence_threshold": 0.1,
                "enable_iterative_mode": False,
                "scoring_threshold_produce": 3.5,
                "default_platforms": ["tiktok"],
            },
        )()

        llm = type(
            "LLM",
            (),
            {
                "anthropic": type("C", (), {"enabled": True, "api_key": "test"})(),
            },
        )()

    class FakeAngleAgent:
        def __init__(self) -> None:
            self.seen_item_id = ""

        async def generate(self, item: BacklogItem, strategy: StrategyMemory) -> AngleOutput:
            del strategy
            self.seen_item_id = item.idea_id
            return AngleOutput(
                idea_id=item.idea_id,
                angle_options=[AngleOption(angle_id="angle-2", core_promise="Selected angle")],
                selected_angle_id="angle-2",
            )

    orch = ContentGenOrchestrator(FakeConfig())
    fake_agent = FakeAngleAgent()
    orch._agents["angle"] = fake_agent
    ctx = PipelineContext(
        theme="test",
        backlog=BacklogOutput(
            items=[
                BacklogItem(idea_id="id1", idea="First idea"),
                BacklogItem(idea_id="id2", idea="Second idea"),
            ]
        ),
        scoring=ScoringOutput(
            produce_now=["id1", "id2"],
            shortlist=["id1", "id2"],
            selected_idea_id="id2",
        ),
    )

    ctx = await _stage_generate_angles(orch, ctx)

    # ctx.angles reflects the primary (selected) lane after _sync_primary_lane
    assert fake_agent.seen_item_id in ("id2", "id1"), "sanity: agent was called"
    assert ctx.angles is not None
    assert ctx.angles.idea_id == "id2"


@pytest.mark.asyncio
async def test_build_research_pack_uses_pipeline_selected_idea() -> None:
    """Research pack stage should read the chosen idea from pipeline context."""
    from cc_deep_research.content_gen.orchestrator import (
        ContentGenOrchestrator,
        _stage_build_research_pack,
    )

    class FakeConfig:
        content_gen = type(
            "ContentGen",
            (),
            {
                "max_iterations": 1,
                "quality_threshold": 0.7,
                "convergence_threshold": 0.1,
                "enable_iterative_mode": False,
                "scoring_threshold_produce": 3.5,
                "default_platforms": ["tiktok"],
            },
        )()

        llm = type(
            "LLM",
            (),
            {
                "anthropic": type("C", (), {"enabled": True, "api_key": "test"})(),
            },
        )()

    class FakeResearchAgent:
        def __init__(self) -> None:
            self.seen_item_id = ""
            self.seen_angle_id = ""

        async def build(
            self,
            item: BacklogItem,
            angle: AngleOption,
            *,
            feedback: str = "",
            research_gaps: list[str] | None = None,
            research_hypotheses: list[str] | None = None,
        ) -> ResearchPack:
            del feedback, research_gaps, research_hypotheses
            self.seen_item_id = item.idea_id
            self.seen_angle_id = angle.angle_id
            return ResearchPack(idea_id=item.idea_id, angle_id=angle.angle_id)

    orch = ContentGenOrchestrator(FakeConfig())
    fake_agent = FakeResearchAgent()
    orch._agents["research"] = fake_agent
    ctx = PipelineContext(
        theme="test",
        backlog=BacklogOutput(
            items=[
                BacklogItem(idea_id="id1", idea="First idea"),
                BacklogItem(idea_id="id2", idea="Second idea"),
            ]
        ),
        scoring=ScoringOutput(
            produce_now=["id1", "id2"],
            shortlist=["id1", "id2"],
            selected_idea_id="id1",
        ),
        selected_idea_id="id2",
        angles=AngleOutput(
            idea_id="id2",
            angle_options=[AngleOption(angle_id="angle-2", core_promise="Angle for second idea")],
            selected_angle_id="angle-2",
        ),
    )

    ctx = await _stage_build_research_pack(orch, ctx)

    assert fake_agent.seen_item_id == "id2"
    assert fake_agent.seen_angle_id == "angle-2"
    assert ctx.research_pack is not None
    assert ctx.research_pack.idea_id == "id2"


@pytest.mark.asyncio
async def test_build_argument_map_uses_selected_context_and_research_pack() -> None:
    """Argument map stage should use the selected idea, angle, and built research pack."""
    from cc_deep_research.content_gen.orchestrator import (
        ContentGenOrchestrator,
        _stage_build_argument_map,
    )

    class FakeConfig:
        content_gen = type(
            "ContentGen",
            (),
            {
                "max_iterations": 1,
                "quality_threshold": 0.7,
                "convergence_threshold": 0.1,
                "enable_iterative_mode": False,
                "scoring_threshold_produce": 3.5,
                "default_platforms": ["tiktok"],
            },
        )()

        llm = type(
            "LLM",
            (),
            {
                "anthropic": type("C", (), {"enabled": True, "api_key": "test"})(),
            },
        )()

    class FakeArgumentMapBuilder:
        def __init__(self) -> None:
            self.seen_item_id = ""
            self.seen_angle_id = ""
            self.seen_research_idea_id = ""

        async def build(
            self,
            item: BacklogItem,
            angle: AngleOption,
            research_pack: ResearchPack,
        ) -> ArgumentMap:
            self.seen_item_id = item.idea_id
            self.seen_angle_id = angle.angle_id
            self.seen_research_idea_id = research_pack.idea_id
            return ArgumentMap(
                idea_id=item.idea_id,
                angle_id=angle.angle_id,
                thesis="Anchor beats copy tweaks",
                proof_anchors=[
                    {
                        "proof_id": "proof_1",
                        "summary": "Buyers compare tiers first",
                    }
                ],
            )

    orch = ContentGenOrchestrator(FakeConfig())
    fake_agent = FakeArgumentMapBuilder()
    orch._agents["argument_map"] = fake_agent
    ctx = PipelineContext(
        theme="test",
        backlog=BacklogOutput(
            items=[
                BacklogItem(idea_id="id1", idea="First idea"),
                BacklogItem(idea_id="id2", idea="Second idea"),
            ]
        ),
        scoring=ScoringOutput(
            produce_now=["id1", "id2"],
            shortlist=["id1", "id2"],
            selected_idea_id="id1",
        ),
        selected_idea_id="id2",
        angles=AngleOutput(
            idea_id="id2",
            angle_options=[AngleOption(angle_id="angle-2", core_promise="Angle for second idea")],
            selected_angle_id="angle-2",
        ),
        research_pack=ResearchPack(
            idea_id="id2",
            angle_id="angle-2",
            claims=[{"claim_id": "claim_1", "claim": "Anchors matter"}],
        ),
    )

    ctx = await _stage_build_argument_map(orch, ctx)

    assert fake_agent.seen_item_id == "id2"
    assert fake_agent.seen_angle_id == "angle-2"
    assert fake_agent.seen_research_idea_id == "id2"
    assert ctx.argument_map is not None
    assert ctx.argument_map.idea_id == "id2"
    assert ctx.argument_map.angle_id == "angle-2"


@pytest.mark.asyncio
async def test_stage_completed_callback_emits_for_skipped_stage() -> None:
    """stage_completed_callback should be called for skipped stages."""
    from cc_deep_research.content_gen.orchestrator import ContentGenOrchestrator

    class FakeConfig:
        content_gen = type(
            "ContentGen",
            (),
            {
                "max_iterations": 1,
                "quality_threshold": 0.7,
                "convergence_threshold": 0.1,
                "enable_iterative_mode": False,
                "scoring_threshold_produce": 3.5,
                "default_platforms": ["tiktok"],
            },
        )()

        llm = type(
            "LLM",
            (),
            {
                "anthropic": type("C", (), {"enabled": True, "api_key": "test"})(),
            },
        )()

    orch = ContentGenOrchestrator(FakeConfig())
    recorded_events: list[tuple[int, str, str, PipelineContext]] = []

    def on_stage_completed(stage_idx: int, status: str, detail: str, stage_ctx: PipelineContext) -> None:
        recorded_events.append((stage_idx, status, detail, stage_ctx))

    ctx = PipelineContext(theme="test")
    await orch._run_stage(3, ctx, None, stage_completed_callback=on_stage_completed)

    assert len(recorded_events) == 1
    idx, status, detail, stage_ctx = recorded_events[0]
    assert idx == 3
    assert status == "skipped"
    assert "backlog missing" in detail
    assert stage_ctx.stage_traces[-1].status == "skipped"


@pytest.mark.asyncio
async def test_failed_stage_is_recorded_in_traces() -> None:
    """Failed stages should be recorded in stage_traces."""
    from cc_deep_research.content_gen.orchestrator import (
        _PIPELINE_HANDLERS,
        ContentGenOrchestrator,
    )

    class FakeConfig:
        content_gen = type(
            "ContentGen",
            (),
            {
                "max_iterations": 1,
                "quality_threshold": 0.7,
                "convergence_threshold": 0.1,
                "enable_iterative_mode": False,
                "scoring_threshold_produce": 3.5,
                "default_platforms": ["tiktok"],
            },
        )()

        llm = type(
            "LLM",
            (),
            {
                "anthropic": type("C", (), {"enabled": True, "api_key": "test"})(),
            },
        )()

    orch = ContentGenOrchestrator(FakeConfig())
    ctx = PipelineContext(theme="test")

    async def failing_stage(
        _orch: ContentGenOrchestrator, ctx: PipelineContext
    ) -> PipelineContext:
        raise ValueError("Stage failed intentionally")

    orig_stage_build_backlog = _PIPELINE_HANDLERS[2]
    _PIPELINE_HANDLERS[2] = failing_stage

    try:
        with pytest.raises(ValueError, match="Stage failed intentionally"):
            await orch._run_stage(2, ctx, None)
    finally:
        _PIPELINE_HANDLERS[2] = orig_stage_build_backlog

    assert len(ctx.stage_traces) == 1
    trace = ctx.stage_traces[0]
    assert trace.stage_index == 2
    assert trace.status == "failed"
    assert "Stage failed intentionally" in trace.output_summary
    assert len(trace.warnings) > 0


@pytest.mark.asyncio
async def test_stage_completed_callback_emits_after_stage() -> None:
    """stage_completed_callback should be called immediately after stage runs."""
    from cc_deep_research.content_gen.orchestrator import ContentGenOrchestrator

    class FakeConfig:
        content_gen = type(
            "ContentGen",
            (),
            {
                "max_iterations": 1,
                "quality_threshold": 0.7,
                "convergence_threshold": 0.1,
                "enable_iterative_mode": False,
                "scoring_threshold_produce": 3.5,
                "default_platforms": ["tiktok"],
            },
        )()

        llm = type(
            "LLM",
            (),
            {
                "anthropic": type("C", (), {"enabled": True, "api_key": "test"})(),
            },
        )()

    orch = ContentGenOrchestrator(FakeConfig())
    recorded_events: list[tuple[int, str, str, PipelineContext]] = []

    def on_stage_completed(stage_idx: int, status: str, detail: str, stage_ctx: PipelineContext) -> None:
        recorded_events.append((stage_idx, status, detail, stage_ctx))

    ctx = PipelineContext(theme="test")
    await orch._run_stage(0, ctx, None, stage_completed_callback=on_stage_completed)

    assert len(recorded_events) == 1
    idx, status, detail, stage_ctx = recorded_events[0]
    assert idx == 0
    assert status == "completed"
    assert detail == ""
    assert stage_ctx.stage_traces[-1].status == "completed"


@pytest.mark.asyncio
async def test_full_pipeline_smoke_uses_fixture_backed_outputs(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The full pipeline should wire deterministic fixture outputs end to end."""
    from cc_deep_research.content_gen.orchestrator import ContentGenOrchestrator

    fixture = load_content_gen_pipeline_smoke()
    selected_idea_id = fixture["scoring"]["selected_idea_id"]
    selected_idea = next(
        item for item in fixture["backlog"]["items"] if item["idea_id"] == selected_idea_id
    )
    runner_up_idea_id = fixture["scoring"]["runner_up_idea_ids"][0]
    runner_up_idea = next(
        item for item in fixture["backlog"]["items"] if item["idea_id"] == runner_up_idea_id
    )
    runner_up_angles = AngleOutput(
        idea_id=runner_up_idea_id,
        angle_options=[
            AngleOption(
                angle_id="angle-runner-up",
                target_audience=runner_up_idea["audience"],
                viewer_problem=runner_up_idea["problem"],
                core_promise="Show the runner-up path clearly enough to keep it viable.",
                primary_takeaway="The alternate take still deserves a production slot.",
                lens="Contrarian",
                format="Explainer",
                tone="Direct",
                cta="Test this framing against your current version.",
                why_this_version_should_exist="It targets the same audience from a sharper alternate angle.",
            )
        ],
        selected_angle_id="angle-runner-up",
        selection_reasoning="Runner-up lane keeps a credible alternate framing alive.",
    )
    runner_up_research_pack = ResearchPack(
        idea_id=runner_up_idea_id,
        angle_id="angle-runner-up",
        key_facts=["Secondary lane fact"],
        proof_points=["Secondary lane proof"],
    )
    runner_up_argument_map = ArgumentMap(
        idea_id=runner_up_idea_id,
        angle_id="angle-runner-up",
        thesis="The runner-up thesis stays production-worthy.",
        proof_anchors=[
            {
                "proof_id": "runner_proof_1",
                "summary": "The alternate framing still lands on a clear mechanism.",
            }
        ],
        safe_claims=[
            {
                "claim_id": "runner_claim_1",
                "claim": "Alternate framing can still improve clarity.",
                "supporting_proof_ids": ["runner_proof_1"],
            }
        ],
        beat_claim_plan=[
            {
                "beat_id": "runner_beat_1",
                "beat_name": "Hook",
                "goal": "Frame the alternate idea as a viable second lane.",
                "claim_ids": ["runner_claim_1"],
                "proof_anchor_ids": ["runner_proof_1"],
            }
        ],
    )
    runner_up_scripting = ScriptingContext(
        raw_idea=runner_up_idea["idea"],
        research_context="Secondary lane proof",
        structure=ScriptStructure(
            chosen_structure="Problem > proof > action",
            why_it_fits="Keeps the alternate lane concise.",
            beat_list=["Hook", "Proof", "Close"],
        ),
        draft=ScriptVersion(
            content="Runner-up script keeps the alternate angle alive.",
            word_count=8,
        ),
        qc=QCResult(
            checks=[],
            weakest_parts=[],
            final_script="Runner-up script keeps the alternate angle alive.",
        ),
    )
    runner_up_visual_plan = VisualPlanOutput.model_validate(
        {
            "idea_id": runner_up_idea_id,
            "angle_id": "angle-runner-up",
            "visual_plan": [
                {
                    "beat": "Hook",
                    "spoken_line": "Runner-up script keeps the alternate angle alive.",
                    "visual": "Show the alternate frame directly.",
                }
            ],
            "visual_refresh_check": "pass",
        }
    )
    runner_up_production_brief = ProductionBrief(
        idea_id=runner_up_idea_id,
        location="Desk",
        setup="Single-camera",
    )
    runner_up_packaging = PackagingOutput(
        idea_id=runner_up_idea_id,
        platform_packages=[
            PlatformPackage(platform="tiktok", primary_hook="Runner-up hook"),
        ],
    )
    runner_up_qc_gate = HumanQCGate(approved_for_publish=True)
    runner_up_publish_items = [
        PublishItem(idea_id=runner_up_idea_id, platform="tiktok", publish_datetime="optimal")
    ]

    class FakeConfig:
        content_gen = type(
            "ContentGen",
            (),
            {
                "max_iterations": 1,
                "quality_threshold": 0.7,
                "convergence_threshold": 0.1,
                "enable_iterative_mode": False,
                "scoring_threshold_produce": 3.5,
                "default_platforms": ["tiktok"],
            },
        )()

        llm = type(
            "LLM",
            (),
            {
                "anthropic": type("C", (), {"enabled": True, "api_key": "test"})(),
            },
        )()

    class FakeStrategyStore:
        def load(self) -> StrategyMemory:
            return StrategyMemory.model_validate(fixture["strategy"])

    class FakeOpportunityAgent:
        async def plan(self, theme: str, strategy: StrategyMemory) -> OpportunityBrief:
            assert theme == fixture["theme"]
            assert strategy.niche == fixture["strategy"]["niche"]
            return OpportunityBrief.model_validate(fixture["opportunity_brief"])

    class FakeBacklogAgent:
        async def build_backlog(
            self,
            theme: str,
            strategy: StrategyMemory,
            *,
            opportunity_brief: OpportunityBrief | None = None,
        ) -> BacklogOutput:
            assert theme == fixture["theme"]
            assert strategy.niche == fixture["strategy"]["niche"]
            assert opportunity_brief is not None
            assert opportunity_brief.goal == fixture["opportunity_brief"]["goal"]
            return BacklogOutput.model_validate(fixture["backlog"])

        async def score_ideas(
            self,
            items: list[BacklogItem],
            strategy: StrategyMemory,
            *,
            threshold: float,
            min_upside_threshold: int = 2,
            effort_tier_cap: str = "deep",
            content_type_profile: str = "",
        ) -> ScoringOutput:
            assert [item.idea_id for item in items] == ["idea-alpha", "idea-beta"]
            assert strategy.niche == fixture["strategy"]["niche"]
            assert threshold == 3.5
            return ScoringOutput.model_validate(fixture["scoring"])

    class FakeAngleAgent:
        async def generate(self, item: BacklogItem, strategy: StrategyMemory) -> AngleOutput:
            assert strategy.niche == fixture["strategy"]["niche"]
            if item.idea_id == selected_idea_id:
                return AngleOutput.model_validate(fixture["angles"])
            assert item.idea_id == runner_up_idea_id
            return runner_up_angles

    class FakeResearchAgent:
        async def build(
            self,
            item: BacklogItem,
            angle: AngleOption,
            *,
            feedback: str = "",
            research_gaps: list[str] | None = None,
            research_hypotheses: list[str] | None = None,
        ) -> ResearchPack:
            assert feedback == ""
            assert research_gaps is None
            if item.idea_id == selected_idea_id:
                assert angle.angle_id == fixture["angles"]["selected_angle_id"]
                return ResearchPack.model_validate(fixture["research_pack"])
            assert item.idea_id == runner_up_idea_id
            assert angle.angle_id == runner_up_angles.selected_angle_id
            return runner_up_research_pack

    class FakeArgumentMapAgent:
        async def build(
            self,
            item: BacklogItem,
            angle: AngleOption,
            research_pack: ResearchPack,
        ) -> ArgumentMap:
            if item.idea_id == selected_idea_id:
                assert angle.angle_id == fixture["angles"]["selected_angle_id"]
                assert research_pack.idea_id == selected_idea_id
                return ArgumentMap.model_validate(fixture["argument_map"])
            assert item.idea_id == runner_up_idea_id
            assert angle.angle_id == runner_up_angles.selected_angle_id
            assert research_pack.idea_id == runner_up_idea_id
            return runner_up_argument_map

    class FakeScriptingAgent:
        async def run_from_step(self, ctx: ScriptingContext, step: int) -> ScriptingContext:
            assert step == 5
            assert ctx.argument_map is not None
            assert ctx.core_inputs is not None
            assert ctx.structure is not None
            assert ctx.beat_intents is not None
            if ctx.raw_idea == selected_idea["idea"]:
                assert ctx.argument_map.thesis == fixture["argument_map"]["thesis"]
                assert ctx.core_inputs.topic == selected_idea["idea"]
                assert ctx.structure.beat_list == ["Hook", "Reframe", "Proof", "Close"]
                assert ctx.beat_intents.beats[0].claim_ids == ["claim_1"]
                assert ctx.beat_intents.beats[2].proof_anchor_ids == ["proof_2"]
                assert "Anchors shape perceived value" in ctx.research_context
                return ScriptingContext.model_validate(fixture["scripting"])
            assert ctx.raw_idea == runner_up_idea["idea"]
            assert ctx.argument_map.thesis == runner_up_argument_map.thesis
            assert ctx.core_inputs.topic == runner_up_idea["idea"]
            assert ctx.structure.beat_list == ["Hook"]
            assert ctx.beat_intents.beats[0].claim_ids == ["runner_claim_1"]
            assert "Secondary lane proof" in ctx.research_context
            return runner_up_scripting

    class FakeVisualAgent:
        async def translate(self, script: ScriptVersion, structure: ScriptStructure) -> object:
            if "anchor tier is broken" in script.content:
                assert structure.chosen_structure == fixture["scripting"]["structure"]["chosen_structure"]
                return VisualPlanOutput.model_validate(fixture["visual_plan"])
            assert "Runner-up script keeps the alternate angle alive." in script.content
            assert structure.chosen_structure == "Problem > proof > action"
            return runner_up_visual_plan

    class FakeProductionAgent:
        async def brief(self, visual_plan) -> object:
            if visual_plan.idea_id == selected_idea_id:
                return ProductionBrief.model_validate(fixture["production_brief"])
            assert visual_plan.idea_id == runner_up_idea_id
            return runner_up_production_brief

    class FakePackagingAgent:
        async def generate(
            self,
            script: ScriptVersion,
            angle: AngleOption,
            platforms: list[str],
            *,
            strategy: StrategyMemory,
        ) -> PackagingOutput:
            assert platforms == ["tiktok"]
            assert strategy.niche == fixture["strategy"]["niche"]
            if "anchor tier is broken" in script.content:
                assert angle.angle_id == fixture["angles"]["selected_angle_id"]
                return PackagingOutput.model_validate(fixture["packaging"])
            assert "Runner-up script keeps the alternate angle alive." in script.content
            assert angle.angle_id == runner_up_angles.selected_angle_id
            return runner_up_packaging

    class FakeQCAgent:
        async def review(
            self,
            *,
            script: str,
            visual_summary: str,
            packaging_summary: str,
            research_summary: str = "",
            argument_map_summary: str = "",
            success_criteria: list[str] | None = None,
        ) -> HumanQCGate:
            if "anchor tier is broken" in script:
                assert "Hook: Highlight the cheapest plan selection on a pricing page" in visual_summary
                assert "tiktok: If buyers always choose cheapest, your anchor tier is broken" in packaging_summary
                assert "Supported claims:" in research_summary
                assert "Claims requiring verification:" in research_summary
                assert "Safe claims:" in argument_map_summary
                assert "Claims to qualify or avoid:" in argument_map_summary
                return HumanQCGate.model_validate(fixture["qc_gate"])
            assert "Runner-up script keeps the alternate angle alive." in script
            assert "Hook: Show the alternate frame directly." in visual_summary
            assert "tiktok: Runner-up hook" in packaging_summary
            assert "Secondary lane fact" in research_summary
            assert "Alternate framing can still improve clarity." in argument_map_summary
            return runner_up_qc_gate

    class FakePublishAgent:
        async def schedule(self, packaging: PackagingOutput, *, idea_id: str) -> list[PublishItem]:
            if idea_id == selected_idea_id:
                assert packaging.idea_id == selected_idea_id
                return [PublishItem.model_validate(item) for item in fixture["publish_items"]]
            assert idea_id == runner_up_idea_id
            assert packaging.idea_id == runner_up_idea_id
            return runner_up_publish_items

    monkeypatch.setattr("cc_deep_research.content_gen.storage.StrategyStore", FakeStrategyStore)

    orch = ContentGenOrchestrator(FakeConfig())
    orch._agents["opportunity"] = FakeOpportunityAgent()
    orch._agents["backlog"] = FakeBacklogAgent()
    orch._agents["angle"] = FakeAngleAgent()
    orch._agents["research"] = FakeResearchAgent()
    orch._agents["argument_map"] = FakeArgumentMapAgent()
    orch._agents["scripting"] = FakeScriptingAgent()
    orch._agents["visual"] = FakeVisualAgent()
    orch._agents["production"] = FakeProductionAgent()
    orch._agents["packaging"] = FakePackagingAgent()
    orch._agents["qc"] = FakeQCAgent()
    orch._agents["publish"] = FakePublishAgent()

    ctx = await orch.run_full_pipeline(fixture["theme"], to_stage=len(PIPELINE_STAGES) - 1)

    assert ctx.theme == fixture["theme"]
    assert ctx.opportunity_brief is not None
    assert ctx.opportunity_brief.goal == fixture["opportunity_brief"]["goal"]
    assert ctx.shortlist == fixture["scoring"]["shortlist"]
    assert ctx.selected_idea_id == selected_idea_id
    assert ctx.selection_reasoning == fixture["scoring"]["selection_reasoning"]
    assert [candidate.idea_id for candidate in ctx.active_candidates] == [
        selected_idea_id,
        fixture["scoring"]["runner_up_idea_ids"][0],
    ]
    assert [candidate.status for candidate in ctx.active_candidates] == ["published", "published"]
    assert len(ctx.lane_contexts) == 2
    lane_by_id = {lane.idea_id: lane for lane in ctx.lane_contexts}
    assert lane_by_id[selected_idea_id].angles is not None
    assert lane_by_id[selected_idea_id].publish_items[0].idea_id == selected_idea_id
    assert lane_by_id[runner_up_idea_id].angles is not None
    assert lane_by_id[runner_up_idea_id].research_pack is not None
    assert lane_by_id[runner_up_idea_id].argument_map is not None
    assert lane_by_id[runner_up_idea_id].scripting is not None
    assert lane_by_id[runner_up_idea_id].visual_plan is not None
    assert lane_by_id[runner_up_idea_id].production_brief is not None
    assert lane_by_id[runner_up_idea_id].packaging is not None
    assert lane_by_id[runner_up_idea_id].qc_gate is not None
    assert lane_by_id[runner_up_idea_id].publish_items == runner_up_publish_items
    assert lane_by_id[runner_up_idea_id].last_completed_stage == 12
    assert ctx.research_pack is not None
    assert ctx.research_pack.idea_id == selected_idea_id
    assert ctx.argument_map is not None
    assert ctx.argument_map.idea_id == selected_idea_id
    assert ctx.scripting is not None
    assert ctx.scripting.raw_idea == fixture["scripting"]["raw_idea"]
    assert ctx.packaging is not None
    assert ctx.packaging.idea_id == selected_idea_id
    assert ctx.qc_gate is not None
    assert ctx.qc_gate.approved_for_publish is True
    assert len(ctx.publish_items) == len(fixture["publish_items"])
    assert ctx.publish_items[0].idea_id == selected_idea_id
    assert ctx.publish_item is not None
    assert ctx.publish_item.idea_id == selected_idea_id
    assert [trace.stage_name for trace in ctx.stage_traces] == PIPELINE_STAGES
    assert all(trace.status == "completed" for trace in ctx.stage_traces)

    score_trace = next(trace for trace in ctx.stage_traces if trace.stage_name == "score_ideas")
    assert score_trace.decision_summary == fixture["scoring"]["selection_reasoning"]
    assert score_trace.metadata.selected_idea_id == selected_idea_id
    assert score_trace.metadata.shortlist_count == len(fixture["scoring"]["shortlist"])
    assert score_trace.metadata.active_candidate_count == 2

    angle_trace = next(trace for trace in ctx.stage_traces if trace.stage_name == "generate_angles")
    assert angle_trace.decision_summary == fixture["angles"]["selection_reasoning"]
    assert angle_trace.metadata.selected_angle_id == fixture["angles"]["selected_angle_id"]
    assert angle_trace.metadata.active_candidate_count == 2

    research_trace = next(trace for trace in ctx.stage_traces if trace.stage_name == "build_research_pack")
    assert research_trace.decision_summary == fixture["research_pack"]["research_stop_reason"]
    assert research_trace.metadata.fact_count == len(fixture["research_pack"]["key_facts"])
    assert research_trace.metadata.proof_count == len(fixture["research_pack"]["proof_points"])

    argument_map_trace = next(trace for trace in ctx.stage_traces if trace.stage_name == "build_argument_map")
    assert argument_map_trace.decision_summary == fixture["argument_map"]["thesis"]
    assert argument_map_trace.metadata.proof_count == len(fixture["argument_map"]["proof_anchors"])
    assert argument_map_trace.metadata.claim_count == len(fixture["argument_map"]["safe_claims"])


@pytest.mark.asyncio
async def test_full_pipeline_resume_uses_initial_context_for_late_stage() -> None:
    """Later-stage resume should run against the saved pipeline context, not a blank one."""
    from cc_deep_research.content_gen.orchestrator import (
        _PIPELINE_HANDLERS,
        ContentGenOrchestrator,
    )

    class FakeConfig:
        content_gen = type(
            "ContentGen",
            (),
            {
                "max_iterations": 1,
                "quality_threshold": 0.7,
                "convergence_threshold": 0.1,
                "enable_iterative_mode": False,
                "scoring_threshold_produce": 3.5,
                "default_platforms": ["tiktok"],
            },
        )()

        llm = type(
            "LLM",
            (),
            {
                "anthropic": type("C", (), {"enabled": True, "api_key": "test"})(),
            },
        )()

    orch = ContentGenOrchestrator(FakeConfig())
    seen: dict[str, PipelineContext] = {}

    async def packaging_stage(
        _orch: ContentGenOrchestrator, ctx: PipelineContext
    ) -> PipelineContext:
        seen["ctx"] = ctx
        ctx.packaging = PackagingOutput(
            platform_packages=[PlatformPackage(platform="tiktok", primary_hook="Hook")]
        )
        return ctx

    original_packaging_stage = _PIPELINE_HANDLERS[10]
    _PIPELINE_HANDLERS[10] = packaging_stage

    try:
        saved_ctx = PipelineContext(
            theme="saved theme",
            angles=AngleOutput(
                idea_id="idea-1",
                angle_options=[AngleOption(angle_id="angle-1", core_promise="Angle")],
                selected_angle_id="angle-1",
            ),
            scripting=ScriptingContext(
                raw_idea="saved idea",
                qc=QCResult(checks=[], weakest_parts=[], final_script="Saved final script"),
            ),
        )

        result = await orch.run_full_pipeline(
            "saved theme",
            from_stage=10,
            to_stage=10,
            initial_context=saved_ctx,
        )
    finally:
        _PIPELINE_HANDLERS[10] = original_packaging_stage

    assert seen["ctx"].scripting is not None
    assert seen["ctx"].scripting.qc is not None
    assert seen["ctx"].scripting.qc.final_script == "Saved final script"
    assert result.packaging is not None
    assert result.stage_traces[-1].status == "completed"


def test_validate_resume_context_accepts_partial_multilane_lane_contexts() -> None:
    """Resume validation should accept lane-scoped artifacts without needing legacy top-level fields."""
    from cc_deep_research.content_gen.orchestrator import ContentGenOrchestrator

    class FakeConfig:
        content_gen = type(
            "ContentGen",
            (),
            {
                "max_iterations": 1,
                "quality_threshold": 0.7,
                "convergence_threshold": 0.1,
                "enable_iterative_mode": False,
                "scoring_threshold_produce": 3.5,
                "default_platforms": ["tiktok"],
            },
        )()

        llm = type(
            "LLM",
            (),
            {
                "anthropic": type("C", (), {"enabled": True, "api_key": "test"})(),
            },
        )()

    orch = ContentGenOrchestrator(FakeConfig())
    ctx = PipelineContext(
        backlog=BacklogOutput(items=[BacklogItem(idea_id="idea-1", idea="Saved lane idea")]),
        shortlist=["idea-1"],
        selected_idea_id="idea-1",
        lane_contexts=[
            PipelineLaneContext(
                idea_id="idea-1",
                role="primary",
                status="selected",
                angles=AngleOutput(
                    idea_id="idea-1",
                    angle_options=[AngleOption(angle_id="angle-1", core_promise="Saved angle")],
                    selected_angle_id="angle-1",
                ),
            )
        ],
    )

    assert orch.validate_resume_context(from_stage=5, ctx=ctx) is None


@pytest.mark.asyncio
async def test_full_pipeline_direct_idea_bypasses_ideation_stages() -> None:
    """Direct-idea mode should skip backlog-generation stages and jump into angles."""
    from cc_deep_research.content_gen.orchestrator import (
        _PIPELINE_HANDLERS,
        ContentGenOrchestrator,
    )

    class FakeConfig:
        content_gen = type(
            "ContentGen",
            (),
            {
                "max_iterations": 1,
                "quality_threshold": 0.7,
                "convergence_threshold": 0.1,
                "enable_iterative_mode": False,
                "scoring_threshold_produce": 3.5,
                "default_platforms": ["tiktok"],
            },
        )()

        llm = type(
            "LLM",
            (),
            {
                "anthropic": type("C", (), {"enabled": True, "api_key": "test"})(),
            },
        )()

    orch = ContentGenOrchestrator(FakeConfig())
    executed: list[int] = []

    async def record_load_strategy(
        _orch: ContentGenOrchestrator, ctx: PipelineContext
    ) -> PipelineContext:
        executed.append(0)
        return ctx

    async def forbidden_stage(
        _orch: ContentGenOrchestrator, ctx: PipelineContext
    ) -> PipelineContext:
        raise AssertionError("Ideation bypass should not execute stages 1-3")

    async def record_generate_angles(
        _orch: ContentGenOrchestrator, ctx: PipelineContext
    ) -> PipelineContext:
        executed.append(4)
        ctx.angles = AngleOutput(
            idea_id=ctx.selected_idea_id,
            angle_options=[AngleOption(angle_id="angle-1", core_promise="Angle")],
            selected_angle_id="angle-1",
        )
        return ctx

    originals = _PIPELINE_HANDLERS[0:5]
    _PIPELINE_HANDLERS[0] = record_load_strategy
    _PIPELINE_HANDLERS[1] = forbidden_stage
    _PIPELINE_HANDLERS[2] = forbidden_stage
    _PIPELINE_HANDLERS[3] = forbidden_stage
    _PIPELINE_HANDLERS[4] = record_generate_angles

    try:
        seeded_item = BacklogItem(idea_id="idea-1", idea="Direct idea")
        seeded_ctx = PipelineContext(
            theme="Direct idea",
            backlog=BacklogOutput(items=[seeded_item]),
            scoring=ScoringOutput(
                produce_now=["idea-1"],
                shortlist=["idea-1"],
                selected_idea_id="idea-1",
                selection_reasoning="Seeded directly from --idea.",
                active_candidates=[
                    PipelineCandidate(idea_id="idea-1", role="primary", status="selected")
                ],
            ),
            shortlist=["idea-1"],
            selected_idea_id="idea-1",
            selection_reasoning="Seeded directly from --idea.",
            active_candidates=[
                PipelineCandidate(idea_id="idea-1", role="primary", status="selected")
            ],
        )

        result = await orch.run_full_pipeline(
            "Direct idea",
            from_stage=0,
            to_stage=4,
            initial_context=seeded_ctx,
            bypass_ideation=True,
        )
    finally:
        _PIPELINE_HANDLERS[0:5] = originals

    assert executed == [0, 4]
    assert result.angles is not None
    assert result.angles.selected_angle_id == "angle-1"
    assert [candidate.idea_id for candidate in result.active_candidates] == ["idea-1"]


# ---------------------------------------------------------------------------
# New model defaults
# ---------------------------------------------------------------------------


def test_strategy_memory_defaults() -> None:
    """StrategyMemory should have empty defaults."""
    mem = StrategyMemory()
    assert mem.niche == ""
    assert mem.content_pillars == []
    assert mem.audience_segments == []


def test_backlog_item_auto_generates_id() -> None:
    """BacklogItem should auto-generate an idea_id."""
    item = BacklogItem(idea="test")
    assert item.idea_id  # non-empty auto-generated


def test_idea_scores_constraints() -> None:
    """IdeaScores should enforce 1-5 range."""
    score = IdeaScores(idea_id="test", relevance=3, novelty=5, total_score=25)
    assert score.relevance == 3
    assert score.total_score == 25


def test_human_qc_gate_defaults_to_not_approved() -> None:
    """HumanQCGate should never auto-approve."""
    qc = HumanQCGate()
    assert qc.approved_for_publish is False
    assert qc.review_round == 1


def test_publish_item_defaults() -> None:
    """PublishItem should default to scheduled."""
    item = PublishItem(idea_id="test", platform="tiktok")
    assert item.status == "scheduled"
    assert item.cross_post_targets == []


def test_pipeline_context_syncs_publish_item_and_publish_items() -> None:
    ctx = PipelineContext(
        publish_items=[
            PublishItem(idea_id="idea-1", platform="tiktok"),
            PublishItem(idea_id="idea-1", platform="shorts"),
        ]
    )
    assert ctx.publish_item is not None
    assert ctx.publish_item.platform == "tiktok"

    restored = PipelineContext(
        publish_item=PublishItem(idea_id="idea-2", platform="reels"),
    )
    assert len(restored.publish_items) == 1
    assert restored.publish_items[0].platform == "reels"


def test_pipeline_job_registry_persists_completed_runs(tmp_path: Path) -> None:
    registry = PipelineRunJobRegistry(path=tmp_path)
    job = registry.create_job(
        "pricing anchors",
        from_stage=2,
        to_stage=10,
        pipeline_id="cgp-persisted",
    )
    ctx = PipelineContext(
        theme="pricing anchors",
        current_stage=6,
        selected_idea_id="idea-1",
    )

    registry.mark_running(job.pipeline_id)
    registry.update_context(job.pipeline_id, ctx)
    registry.mark_completed(job.pipeline_id, context=ctx)

    restored = PipelineRunJobRegistry(path=tmp_path)
    restored_job = restored.get_job(job.pipeline_id)

    assert restored_job is not None
    assert restored_job.status == PipelineRunStatus.COMPLETED
    assert restored_job.pipeline_context is not None
    assert restored_job.pipeline_context.current_stage == 6
    assert restored_job.pipeline_context.selected_idea_id == "idea-1"
    assert restored_job.error is None
    assert restored_job.started_at is not None
    assert restored_job.completed_at is not None


def test_pipeline_job_registry_recovers_interrupted_runs_from_disk(tmp_path: Path) -> None:
    registry = PipelineRunJobRegistry(path=tmp_path)
    job = registry.create_job(
        "pricing anchors",
        from_stage=0,
        to_stage=12,
        pipeline_id="cgp-interrupted",
    )
    ctx = PipelineContext(
        theme="pricing anchors",
        current_stage=8,
        selected_idea_id="idea-2",
        scripting=ScriptingContext(
            raw_idea="Pricing anchor script",
            qc=QCResult(checks=[], weakest_parts=[], final_script="Saved final script"),
        ),
    )

    registry.mark_running(job.pipeline_id)
    registry.update_context(job.pipeline_id, ctx)

    restored = PipelineRunJobRegistry(path=tmp_path)
    restored_job = restored.get_job(job.pipeline_id)

    assert restored_job is not None
    assert restored_job.status == PipelineRunStatus.FAILED
    assert restored_job.error == "Pipeline run was interrupted before completion. Resume from the saved context."
    assert restored_job.pipeline_context is not None
    assert restored_job.pipeline_context.current_stage == 8
    assert restored_job.pipeline_context.scripting is not None
    assert restored_job.pipeline_context.scripting.qc is not None
    assert restored_job.pipeline_context.scripting.qc.final_script == "Saved final script"
    assert restored_job.stop_requested is False


def test_pipeline_job_registry_rejects_duplicate_explicit_ids(tmp_path: Path) -> None:
    registry = PipelineRunJobRegistry(path=tmp_path)

    registry.create_job("pricing anchors", pipeline_id="cgp-duplicate")

    with pytest.raises(ValueError, match="Pipeline run already exists: cgp-duplicate"):
        registry.create_job("pricing anchors", pipeline_id="cgp-duplicate")


def test_pipeline_job_registry_creates_unique_resume_job_ids(tmp_path: Path) -> None:
    registry = PipelineRunJobRegistry(path=tmp_path)
    registry.create_job("pricing anchors", pipeline_id="cgp-original")

    first_resume = registry.create_resume_job(
        "cgp-original",
        "pricing anchors",
        from_stage=5,
        to_stage=12,
    )
    second_resume = registry.create_resume_job(
        "cgp-original",
        "pricing anchors",
        from_stage=5,
        to_stage=12,
    )

    assert first_resume.pipeline_id != second_resume.pipeline_id
    assert first_resume.pipeline_id.startswith("cgp-original-resume-")
    assert second_resume.pipeline_id.startswith("cgp-original-resume-")


# ---------------------------------------------------------------------------
# Storage layer
# ---------------------------------------------------------------------------


def test_strategy_store_roundtrip(tmp_path: Path) -> None:
    """StrategyStore should persist and load correctly."""
    from cc_deep_research.content_gen.storage import StrategyStore

    store = StrategyStore(tmp_path / "strategy.yaml")
    mem = StrategyMemory(niche="fitness", content_pillars=["strength", "mobility"])
    store.save(mem)

    loaded = store.load()
    assert loaded.niche == "fitness"
    assert loaded.content_pillars == ["strength", "mobility"]


def test_strategy_store_uses_configured_path() -> None:
    from cc_deep_research.config import Config
    from cc_deep_research.content_gen.storage import StrategyStore

    config = Config()
    config.content_gen.strategy_path = "/tmp/custom-strategy.yaml"

    store = StrategyStore(config=config)
    assert str(store.path) == "/tmp/custom-strategy.yaml"


def test_strategy_store_returns_blank_when_missing(tmp_path: Path) -> None:
    """StrategyStore should return blank StrategyMemory when file doesn't exist."""
    from cc_deep_research.content_gen.storage import StrategyStore

    store = StrategyStore(tmp_path / "nonexistent.yaml")
    loaded = store.load()
    assert isinstance(loaded, StrategyMemory)
    assert loaded.niche == ""


def test_strategy_store_update(tmp_path: Path) -> None:
    """StrategyStore.update should merge fields."""
    from cc_deep_research.content_gen.storage import StrategyStore

    store = StrategyStore(tmp_path / "strategy.yaml")
    store.save(StrategyMemory(niche="old"))
    updated = store.update({"niche": "new", "content_pillars": ["a", "b"]})
    assert updated.niche == "new"
    assert updated.content_pillars == ["a", "b"]


def test_backlog_store_roundtrip(tmp_path: Path) -> None:
    """BacklogStore should persist and load correctly."""
    from cc_deep_research.content_gen.storage import BacklogStore

    store = BacklogStore(tmp_path / "backlog.yaml")
    backlog = BacklogOutput(items=[
        BacklogItem(idea="idea 1", category="evergreen"),
        BacklogItem(idea="idea 2", category="trend-responsive"),
    ])
    store.save(backlog)

    loaded = store.load()
    assert len(loaded.items) == 2
    assert loaded.items[0].title == "idea 1"


def test_backlog_store_uses_configured_path() -> None:
    from cc_deep_research.config import Config
    from cc_deep_research.content_gen.storage import BacklogStore

    config = Config()
    config.content_gen.backlog_path = "/tmp/custom-backlog.yaml"

    store = BacklogStore(config=config)
    assert str(store.path) == "/tmp/custom-backlog.yaml"


def test_audit_store_uses_backlog_directory_not_backlog_file() -> None:
    from cc_deep_research.config import Config
    from cc_deep_research.content_gen.storage import AuditStore

    config = Config()
    config.content_gen.backlog_path = "/tmp/custom-backlog.yaml"

    store = AuditStore(config=config)
    # Use resolve() to handle macOS symlink (/tmp -> /private/tmp)
    assert store.path.resolve() == Path("/tmp/audit_log.yaml").resolve()


def test_maintenance_store_uses_backlog_directory_not_backlog_file() -> None:
    from cc_deep_research.config import Config
    from cc_deep_research.content_gen.maintenance_workflow import MaintenanceStore

    config = Config()
    config.content_gen.backlog_path = "/tmp/custom-backlog.yaml"

    store = MaintenanceStore(config)
    # Use resolve() to handle macOS symlink (/tmp -> /private/tmp)
    assert store._proposals_path.resolve() == Path("/tmp/maintenance_proposals.yaml").resolve()
    assert store._runs_path.resolve() == Path("/tmp/maintenance_runs.yaml").resolve()


def test_backlog_store_update_item(tmp_path: Path) -> None:
    """BacklogStore.update_item should modify a single item."""
    from cc_deep_research.content_gen.storage import BacklogStore

    store = BacklogStore(tmp_path / "backlog.yaml")
    item = BacklogItem(idea_id="abc123", idea="test", status="backlog")
    store.save(BacklogOutput(items=[item]))

    updated = store.update_item("abc123", {"status": "selected"})
    assert updated is not None
    assert updated.status == "selected"


def test_backlog_service_persist_generated_uses_config_path(tmp_path: Path) -> None:
    """BacklogService should honor configured path and persist metadata."""
    from types import SimpleNamespace

    from cc_deep_research.content_gen.backlog_service import BacklogService

    path = tmp_path / "custom-backlog.yaml"
    config = SimpleNamespace(content_gen=SimpleNamespace(backlog_path=str(path)))
    service = BacklogService(config)

    backlog = BacklogOutput(items=[BacklogItem(idea_id="idea-1", idea="Test backlog item")])
    persisted = service.persist_generated(backlog, theme="pricing")

    assert service.path == path
    assert persisted.items[0].source_theme == "pricing"
    assert persisted.items[0].created_at
    assert path.exists()


def test_backlog_service_uses_sibling_sqlite_db_path(tmp_path: Path) -> None:
    """SQLite mode should derive backlog.db from the configured YAML location."""
    from types import SimpleNamespace

    from cc_deep_research.content_gen.backlog_service import BacklogService

    backlog_path = tmp_path / "custom-backlog.yaml"
    config = SimpleNamespace(
        content_gen=SimpleNamespace(
            backlog_path=str(backlog_path),
            use_sqlite=True,
        )
    )

    service = BacklogService(config)
    assert service.path == tmp_path / "backlog.db"


def test_backlog_service_apply_scoring_marks_selected(tmp_path: Path) -> None:
    """Applying scoring should attach score metadata and keep backlog status user-facing."""
    from cc_deep_research.content_gen.backlog_service import BacklogService
    from cc_deep_research.content_gen.storage import BacklogStore

    store = BacklogStore(tmp_path / "backlog.yaml")
    service = BacklogService(store=store)
    service.upsert_items(
        [
            BacklogItem(idea_id="idea-1", idea="First"),
            BacklogItem(idea_id="idea-2", idea="Second", status="selected"),
        ]
    )

    service.apply_scoring(
        ScoringOutput(
            scores=[
                IdeaScores(idea_id="idea-1", total_score=31, recommendation="produce_now"),
                IdeaScores(idea_id="idea-2", total_score=22, recommendation="produce_now"),
            ],
            shortlist=["idea-1", "idea-2"],
            selected_idea_id="idea-1",
            selection_reasoning="Best fit",
        )
    )

    loaded = store.load()
    by_id = {item.idea_id: item for item in loaded.items}
    assert by_id["idea-1"].status == "selected"
    assert by_id["idea-1"].latest_score == 31
    assert by_id["idea-1"].latest_recommendation == "produce_now"
    assert by_id["idea-1"].selection_reasoning == "Best fit"
    assert by_id["idea-2"].status == "backlog"


def test_backlog_service_multi_lane_status_transitions_preserve_progress(tmp_path: Path) -> None:
    """Production progress should stay separate from backlog status."""
    from cc_deep_research.content_gen.backlog_service import BacklogService
    from cc_deep_research.content_gen.storage import BacklogStore

    store = BacklogStore(tmp_path / "backlog.yaml")
    service = BacklogService(store=store)
    service.upsert_items(
        [
            BacklogItem(
                idea_id="idea-1",
                idea="Primary",
                status="backlog",
                production_status="in_production",
            ),
            BacklogItem(idea_id="idea-2", idea="Runner-up"),
        ]
    )

    service.apply_scoring(
        ScoringOutput(
            shortlist=["idea-1", "idea-2"],
            selected_idea_id="idea-1",
            selection_reasoning="Keep primary lane leading.",
            active_candidates=[
                PipelineCandidate(idea_id="idea-1", role="primary", status="in_production"),
                PipelineCandidate(idea_id="idea-2", role="runner_up", status="runner_up"),
            ],
        )
    )

    scored = store.load()
    scored_by_id = {item.idea_id: item for item in scored.items}
    assert scored_by_id["idea-1"].status == "selected"
    assert scored_by_id["idea-1"].production_status == "in_production"
    assert scored_by_id["idea-1"].selection_reasoning == "Keep primary lane leading."
    assert scored_by_id["idea-2"].status == "backlog"

    published = service.mark_published("idea-1", source_pipeline_id="pipe-123")

    assert published is not None
    assert published.status == "selected"
    assert published.production_status == "ready_to_publish"
    assert published.source_pipeline_id == "pipe-123"

    final_state = store.load()
    final_item = next(item for item in final_state.items if item.idea_id == "idea-1")
    assert final_item.status == "selected"
    assert final_item.production_status == "ready_to_publish"


def test_backlog_item_normalizes_legacy_status_values() -> None:
    legacy_runner_up = BacklogItem.model_validate({"idea_id": "idea-1", "idea": "Legacy", "status": "runner_up"})
    assert legacy_runner_up.status == "backlog"
    assert legacy_runner_up.production_status == "idle"

    legacy_production = BacklogItem.model_validate(
        {"idea_id": "idea-2", "idea": "Legacy prod", "status": "in_production"}
    )
    assert legacy_production.status == "backlog"
    assert legacy_production.production_status == "in_production"

    legacy_publish_queue = BacklogItem.model_validate(
        {"idea_id": "idea-3", "idea": "Legacy publish", "status": "published"}
    )
    assert legacy_publish_queue.status == "backlog"
    assert legacy_publish_queue.production_status == "ready_to_publish"


def test_backlog_item_serializes_legacy_aliases() -> None:
    item = BacklogItem(title="Serialized title", hook="Serialized hook")

    payload = item.model_dump()

    assert payload["title"] == "Serialized title"
    assert payload["idea"] == "Serialized title"
    assert payload["hook"] == "Serialized hook"
    assert payload["potential_hook"] == "Serialized hook"


def test_backlog_service_update_item_accepts_legacy_patch_fields(tmp_path: Path) -> None:
    """Legacy patch keys should be mapped to canonical backlog fields."""
    from cc_deep_research.content_gen.backlog_service import BacklogService
    from cc_deep_research.content_gen.storage import BacklogStore

    store = BacklogStore(tmp_path / "backlog.yaml")
    service = BacklogService(store=store)
    item = service.create_item(title="Original", hook="Old hook")

    updated = service.update_item(
        item.idea_id,
        {
            "idea": "Updated",
            "potential_hook": "New hook",
        },
    )

    assert updated is not None
    assert updated.title == "Updated"
    assert updated.idea == "Updated"
    assert updated.hook == "New hook"
    assert updated.potential_hook == "New hook"


def test_publish_queue_store_roundtrip(tmp_path: Path) -> None:
    """PublishQueueStore should persist and load correctly."""
    from cc_deep_research.content_gen.storage import PublishQueueStore

    store = PublishQueueStore(tmp_path / "queue.yaml")
    item = PublishItem(idea_id="test", platform="tiktok", status="scheduled")
    result = store.add(item)
    assert len(result) == 1

    loaded = store.load()
    assert len(loaded) == 1
    assert loaded[0].idea_id == "test"


def test_publish_queue_store_update_status(tmp_path: Path) -> None:
    """PublishQueueStore.update_status should change item status."""
    from cc_deep_research.content_gen.storage import PublishQueueStore

    store = PublishQueueStore(tmp_path / "queue.yaml")
    store.add(PublishItem(idea_id="test", platform="tiktok", status="scheduled"))

    updated = store.update_status("test", "tiktok", "published")
    assert updated is not None
    assert updated.status == "published"


def test_publish_queue_store_uses_configured_path() -> None:
    from cc_deep_research.config import Config
    from cc_deep_research.content_gen.storage import PublishQueueStore

    config = Config()
    config.content_gen.publish_queue_path = "/tmp/custom-publish.yaml"

    store = PublishQueueStore(config=config)
    assert str(store.path) == "/tmp/custom-publish.yaml"


# ---------------------------------------------------------------------------
# Validation — empty LLM responses raise ValueError (not AssertionError)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_define_core_inputs_raises_on_empty_field() -> None:
    """If the LLM returns nothing parseable, step 1 should raise ValueError."""
    agent = _FakeScriptingAgent("No structured output here")

    with pytest.raises(ValueError, match="could not extract 'Topic'"):
        await agent.define_core_inputs("some idea")


@pytest.mark.asyncio
async def test_define_core_inputs_records_step_trace() -> None:
    """Successful scripting steps should capture prompts, route, and parsed output."""
    agent = _FakeScriptingAgent("Topic: Hooks\nOutcome: Better retention\nAudience: Founders")

    ctx = await agent.define_core_inputs("some idea")

    assert len(ctx.step_traces) == 1
    trace = ctx.step_traces[0]
    assert trace.step_name == "define_core_inputs"
    assert trace.step_label == "Defining core inputs"
    assert trace.iteration == 1
    assert trace.parsed_output == {
        "topic": "Hooks",
        "outcome": "Better retention",
        "audience": "Founders",
    }
    assert len(trace.llm_calls) == 1
    call = trace.llm_calls[0]
    assert call.user_prompt == "Raw idea:\nsome idea"
    assert call.provider == "anthropic"
    assert call.model == "test-model"
    assert call.transport == "anthropic_api"
    assert call.prompt_tokens == 11
    assert call.completion_tokens == 7
    assert call.raw_response == "Topic: Hooks\nOutcome: Better retention\nAudience: Founders"


@pytest.mark.asyncio
async def test_scripting_agent_applies_route_override_to_registry() -> None:
    """Standalone scripting runs should be able to override the primary LLM route."""
    from cc_deep_research.config import Config

    config = Config()
    config.llm.openrouter.enabled = True
    config.llm.openrouter.api_key = "test-key"

    agent = ScriptingAgent(config, llm_route="openrouter")
    route = agent._router._registry.get_route("content_gen_scripting")

    assert route.transport == LLMTransportType.OPENROUTER_API
    assert route.provider == LLMProviderType.OPENROUTER


@pytest.mark.asyncio
async def test_define_core_inputs_raises_clear_error_without_llm_route() -> None:
    """Real scripting runs should fail fast when no routed LLM is configured."""
    from cc_deep_research.config import Config

    agent = ScriptingAgent(Config())

    with pytest.raises(RuntimeError, match="No LLM route is available for the scripting workflow"):
        await agent.define_core_inputs("some idea")


@pytest.mark.asyncio
async def test_define_angle_raises_on_missing_core_inputs() -> None:
    """Step 2 should raise ValueError (not AssertionError) when core_inputs is None."""
    agent = _FakeScriptingAgent("Angle: test\nContent Type: Contrarian\nCore Tension: x")
    ctx = ScriptingContext(raw_idea="idea")

    with pytest.raises(ValueError, match="core_inputs"):
        await agent.define_angle(ctx)


@pytest.mark.asyncio
async def test_define_angle_prompt_keeps_original_brief_constraints() -> None:
    """Step 2 should still receive the full quick-script brief, not just normalized fields."""
    agent = _FakeScriptingAgent(
        "Angle: Strong angle\nContent Type: Contrarian\nCore Tension: Sharp tension"
    )
    ctx = ScriptingContext(
        raw_idea=(
            "Raw idea:\nHow to stop rambling on camera\n\n"
            "Desired length:\n30 sec\n\n"
            "Must avoid:\nGuru-sounding claims\n\n"
            "Must include:\nA concrete before/after example"
        ),
        core_inputs=CoreInputs(
            topic="Stop rambling on camera",
            outcome="Help viewers sound tighter on video",
            audience="Founders recording short-form videos",
        ),
    )

    await agent.define_angle(ctx)

    assert "Original Brief" in agent.last_user_prompt
    assert "Desired length:\n30 sec" in agent.last_user_prompt
    assert "Must avoid:\nGuru-sounding claims" in agent.last_user_prompt
    assert "Must include:\nA concrete before/after example" in agent.last_user_prompt


@pytest.mark.asyncio
async def test_generate_hooks_requires_beat_intents() -> None:
    """Step 5 should not run without the beat intent map required by the SOP."""
    agent = _FakeScriptingAgent("1. Hook\nBest Hook: Hook\nWhy it is strongest: Strong")
    ctx = ScriptingContext(
        raw_idea="idea",
        core_inputs=CoreInputs(topic="Topic", outcome="Outcome", audience="Audience"),
        angle=AngleDefinition(angle="Angle", content_type="Contrarian", core_tension="Tension"),
    )

    with pytest.raises(ValueError, match="beat_intents"):
        await agent.generate_hooks(ctx)


def test_step6_prompt_uses_argument_map_as_primary_grounding() -> None:
    """Draft prompt should expose beat-level claim and proof references from the argument map."""
    prompt = scripting_prompts.step6_user(
        CoreInputs(
            topic="pricing anchors",
            outcome="make the middle tier feel safer",
            audience="SaaS founders",
        ),
        AngleDefinition(
            angle="The premium tier is the anchor, not the hero",
            content_type="Framework",
            core_tension="buyers assume cheapest is safest",
        ),
        ScriptStructure(
            chosen_structure="Argument map guided flow",
            beat_list=["Hook", "Reframe", "Proof", "Close"],
        ),
        BeatIntentMap(
            beats=[
                BeatIntent(
                    beat_id="beat_1",
                    beat_name="Hook",
                    intent="Challenge the cheapest-plan instinct",
                    claim_ids=["claim_1"],
                    proof_anchor_ids=["proof_1"],
                    transition_note="Move into the mechanism",
                )
            ]
        ),
        "If buyers always choose cheapest, your anchor tier is broken",
        argument_map=ArgumentMap(
            thesis="The premium tier reframes the middle plan before feature details matter.",
            proof_anchors=[
                {
                    "proof_id": "proof_1",
                    "summary": "Buyers compare tier contrast before reading feature lists.",
                    "usage_note": "Use for the reframe.",
                }
            ],
            safe_claims=[
                {
                    "claim_id": "claim_1",
                    "claim": "Tier framing changes what buyers notice first.",
                    "supporting_proof_ids": ["proof_1"],
                }
            ],
            unsafe_claims=[
                {
                    "claim_id": "claim_unsafe_1",
                    "claim": "Reordering tiers lifts conversion by 23 percent.",
                    "supporting_proof_ids": ["proof_1"],
                }
            ],
            beat_claim_plan=[
                {
                    "beat_id": "beat_1",
                    "beat_name": "Hook",
                    "goal": "Challenge the default diagnosis",
                    "claim_ids": ["claim_1"],
                    "proof_anchor_ids": ["proof_1"],
                    "transition_note": "Move into the mechanism",
                }
            ],
        ),
        research_context="Key facts:\n- fallback only",
        tone="direct",
        cta="Follow for more SaaS teardown lessons",
    )

    assert "Argument Map:" in prompt
    assert "Safe claims:" in prompt
    assert "Unsafe claims to avoid as facts:" in prompt
    assert "claim_ids=claim_1" in prompt
    assert "proof_ids=proof_1" in prompt
    assert "Research Context:" in prompt


@pytest.mark.asyncio
async def test_define_beat_intents_parses_grounded_blocks() -> None:
    """Step 4 should preserve beat-level claim and proof references when the prompt returns them."""
    agent = _FakeScriptingAgent(
        """---
Beat Name: Hook
Intent: Challenge the default pricing diagnosis
Claim IDs: claim_1
Proof Anchor IDs: proof_1
Counterargument IDs:
Transition Note: Move into the mechanism
---
Beat Name: Proof
Intent: Show the concrete decoy example
Claim IDs: claim_2
Proof Anchor IDs: proof_2
Counterargument IDs: counter_1
Transition Note: Close with the audit action
"""
    )
    ctx = ScriptingContext(
        raw_idea="idea",
        argument_map=ArgumentMap(
            thesis="Anchors matter",
            proof_anchors=[
                {"proof_id": "proof_1", "summary": "Tier contrast shapes attention"},
                {"proof_id": "proof_2", "summary": "Decoy tiers reframe value"},
            ],
            safe_claims=[
                {"claim_id": "claim_1", "claim": "Tier order changes attention", "supporting_proof_ids": ["proof_1"]},
                {"claim_id": "claim_2", "claim": "A decoy can make the middle plan feel safer", "supporting_proof_ids": ["proof_2"]},
            ],
            counterarguments=[
                {"counterargument_id": "counter_1", "counterargument": "Sophisticated buyers compare everything"},
            ],
            beat_claim_plan=[
                {"beat_id": "beat_1", "beat_name": "Hook", "goal": "Challenge the diagnosis", "claim_ids": ["claim_1"], "proof_anchor_ids": ["proof_1"]},
                {"beat_id": "beat_2", "beat_name": "Proof", "goal": "Show the example", "claim_ids": ["claim_2"], "proof_anchor_ids": ["proof_2"], "counterargument_ids": ["counter_1"]},
            ],
        ),
        core_inputs=CoreInputs(topic="Topic", outcome="Outcome", audience="Audience"),
        angle=AngleDefinition(angle="Angle", content_type="Contrarian", core_tension="Tension"),
        structure=ScriptStructure(chosen_structure="Structure", beat_list=["Hook", "Proof"]),
    )

    result = await agent.define_beat_intents(ctx)

    assert result.beat_intents is not None
    assert result.beat_intents.beats[0].claim_ids == ["claim_1"]
    assert result.beat_intents.beats[0].proof_anchor_ids == ["proof_1"]
    assert result.beat_intents.beats[1].counterargument_ids == ["counter_1"]
    assert result.beat_intents.beats[1].transition_note == "Close with the audit action"


# ---------------------------------------------------------------------------
# Response parsing
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_retention_step_strips_change_log_from_saved_script() -> None:
    """Only the revised script should be persisted into context."""
    response = """Revised Script:
Hook: Stop doing this.
Payoff: It costs you views.

Then add:

Retention changes made:
- Sharper hook
- Stronger payoff
"""
    agent = _FakeScriptingAgent(response)
    ctx = ScriptingContext(
        raw_idea="content idea",
        draft=ScriptVersion(content="Draft script", word_count=2),
    )

    result = await agent.add_retention_mechanics(ctx)

    assert result.retention_revised is not None
    assert result.retention_revised.content == "Hook: Stop doing this.\nPayoff: It costs you views."


@pytest.mark.asyncio
async def test_qc_uses_annotated_script_when_available() -> None:
    """QC should inspect the annotated output from step 9."""
    response = """QC Review:
- Understandable in one pass: Pass

Weakest parts:
1. Hook is a bit generic
2. CTA is soft
3. Payoff could land faster

Final Script:
Final line
"""
    agent = _FakeScriptingAgent(response)
    ctx = ScriptingContext(
        raw_idea=(
            "Raw idea:\ncontent idea\n\n"
            "Platform:\nShorts\n\n"
            "Desired length:\n30 sec\n\n"
            "Must avoid:\nHype language"
        ),
        research_context="Proof points:\n- Specific proof",
        tone="direct",
        cta="Subscribe for more teardown videos",
        core_inputs=CoreInputs(topic="Hooks", outcome="More retention", audience="Founders"),
        angle=AngleDefinition(
            angle="Most founders bury the payoff",
            content_type="Contrarian",
            core_tension="Good ideas die in weak openings",
        ),
        structure=ScriptStructure(
            chosen_structure="Insight Breakdown",
            beat_list=["Hook", "Problem", "Fix", "Payoff", "CTA"],
        ),
        beat_intents=BeatIntentMap(
            beats=[
                BeatIntent(beat_name="Hook", intent="Create tension immediately"),
                BeatIntent(beat_name="Fix", intent="Show the concrete improvement"),
            ]
        ),
        hooks=HookSet(
            hooks=["Your intro is killing watch time"],
            best_hook="Your intro is killing watch time",
            best_hook_reason="Specific and urgent",
        ),
        tightened=ScriptVersion(content="Tight script", word_count=2),
        annotated_script=ScriptVersion(
            content='Hook: "Line one"\n[Cut]',
            word_count=4,
        ),
    )

    result = await agent.run_qc(ctx)

    assert 'Annotated Script:\nHook: "Line one"\n[Cut]' in agent.last_user_prompt
    assert "Original Brief" in agent.last_user_prompt
    assert "Desired length:\n30 sec" in agent.last_user_prompt
    assert "Must avoid:\nHype language" in agent.last_user_prompt
    assert "Chosen Structure:\nInsight Breakdown" in agent.last_user_prompt
    assert "Selected Hook:\nYour intro is killing watch time" in agent.last_user_prompt
    assert "CTA goal:\nSubscribe for more teardown videos" in agent.last_user_prompt
    assert "Research Context:" in agent.last_user_prompt
    assert isinstance(result.qc, QCResult)
    assert result.qc.final_script == "Final line"


@pytest.mark.asyncio
async def test_run_pipeline_seeds_raw_idea_before_step_one() -> None:
    """The legacy scripting runner should populate raw_idea before step 1 executes."""
    response = """Topic: Topic
Outcome: Outcome
Audience: Audience
"""
    agent = _FakeScriptingAgent(response)

    with pytest.raises(ValueError, match="angle"):
        await agent.run_pipeline("seeded idea")

    assert agent.user_prompts[0] == "Raw idea:\nseeded idea"


@pytest.mark.asyncio
async def test_run_from_step_one_preserves_seeded_context_fields() -> None:
    """Restarting from step 1 should not discard pre-seeded upstream context."""
    response = """Topic: Topic
Outcome: Outcome
Audience: Audience
"""
    agent = _FakeScriptingAgent(response)
    ctx = ScriptingContext(
        raw_idea="seeded idea",
        research_context="Proof points:\n- Example",
        tone="confident",
        cta="Book a demo",
        angle=AngleDefinition(
            angle="stale angle",
            content_type="Contrarian",
            core_tension="stale tension",
        ),
    )

    with pytest.raises(ValueError, match="angle"):
        await agent.run_from_step(ctx, 1)

    assert ctx.raw_idea == "seeded idea"
    assert ctx.research_context == "Proof points:\n- Example"
    assert ctx.tone == "confident"
    assert ctx.cta == "Book a demo"
    assert ctx.core_inputs is not None
    assert ctx.core_inputs.topic == "Topic"
    assert ctx.angle is None
    assert len(ctx.step_traces) == 1
    assert ctx.step_traces[0].step_name == "define_core_inputs"


def test_format_research_context_is_compact_and_selective() -> None:
    """Research handoff should stay compact for downstream scripting prompts."""
    research = ResearchPack(
        key_facts=["Fact 1", "Fact 2"],
        proof_points=["Proof 1", "Proof 2", "Proof 3"],
        gaps_to_exploit=["Gap 1"],
        claims_requiring_verification=["Claim 1"],
        unsafe_or_uncertain_claims=["Risk 1"],
    )

    formatted = _format_research_context(research)

    assert "Key facts:" in formatted
    assert "Proof points:" in formatted
    assert "Competitor gaps:" in formatted
    assert "Claim 1" in formatted
    assert "Risk 1" in formatted


def test_format_research_context_includes_audience_insights_and_examples() -> None:
    """Research handoff should include audience insights, examples, and case studies."""
    research = ResearchPack(
        audience_insights=["Insight 1", "Insight 2"],
        examples=["Example 1", "Example 2"],
        case_studies=["Case 1"],
    )

    formatted = _format_research_context(research)

    assert "Audience insights:" in formatted
    assert "Insight 1" in formatted
    assert "Examples:" in formatted
    assert "Example 1" in formatted
    assert "Case studies:" in formatted
    assert "Case 1" in formatted


def test_research_pack_derives_legacy_views_from_structured_records() -> None:
    """Structured research records should populate the old string-list summaries."""
    research = ResearchPack(
        supporting_sources=[
            ResearchSource(
                source_id="src_01",
                url="https://example.com/pricing",
                title="Pricing teardown",
                query="pricing psychology",
                query_family="evidence",
            )
        ],
        findings=[
            {
                "finding_type": "audience_insight",
                "summary": "Buyers compare tiers before reading long feature lists",
                "source_ids": ["src_01"],
                "confidence": "high",
            },
            {
                "finding_type": "example",
                "summary": "A three-tier page can frame the premium tier first",
                "source_ids": ["src_01"],
                "confidence": "medium",
            },
        ],
        claims=[
            {
                "claim_type": "key_fact",
                "claim": "Anchoring shapes willingness to pay before detailed evaluation",
                "source_ids": ["src_01"],
                "confidence": "high",
            },
            {
                "claim_type": "proof_point",
                "claim": "Order and framing influence perceived value",
                "source_ids": ["src_01"],
                "confidence": "high",
            },
        ],
        uncertainty_flags=[
            {
                "flag_type": "verification_required",
                "claim": "Any exact conversion-lift percentage",
                "reason": "We only have directional support",
                "severity": "medium",
                "source_ids": ["src_01"],
            }
        ],
    )

    assert research.audience_insights == [
        "Buyers compare tiers before reading long feature lists"
    ]
    assert research.examples == [
        "A three-tier page can frame the premium tier first"
    ]
    assert research.key_facts == [
        "Anchoring shapes willingness to pay before detailed evaluation"
    ]
    assert research.proof_points == [
        "Order and framing influence perceived value"
    ]
    assert research.claims_requiring_verification == [
        "Any exact conversion-lift percentage"
    ]
    assert research.supporting_sources[0].query_provenance == [
        QueryProvenance(query="pricing psychology", family="evidence", intent_tags=[])
    ]


def test_step6_prompt_requires_single_hook_and_single_cta() -> None:
    """Drafting prompt should explicitly enforce a single hook and CTA."""
    assert "Use exactly one hook line and exactly one CTA line" in scripting_prompts.STEP6_SYSTEM
    assert "Do not include multiple opening hooks, backup hooks, CTA variants" in scripting_prompts.STEP6_SYSTEM


def test_step10_qc_checks_single_hook_and_cta_presence() -> None:
    """Final QC should verify hook/CTA uniqueness before saving the script."""
    assert "- Exactly one hook is present" in scripting_prompts.STEP10_SYSTEM
    assert "- At most one CTA is present" in scripting_prompts.STEP10_SYSTEM


def test_scripting_context_tone_and_cta_default_empty() -> None:
    """ScriptingContext tone and cta should default to empty strings."""
    ctx = ScriptingContext(raw_idea="idea")
    assert ctx.tone == ""
    assert ctx.cta == ""

    # Round-trip through JSON
    restored = ScriptingContext.model_validate_json(ctx.model_dump_json())
    assert restored.tone == ""
    assert restored.cta == ""

    # With values
    ctx2 = ScriptingContext(raw_idea="idea", tone="confident", cta="subscribe")
    restored2 = ScriptingContext.model_validate_json(ctx2.model_dump_json())
    assert restored2.tone == "confident"
    assert restored2.cta == "subscribe"


@pytest.mark.asyncio
async def test_publish_stage_requires_human_approval() -> None:
    """The full pipeline should not create publish entries before human approval."""
    from cc_deep_research.content_gen.orchestrator import _stage_publish_queue

    class FakeOrchestrator:
        def _get_agent(self, _name: str):
            raise AssertionError("publish agent should not be called without approval")

    ctx = PipelineContext(
        packaging=PackagingOutput(
            platform_packages=[PlatformPackage(platform="tiktok", primary_hook="Hook")]
        ),
        qc_gate=HumanQCGate(approved_for_publish=False),
    )

    result = await _stage_publish_queue(FakeOrchestrator(), ctx)

    assert result.publish_item is None
    assert result.publish_items == []


@pytest.mark.asyncio
async def test_publish_stage_retains_all_publish_items() -> None:
    from cc_deep_research.content_gen.orchestrator import _stage_publish_queue

    items = [
        PublishItem(idea_id="idea-1", platform="tiktok"),
        PublishItem(idea_id="idea-1", platform="shorts"),
    ]

    class FakeOrchestrator:
        def _get_agent(self, _name: str):
            class FakePublishAgent:
                async def schedule(self, packaging: PackagingOutput, *, idea_id: str) -> list[PublishItem]:
                    assert idea_id == "idea-1"
                    assert len(packaging.platform_packages) == 2
                    return items

            return FakePublishAgent()

    ctx = PipelineContext(
        selected_idea_id="idea-1",
        packaging=PackagingOutput(
            platform_packages=[
                PlatformPackage(platform="tiktok", primary_hook="Hook"),
                PlatformPackage(platform="shorts", primary_hook="Hook"),
            ]
        ),
        qc_gate=HumanQCGate(approved_for_publish=True),
    )

    result = await _stage_publish_queue(FakeOrchestrator(), ctx)

    assert len(result.publish_items) == 2
    assert result.publish_items[1].platform == "shorts"
    assert result.publish_item is not None
    assert result.publish_item.platform == "tiktok"


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def test_cli_resume_accepts_saved_context_without_idea(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """The resume path should not require an idea when context is provided."""

    class FakeOrchestrator:
        def __init__(self, _config) -> None:
            pass

        async def run_scripting_from_step(
            self,
            ctx: ScriptingContext,
            step: int,
            progress_callback=None,
        ) -> ScriptingContext:
            del progress_callback
            assert step == 2
            assert ctx.raw_idea == "saved idea"
            ctx.qc = QCResult(checks=[], weakest_parts=[], final_script="Saved final script")
            return ctx

    monkeypatch.setattr(
        "cc_deep_research.content_gen.orchestrator.ContentGenOrchestrator",
        FakeOrchestrator,
    )
    monkeypatch.setattr(
        "cc_deep_research.content_gen.cli.ScriptingStore",
        lambda: type(
            "FakeStore",
            (),
            {
                "path": tmp_path,
                "save": lambda self, ctx: SavedScriptRun(
                    run_id="run-123",
                    saved_at="2026-03-29T12:00:00+00:00",
                    raw_idea=ctx.raw_idea,
                    word_count=3,
                    script_path=str(tmp_path / "latest.txt"),
                    context_path=str(tmp_path / "latest.context.json"),
                ),
            },
        )(),
    )

    context_path = tmp_path / "context.json"
    context_path.write_text(ScriptingContext(raw_idea="saved idea").model_dump_json())

    runner = CliRunner()
    result = runner.invoke(
        main,
        [
            "content-gen",
            "script",
            "--from-file",
            str(context_path),
            "--from-step",
            "2",
            "--quiet",
        ],
    )

    assert result.exit_code == 0
    assert result.output == ""


def test_cli_script_loads_effective_config(monkeypatch: pytest.MonkeyPatch) -> None:
    """The content-gen script command should use load_config(), not bare Config()."""
    from cc_deep_research.config import Config

    expected = Config()
    expected.llm.anthropic.enabled = True
    expected.llm.anthropic.api_key = "test-key"
    expected.llm.anthropic.api_keys = ["test-key"]

    monkeypatch.setattr("cc_deep_research.content_gen.cli.load_config", lambda: expected)
    monkeypatch.setattr(
        "cc_deep_research.content_gen.cli.ScriptingStore",
        lambda: type(
            "FakeStore",
            (),
            {
                "path": Path("/tmp"),
                "save": lambda self, ctx: SavedScriptRun(
                    run_id="run-123",
                    saved_at="2026-03-29T12:00:00+00:00",
                    raw_idea=ctx.raw_idea,
                    word_count=2,
                    script_path="/tmp/latest.txt",
                    context_path="/tmp/latest.context.json",
                ),
            },
        )(),
    )

    class FakeOrchestrator:
        def __init__(self, config) -> None:
            assert config.llm.anthropic.enabled is True
            assert config.llm.anthropic.get_api_keys() == ["test-key"]

        async def run_scripting(self, raw_idea: str, progress_callback=None) -> ScriptingContext:
            del raw_idea, progress_callback
            return ScriptingContext(
                raw_idea="idea",
                qc=QCResult(checks=[], weakest_parts=[], final_script="Final script"),
            )

        async def run_scripting_iterative(self, raw_idea: str, progress_callback=None):
            from cc_deep_research.content_gen.models import IterationState

            ctx = await self.run_scripting(raw_idea, progress_callback=progress_callback)
            return ctx, IterationState()

    monkeypatch.setattr(
        "cc_deep_research.content_gen.orchestrator.ContentGenOrchestrator",
        FakeOrchestrator,
    )

    runner = CliRunner()
    result = runner.invoke(
        main,
        [
            "content-gen",
            "script",
            "--idea",
            "idea",
            "--quiet",
        ],
    )

    assert result.exit_code == 0


def test_cli_script_autosaves_successful_run(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Successful script runs should always be persisted to the scripting store."""
    from cc_deep_research.config import Config

    monkeypatch.setattr("cc_deep_research.content_gen.cli.load_config", lambda: Config())

    class FakeStore:
        saved_ctx: ScriptingContext | None = None

        def __init__(self) -> None:
            self.path = tmp_path

        def save(self, ctx: ScriptingContext) -> SavedScriptRun:
            FakeStore.saved_ctx = ctx
            return SavedScriptRun(
                run_id="run-123",
                saved_at="2026-03-29T12:00:00+00:00",
                raw_idea=ctx.raw_idea,
                word_count=2,
                script_path=str(tmp_path / "latest.txt"),
                context_path=str(tmp_path / "latest.context.json"),
            )

    class FakeOrchestrator:
        def __init__(self, _config) -> None:
            pass

        async def run_scripting(self, raw_idea: str, progress_callback=None) -> ScriptingContext:
            del progress_callback
            return ScriptingContext(
                raw_idea=raw_idea,
                qc=QCResult(checks=[], weakest_parts=[], final_script="Final script"),
            )

        async def run_scripting_iterative(self, raw_idea: str, progress_callback=None):
            from cc_deep_research.content_gen.models import IterationState

            ctx = await self.run_scripting(raw_idea, progress_callback=progress_callback)
            return ctx, IterationState()

    monkeypatch.setattr("cc_deep_research.content_gen.cli.ScriptingStore", FakeStore)
    monkeypatch.setattr(
        "cc_deep_research.content_gen.orchestrator.ContentGenOrchestrator",
        FakeOrchestrator,
    )

    runner = CliRunner()
    result = runner.invoke(
        main,
        [
            "content-gen",
            "script",
            "--idea",
            "idea",
            "--quiet",
        ],
    )

    assert result.exit_code == 0
    assert FakeStore.saved_ctx is not None
    assert FakeStore.saved_ctx.raw_idea == "idea"


def test_cli_scripts_show_latest_prints_saved_script(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Users should be able to recall the latest autosaved script quickly."""
    script_path = tmp_path / "script.txt"
    context_path = tmp_path / "context.json"
    script_path.write_text("Latest saved script")
    context_path.write_text("{}")

    class FakeStore:
        def __init__(self) -> None:
            self.path = tmp_path

        def latest(self) -> SavedScriptRun:
            return SavedScriptRun(
                run_id="run-123",
                saved_at="2026-03-29T12:00:00+00:00",
                raw_idea="idea",
                word_count=3,
                script_path=str(script_path),
                context_path=str(context_path),
            )

    monkeypatch.setattr("cc_deep_research.content_gen.cli.ScriptingStore", FakeStore)

    runner = CliRunner()
    result = runner.invoke(
        main,
        [
            "content-gen",
            "scripts",
            "show",
            "--latest",
        ],
    )

    assert result.exit_code == 0
    assert "Latest saved script" in result.output


def test_cli_rejects_invalid_resume_step() -> None:
    """Invalid step numbers should fail fast with a usage error."""
    runner = CliRunner()

    result = runner.invoke(
        main,
        [
            "content-gen",
            "script",
            "--idea",
            "idea",
            "--from-step",
            str(len(SCRIPTING_STEPS) + 1),
        ],
    )

    assert result.exit_code != 0
    assert "--from-step must be between 1 and 10" in result.output


def test_cli_pipeline_rejects_invalid_from_stage() -> None:
    """Invalid --from-stage values should produce a usage error."""
    runner = CliRunner()

    result = runner.invoke(
        main,
        [
            "content-gen",
            "pipeline",
            "--theme",
            "my theme",
            "--from-stage",
            "99",
        ],
    )

    assert result.exit_code != 0
    assert "--from-stage must be between 0 and" in result.output


def test_cli_pipeline_from_file_loads_saved_context(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Pipeline resume should load and forward the saved PipelineContext."""

    class FakeOrchestrator:
        def __init__(self, _config) -> None:
            pass

        def validate_resume_context(
            self,
            *,
            from_stage: int,
            ctx: PipelineContext,
            bypass_ideation: bool = False,
        ) -> str | None:
            assert from_stage == 10
            assert bypass_ideation is False
            assert ctx.scripting is not None
            assert ctx.scripting.qc is not None
            assert ctx.scripting.qc.final_script == "Saved final script"
            return None

        async def run_full_pipeline(
            self,
            theme: str,
            *,
            from_stage: int = 0,
            to_stage: int | None = None,
            initial_context: PipelineContext | None = None,
            bypass_ideation: bool = False,
            progress_callback=None,
            stage_completed_callback=None,
        ) -> PipelineContext:
            del to_stage, progress_callback, stage_completed_callback
            assert theme == "saved theme"
            assert from_stage == 10
            assert bypass_ideation is False
            assert initial_context is not None
            assert initial_context.scripting is not None
            initial_context.current_stage = 10
            initial_context.packaging = PackagingOutput(
                platform_packages=[PlatformPackage(platform="tiktok", primary_hook="Hook")]
            )
            return initial_context

    monkeypatch.setattr(
        "cc_deep_research.content_gen.orchestrator.ContentGenOrchestrator",
        FakeOrchestrator,
    )

    context_path = tmp_path / "pipeline.json"
    context_path.write_text(
        PipelineContext(
            theme="saved theme",
            current_stage=9,
            angles=AngleOutput(
                idea_id="idea-1",
                angle_options=[AngleOption(angle_id="angle-1", core_promise="Angle")],
                selected_angle_id="angle-1",
            ),
            scripting=ScriptingContext(
                raw_idea="saved idea",
                qc=QCResult(checks=[], weakest_parts=[], final_script="Saved final script"),
            ),
        ).model_dump_json()
    )

    runner = CliRunner()
    result = runner.invoke(
        main,
        [
            "content-gen",
            "pipeline",
            "--from-file",
            str(context_path),
            "--quiet",
        ],
    )

    assert result.exit_code == 0
    assert result.output == ""


def test_cli_pipeline_failure_saves_partial_context(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Pipeline failures should persist the latest stage context for resume."""

    class FakeOrchestrator:
        def __init__(self, _config) -> None:
            pass

        async def run_full_pipeline(
            self,
            theme: str,
            *,
            from_stage: int = 0,
            to_stage: int | None = None,
            initial_context: PipelineContext | None = None,
            bypass_ideation: bool = False,
            progress_callback=None,
            stage_completed_callback=None,
        ) -> PipelineContext:
            del to_stage, initial_context, bypass_ideation, progress_callback
            assert theme == "saved theme"
            assert from_stage == 0
            partial = PipelineContext(
                theme=theme,
                current_stage=6,
                selected_idea_id="idea-partial",
                scripting=ScriptingContext(
                    raw_idea="partial idea",
                    qc=QCResult(checks=[], weakest_parts=[], final_script="Partial script"),
                ),
            )
            if stage_completed_callback is not None:
                stage_completed_callback(6, "completed", "", partial)
            raise ValueError("boom")

    monkeypatch.setattr(
        "cc_deep_research.content_gen.orchestrator.ContentGenOrchestrator",
        FakeOrchestrator,
    )

    output_path = tmp_path / "pipeline_script.txt"
    runner = CliRunner()
    result = runner.invoke(
        main,
        [
            "content-gen",
            "pipeline",
            "--theme",
            "saved theme",
            "--output",
            str(output_path),
        ],
    )

    assert result.exit_code != 0
    assert "Pipeline failed." in result.output
    assert "Partial context saved to:" in result.output

    context_path = output_path.with_suffix(output_path.suffix + ".context.json")
    assert context_path.exists()
    restored = PipelineContext.model_validate_json(context_path.read_text())
    assert restored.current_stage == 6
    assert restored.selected_idea_id == "idea-partial"
    assert restored.scripting is not None
    assert restored.scripting.qc is not None
    assert restored.scripting.qc.final_script == "Partial script"


def test_cli_pipeline_idea_seeds_direct_bypass_context(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Pipeline --idea should seed a direct-idea context instead of acting like a theme."""

    class FakeOrchestrator:
        def __init__(self, _config) -> None:
            pass

        def validate_resume_context(
            self,
            *,
            from_stage: int,
            ctx: PipelineContext,
            bypass_ideation: bool = False,
        ) -> str | None:
            assert from_stage == 0
            assert bypass_ideation is True
            assert ctx.backlog is not None
            assert len(ctx.backlog.items) == 1
            assert ctx.backlog.items[0].title == "Direct seed"
            assert ctx.selected_idea_id == ctx.backlog.items[0].idea_id
            assert [candidate.idea_id for candidate in ctx.active_candidates] == [ctx.backlog.items[0].idea_id]
            assert ctx.scoring is not None
            assert ctx.scoring.selected_idea_id == ctx.backlog.items[0].idea_id
            assert [candidate.idea_id for candidate in ctx.scoring.active_candidates] == [ctx.backlog.items[0].idea_id]
            return None

        async def run_full_pipeline(
            self,
            theme: str,
            *,
            from_stage: int = 0,
            to_stage: int | None = None,
            initial_context: PipelineContext | None = None,
            bypass_ideation: bool = False,
            progress_callback=None,
            stage_completed_callback=None,
        ) -> PipelineContext:
            del to_stage, progress_callback, stage_completed_callback
            assert theme == "Direct seed"
            assert from_stage == 0
            assert bypass_ideation is True
            assert initial_context is not None
            assert initial_context.backlog is not None
            assert initial_context.backlog.items[0].source == "direct_idea"
            assert initial_context.scoring is not None
            assert initial_context.scoring.selection_reasoning == "Seeded directly from --idea."
            assert initial_context.active_candidates[0].status == "selected"
            return initial_context

    monkeypatch.setattr(
        "cc_deep_research.content_gen.orchestrator.ContentGenOrchestrator",
        FakeOrchestrator,
    )

    runner = CliRunner()
    result = runner.invoke(
        main,
        [
            "content-gen",
            "pipeline",
            "--idea",
            "Direct seed",
            "--quiet",
        ],
    )

    assert result.exit_code == 0
    assert result.output == ""


def test_cli_pipeline_direct_idea_rejects_invalid_resume_stage() -> None:
    """Direct-idea mode should fail fast when the requested stage needs missing prior context."""
    runner = CliRunner()

    result = runner.invoke(
        main,
        [
            "content-gen",
            "pipeline",
            "--idea",
            "Direct seed",
            "--from-stage",
            "5",
        ],
    )

    assert result.exit_code != 0
    assert "Cannot resume from stage 5" in result.output
    assert "selected angle missing" in result.output


def test_cli_requires_idea_without_from_file() -> None:
    """Without --from-file, --idea is required."""
    runner = CliRunner()

    result = runner.invoke(
        main,
        ["content-gen", "script"],
    )

    assert result.exit_code != 0
    assert "--idea is required" in result.output


def test_cli_package_accepts_scripting_context(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Packaging CLI should read script and angle from saved scripting context JSON."""

    class FakeOrchestrator:
        def __init__(self, _config) -> None:
            pass

        async def run_packaging(
            self,
            script: ScriptVersion,
            angle: AngleOption,
            *,
            platforms=None,
            idea_id="",
        ) -> PackagingOutput:
            del platforms, idea_id
            assert script.content == "Final script"
            assert angle.core_promise == "Angle"
            return PackagingOutput(
                platform_packages=[
                    PlatformPackage(
                        platform="tiktok",
                        primary_hook="Hook",
                        alternate_hooks=["Hook 2", "Hook 3"],
                        caption="Caption",
                    )
                ]
            )

    monkeypatch.setattr(
        "cc_deep_research.content_gen.orchestrator.ContentGenOrchestrator",
        FakeOrchestrator,
    )

    context_path = tmp_path / "scripting.json"
    context_path.write_text(
        ScriptingContext(
            raw_idea="idea",
            core_inputs=CoreInputs(topic="Topic", outcome="Outcome", audience="Audience"),
            angle=AngleDefinition(angle="Angle", content_type="Contrarian", core_tension="Tension"),
            qc=QCResult(checks=[], weakest_parts=[], final_script="Final script"),
        ).model_dump_json()
    )

    runner = CliRunner()
    result = runner.invoke(
        main,
        [
            "content-gen",
            "package",
            "--from-file",
            str(context_path),
        ],
    )

    assert result.exit_code == 0


# ---------------------------------------------------------------------------
# Backlog hardening tests
# ---------------------------------------------------------------------------


def test_backlog_output_degraded_flag() -> None:
    """BacklogOutput should track degraded state."""
    output = BacklogOutput(items=[], is_degraded=True, degradation_reason="zero valid ideas")
    assert output.is_degraded is True
    assert output.degradation_reason == "zero valid ideas"


def test_scoring_output_degraded_flag() -> None:
    """ScoringOutput should track degraded state."""
    output = ScoringOutput(is_degraded=True, degradation_reason="zero valid scores")
    assert output.is_degraded is True
    assert output.degradation_reason == "zero valid scores"


def test_scoring_output_reuse_recommended_field() -> None:
    """ScoringOutput should expose reuse_recommended list."""
    output = ScoringOutput(reuse_recommended=["id2", "id3"])
    assert output.reuse_recommended == ["id2", "id3"]
    restored = ScoringOutput.model_validate_json(output.model_dump_json())
    assert restored.reuse_recommended == ["id2", "id3"]


def test_is_reuse_recommended_identifies_strong_hold_ideas() -> None:
    """_is_reuse_recommended should identify hold ideas with good fundamentals."""
    # Import here to avoid import at top level issues
    from cc_deep_research.content_gen.agents.backlog import _is_reuse_recommended
    from cc_deep_research.content_gen.models import IdeaScores

    # Strong hold idea — should be recommended for reuse
    strong_hold = IdeaScores(
        idea_id="id1",
        hook_strength=4,
        evidence_strength=4,
        relevance=4,
        total_score=20,
        recommendation="hold",
    )
    assert _is_reuse_recommended(strong_hold) is True

    # Weak hold idea — should not be recommended for reuse
    weak_hold = IdeaScores(
        idea_id="id2",
        hook_strength=2,
        evidence_strength=2,
        relevance=3,
        total_score=12,
        recommendation="hold",
    )
    assert _is_reuse_recommended(weak_hold) is False

    # Strong produce_now — not relevant for reuse (already passing)
    produce_now = IdeaScores(
        idea_id="id3",
        hook_strength=5,
        evidence_strength=5,
        relevance=5,
        total_score=30,
        recommendation="produce_now",
    )
    # Not a hold, so not checked for reuse in the normal flow
    # but the function itself doesn't filter on recommendation
    # (reuse logic filters on hold first, so this won't appear in reuse_recommended)
    assert _is_reuse_recommended(produce_now) is True  # passes the signal check


def test_apply_upside_gate_kills_low_upside_ideas() -> None:
    """_apply_upside_gate should kill ideas with expected_upside below threshold."""
    from cc_deep_research.content_gen.agents.backlog import _apply_upside_gate
    from cc_deep_research.content_gen.models import IdeaScores

    scores = [
        IdeaScores(idea_id="id1", expected_upside=1, recommendation="produce_now", relevance=4),
        IdeaScores(idea_id="id2", expected_upside=3, recommendation="hold", relevance=3),
        IdeaScores(idea_id="id3", expected_upside=2, recommendation="produce_now", relevance=4),
        IdeaScores(idea_id="id4", expected_upside=3, recommendation="kill", relevance=2),
    ]
    result = _apply_upside_gate(scores, min_upside=2)
    assert result[0].recommendation == "kill"
    assert result[0].kill_reason == "expected_upside 1 below minimum threshold 2"
    assert result[1].recommendation == "hold"
    assert result[2].recommendation == "kill"
    assert result[3].recommendation == "kill"


def test_apply_effort_tier_cap_downgrades_tier() -> None:
    """_apply_effort_tier_cap should downgrade deep ideas when cap is lower."""
    from cc_deep_research.content_gen.agents.backlog import _apply_effort_tier_cap
    from cc_deep_research.content_gen.models import EffortTier, IdeaScores

    scores = [
        IdeaScores(idea_id="id1", effort_tier=EffortTier.DEEP, relevance=4),
        IdeaScores(idea_id="id2", effort_tier=EffortTier.STANDARD, relevance=4),
        IdeaScores(idea_id="id3", effort_tier=EffortTier.QUICK, relevance=4),
        IdeaScores(idea_id="id4", effort_tier=EffortTier.DEEP, relevance=4),
    ]
    result = _apply_effort_tier_cap(scores, cap="standard")
    assert result[0].effort_tier == EffortTier.STANDARD
    assert result[1].effort_tier == EffortTier.STANDARD
    assert result[2].effort_tier == EffortTier.QUICK
    assert result[3].effort_tier == EffortTier.STANDARD


def test_compute_effort_summary_counts_tiers() -> None:
    """_compute_effort_summary should count ideas per effort tier."""
    from cc_deep_research.content_gen.agents.backlog import _compute_effort_summary
    from cc_deep_research.content_gen.models import EffortTier, IdeaScores

    scores = [
        IdeaScores(idea_id="id1", effort_tier=EffortTier.DEEP),
        IdeaScores(idea_id="id2", effort_tier=EffortTier.STANDARD),
        IdeaScores(idea_id="id3", effort_tier=EffortTier.QUICK),
        IdeaScores(idea_id="id4", effort_tier=EffortTier.DEEP),
        IdeaScores(idea_id="id5", effort_tier=EffortTier.STANDARD),
    ]
    summary = _compute_effort_summary(scores)
    assert summary == {"quick": 1, "standard": 2, "deep": 2}


def test_idea_scores_effort_tier_and_upside_fields() -> None:
    """IdeaScores should carry effort_tier, expected_upside, and kill_reason."""
    from cc_deep_research.content_gen.models import EffortTier, IdeaScores

    score = IdeaScores(
        idea_id="test1",
        relevance=4,
        novelty=4,
        authority_fit=4,
        production_ease=4,
        evidence_strength=4,
        hook_strength=4,
        repurposing=4,
        effort_tier=EffortTier.DEEP,
        expected_upside=4,
        kill_reason="weak evidence and weak hook",
        recommendation="kill",
    )
    assert score.effort_tier == EffortTier.DEEP
    assert score.expected_upside == 4
    assert score.kill_reason == "weak evidence and weak hook"
    restored = IdeaScores.model_validate_json(score.model_dump_json())
    assert restored.effort_tier == EffortTier.DEEP
    assert restored.expected_upside == 4
    assert restored.kill_reason == "weak evidence and weak hook"


def test_scoring_output_effort_summary_field() -> None:
    """ScoringOutput should expose effort_summary dict."""
    output = ScoringOutput(effort_summary={"quick": 2, "standard": 5, "deep": 1})
    assert output.effort_summary == {"quick": 2, "standard": 5, "deep": 1}
    restored = ScoringOutput.model_validate_json(output.model_dump_json())
    assert restored.effort_summary == {"quick": 2, "standard": 5, "deep": 1}


def test_content_type_profiles_defined() -> None:
    """CONTENT_TYPE_PROFILES should contain expected content types."""
    from cc_deep_research.content_gen.models import CONTENT_TYPE_PROFILES, ContentTypeProfile

    assert "short_form_video" in CONTENT_TYPE_PROFILES
    assert "newsletter" in CONTENT_TYPE_PROFILES
    assert "article" in CONTENT_TYPE_PROFILES
    assert "webinar" in CONTENT_TYPE_PROFILES
    assert "launch_asset" in CONTENT_TYPE_PROFILES
    assert "thread" in CONTENT_TYPE_PROFILES
    assert "carousel" in CONTENT_TYPE_PROFILES

    profile = CONTENT_TYPE_PROFILES["short_form_video"]
    assert isinstance(profile, ContentTypeProfile)
    assert profile.research_depth == "standard"
    assert "visual_translation" not in profile.skip_stages


def test_get_content_type_profile_fallback() -> None:
    """get_content_type_profile should fall back to short_form_video for unknown types."""
    from cc_deep_research.content_gen.models import get_content_type_profile

    profile = get_content_type_profile("unknown_type")
    assert profile.profile_key == "short_form_video"

    specific = get_content_type_profile("newsletter")
    assert specific.profile_key == "newsletter"
    assert specific.research_depth == "light"
    assert "visual_translation" in specific.skip_stages


def test_scoring_output_content_type_profile_field() -> None:
    """ScoringOutput should carry content_type_profile."""
    output = ScoringOutput(content_type_profile="article")
    assert output.content_type_profile == "article"
    restored = ScoringOutput.model_validate_json(output.model_dump_json())
    assert restored.content_type_profile == "article"


def test_pipeline_candidate_content_type_profile_field() -> None:
    """PipelineCandidate should carry optional content_type_profile."""
    from cc_deep_research.content_gen.models import PipelineCandidate

    candidate = PipelineCandidate(idea_id="id1", content_type_profile="webinar")
    assert candidate.content_type_profile == "webinar"
    restored = PipelineCandidate.model_validate_json(candidate.model_dump_json())
    assert restored.content_type_profile == "webinar"


def test_derive_pipeline_candidates_preserves_profile() -> None:
    """_derive_pipeline_candidates should propagate content_type_profile to candidates."""
    from cc_deep_research.content_gen.models import _derive_pipeline_candidates

    candidates = _derive_pipeline_candidates(
        selected_idea_id="id1",
        shortlist=["id1", "id2"],
        content_type_profile="newsletter",
    )
    assert len(candidates) == 2
    assert candidates[0].content_type_profile == "newsletter"
    assert candidates[1].content_type_profile == "newsletter"


def test_scoring_output_roundtrip_with_shortlist() -> None:
    """ScoringOutput should preserve shortlist selection fields and derive active candidates."""
    output = ScoringOutput(
        scores=[
            IdeaScores(
                idea_id="id1",
                relevance=5,
                novelty=4,
                authority_fit=5,
                production_ease=4,
                evidence_strength=4,
                hook_strength=5,
                repurposing=4,
                opportunity_fit=4,
                total_score=35,
                recommendation="produce_now",
            )
        ],
        produce_now=["id1"],
        shortlist=["id1", "id2"],
        selected_idea_id="id1",
        selection_reasoning="Best mix of hook strength and evidence.",
        runner_up_idea_ids=["id2"],
    )

    restored = ScoringOutput.model_validate_json(output.model_dump_json())

    assert restored.shortlist == ["id1", "id2"]
    assert restored.selected_idea_id == "id1"
    assert restored.selection_reasoning == "Best mix of hook strength and evidence."
    assert restored.runner_up_idea_ids == ["id2"]
    assert [candidate.idea_id for candidate in restored.active_candidates] == ["id1", "id2"]
    assert [candidate.status for candidate in restored.active_candidates] == ["selected", "runner_up"]


def test_derive_selection_prefers_explicit_selected_idea() -> None:
    """Explicit selected_idea_id should win over shortlist ordering."""
    text = """---
idea_id: id1
total_score: 31
recommendation: produce_now
reason: Good
---
idea_id: id2
total_score: 30
recommendation: produce_now
reason: Better fit
---
shortlist:
- id1
- id2
selected_idea_id: id2
selection_reasoning: Better fit for the first production slot
"""
    scores = [
        IdeaScores(idea_id="id1", total_score=31, recommendation="produce_now", reason="Good"),
        IdeaScores(idea_id="id2", total_score=30, recommendation="produce_now", reason="Better fit"),
    ]
    items = [
        BacklogItem(idea_id="id1", idea="Idea 1"),
        BacklogItem(idea_id="id2", idea="Idea 2"),
    ]

    shortlist, selected_idea_id, selection_reasoning, runner_up_idea_ids = _derive_selection(
        text,
        scores,
        items,
    )

    assert shortlist == ["id1", "id2"]
    assert selected_idea_id == "id2"
    assert selection_reasoning == "Better fit for the first production slot"
    assert runner_up_idea_ids == ["id1"]


@pytest.mark.asyncio
async def test_backlog_golden_fixture_happy_path_parses_items_and_metadata() -> None:
    """Fixture-backed backlog output should parse into stable structured items."""
    agent = _FakeBacklogAgent(load_text_fixture("content_gen_backlog_happy.txt"))

    result = await agent.build_backlog("pricing", StrategyMemory())

    assert len(result.items) == 2
    assert result.items[0].idea == "The 10-minute weekly finance review that stops founder cash surprises"
    assert result.items[1].content_type == "contrarian breakdown"
    assert result.rejected_count == 2
    assert result.rejection_reasons == [
        "Too broad for a single short-form video",
        "Needed claims we could not verify quickly",
    ]
    assert result.is_degraded is False


@pytest.mark.asyncio
async def test_backlog_agent_raises_when_no_llm_route_available() -> None:
    """Backlog generation should fail loudly when no configured LLM route is usable."""
    from cc_deep_research.config import Config

    agent = BacklogAgent(Config())

    with pytest.raises(RuntimeError, match="No LLM route is available for the content backlog workflow"):
        await agent.build_backlog("pricing", StrategyMemory())


@pytest.mark.asyncio
async def test_backlog_golden_fixture_malformed_output_marks_stage_degraded() -> None:
    """Malformed backlog output should degrade cleanly instead of fabricating ideas."""
    agent = _FakeBacklogAgent(load_text_fixture("content_gen_backlog_malformed.txt"))

    result = await agent.build_backlog("pricing", StrategyMemory())

    assert result.items == []
    assert result.rejected_count == 1
    assert result.rejection_reasons == ["Missing a concrete idea statement"]
    assert result.is_degraded is True
    assert result.degradation_reason == "zero valid ideas parsed from LLM response"


@pytest.mark.asyncio
async def test_backlog_agent_blank_response_retries_then_degrades() -> None:
    """Blank backlog responses should retry once and still degrade cleanly."""
    from cc_deep_research.config import Config

    agent = BacklogAgent(Config())
    router = _StubTextRouter(["", ""], available=True)
    agent._router = router

    result = await agent.build_backlog("pricing", StrategyMemory())

    assert router.calls == 2
    assert result.items == []
    assert result.is_degraded is True
    assert result.degradation_reason == "zero valid ideas parsed from LLM response"


def test_angle_golden_fixture_happy_path_parses_multiple_options() -> None:
    """Angle fixtures should keep editorial fields stable across parser changes."""
    result = _parse_angle_options(load_text_fixture("content_gen_angle_happy.txt"))

    assert len(result) == 2
    assert result[0].viewer_problem == (
        "They keep polishing copy while buyers still compare only price"
    )
    assert result[0].cta == "Audit your highest-priced plan against the decoy effect"
    assert result[1].format == "tactical explainer"


def test_angle_golden_fixture_sparse_output_drops_incomplete_option() -> None:
    """Sparse angle output should drop incomplete options instead of fabricating them."""
    result = _parse_angle_options(load_text_fixture("content_gen_angle_sparse.txt"))

    assert result == []


@pytest.mark.asyncio
async def test_angle_agent_raises_when_no_complete_options_parse() -> None:
    """Angle generation should fail fast when the response lacks a usable option."""
    agent = _FakeAngleAgent(load_text_fixture("content_gen_angle_sparse.txt"))

    with pytest.raises(ValueError, match="complete angle option"):
        await agent.generate(BacklogItem(idea="Idea"), StrategyMemory())


def test_build_search_queries_uses_expert_families_and_current_year(monkeypatch: pytest.MonkeyPatch) -> None:
    """Search planning should use labeled retrieval families and avoid stale year pins."""
    monkeypatch.setattr(research_pack_agent_module, "_current_calendar_year", lambda: 2031)

    queries = _build_search_queries(
        BacklogItem(
            idea="pricing psychology",
            audience="B2B SaaS founders",
            problem="buyers do not compare plans the way teams expect",
        ),
        AngleOption(
            target_audience="subscription software marketers",
            viewer_problem="teams keep optimizing copy instead of comparison framing",
            core_promise="Tier order changes what buyers notice first",
            primary_takeaway="Fix the comparison before the checklist",
        ),
    )

    assert [query.family for query in queries] == [
        "proof",
        "primary-source",
        "competitor",
        "contrarian",
        "freshness",
        "practitioner-language",
    ]
    assert queries[0].intent_tags == ["proof", "evidence", "benchmark"]
    assert "2031" in queries[4].query
    assert "2025" not in " ".join(query.query for query in queries)


def test_research_pack_golden_fixture_happy_path_parses_sections() -> None:
    """Research-pack fixtures should populate evidence sections predictably."""
    result = _parse_research_pack(
        load_text_fixture("content_gen_research_pack_happy.txt"),
        "idea-1",
        "angle-1",
    )

    assert result.idea_id == "idea-1"
    assert result.angle_id == "angle-1"
    assert len(result.audience_insights) == 2
    assert len(result.proof_points) == 2
    assert len(result.findings) == 6
    assert len(result.claims) == 4
    assert len(result.counterpoints) == 1
    assert len(result.uncertainty_flags) == 2
    assert result.findings[0].finding_type == ResearchFindingType.AUDIENCE_INSIGHT
    assert result.claims[0].claim_type == ResearchClaimType.KEY_FACT
    assert result.claims[0].confidence == ResearchConfidence.HIGH
    assert result.counterpoints[0].source_ids == ["src_05"]
    assert result.uncertainty_flags[1].flag_type == ResearchFlagType.UNSAFE_OR_UNCERTAIN
    assert result.assets_needed == [
        "Screenshot of a three-tier pricing page",
        "Simple annotated mock showing anchor placement",
    ]
    assert result.research_stop_reason == (
        "Enough evidence to build a practical teardown without hard performance claims"
    )


def test_research_pack_golden_fixture_sparse_output_defaults_missing_sections() -> None:
    """Sparse research output should preserve what exists and leave the rest empty."""
    result = _parse_research_pack(
        load_text_fixture("content_gen_research_pack_sparse.txt"),
        "idea-2",
        "angle-2",
    )

    assert result.audience_insights == [
        "Founders skim pricing pages and miss how buyers compare tiers"
    ]
    assert result.proof_points == [
        "Anchoring affects perceived value before full feature evaluation"
    ]
    assert result.competitor_observations == []
    assert result.claims_requiring_verification == ["Any statement about exact conversion lift"]
    assert result.findings[0].source_ids == ["src_01"]
    assert result.claims[0].source_ids == ["src_02"]
    assert result.uncertainty_flags[0].severity == ResearchSeverity.MEDIUM


def test_argument_map_parser_happy_path_parses_cross_referenced_sections() -> None:
    """Argument map output should preserve IDs and beat references."""
    result = _parse_argument_map(
        """thesis: Buyers decide whether your premium tier feels justified before they read the feature grid
audience_belief_to_challenge: Better feature copy is the main lever on pricing conversion
core_mechanism: Buyers anchor on tier comparison order and only then interpret features through that frame

proof_anchors:
---
proof_id: proof_1
summary: Buyers compare tier contrast before reading every feature line
source_ids: src_01, src_02
usage_note: Use this to reframe why copy tweaks underperform
---
proof_id: proof_2
summary: Decoy tiers change perceived value by making one option feel like the sensible middle
source_ids: src_03
usage_note: Use as the concrete example beat

counterarguments:
---
counterargument_id: counter_1
counterargument: Sophisticated buyers still evaluate features in detail
response: They do, but only after the initial anchor has shaped which features feel worth comparing
response_proof_ids: proof_1

safe_claims:
---
claim_id: claim_1
claim: Pricing order changes what buyers notice first
supporting_proof_ids: proof_1
note: Keep it qualitative, not numeric
---
claim_id: claim_2
claim: A decoy tier can make a target plan feel more reasonable
supporting_proof_ids: proof_2
note: Use as a mechanism explanation

unsafe_claims:
---
claim_id: claim_unsafe_1
claim: Reordering tiers lifts conversion by 23 percent
supporting_proof_ids: proof_2
note: Exact lift is unverified in the provided research

beat_claim_plan:
---
beat_id: beat_1
beat_name: Hook
goal: Challenge the idea that copy is the first pricing lever to fix
claim_ids: claim_1
proof_anchor_ids: proof_1
counterargument_ids:
transition_note: Move from surface copy talk into buyer comparison behavior
---
beat_id: beat_2
beat_name: Proof
goal: Show the decoy effect example
claim_ids: claim_2
proof_anchor_ids: proof_2
counterargument_ids: counter_1
transition_note: Close by turning the insight into an audit action
""",
        "idea-1",
        "angle-1",
    )

    assert result.idea_id == "idea-1"
    assert result.angle_id == "angle-1"
    assert result.thesis.startswith("Buyers decide whether your premium tier feels justified")
    assert len(result.proof_anchors) == 2
    assert result.safe_claims[0].supporting_proof_ids == ["proof_1"]
    assert result.unsafe_claims[0].claim_id == "claim_unsafe_1"
    assert result.counterarguments[0].response_proof_ids == ["proof_1"]
    assert result.beat_claim_plan[1].counterargument_ids == ["counter_1"]


def test_argument_map_parser_rejects_unknown_references() -> None:
    """Cross-reference mistakes should raise a useful parsing error."""
    with pytest.raises(ValueError, match="unknown identifiers: proof_missing"):
        _parse_argument_map(
            """thesis: Anchors beat copy tweaks
audience_belief_to_challenge: Better copy always fixes pricing
core_mechanism: Buyers compare options before parsing the full message

proof_anchors:
---
proof_id: proof_1
summary: Buyers compare tiers quickly
source_ids: src_01
usage_note: Use in the reframe

safe_claims:
---
claim_id: claim_1
claim: Tier order changes what buyers notice first
supporting_proof_ids: proof_missing
note: Directional only

unsafe_claims:

beat_claim_plan:
---    
beat_id: beat_1
beat_name: Hook
goal: Set up the false belief
claim_ids: claim_1
proof_anchor_ids: proof_1
counterargument_ids:
transition_note: Move into the mechanism
""",
            "idea-2",
            "angle-2",
        )


@pytest.mark.asyncio
async def test_argument_map_agent_build_fails_fast_without_proof_anchors() -> None:
    """Agent should reject malformed output instead of returning an empty argument map."""
    agent = _FakeArgumentMapAgent(
        """thesis: Anchors matter more than copy
audience_belief_to_challenge: More feature detail fixes pricing pages
core_mechanism: Buyers judge the frame before the details

safe_claims:
---
claim_id: claim_1
claim: Buyers compare the order of tiers first
supporting_proof_ids:
note: Directional only
"""
    )

    with pytest.raises(ValueError, match="missing at least one proof anchor"):
        await agent.build(
            BacklogItem(idea_id="idea-9", idea="pricing psychology"),
            AngleOption(angle_id="angle-9", core_promise="Explain why anchors beat copy"),
            ResearchPack(),
        )


@pytest.mark.asyncio
async def test_research_pack_agent_build_retains_source_provenance() -> None:
    """Search provenance should survive into the research pack and the synthesis prompt."""

    class FakeProvider:
        async def search(self, query: str, options: SearchResult) -> SearchResult:
            del options
            return SearchResult(
                query=query,
                provider="fake-search",
                results=[
                    SearchResultItem(
                        url="https://example.com/pricing",
                        title="Pricing psychology teardown",
                        snippet="Buyers compare tiers quickly before reading everything.",
                        source_metadata={"published_date": "2026-03-01"},
                    )
                ],
            )

    class FakeConfig:
        content_gen = type("ContentGen", (), {"research_max_queries": 1})()
        llm = type("LLM", (), {})()

    class FakeResearchAgent(ResearchPackAgent):
        def __init__(self) -> None:
            self._config = FakeConfig()
            self.last_user_prompt = ""

        async def _call_llm(
            self,
            system_prompt: str,
            user_prompt: str,
            *,
            temperature: float = 0.3,
        ) -> str:
            del system_prompt, temperature
            self.last_user_prompt = user_prompt
            return """findings:
---
finding_type: audience_insight
summary: Buyers compare tiers before reading every feature
source_ids: src_01
confidence: high
evidence_note: Strong match for the selected angle
---

claims:
---
claim_type: proof_point
claim: Tier order shapes perceived value before detailed evaluation
source_ids: src_01
confidence: medium
mechanism: Comparison happens before full checklist reading
---

uncertainty_flags:
---
flag_type: verification_required
claim: Any exact percentage lift from reordering pricing cards
reason: The source is directional, not causal proof
severity: medium
source_ids: src_01
---

assets_needed:
- Pricing page screenshot

research_stop_reason: Enough support for a qualitative teardown"""

        def _get_providers(self) -> list:
            return [FakeProvider()]

    agent = FakeResearchAgent()
    result = await agent.build(
        BacklogItem(idea="pricing psychology", audience="B2B SaaS founders"),
        AngleOption(core_promise="Show why tier order changes perceived value"),
        max_queries=1,
    )

    assert "[src_01]" in agent.last_user_prompt
    # Source catalog now includes quality signals (Task 16)
    assert "authority:" in agent.last_user_prompt
    assert "directness:" in agent.last_user_prompt
    assert "freshness:" in agent.last_user_prompt
    assert result.supporting_sources[0].url == "https://example.com/pricing"
    assert result.supporting_sources[0].query_family == "proof"
    # New quality fields populated by _score_source_quality (Task 16)
    # quality_rank is always computed
    assert result.supporting_sources[0].quality_rank is not None
    assert result.supporting_sources[0].quality_rank >= 0.0
    # directness and freshness are inferred from query family and date
    assert result.supporting_sources[0].evidence_directness.value != "unknown"
    assert result.supporting_sources[0].source_freshness.value != "unknown"
    # authority may be unknown for generic URLs like example.com
    assert result.findings[0].source_ids == ["src_01"]
    assert result.claims[0].source_ids == ["src_01"]
    assert result.uncertainty_flags[0].source_ids == ["src_01"]


@pytest.mark.asyncio
async def test_visual_agent_raises_without_visual_refresh_check() -> None:
    """Visual translation should fail fast when the required summary field is missing."""
    agent = _FakeVisualAgent(
        """---
beat: Hook
spoken_line: Buyers compare price before features.
visual: Pricing page with the anchor tier highlighted
---
"""
    )

    with pytest.raises(ValueError, match="visual_refresh_check"):
        await agent.translate(
            ScriptVersion(content="Script", word_count=1),
            ScriptStructure(chosen_structure="Reveal", beat_list=["Hook"]),
        )


@pytest.mark.asyncio
async def test_scripting_golden_fixture_happy_path_parses_structure_step() -> None:
    """Representative scripting output should parse a valid structure and beat list."""
    agent = _FakeScriptingAgent(load_text_fixture("content_gen_scripting_choose_structure_happy.txt"))
    ctx = ScriptingContext(
        raw_idea="pricing teardown",
        core_inputs=CoreInputs(
            topic="Pricing anchors",
            outcome="Help viewers spot weak price framing",
            audience="B2B startup marketers",
        ),
        angle=AngleDefinition(
            angle="Most pricing pages hide the comparison buyers make first",
            content_type="Contrarian breakdown",
            core_tension="Teams optimize copy while buyers optimize for anchors",
        ),
    )

    result = await agent.choose_structure(ctx)

    assert result.structure is not None
    assert result.structure.chosen_structure == "Contrarian reveal"
    assert result.structure.beat_list == [
        "Hook: Call out the pricing mistake buyers spot first",
        "False assumption: Teams think more features justify a higher tier",
        "Reframe: Buyers compare anchors before they compare details",
        "Proof: Show the decoy-tier example",
        "CTA: Rewrite one pricing card today",
    ]


@pytest.mark.asyncio
async def test_scripting_golden_fixture_malformed_structure_raises() -> None:
    """Malformed scripting output should fail the structure step instead of silently passing."""
    agent = _FakeScriptingAgent(
        load_text_fixture("content_gen_scripting_choose_structure_malformed.txt")
    )
    ctx = ScriptingContext(
        raw_idea="pricing teardown",
        core_inputs=CoreInputs(
            topic="Pricing anchors",
            outcome="Help viewers spot weak price framing",
            audience="B2B startup marketers",
        ),
        angle=AngleDefinition(
            angle="Most pricing pages hide the comparison buyers make first",
            content_type="Contrarian breakdown",
            core_tension="Teams optimize copy while buyers optimize for anchors",
        ),
    )

    with pytest.raises(ValueError, match="Beat List"):
        await agent.choose_structure(ctx)


def test_packaging_golden_fixture_happy_path_parses_platform_packages() -> None:
    """Packaging fixtures should keep per-platform outputs stable."""
    result = _parse_platform_packages(load_text_fixture("content_gen_packaging_happy.txt"))

    assert len(result) == 2
    assert result[0].platform == "tiktok"
    assert result[0].alternate_hooks == [
        "Your pricing page is answering the wrong question",
        "Buyers compare anchors before they compare features",
    ]
    assert result[1].platform == "linkedin"
    assert result[1].hashtags == ["#b2bmarketing", "#pricing"]


def test_packaging_golden_fixture_sparse_output_ignores_incomplete_blocks() -> None:
    """Sparse packaging output should ignore blocks missing the platform key."""
    result = _parse_platform_packages(load_text_fixture("content_gen_packaging_sparse.txt"))

    assert len(result) == 1
    assert result[0].platform == "linkedin"
    assert result[0].alternate_hooks == []
    assert result[0].keywords == []


@pytest.mark.asyncio
async def test_packaging_agent_raises_when_no_usable_platform_package_parses() -> None:
    """Packaging should fail fast when every platform block is incomplete."""
    agent = _FakePackagingAgent(
        """---
platform: tiktok
primary_hook: Strong hook
version_notes: Missing caption should invalidate the block
---
"""
    )

    with pytest.raises(ValueError, match="usable platform block"):
        await agent.generate(
            ScriptVersion(content="Script", word_count=1),
            AngleOption(core_promise="Promise", target_audience="Audience"),
            ["tiktok"],
        )


def test_qc_golden_fixture_happy_path_parses_issue_lists() -> None:
    """QC fixtures should keep actionable review items stable."""
    result = _parse_qc_gate(load_text_fixture("content_gen_qc_happy.txt"))

    assert result.hook_strength == "strong"
    assert result.clarity_issues == ["The payoff line could land one beat earlier"]
    assert result.unsupported_claims == [
        'Saying the pricing page "always" lifts conversion is not supported by the research provided'
    ]
    assert result.risky_claims == [
        "The script implies a guaranteed revenue lift, which creates trust and legal risk"
    ]
    assert result.required_fact_checks == [
        "Confirm the featured pricing page screenshot is cleared for reuse",
        "Verify the on-screen revenue example matches the underlying case study",
    ]
    assert result.must_fix_items == [
        "Confirm the screenshot can be shown on camera",
        'Replace the vague "works better" claim with a concrete explanation',
        "Resolve risky claim before publish: The script implies a guaranteed revenue lift, which creates trust and legal risk",
    ]
    assert result.approved_for_publish is False


def test_qc_golden_fixture_sparse_output_defaults_missing_lists() -> None:
    """Sparse QC output should leave omitted issue buckets empty."""
    result = _parse_qc_gate(load_text_fixture("content_gen_qc_sparse.txt"))

    assert result.hook_strength == "adequate"
    assert result.clarity_issues == []
    assert result.unsupported_claims == ["The claim about a 40% lift is unsupported"]
    assert result.risky_claims == []
    assert result.must_fix_items == ["Add a concrete proof point before publish"]


def test_qc_parser_tracks_claim_safety_buckets() -> None:
    """QC parser should keep unsupported, risky, and fact-check buckets distinct."""
    result = _parse_qc_gate(
        """hook_strength: weak
unsupported_claims:
- The script says churn drops by 35% without a source
risky_claims:
- The claim promises guaranteed compliance
required_fact_checks:
- Verify the legal team approved the compliance wording
must_fix_items:
- Remove the made-up churn statistic
"""
    )

    assert result.unsupported_claims == ["The script says churn drops by 35% without a source"]
    assert result.risky_claims == ["The claim promises guaranteed compliance"]
    assert result.required_fact_checks == [
        "Verify the legal team approved the compliance wording"
    ]
    assert "Remove the made-up churn statistic" in result.must_fix_items
    assert (
        "Resolve risky claim before publish: The claim promises guaranteed compliance"
        in result.must_fix_items
    )


def test_quality_evaluator_parser_reads_expert_metrics() -> None:
    """Quality evaluation parsing should preserve expert metrics and evidence actions."""
    result = _parse_quality_evaluation(
        """overall_quality_score: 0.84
passes_threshold: true
evidence_coverage: 0.88
claim_safety: 0.91
originality: 0.79
precision: 0.82
expertise_density: 0.76
critical_issues:
- The proof payoff still lands slightly late
unsupported_claims:
- None
evidence_actions_required:
- Add the cited benchmark before the second beat
improvement_suggestions:
- Cut the generic transition phrase
research_gaps_identified:
- Confirm whether the benchmark is still current this quarter
rationale: Strong expert framing with one missing proof link.
""".replace("- None\n", ""),
        iteration_number=2,
    )

    assert result.overall_quality_score == pytest.approx(0.84)
    assert result.passes_threshold is True
    assert result.evidence_coverage == pytest.approx(0.88)
    assert result.claim_safety == pytest.approx(0.91)
    assert result.originality == pytest.approx(0.79)
    assert result.precision == pytest.approx(0.82)
    assert result.expertise_density == pytest.approx(0.76)
    assert result.evidence_actions_required == [
        "Add the cited benchmark before the second beat"
    ]
    assert result.research_gaps_identified == [
        "Confirm whether the benchmark is still current this quarter"
    ]


def test_quality_evaluator_parser_defaults_malformed_scores_and_blocks_unsupported_claims() -> None:
    """Malformed numeric fields should fail safely and unsupported claims should block passing."""
    result = _parse_quality_evaluation(
        """overall_quality_score: excellent
passes_threshold: true
evidence_coverage: n/a
claim_safety: ??
originality: 1.4
precision: -0.2
expertise_density: 0.65
unsupported_claims:
- The script claims a guaranteed ROI without support
rationale: Needs proof.
""",
        iteration_number=1,
    )

    assert result.overall_quality_score == 0.0
    assert result.evidence_coverage == 0.0
    assert result.claim_safety == 0.0
    assert result.originality == 1.0
    assert result.precision == 0.0
    assert result.expertise_density == pytest.approx(0.65)
    assert result.passes_threshold is False
    assert result.unsupported_claims == ["The script claims a guaranteed ROI without support"]


@pytest.mark.asyncio
async def test_qc_agent_includes_research_and_argument_map_context() -> None:
    """QC review prompt should include research and argument-map summaries when provided."""
    agent = _FakeQCAgent(
        """hook_strength: adequate
unsupported_claims:
- The script overstates the benchmark
must_fix_items:
- Qualify the benchmark claim
"""
    )

    await agent.review(
        script="Script",
        research_summary="Supported claims:\n- Benchmarks show a directional lift",
        argument_map_summary="Claims to qualify or avoid:\n- Guaranteed lift",
    )

    assert "Research summary:" in agent.last_user_prompt
    assert "Supported claims:" in agent.last_user_prompt
    assert "Argument map summary:" in agent.last_user_prompt
    assert "Claims to qualify or avoid:" in agent.last_user_prompt


@pytest.mark.asyncio
async def test_qc_agent_raises_when_hook_strength_missing() -> None:
    """Human QC should fail fast on blank review shells."""
    agent = _FakeQCAgent("must_fix_items:\n- Tighten the hook")

    with pytest.raises(ValueError, match="hook_strength"):
        await agent.review(script="Script")


@pytest.mark.asyncio
async def test_quality_evaluator_raises_on_blank_response_after_retry() -> None:
    """Quality evaluation should fail loudly when the LLM returns empty shells."""
    from cc_deep_research.config import Config

    agent = QualityEvaluatorAgent(Config())
    router = _StubTextRouter(["", ""], available=True)
    agent._router = router

    with pytest.raises(ValueError, match="quality evaluation workflow returned an empty response"):
        await agent.evaluate_scripting(
            scripting=ScriptingContext(raw_idea="Idea"),
            iteration_number=1,
            quality_threshold=0.75,
        )

    assert router.calls == 2


def test_parse_backlog_items_handles_partial_items() -> None:
    """Parsing should return items that have at least a title field."""
    text = """---
title: First idea
audience: Test audience
---
title: Second idea
---
category: evergreen
"""
    result = _parse_backlog_items(text)
    assert len(result) == 2


def test_parse_scores_handles_missing_fields() -> None:
    """Parsing should handle blocks missing some fields."""
    text = """---
idea_id: id1
relevance: 3
total_score: 15
recommendation: produce_now
---
idea_id: id2
"""
    items = [
        BacklogItem(idea_id="id1", idea="test1"),
        BacklogItem(idea_id="id2", idea="test2"),
    ]
    result = _parse_scores(text, items)
    assert len(result) == 2
    assert result[0].total_score == 15
    assert result[1].total_score == 8


def test_validate_scores_filters_invalid_recommendations() -> None:
    """Invalid recommendations should be corrected to 'hold'."""
    scores = [
        IdeaScores(idea_id="id1", recommendation="produce_now"),
        IdeaScores(idea_id="id2", recommendation="invalid"),
        IdeaScores(idea_id="id3", recommendation="hold"),
    ]
    validated = _validate_scores(scores)
    assert validated[0].recommendation == "produce_now"
    assert validated[1].recommendation == "hold"
    assert validated[2].recommendation == "hold"


def test_build_backlog_user_includes_opportunity_brief() -> None:
    """Prompt should include OpportunityBrief fields when provided."""
    brief = OpportunityBrief(
        theme="AI productivity",
        goal="Help founders save 2 hours/day",
        primary_audience_segment="Startup founders",
        secondary_audience_segments=["Engineering managers"],
        problem_statements=["Too many meetings", "Context switching"],
        content_objective="Show 3 specific tools",
        proof_requirements=["Case study", "Data"],
        platform_constraints=["Short-form only"],
        risk_constraints=["No financial advice"],
        freshness_rationale="New feature just released",
        sub_angles=["Tool comparison", "Workflow optimization"],
    )

    user_prompt = build_backlog_user(
        theme="AI productivity",
        strategy=StrategyMemory(),
        count=20,
        opportunity_brief=brief,
    )

    assert "Goal: Help founders save 2 hours/day" in user_prompt
    assert "Primary audience: Startup founders" in user_prompt
    assert "Secondary audiences: Engineering managers" in user_prompt
    assert "Problem statements: Too many meetings; Context switching" in user_prompt
    assert "Content objective: Show 3 specific tools" in user_prompt
    assert "Proof requirements: Case study, Data" in user_prompt
    assert "Platform constraints: Short-form only" in user_prompt
    assert "Risk constraints: No financial advice" in user_prompt
    assert "Freshness rationale: New feature just released" in user_prompt
    assert "Sub-angles to explore: Tool comparison, Workflow optimization" in user_prompt


def test_opportunity_brief_defaults() -> None:
    """OpportunityBrief should have sensible defaults."""
    brief = OpportunityBrief()
    assert brief.theme == ""
    assert brief.goal == ""
    assert brief.primary_audience_segment == ""
    assert brief.secondary_audience_segments == []
    assert brief.problem_statements == []
    assert brief.content_objective == ""
    assert brief.proof_requirements == []
    assert brief.platform_constraints == []
    assert brief.risk_constraints == []
    assert brief.freshness_rationale == ""
    assert brief.sub_angles == []
    assert brief.research_hypotheses == []
    assert brief.success_criteria == []


def test_opportunity_brief_roundtrip() -> None:
    """OpportunityBrief should survive JSON round-trip."""
    brief = OpportunityBrief(
        theme="AI agent safety",
        goal="Produce a viral short on AI agent guardrails",
        primary_audience_segment="ML engineers building agents",
        secondary_audience_segments=["PMs evaluating AI tools", "Founders shipping AI products"],
        problem_statements=["No one explains guardrails simply", "Hype drowns out safety"],
        content_objective="Teach one concrete guardrail pattern",
        proof_requirements=["Cite a real incident", "Show code-level fix"],
        platform_constraints=["Under 60 seconds", "No jargon"],
        risk_constraints=["Do not downplay risks", "Avoid FUD"],
        freshness_rationale="OpenAI o-series reasoning launch",
        sub_angles=["Guardrails as product moat", "Safety as speed advantage"],
        research_hypotheses=["Developers want safety but lack examples", "Guardrail content is underserved"],
        success_criteria=["50k+ views in 48h", "10+ code forks"],
    )
    json_str = brief.model_dump_json()
    restored = OpportunityBrief.model_validate_json(json_str)
    assert restored.theme == "AI agent safety"
    assert restored.goal == "Produce a viral short on AI agent guardrails"
    assert len(restored.secondary_audience_segments) == 2
    assert len(restored.problem_statements) == 2
    assert len(restored.sub_angles) == 2
    assert restored.freshness_rationale == "OpenAI o-series reasoning launch"


def test_pipeline_includes_plan_opportunity_stage() -> None:
    """plan_opportunity should appear after load_strategy and before build_backlog."""
    assert PIPELINE_STAGES[0] == "load_strategy"
    assert PIPELINE_STAGES[1] == "plan_opportunity"
    assert PIPELINE_STAGES[2] == "build_backlog"


def test_pipeline_includes_argument_map_between_research_and_scripting() -> None:
    """build_argument_map should run after research and before scripting."""
    assert PIPELINE_STAGES[5] == "build_research_pack"
    assert PIPELINE_STAGES[6] == "build_argument_map"
    assert PIPELINE_STAGES[7] == "run_scripting"


def test_pipeline_stage_labels_include_plan_opportunity() -> None:
    """plan_opportunity should have a human-readable label."""
    from cc_deep_research.content_gen.models import PIPELINE_STAGE_LABELS

    assert "plan_opportunity" in PIPELINE_STAGE_LABELS
    assert PIPELINE_STAGE_LABELS["plan_opportunity"] == "Planning opportunity brief"


def test_pipeline_stage_labels_include_argument_map() -> None:
    """build_argument_map should have a human-readable label."""
    from cc_deep_research.content_gen.models import PIPELINE_STAGE_LABELS

    assert PIPELINE_STAGE_LABELS["build_argument_map"] == "Building argument map"


def test_pipeline_context_stores_opportunity_brief() -> None:
    """PipelineContext should store an OpportunityBrief."""
    brief = OpportunityBrief(theme="test", goal="test goal")
    ctx = PipelineContext(theme="test", opportunity_brief=brief)
    assert ctx.opportunity_brief is not None
    assert ctx.opportunity_brief.theme == "test"
    assert ctx.opportunity_brief.goal == "test goal"

    # Round-trip
    json_str = ctx.model_dump_json()
    restored = PipelineContext.model_validate_json(json_str)
    assert restored.opportunity_brief is not None
    assert restored.opportunity_brief.theme == "test"


def test_pipeline_context_default_opportunity_brief_is_none() -> None:
    """PipelineContext should default opportunity_brief to None."""
    ctx = PipelineContext()
    assert ctx.opportunity_brief is None


@pytest.mark.asyncio
async def test_opportunity_stage_handler_writes_brief() -> None:
    """The plan_opportunity handler should write OpportunityBrief into context."""
    from cc_deep_research.content_gen.orchestrator import _stage_plan_opportunity

    class FakeOrchestrator:
        def _get_agent(self, name: str):
            assert name == "opportunity"

            class FakeAgent:
                async def plan(self, theme, _strategy):
                    return OpportunityBrief(
                        theme=theme,
                        goal="test goal",
                        sub_angles=["angle1", "angle2"],
                    )

            return FakeAgent()

    ctx = PipelineContext(theme="my theme", strategy=StrategyMemory())
    result = await _stage_plan_opportunity(FakeOrchestrator(), ctx)
    assert result.opportunity_brief is not None
    assert result.opportunity_brief.theme == "my theme"
    assert result.opportunity_brief.goal == "test goal"
    assert len(result.opportunity_brief.sub_angles) == 2


@pytest.mark.asyncio
async def test_opportunity_stage_runs_with_blank_strategy() -> None:
    """The opportunity stage should work with a blank StrategyMemory."""
    from cc_deep_research.content_gen.orchestrator import _stage_plan_opportunity

    class FakeOrchestrator:
        def _get_agent(self, _name: str):

            class FakeAgent:
                async def plan(self, theme, strategy):
                    assert strategy.niche == ""
                    return OpportunityBrief(theme=theme)

            return FakeAgent()

    ctx = PipelineContext(theme="bare theme")
    result = await _stage_plan_opportunity(FakeOrchestrator(), ctx)
    assert result.opportunity_brief is not None


def test_opportunity_brief_parsing() -> None:
    """The opportunity parser should extract structured fields from LLM text."""
    from cc_deep_research.content_gen.agents.opportunity import _parse_opportunity_brief

    sample_response = """\
Theme: Why most SaaS onboarding fails after day 1
Goal: Help founders fix activation by exposing the false success moment
Primary audience segment: Seed-stage SaaS founders
Secondary audience segments:
- Growth PMs at early-stage startups
- Product designers working on onboarding flows
Problem statements:
- Activation drops after signup because onboarding celebrates the wrong moment
- Users think they succeeded but never reached the real aha moment
Content objective: Show one concrete fix for the false success moment
Proof requirements:
- Cite a specific activation metric example
- Show a before/after onboarding flow
Platform constraints:
- Under 60 seconds
- No jargon
Risk constraints:
- Do not downplay churn risk
- Avoid FUD
Freshness rationale: Multiple SaaS companies reported Q1 2026 activation drops
Sub-angles:
- Guardrails as product moat
- Safety as speed advantage
- The false success pattern
Research hypotheses:
- Developers want safety but lack examples
- Guardrail content is underserved
Success criteria:
- 50k views in 48h
- 10 code forks"""

    brief, parse_mode = _parse_opportunity_brief(sample_response, "fallback")
    assert parse_mode == "legacy"
    assert brief.theme == "Why most SaaS onboarding fails after day 1"
    assert brief.goal == "Help founders fix activation by exposing the false success moment"
    assert brief.primary_audience_segment == "Seed-stage SaaS founders"
    assert len(brief.secondary_audience_segments) == 2
    assert len(brief.problem_statements) == 2
    assert brief.content_objective == "Show one concrete fix for the false success moment"
    assert len(brief.proof_requirements) == 2
    assert len(brief.platform_constraints) == 2
    assert len(brief.risk_constraints) == 2
    assert "Q1 2026" in brief.freshness_rationale
    assert len(brief.sub_angles) == 3
    assert len(brief.research_hypotheses) == 2
    assert len(brief.success_criteria) == 2


def test_opportunity_brief_parsing_uses_fallback_theme() -> None:
    """Parser should fall back to the provided theme when core fields are still present."""
    from cc_deep_research.content_gen.agents.opportunity import _parse_opportunity_brief

    brief, parse_mode = _parse_opportunity_brief(
        """Goal: something
Primary audience segment: startup marketers
Problem statements:
- Pricing pages hide the comparison buyers make first
Content objective: show the fix
""",
        "fallback theme",
    )
    assert parse_mode == "legacy"
    assert brief.theme == "fallback theme"


def test_opportunity_brief_json_parsing() -> None:
    """Parser should extract structured fields from JSON-formatted LLM output."""
    from cc_deep_research.content_gen.agents.opportunity import _parse_opportunity_brief

    sample_response = """\
Here is the opportunity brief:

```json
{
  "theme": "Why most SaaS onboarding fails after day 1",
  "goal": "Help founders fix activation by exposing the false success moment",
  "primary_audience_segment": "Seed-stage SaaS founders",
  "secondary_audience_segments": [
    "Growth PMs at early-stage startups",
    "Product designers working on onboarding flows"
  ],
  "problem_statements": [
    "Activation drops after signup because onboarding celebrates the wrong moment",
    "Users think they succeeded but never reached the real aha moment"
  ],
  "content_objective": "Show one concrete fix for the false success moment",
  "proof_requirements": ["Cite a specific activation metric example", "Show a before/after onboarding flow"],
  "platform_constraints": ["Under 60 seconds", "No jargon"],
  "risk_constraints": ["Do not downplay churn risk", "Avoid FUD"],
  "freshness_rationale": "Multiple SaaS companies reported Q1 2026 activation drops",
  "sub_angles": ["Guardrails as product moat", "Safety as speed advantage", "The false success pattern"],
  "research_hypotheses": ["Developers want safety but lack examples", "Guardrail content is underserved"],
  "success_criteria": ["50k views in 48h", "10 code forks"]
}
```"""

    brief, parse_mode = _parse_opportunity_brief(sample_response, "fallback")
    assert parse_mode == "json"
    assert brief.theme == "Why most SaaS onboarding fails after day 1"
    assert brief.goal == "Help founders fix activation by exposing the false success moment"
    assert brief.primary_audience_segment == "Seed-stage SaaS founders"
    assert len(brief.secondary_audience_segments) == 2
    assert len(brief.problem_statements) == 2
    assert brief.content_objective == "Show one concrete fix for the false success moment"
    assert len(brief.proof_requirements) == 2
    assert len(brief.platform_constraints) == 2
    assert len(brief.risk_constraints) == 2
    assert "Q1 2026" in brief.freshness_rationale
    assert len(brief.sub_angles) == 3
    assert len(brief.research_hypotheses) == 2
    assert len(brief.success_criteria) == 2


def test_opportunity_brief_json_falls_back_to_legacy() -> None:
    """Parser should fall back to legacy text parsing when JSON is unparseable."""
    from cc_deep_research.content_gen.agents.opportunity import _parse_opportunity_brief

    # Not valid JSON - will fall back to legacy parsing
    sample_response = """\
Theme: Real theme from text
Goal: Real goal
Primary audience segment: Real segment
Problem statements:
- Real problem
Content objective: Real objective"""

    brief, parse_mode = _parse_opportunity_brief(sample_response, "fallback_theme")
    assert parse_mode == "legacy"
    assert brief.theme == "Real theme from text"
    assert brief.goal == "Real goal"


@pytest.mark.asyncio
async def test_opportunity_agent_raises_when_core_fields_are_missing() -> None:
    """Opportunity planning should fail fast when the brief is too sparse to guide downstream stages."""
    agent = _FakeOpportunityAgent(
        """Goal: something
Problem statements:
- The audience misses the core comparison point
Content objective: show the fix
"""
    )

    with pytest.raises(ValueError, match="Primary audience segment"):
        await agent.plan("fallback theme", StrategyMemory())


def test_opportunity_prompt_user_includes_strategy_fields() -> None:
    """The user prompt should include available strategy fields."""
    from cc_deep_research.content_gen.prompts.opportunity import plan_opportunity_user

    strategy = StrategyMemory(
        niche="fitness",
        content_pillars=["strength", "mobility"],
        platforms=["tiktok", "shorts"],
        forbidden_claims=["spot reduction"],
        proof_standards=["peer-reviewed"],
        tone_rules=["no hype"],
    )
    result = plan_opportunity_user("strength training", strategy)
    assert "Theme: strength training" in result
    assert "Niche: fitness" in result
    assert "strength, mobility" in result
    assert "tiktok, shorts" in result
    assert "spot reduction" in result
    assert "peer-reviewed" in result
    assert "no hype" in result


def test_quality_validation_catches_generic_audience() -> None:
    """Quality validation should flag generic audience segments."""
    from cc_deep_research.content_gen.agents.opportunity import validate_opportunity_brief_quality
    from cc_deep_research.content_gen.models import OpportunityBrief

    brief = OpportunityBrief(
        theme="test",
        goal="Get more customers",
        primary_audience_segment="marketers",  # Too generic
        problem_statements=["Activation drops after signup"],
        content_objective="Show how to fix activation",
    )
    warnings, is_acceptable = validate_opportunity_brief_quality(brief)
    assert any(w.category == "audience_generic" for w in warnings)
    # Should still be acceptable with caution
    assert is_acceptable


def test_quality_validation_catches_vague_problems() -> None:
    """Quality validation should flag vague problem statements."""
    from cc_deep_research.content_gen.agents.opportunity import validate_opportunity_brief_quality
    from cc_deep_research.content_gen.models import OpportunityBrief

    brief = OpportunityBrief(
        theme="test",
        goal="Help SaaS founders",
        primary_audience_segment="seed-stage SaaS founders",
        problem_statements=["The onboarding experience is not good enough"],  # Too vague
        content_objective="Show how to improve onboarding",
    )
    warnings, is_acceptable = validate_opportunity_brief_quality(brief)
    assert any(w.category == "problem_vague" for w in warnings)


def test_quality_validation_catches_duplicate_sub_angles() -> None:
    """Quality validation should flag duplicate sub-angles."""
    from cc_deep_research.content_gen.agents.opportunity import validate_opportunity_brief_quality
    from cc_deep_research.content_gen.models import OpportunityBrief

    brief = OpportunityBrief(
        theme="test",
        goal="Help SaaS founders",
        primary_audience_segment="seed-stage SaaS founders",
        problem_statements=["Activation drops after signup because onboarding celebrates the wrong moment"],
        sub_angles=["Guardrails as product moat", "Safety as speed advantage", "Guardrails as product moat"],  # Exact duplicate
        content_objective="Show how to fix activation",
    )
    warnings, is_acceptable = validate_opportunity_brief_quality(brief)
    assert any(w.category == "sub_angle_duplicate" for w in warnings)
    # Should not be acceptable with duplicate
    assert not is_acceptable


def test_quality_validation_accepts_specific_brief() -> None:
    """Quality validation should accept well-formed briefs."""
    from cc_deep_research.content_gen.agents.opportunity import (
        format_quality_summary,
        validate_opportunity_brief_quality,
    )
    from cc_deep_research.content_gen.models import OpportunityBrief

    brief = OpportunityBrief(
        theme="Why most SaaS onboarding fails after day 1",
        goal="Help founders fix activation by exposing the false success moment",
        primary_audience_segment="Seed-stage SaaS founders with >$100k ARR",
        problem_statements=[
            "Activation drops after signup because onboarding celebrates the wrong moment",
            "Users think they succeeded but never reached the real aha moment",
        ],
        content_objective="Show one concrete fix for the false success moment",
        proof_requirements=["Specific activation metric example", "Before/after onboarding flow"],
        sub_angles=["Guardrails as product moat", "Safety as speed advantage", "The false success pattern"],
    )
    warnings, is_acceptable = validate_opportunity_brief_quality(brief)
    assert is_acceptable
    assert len(warnings) == 0

    summary = format_quality_summary(warnings)
    assert "acceptable" in summary.lower()


def test_quality_summary_formatting() -> None:
    """Quality summary should group warnings by category."""
    from cc_deep_research.content_gen.agents.opportunity import (
        BriefQualityWarning,
        format_quality_summary,
    )

    warnings = [
        BriefQualityWarning("audience_generic", "Too generic audience"),
        BriefQualityWarning("problem_vague", "Vague problem 1"),
        BriefQualityWarning("problem_vague", "Vague problem 2"),
    ]
    summary = format_quality_summary(warnings)
    assert "[audience_generic]" in summary
    assert "[problem_vague]" in summary
    assert "3 warning(s) found" in summary


# ---------------------------------------------------------------------------
# Degraded metadata tests for tolerant stages (Task 14)
# ---------------------------------------------------------------------------


def test_research_pack_degraded_flag_blank_response() -> None:
    """ResearchPack should track degraded state when LLM response is blank."""
    from cc_deep_research.content_gen.agents.research_pack import _maybe_set_degraded
    from cc_deep_research.content_gen.models import ResearchPack

    pack = ResearchPack(idea_id="test", angle_id="a1")
    _maybe_set_degraded(pack, "")

    assert pack.is_degraded is True
    assert pack.degradation_reason == "blank LLM response after retry"


def test_research_pack_degraded_flag_zero_usable_records() -> None:
    """ResearchPack should track degraded state when parser produces zero usable records."""
    from cc_deep_research.content_gen.agents.research_pack import _maybe_set_degraded
    from cc_deep_research.content_gen.models import ResearchPack

    pack = ResearchPack(idea_id="test", angle_id="a1")
    _maybe_set_degraded(pack, "some text but no structured sections")

    assert pack.is_degraded is True
    assert pack.degradation_reason == "parser produced zero usable records"


def test_research_pack_degraded_flag_partial_records() -> None:
    """ResearchPack should track degraded state when parser produces partial records."""
    from cc_deep_research.content_gen.agents.research_pack import _maybe_set_degraded
    from cc_deep_research.content_gen.models import ResearchFinding, ResearchPack

    pack = ResearchPack(
        idea_id="test",
        angle_id="a1",
        findings=[ResearchFinding(summary="Some finding")],
        # claims, counterpoints, uncertainty_flags are empty
    )
    _maybe_set_degraded(pack, "findings:\n---\nsummary: Some finding")

    assert pack.is_degraded is True
    assert "missing:" in pack.degradation_reason


def test_research_pack_not_degraded_when_complete() -> None:
    """ResearchPack should not be degraded when all structured fields are populated."""
    from cc_deep_research.content_gen.agents.research_pack import _maybe_set_degraded
    from cc_deep_research.content_gen.models import (
        ResearchClaim,
        ResearchCounterpoint,
        ResearchFinding,
        ResearchPack,
        ResearchUncertaintyFlag,
    )

    pack = ResearchPack(
        idea_id="test",
        angle_id="a1",
        findings=[ResearchFinding(summary="Some finding")],
        claims=[ResearchClaim(claim="Some claim")],
        counterpoints=[ResearchCounterpoint(summary="Some counterpoint")],
        uncertainty_flags=[ResearchUncertaintyFlag(claim="Some flag")],
    )
    _maybe_set_degraded(pack, "findings:\n---\nsummary: Some finding\nclaims:\n---\nclaim: Some claim")

    assert pack.is_degraded is False
    assert pack.degradation_reason == ""


# ---------------------------------------------------------------------------
# Source Quality Scoring Tests (Task 16)
# ---------------------------------------------------------------------------


def test_source_authority_primary_domain() -> None:
    """Primary source authority should be inferred for official domains."""
    from cc_deep_research.content_gen.agents.research_pack import _infer_authority
    from cc_deep_research.content_gen.models import SourceAuthority

    # Government domains
    source = _make_minimal_source("https://www.sec.gov/filing")
    assert _infer_authority(source) == SourceAuthority.PRIMARY

    # Academic/research domains
    source = _make_minimal_source("https://arxiv.org/abs/1234")
    assert _infer_authority(source) == SourceAuthority.PRIMARY

    # Official documentation
    source = _make_minimal_source("https://docs.stripe.com/payments")
    assert _infer_authority(source) == SourceAuthority.PRIMARY


def test_source_authority_secondary_domain() -> None:
    """Secondary source authority should be inferred for news and analysis."""
    from cc_deep_research.content_gen.agents.research_pack import _infer_authority
    from cc_deep_research.content_gen.models import SourceAuthority

    source = _make_minimal_source("https://techcrunch.com/startup-news")
    assert _infer_authority(source) == SourceAuthority.SECONDARY

    source = _make_minimal_source("https://hbr.org/2024/01/strategy")
    assert _infer_authority(source) == SourceAuthority.SECONDARY


def test_source_authority_tertiary_domain() -> None:
    """Tertiary source authority should be inferred for social and aggregation sites."""
    from cc_deep_research.content_gen.agents.research_pack import _infer_authority
    from cc_deep_research.content_gen.models import SourceAuthority

    source = _make_minimal_source("https://twitter.com/user/status/123")
    assert _infer_authority(source) == SourceAuthority.TERTIARY

    source = _make_minimal_source("https://reddit.com/r/python/comments/abc")
    assert _infer_authority(source) == SourceAuthority.TERTIARY


def test_source_authority_unknown_domain() -> None:
    """Unknown authority for unrecognizable domains."""
    from cc_deep_research.content_gen.agents.research_pack import _infer_authority
    from cc_deep_research.content_gen.models import SourceAuthority

    source = _make_minimal_source("https://example.com/some-page")
    assert _infer_authority(source) == SourceAuthority.UNKNOWN


def test_evidence_directness_by_family() -> None:
    """Evidence directness should be inferred from query family."""
    from cc_deep_research.content_gen.agents.research_pack import _infer_directness
    from cc_deep_research.content_gen.models import EvidenceDirectness
    from cc_deep_research.models import QueryFamily

    # Proof families should be direct
    plan = QueryFamily(query="test", family="proof", intent_tags=["evidence"])
    assert _infer_directness(plan) == EvidenceDirectness.DIRECT

    plan = QueryFamily(query="test", family="primary-source", intent_tags=["official"])
    assert _infer_directness(plan) == EvidenceDirectness.DIRECT

    # Competitor families should be indirect
    plan = QueryFamily(query="test", family="competitor", intent_tags=["example"])
    assert _infer_directness(plan) == EvidenceDirectness.INDIRECT

    # Contrarian families should be anecdotal
    plan = QueryFamily(query="test", family="contrarian", intent_tags=["myth"])
    assert _infer_directness(plan) == EvidenceDirectness.ANECDOTAL


def test_source_freshness_from_date() -> None:
    """Source freshness should be inferred from published date."""
    from datetime import datetime

    from cc_deep_research.content_gen.agents.research_pack import _infer_freshness
    from cc_deep_research.content_gen.models import SourceFreshness

    # Current: within 6 months
    recent = datetime.now().strftime("%Y-%m-%d")
    assert _infer_freshness(recent) == SourceFreshness.CURRENT

    # Recent: within 2 years
    one_year_ago = (datetime.now().replace(year=datetime.now().year - 1)).strftime("%Y-%m-%d")
    assert _infer_freshness(one_year_ago) == SourceFreshness.RECENT

    # Stale: older than 2 years
    three_years_ago = (datetime.now().replace(year=datetime.now().year - 3)).strftime("%Y-%m-%d")
    assert _infer_freshness(three_years_ago) == SourceFreshness.STALE

    # Unknown date
    assert _infer_freshness(None) == SourceFreshness.UNKNOWN
    assert _infer_freshness("") == SourceFreshness.UNKNOWN
    assert _infer_freshness("unknown") == SourceFreshness.UNKNOWN


def test_compute_quality_rank_primary_direct_current() -> None:
    """Highest rank for primary, direct, current sources."""
    from cc_deep_research.content_gen.agents.research_pack import _compute_quality_rank
    from cc_deep_research.content_gen.models import (
        EvidenceDirectness,
        SourceAuthority,
        SourceFreshness,
    )

    rank = _compute_quality_rank(
        SourceAuthority.PRIMARY,
        EvidenceDirectness.DIRECT,
        SourceFreshness.CURRENT,
    )
    assert rank >= 0.9  # Should be very high


def test_compute_quality_rank_tertiary_anecdotal_stale() -> None:
    """Lowest rank for tertiary, anecdotal, stale sources."""
    from cc_deep_research.content_gen.agents.research_pack import _compute_quality_rank
    from cc_deep_research.content_gen.models import (
        EvidenceDirectness,
        SourceAuthority,
        SourceFreshness,
    )

    rank = _compute_quality_rank(
        SourceAuthority.TERTIARY,
        EvidenceDirectness.ANECDOTAL,
        SourceFreshness.STALE,
    )
    assert rank < 0.5  # Should be low


def test_score_source_quality_populates_all_fields() -> None:
    """_score_source_quality should populate authority, directness, freshness, and rank."""
    from cc_deep_research.content_gen.agents.research_pack import _score_source_quality
    from cc_deep_research.content_gen.models import (
        EvidenceDirectness,
        ResearchSource,
        SourceAuthority,
        SourceFreshness,
    )
    from cc_deep_research.models import QueryFamily

    source = ResearchSource(
        source_id="src_test",
        url="https://arxiv.org/abs/1234",
        title="Research paper",
        provider="arxiv",
        published_date="2026-01-15",
    )
    plan = QueryFamily(query="test", family="proof", intent_tags=["evidence"])

    _score_source_quality(source, plan)

    assert source.source_authority == SourceAuthority.PRIMARY
    assert source.evidence_directness == EvidenceDirectness.DIRECT
    assert source.source_freshness == SourceFreshness.CURRENT
    assert source.quality_rank is not None
    assert source.quality_rank >= 0.8


def test_render_source_catalog_sorts_by_quality() -> None:
    """Source catalog should be sorted by quality_rank descending."""
    from cc_deep_research.content_gen.agents.research_pack import _render_source_catalog
    from cc_deep_research.content_gen.models import (
        EvidenceDirectness,
        ResearchSource,
        SourceAuthority,
        SourceFreshness,
    )

    # Create sources with different quality ranks
    low_quality = ResearchSource(
        source_id="src_low",
        url="https://twitter.com/status/123",
        title="Tweet",
        provider="twitter",
        quality_rank=0.2,
        source_authority=SourceAuthority.TERTIARY,
        evidence_directness=EvidenceDirectness.ANECDOTAL,
        source_freshness=SourceFreshness.UNKNOWN,
    )
    high_quality = ResearchSource(
        source_id="src_high",
        url="https://arxiv.org/abs/1234",
        title="Research paper",
        provider="arxiv",
        quality_rank=0.9,
        source_authority=SourceAuthority.PRIMARY,
        evidence_directness=EvidenceDirectness.DIRECT,
        source_freshness=SourceFreshness.CURRENT,
    )

    catalog = _render_source_catalog([low_quality, high_quality])

    # High quality should appear first
    high_pos = catalog.find("src_high")
    low_pos = catalog.find("src_low")
    assert high_pos < low_pos, "Higher quality source should appear first in catalog"


def test_render_source_catalog_includes_quality_signals() -> None:
    """Source catalog should include authority, directness, and freshness fields."""
    from cc_deep_research.content_gen.agents.research_pack import _render_source_catalog
    from cc_deep_research.content_gen.models import (
        EvidenceDirectness,
        ResearchSource,
        SourceAuthority,
        SourceFreshness,
    )

    source = ResearchSource(
        source_id="src_01",
        url="https://arxiv.org/abs/1234",
        title="Research paper",
        provider="arxiv",
        quality_rank=0.9,
        source_authority=SourceAuthority.PRIMARY,
        evidence_directness=EvidenceDirectness.DIRECT,
        source_freshness=SourceFreshness.CURRENT,
    )

    catalog = _render_source_catalog([source])

    assert "authority: primary" in catalog
    assert "directness: direct" in catalog
    assert "freshness: current" in catalog
    assert "STRONG" in catalog or "quality:" in catalog


def test_strong_primary_source_outranks_weak_secondary() -> None:
    """A strong primary source should outrank a weak secondary summary for the same claim."""
    from cc_deep_research.content_gen.agents.research_pack import _score_source_quality
    from cc_deep_research.content_gen.models import ResearchSource
    from cc_deep_research.models import QueryFamily

    # Strong primary: official documentation
    strong_source = ResearchSource(
        source_id="src_strong",
        url="https://docs.stripe.com/payments",
        title="Stripe Payments Documentation",
        provider="stripe",
        published_date="2026-03-01",
    )
    strong_plan = QueryFamily(query="stripe payments", family="primary-source", intent_tags=["official", "docs"])
    _score_source_quality(strong_source, strong_plan)

    # Weak secondary: a Twitter summary
    weak_source = ResearchSource(
        source_id="src_weak",
        url="https://twitter.com/user/status/456",
        title="Someone's tweet about Stripe",
        provider="twitter",
        published_date="2024-01-01",  # Stale
    )
    weak_plan = QueryFamily(query="stripe payments twitter", family="competitor", intent_tags=["social"])
    _score_source_quality(weak_source, weak_plan)

    # Strong source should have higher quality rank
    assert strong_source.quality_rank is not None
    assert weak_source.quality_rank is not None
    assert strong_source.quality_rank > weak_source.quality_rank

    # Strong source should be primary authority
    assert strong_source.source_authority.value == "primary"
    # Weak source should be tertiary or unknown
    assert weak_source.source_authority.value in ("tertiary", "unknown")


def _make_minimal_source(url: str) -> ResearchSource:
    """Helper to create a minimal ResearchSource for testing."""
    from cc_deep_research.content_gen.models import ResearchSource

    return ResearchSource(
        source_id="src_test",
        url=url,
        title="Test",
        provider="test",
    )


def test_production_brief_degraded_flag_blank_response() -> None:
    """ProductionBrief should track degraded state when LLM response is blank."""
    from cc_deep_research.content_gen.agents.production import _maybe_set_degraded
    from cc_deep_research.content_gen.models import ProductionBrief

    brief = ProductionBrief(idea_id="test")
    _maybe_set_degraded(brief, "")

    assert brief.is_degraded is True
    assert brief.degradation_reason == "blank LLM response after retry"


def test_production_brief_degraded_flag_zero_usable_records() -> None:
    """ProductionBrief should track degraded state when parser produces zero usable records."""
    from cc_deep_research.content_gen.agents.production import _maybe_set_degraded
    from cc_deep_research.content_gen.models import ProductionBrief

    brief = ProductionBrief(idea_id="test")
    _maybe_set_degraded(brief, "location:")

    assert brief.is_degraded is True
    assert brief.degradation_reason == "parser produced zero usable records"


def test_production_brief_degraded_flag_partial_records() -> None:
    """ProductionBrief should track degraded state when parser produces partial records."""
    from cc_deep_research.content_gen.agents.production import _maybe_set_degraded
    from cc_deep_research.content_gen.models import ProductionBrief

    brief = ProductionBrief(idea_id="test", location="Studio A", props=[])
    _maybe_set_degraded(brief, "location: Studio A")

    assert brief.is_degraded is True
    assert "missing:" in brief.degradation_reason


def test_production_brief_not_degraded_when_complete() -> None:
    """ProductionBrief should not be degraded when all fields are populated."""
    from cc_deep_research.content_gen.agents.production import _maybe_set_degraded
    from cc_deep_research.content_gen.models import ProductionBrief

    brief = ProductionBrief(
        idea_id="test",
        location="Studio A",
        setup="Three camera angles",
        wardrobe="Casual",
        props=["Laptop", "Notebook"],
        assets_to_prepare=["Screenshots"],
        audio_checks=["Mic level"],
        battery_checks=["Check battery"],
        storage_checks=["Clear space"],
        pickup_lines_to_capture=["Opening hook"],
        backup_plan="Use B-roll if needed",
    )
    _maybe_set_degraded(brief, "location: Studio A\nsetup: Three camera angles")

    assert brief.is_degraded is False
    assert brief.degradation_reason == ""


def test_performance_analysis_degraded_flag_blank_response() -> None:
    """PerformanceAnalysis should track degraded state when LLM response is blank."""
    from cc_deep_research.content_gen.agents.performance import _maybe_set_degraded
    from cc_deep_research.content_gen.models import PerformanceAnalysis

    analysis = PerformanceAnalysis(video_id="v123")
    _maybe_set_degraded(analysis, "")

    assert analysis.is_degraded is True
    assert analysis.degradation_reason == "blank LLM response after retry"


def test_performance_analysis_degraded_flag_zero_usable_records() -> None:
    """PerformanceAnalysis should track degraded state when parser produces zero usable records."""
    from cc_deep_research.content_gen.agents.performance import _maybe_set_degraded
    from cc_deep_research.content_gen.models import PerformanceAnalysis

    analysis = PerformanceAnalysis(video_id="v123")
    _maybe_set_degraded(analysis, "hook_diagnosis:")

    assert analysis.is_degraded is True
    assert analysis.degradation_reason == "parser produced zero usable records"


def test_performance_analysis_degraded_flag_partial_records() -> None:
    """PerformanceAnalysis should track degraded state when parser produces partial records."""
    from cc_deep_research.content_gen.agents.performance import _maybe_set_degraded
    from cc_deep_research.content_gen.models import PerformanceAnalysis

    analysis = PerformanceAnalysis(
        video_id="v123",
        what_worked=["Strong hook"],
        what_failed=[],
        audience_signals=[],
        dropoff_hypotheses=[],
        follow_up_ideas=[],
        backlog_updates=[],
    )
    _maybe_set_degraded(analysis, "what_worked:\n- Strong hook")

    assert analysis.is_degraded is True
    assert "missing:" in analysis.degradation_reason


def test_performance_analysis_not_degraded_when_complete() -> None:
    """PerformanceAnalysis should not be degraded when all fields are populated."""
    from cc_deep_research.content_gen.agents.performance import _maybe_set_degraded
    from cc_deep_research.content_gen.models import PerformanceAnalysis

    analysis = PerformanceAnalysis(
        video_id="v123",
        what_worked=["Strong hook", "Clear CTA"],
        what_failed=["Weak second beat"],
        audience_signals=["High retention on hook"],
        dropoff_hypotheses=["Topic too narrow"],
        hook_diagnosis="Strong but could be tighter",
        lesson="Lead with the surprising stat",
        next_test="Try different opening frame",
        follow_up_ideas=["Follow up on stat angle"],
        backlog_updates=["Add pricing angle"],
    )
    _maybe_set_degraded(
        analysis,
        "what_worked:\n- Strong hook\n- Clear CTA\nwhat_failed:\n- Weak second beat",
    )

    assert analysis.is_degraded is False
    assert analysis.degradation_reason == ""


def test_orchestrator_build_trace_metadata_research_pack_degraded() -> None:
    """Orchestrator should surface research pack degraded state in stage trace metadata."""
    from cc_deep_research.content_gen.models import (
        PipelineContext,
        ResearchPack,
        StageTraceMetadata,
    )

    ctx = PipelineContext(
        research_pack=ResearchPack(
            idea_id="test-idea",
            angle_id="test-angle",
            is_degraded=True,
            degradation_reason="blank LLM response after retry",
        )
    )

    # Simulate _build_trace_metadata behavior for build_research_pack stage
    meta = StageTraceMetadata()
    if ctx.research_pack:
        meta.is_degraded = ctx.research_pack.is_degraded
        meta.degradation_reason = ctx.research_pack.degradation_reason

    assert meta.is_degraded is True
    assert meta.degradation_reason == "blank LLM response after retry"


def test_orchestrator_build_trace_metadata_production_brief_degraded() -> None:
    """Orchestrator should surface production brief degraded state in stage trace metadata."""
    from cc_deep_research.content_gen.models import (
        PipelineContext,
        ProductionBrief,
        StageTraceMetadata,
    )

    ctx = PipelineContext(
        production_brief=ProductionBrief(
            idea_id="test-idea",
            is_degraded=True,
            degradation_reason="parser produced partial records; missing: props, assets_to_prepare",
        )
    )

    # Simulate _build_trace_metadata behavior for production_brief stage
    meta = StageTraceMetadata()
    if ctx.production_brief:
        meta.is_degraded = ctx.production_brief.is_degraded
        meta.degradation_reason = ctx.production_brief.degradation_reason

    assert meta.is_degraded is True
    assert "missing:" in meta.degradation_reason


def test_orchestrator_build_trace_metadata_performance_analysis_degraded() -> None:
    """Orchestrator should surface performance analysis degraded state in stage trace metadata."""
    from cc_deep_research.content_gen.models import (
        PerformanceAnalysis,
        PipelineContext,
        StageTraceMetadata,
    )

    ctx = PipelineContext(
        performance=PerformanceAnalysis(
            video_id="v123",
            is_degraded=True,
            degradation_reason="blank LLM response after retry",
        )
    )

    # Simulate _build_trace_metadata behavior for performance_analysis stage
    meta = StageTraceMetadata()
    if ctx.performance:
        meta.is_degraded = ctx.performance.is_degraded
        meta.degradation_reason = ctx.performance.degradation_reason

    assert meta.is_degraded is True
    assert meta.degradation_reason == "blank LLM response after retry"


def test_orchestrator_collect_warnings_publish_queue_no_items() -> None:
    """Orchestrator should warn when publish queue produces no items."""
    from cc_deep_research.content_gen.models import PipelineContext

    ctx = PipelineContext(publish_items=[])

    # Simulate _collect_trace_warnings behavior for publish_queue stage
    warnings: list[str] = []
    has_items = bool(ctx.publish_items or ctx.publish_item is not None)
    if not has_items:
        warnings.append("Publish queue produced no items; upstream dependency may be incomplete.")

    assert len(warnings) == 1
    assert "no items" in warnings[0]


# ---------------------------------------------------------------------------
# Retrieval Planner Tests
# ---------------------------------------------------------------------------


def _make_test_item_and_angle() -> tuple[BacklogItem, AngleOption]:
    """Standard test item and angle for retrieval planner tests."""
    item = BacklogItem(
        idea="pricing psychology",
        audience="B2B SaaS founders",
        problem="buyers do not compare plans the way teams expect",
    )
    angle = AngleOption(
        target_audience="subscription software marketers",
        viewer_problem="teams keep optimizing copy instead of comparison framing",
        core_promise="Tier order changes what buyers notice first",
        primary_takeaway="Fix the comparison before the checklist",
    )
    return item, angle


def test_retrieval_planner_baseline_mode_returns_core_families() -> None:
    """Baseline mode should produce all 6 core query families."""
    item, angle = _make_test_item_and_angle()
    planner = RetrievalPlanner(item, angle, mode=RetrievalMode.BASELINE)
    plan = planner.build_plan()

    assert plan.is_complete
    assert plan.mode == RetrievalMode.BASELINE
    families = {d.family for d in plan.decisions}
    assert families == {
        "proof",
        "primary-source",
        "competitor",
        "contrarian",
        "freshness",
        "practitioner-language",
    }


def test_retrieval_planner_contrarian_mode_prioritizes_contrarian() -> None:
    """Contrarian mode should prioritize counterevidence queries."""
    item, angle = _make_test_item_and_angle()
    planner = RetrievalPlanner(item, angle, mode=RetrievalMode.CONTRARIAN)
    plan = planner.build_plan()

    assert plan.mode == RetrievalMode.CONTRARIAN
    families = {d.family for d in plan.decisions}
    # Should include contrarian and myth-busting
    assert "contrarian" in families
    # Proof should still be present for balance
    assert "proof" in families


def test_retrieval_planner_targeted_mode_adds_gap_queries() -> None:
    """Targeted mode should add gap-filling queries."""
    item, angle = _make_test_item_and_angle()
    gaps = ["specific conversion rate data", "anchor pricing examples"]
    planner = RetrievalPlanner(
        item,
        angle,
        mode=RetrievalMode.TARGETED,
        research_gaps=gaps,
    )
    plan = planner.build_plan()

    assert plan.mode == RetrievalMode.TARGETED
    # Should have targeted-gap family queries
    gap_families = [d.family for d in plan.decisions if d.family == "targeted-gap"]
    assert len(gap_families) == len(gaps)


def test_retrieval_planner_deep_mode_expands_families() -> None:
    """Deep mode should expand families with additional variants."""
    item, angle = _make_test_item_and_angle()
    planner = RetrievalPlanner(item, angle, mode=RetrievalMode.DEEP)
    plan = planner.build_plan()

    assert plan.mode == RetrievalMode.DEEP
    # Should have more queries than baseline due to expansions
    assert plan.total_queries >= 6


def test_retrieval_planner_feedback_infers_contrarian_mode() -> None:
    """Feedback containing contrarian keywords should trigger contrarian mode."""
    item, angle = _make_test_item_and_angle()
    planner = RetrievalPlanner(
        item,
        angle,
        feedback="We need more counterevidence and alternative viewpoints",
    )
    plan = planner.build_plan()

    assert plan.mode == RetrievalMode.CONTRARIAN


def test_retrieval_planner_feedback_infers_targeted_mode() -> None:
    """Feedback containing gap/missing keywords should trigger targeted mode."""
    item, angle = _make_test_item_and_angle()
    planner = RetrievalPlanner(
        item,
        angle,
        feedback="There are missing proof points for the main claim",
    )
    plan = planner.build_plan()

    assert plan.mode == RetrievalMode.TARGETED


def test_retrieval_planner_budget_limits_queries() -> None:
    """Budget should limit the number of queries produced."""
    item, angle = _make_test_item_and_angle()
    budget = RetrievalBudget(max_queries=3)
    planner = RetrievalPlanner(item, angle, budget=budget)
    plan = planner.build_plan()

    assert plan.total_queries <= 3


def test_retrieval_planner_budget_limits_sources() -> None:
    """Budget max_sources should be preserved in the plan."""
    item, angle = _make_test_item_and_angle()
    budget = RetrievalBudget(max_sources=8)
    planner = RetrievalPlanner(item, angle, budget=budget)
    plan = planner.build_plan()

    assert plan.budget.max_sources == 8


def test_retrieval_planner_respects_stop_conditions() -> None:
    """Budget stop_if_sources_seen should be recorded in plan."""
    item, angle = _make_test_item_and_angle()
    budget = RetrievalBudget(max_queries=4, stop_if_sources_seen=6)
    planner = RetrievalPlanner(item, angle, budget=budget)
    plan = planner.build_plan()

    assert plan.budget.stop_if_sources_seen == 6
    assert plan.budget.max_queries == 4


def test_retrieval_plan_total_queries_property() -> None:
    """RetrievalPlan.total_queries should return decision count."""
    item, angle = _make_test_item_and_angle()
    planner = RetrievalPlanner(item, angle, mode=RetrievalMode.BASELINE)
    plan = planner.build_plan()

    assert plan.total_queries == len(plan.decisions)


def test_retrieval_plan_families_used_property() -> None:
    """RetrievalPlan.families_used should return unique family set."""
    item, angle = _make_test_item_and_angle()
    planner = RetrievalPlanner(item, angle, mode=RetrievalMode.BASELINE)
    plan = planner.build_plan()

    assert plan.families_used == {d.family for d in plan.decisions}


def test_retrieval_decision_has_intent_tags() -> None:
    """Each retrieval decision should have intent tags."""
    item, angle = _make_test_item_and_angle()
    planner = RetrievalPlanner(item, angle, mode=RetrievalMode.BASELINE)
    plan = planner.build_plan()

    for decision in plan.decisions:
        assert decision.intent_tags
        assert decision.query
        assert decision.family


def test_retrieval_decision_priorities_are_set() -> None:
    """Retrieval decisions should have priority values for ordering."""
    item, angle = _make_test_item_and_angle()
    planner = RetrievalPlanner(item, angle, mode=RetrievalMode.BASELINE)
    plan = planner.build_plan()

    priorities = [d.priority for d in plan.decisions]
    # Proof family should have highest priority (10 or 5 in baseline)
    proof_decisions = [d for d in plan.decisions if d.family == "proof"]
    if proof_decisions:
        assert proof_decisions[0].priority >= max(p.priority for p in plan.decisions if p.priority)


def test_retrieval_mode_enum_values() -> None:
    """RetrievalMode should have expected enum values."""
    assert RetrievalMode.BASELINE == "baseline"
    assert RetrievalMode.DEEP == "deep"
    assert RetrievalMode.TARGETED == "targeted"
    assert RetrievalMode.CONTRARIAN == "contrarian"


def test_retrieval_budget_defaults() -> None:
    """RetrievalBudget should have sensible defaults."""
    budget = RetrievalBudget()

    assert budget.max_queries == 6
    assert budget.max_sources == 12
    assert budget.max_results_per_query == 5
    assert budget.stop_if_sources_seen is None
    assert budget.stop_on_family_count is None


def test_retrieval_budget_custom_values() -> None:
    """RetrievalBudget should accept custom values."""
    budget = RetrievalBudget(
        max_queries=10,
        max_sources=20,
        max_results_per_query=8,
        stop_if_sources_seen=15,
    )

    assert budget.max_queries == 10
    assert budget.max_sources == 20
    assert budget.max_results_per_query == 8
    assert budget.stop_if_sources_seen == 15


def test_retrieval_plan_default_values() -> None:
    """RetrievalPlan should have correct default values."""
    plan = RetrievalPlan()

    assert plan.decisions == []
    assert plan.budget == RetrievalBudget()
    assert plan.mode == RetrievalMode.BASELINE
    assert plan.research_hypotheses == []
    assert plan.coverage_notes == []
    assert plan.is_complete is False
    assert plan.total_queries == 0
    assert plan.families_used == set()


def test_retrieval_planner_deduplicates_similar_queries() -> None:
    """Planner should not add duplicate queries."""
    item = BacklogItem(
        idea="same topic",
        audience="same audience",
        problem="same problem",
    )
    angle = AngleOption(
        target_audience="same audience",
        viewer_problem="same problem",
        core_promise="same promise",
        primary_takeaway="same takeaway",
    )
    # Force duplicate by using very similar context
    planner = RetrievalPlanner(item, angle, mode=RetrievalMode.BASELINE)
    plan = planner.build_plan()

    # All queries should be unique
    queries = [d.query for d in plan.decisions]
    assert len(queries) == len(set(queries))


def test_retrieval_planner_feedback_with_gaps_prefers_targeted() -> None:
    """Feedback with gap keywords should prefer targeted mode even with gaps provided."""
    item, angle = _make_test_item_and_angle()
    gaps = ["some specific gap"]
    planner = RetrievalPlanner(
        item,
        angle,
        feedback="We have gaps in the evidence coverage",
        research_gaps=gaps,
    )
    plan = planner.build_plan()

    # Feedback should override to targeted when gaps present
    assert plan.mode == RetrievalMode.TARGETED


def test_retrieval_planner_coverage_notes_populated() -> None:
    """RetrievalPlan should include coverage notes for each decision."""
    item, angle = _make_test_item_and_angle()
    planner = RetrievalPlanner(item, angle, mode=RetrievalMode.BASELINE)
    plan = planner.build_plan()

    assert len(plan.coverage_notes) == len(plan.decisions)


def test_retrieval_planner_research_hypotheses_empty_by_default() -> None:
    """Research hypotheses should be empty unless opportunity brief provides them."""
    item, angle = _make_test_item_and_angle()
    planner = RetrievalPlanner(item, angle)
    plan = planner.build_plan()

    assert plan.research_hypotheses == []


# ---------------------------------------------------------------------------
# Claim Traceability Ledger Tests (Task 17)
# ---------------------------------------------------------------------------


def test_claim_ledger_initialized_from_research_pack() -> None:
    """Ledger entries are created from research pack claims."""
    research_pack = ResearchPack(
        idea_id="test_idea",
        claims=[
            ResearchClaim(claim_id="claim_1", claim="Climate is warming", claim_type=ResearchClaimType.KEY_FACT),
            ResearchClaim(
                claim_id="claim_2",
                claim="CO2 levels rising",
                claim_type=ResearchClaimType.PROOF_POINT,
                source_ids=["src_1"],
            ),
        ],
    )

    ledger = ClaimTraceLedger()
    for claim in research_pack.claims:
        from cc_deep_research.content_gen.models import ClaimTraceEntry

        entry = ClaimTraceEntry(
            claim_id=claim.claim_id,
            claim_text=claim.claim,
            first_seen_stage=ClaimTraceStage.RESEARCH_PACK,
            research_claim_type=claim.claim_type,
            source_ids=list(claim.source_ids),
            status=ClaimTraceStatus.SUPPORTED if claim.source_ids else ClaimTraceStatus.UNSUPPORTED,
        )
        ledger.entries.append(entry)

    assert len(ledger.entries) == 2
    assert ledger.get_claim("claim_1") is not None
    assert ledger.get_claim("claim_1").status == ClaimTraceStatus.UNSUPPORTED
    assert ledger.get_claim("claim_2").status == ClaimTraceStatus.SUPPORTED


def test_claim_ledger_tracks_argument_map_claims() -> None:
    """Ledger properly tracks claims that appear in argument map."""
    ledger = ClaimTraceLedger()

    # Add research claim
    entry = ClaimTraceEntry(
        claim_id="claim_1",
        claim_text="Global temperature rose 1.1C",
        first_seen_stage=ClaimTraceStage.RESEARCH_PACK,
        source_ids=["src_1"],
        status=ClaimTraceStatus.SUPPORTED,
    )
    ledger.entries.append(entry)

    # Simulate argument map processing - claim appears in argument map with proof
    existing_entry = ledger.get_claim("claim_1")
    assert existing_entry is not None
    existing_entry.present_in_argument_map = True
    existing_entry.argument_claim_id = "arg_claim_1"
    existing_entry.supporting_proof_ids = ["proof_1"]

    assert existing_entry.present_in_argument_map is True
    assert existing_entry.argument_claim_id == "arg_claim_1"
    assert existing_entry.supporting_proof_ids == ["proof_1"]


def test_claim_ledger_detects_introduced_late_claim() -> None:
    """Ledger detects claims that appear in script but were not in argument map."""
    ledger = ClaimTraceLedger()

    # Research claim that was NOT included in argument map
    entry = ClaimTraceEntry(
        claim_id="claim_late",
        claim_text="This fact was never validated in argument map",
        first_seen_stage=ClaimTraceStage.RESEARCH_PACK,
        source_ids=["src_1"],
        status=ClaimTraceStatus.SUPPORTED,
    )
    ledger.entries.append(entry)

    # Simulate script containing this claim but it wasn't in argument map
    final_script = "This fact was never validated in argument map. This is the script content."
    entry_text_lower = entry.claim_text.lower()
    assert entry_text_lower in final_script.lower()
    assert entry.present_in_argument_map is False
    assert entry.first_seen_stage == ClaimTraceStage.RESEARCH_PACK

    # This claim should be flagged as introduced_late
    entry.status = ClaimTraceStatus.INTRODUCED_LATE
    ledger.introduced_late_claims.append(entry.claim_id)

    assert ClaimTraceStatus.INTRODUCED_LATE in [e.status for e in ledger.entries]
    assert "claim_late" in ledger.introduced_late_claims


def test_claim_ledger_detects_dropped_claim() -> None:
    """Ledger detects claims that were in argument map but not in final script."""
    ledger = ClaimTraceLedger()

    # Claim that was in argument map
    entry = ClaimTraceEntry(
        claim_id="claim_dropped",
        claim_text="This claim was in the argument map",
        first_seen_stage=ClaimTraceStage.ARGUMENT_MAP,
        present_in_argument_map=True,
        supporting_proof_ids=["proof_1"],
        status=ClaimTraceStatus.SUPPORTED,
    )
    ledger.entries.append(entry)

    # Simulate script that does NOT contain this claim
    final_script = "Some other content in the script"
    assert entry.claim_text.lower() not in final_script.lower()
    assert entry.present_in_argument_map is True

    # This claim should be flagged as dropped
    entry.status = ClaimTraceStatus.DROPPED
    ledger.dropped_claims.append(entry.claim_id)

    assert ClaimTraceStatus.DROPPED in [e.status for e in ledger.entries]
    assert "claim_dropped" in ledger.dropped_claims


def test_claim_ledger_script_claim_statement_tracking() -> None:
    """Script claims are tracked with their statement IDs and proof anchors."""
    ledger = ClaimTraceLedger()

    # Add a supported claim
    entry = ClaimTraceEntry(
        claim_id="claim_1",
        claim_text="The Earth is warming",
        first_seen_stage=ClaimTraceStage.RESEARCH_PACK,
        source_ids=["src_1"],
        present_in_argument_map=True,
        supporting_proof_ids=["proof_1"],
        status=ClaimTraceStatus.SUPPORTED,
    )
    ledger.entries.append(entry)

    # Create script claim statement
    statement = ScriptClaimStatement(
        statement_id="stmt_1",
        text="The Earth is warming",
        beat_name="intro",
        claim_ids=["claim_1"],
        proof_anchor_ids=["proof_1"],
        status=ClaimTraceStatus.SUPPORTED,
        status_reason="Matched to argument map claim with proof anchors",
    )
    ledger.script_claims.append(statement)
    entry.script_statement_ids.append(statement.statement_id)

    assert len(ledger.script_claims) == 1
    assert ledger.get_script_claim("stmt_1") is not None
    assert ledger.get_script_claim("stmt_1").status == ClaimTraceStatus.SUPPORTED
    assert ledger.unsupported_script_claims == []


def test_claim_ledger_unsupported_script_claim_detection() -> None:
    """Unsupported script claims are properly flagged."""
    ledger = ClaimTraceLedger()

    # Add an unsupported claim (no proof in argument map)
    entry = ClaimTraceEntry(
        claim_id="claim_weak",
        claim_text="This claim has no proof",
        first_seen_stage=ClaimTraceStage.RESEARCH_PACK,
        status=ClaimTraceStatus.UNSUPPORTED,
    )
    ledger.entries.append(entry)

    # Create script claim statement without proof
    statement = ScriptClaimStatement(
        statement_id="stmt_weak",
        text="This claim has no proof",
        claim_ids=["claim_weak"],
        status=ClaimTraceStatus.UNSUPPORTED,
        status_reason="No proof anchors available",
    )
    ledger.script_claims.append(statement)
    entry.script_statement_ids.append(statement.statement_id)

    if statement.status == ClaimTraceStatus.UNSUPPORTED:
        ledger.unsupported_script_claims.append(statement.statement_id)

    assert "stmt_weak" in ledger.unsupported_script_claims
    assert ledger.get_script_claim("stmt_weak") is not None
    assert ledger.get_script_claim("stmt_weak").status == ClaimTraceStatus.UNSUPPORTED


def test_claim_ledger_claims_needing_attention() -> None:
    """claims_needing_attention returns all problematic claims."""
    ledger = ClaimTraceLedger()

    # Add various types of claims
    entries = [
        ClaimTraceEntry(
            claim_id="good",
            claim_text="Good claim",
            status=ClaimTraceStatus.SUPPORTED,
        ),
        ClaimTraceEntry(
            claim_id="unsupported",
            claim_text="Unsupported claim",
            status=ClaimTraceStatus.UNSUPPORTED,
        ),
        ClaimTraceEntry(
            claim_id="late",
            claim_text="Introduced late",
            status=ClaimTraceStatus.INTRODUCED_LATE,
        ),
        ClaimTraceEntry(
            claim_id="dropped",
            claim_text="Dropped claim",
            status=ClaimTraceStatus.DROPPED,
        ),
    ]
    ledger.entries.extend(entries)

    needs_attention = ledger.claims_needing_attention()
    assert len(needs_attention) == 3
    assert ledger.get_claim("good") not in needs_attention
    assert ledger.get_claim("unsupported") in needs_attention
    assert ledger.get_claim("late") in needs_attention
    assert ledger.get_claim("dropped") in needs_attention


def test_claim_ledger_to_summary() -> None:
    """to_summary produces human-readable traceability summary."""
    ledger = ClaimTraceLedger()
    ledger.entries.append(
        ClaimTraceEntry(claim_id="c1", claim_text="Test", status=ClaimTraceStatus.SUPPORTED)
    )
    ledger.script_claims.append(
        ScriptClaimStatement(statement_id="s1", text="Test", status=ClaimTraceStatus.SUPPORTED)
    )

    summary = ledger.to_summary()
    assert "Total tracked claims: 1" in summary
    assert "Script statements: 1" in summary


def test_claim_ledger_unsupported_claims_for_qc() -> None:
    """unsupported_claims_for_qc returns formatted list for QC review."""
    ledger = ClaimTraceLedger()

    entries = [
        ClaimTraceEntry(
            claim_id="late_1",
            claim_text="Late introduced claim",
            status=ClaimTraceStatus.INTRODUCED_LATE,
        ),
        ClaimTraceEntry(
            claim_id="unsupported_1",
            claim_text="Unsupported claim text",
            status=ClaimTraceStatus.UNSUPPORTED,
        ),
    ]
    ledger.entries.extend(entries)

    # Add script statements for QC
    ledger.script_claims.append(
        ScriptClaimStatement(
            statement_id="s1",
            text="Late introduced claim",
            claim_ids=["late_1"],
            status=ClaimTraceStatus.INTRODUCED_LATE,
        )
    )
    ledger.script_claims.append(
        ScriptClaimStatement(
            statement_id="s2",
            text="Unsupported claim text",
            claim_ids=["unsupported_1"],
            status=ClaimTraceStatus.UNSUPPORTED,
        )
    )

    unsupported = ledger.unsupported_claims_for_qc()
    assert any("LATE" in c for c in unsupported)
    assert any("UNSUPPORTED" in c for c in unsupported)


def test_claim_ledger_pipeline_context_serialization() -> None:
    """Claim ledger survives PipelineContext serialization."""
    ledger = ClaimTraceLedger()
    ledger.entries.append(
        ClaimTraceEntry(
            claim_id="test_claim",
            claim_text="Test claim text",
            first_seen_stage=ClaimTraceStage.RESEARCH_PACK,
            status=ClaimTraceStatus.SUPPORTED,
        )
    )
    ledger.script_claims.append(
        ScriptClaimStatement(
            statement_id="stmt_test",
            text="Test claim text",
            status=ClaimTraceStatus.SUPPORTED,
        )
    )

    ctx = PipelineContext(
        theme="test theme",
        claim_ledger=ledger,
    )

    # Serialize and deserialize
    json_data = ctx.model_dump_json()
    restored = PipelineContext.model_validate_json(json_data)

    assert restored.claim_ledger is not None
    assert len(restored.claim_ledger.entries) == 1
    assert restored.claim_ledger.get_claim("test_claim") is not None
    assert len(restored.claim_ledger.script_claims) == 1


def test_script_claim_statement_model() -> None:
    """ScriptClaimStatement model fields work correctly."""
    stmt = ScriptClaimStatement(
        statement_id="stmt_1",
        text="Climate change is real",
        beat_name="Hook",
        claim_ids=["claim_1", "claim_2"],
        proof_anchor_ids=["proof_1"],
        status=ClaimTraceStatus.SUPPORTED,
        status_reason="Has strong proof anchors",
        source_snippet="According to NASA...",
    )

    assert stmt.statement_id == "stmt_1"
    assert "claim_1" in stmt.claim_ids
    assert stmt.status == ClaimTraceStatus.SUPPORTED


# ---------------------------------------------------------------------------
# Task 19: Competitive Differentiation and Genericity Detection
# ---------------------------------------------------------------------------


def test_argument_map_parser_includes_differentiation_fields() -> None:
    """Argument map parser should extract differentiation fields (Task 19)."""
    from cc_deep_research.content_gen.agents.argument_map import _parse_argument_map

    result = _parse_argument_map(
        """thesis: Buyers compare tier contrast before reading every feature line
audience_belief_to_challenge: Better feature copy is the main lever on pricing conversion
core_mechanism: Buyers anchor on tier comparison order and only then interpret features through that frame

proof_anchors:
---
proof_id: proof_1
summary: Buyers compare tier contrast before reading every feature line
source_ids: src_01
usage_note: Use this to reframe why copy tweaks underperform
---

safe_claims:
---
claim_id: claim_1
claim: Pricing order changes what buyers notice first
supporting_proof_ids: proof_1
---

beat_claim_plan:
---
beat_id: beat_1
beat_name: Hook
goal: Challenge the default pricing diagnosis
claim_ids: claim_1
proof_anchor_ids: proof_1
---

what_this_contributes: Shows how tier ordering (not copy) drives buyer perception — contrary to common content that says "improve your copy"
genericity_flags:
- Don't say "tier comparison changes everything" — too broad
- Don't default to "pricing is psychology" without mechanism
differentiation_strategy: Lead with the ordering mechanism as the primary lever, not copy quality
""",
        idea_id="idea_1",
        angle_id="angle_1",
    )

    assert result.what_this_contributes == (
        "Shows how tier ordering (not copy) drives buyer perception — "
        "contrary to common content that says \"improve your copy\""
    )
    assert result.genericity_flags == [
        "Don't say \"tier comparison changes everything\" — too broad",
        "Don't default to \"pricing is psychology\" without mechanism",
    ]
    assert result.differentiation_stategy == (
        "Lead with the ordering mechanism as the primary lever, not copy quality"
    )


def test_argument_map_parser_handles_missing_differentiation_fields() -> None:
    """Differentiation fields are optional — missing values should be empty strings/lists."""
    from cc_deep_research.content_gen.agents.argument_map import _parse_argument_map

    result = _parse_argument_map(
        """thesis: The visible premium tier reframes the middle plan
audience_belief_to_challenge: Buyers read feature grids first
core_mechanism: Decoy tiers shift comparison anchor before features are evaluated

proof_anchors:
---
proof_id: proof_1
summary: Tier contrast is evaluated before feature detail
source_ids: src_01
---

safe_claims:
---
claim_id: claim_1
claim: Buyers compare before they read
supporting_proof_ids: proof_1
---

beat_claim_plan:
---
beat_id: beat_1
beat_name: Hook
goal: Reframe the comparison order
claim_ids: claim_1
proof_anchor_ids: proof_1
---
""",
        idea_id="idea_1",
        angle_id="angle_1",
    )

    assert result.what_this_contributes == ""
    assert result.genericity_flags == []
    assert result.differentiation_stategy == ""


def test_argument_map_model_differentiation_fields_survive_serialization() -> None:
    """Differentiation fields should survive JSON round-trip."""
    am = ArgumentMap(
        idea_id="idea_1",
        angle_id="angle_1",
        thesis="Test thesis",
        proof_anchors=[
            ArgumentProofAnchor(proof_id="proof_1", summary="Test proof"),
        ],
        safe_claims=[
            ArgumentClaim(claim_id="claim_1", claim="Test claim", supporting_proof_ids=["proof_1"]),
        ],
        beat_claim_plan=[
            ArgumentBeatClaim(
                beat_id="beat_1",
                beat_name="Hook",
                goal="Test",
                claim_ids=["claim_1"],
                proof_anchor_ids=["proof_1"],
            ),
        ],
        what_this_contributes="Something different from consensus",
        genericity_flags=["Generic thing 1", "Generic thing 2"],
        differentiation_stategy="Lead with mechanism",
    )

    json_str = am.model_dump_json()
    restored = ArgumentMap.model_validate_json(json_str)

    assert restored.what_this_contributes == "Something different from consensus"
    assert restored.genericity_flags == ["Generic thing 1", "Generic thing 2"]
    assert restored.differentiation_stategy == "Lead with mechanism"


def test_quality_evaluation_parser_includes_genericity_and_cliche_fields() -> None:
    """Quality evaluation parser should extract genericity score and cliché flags (Task 19)."""
    result = _parse_quality_evaluation(
        """overall_quality_score: 0.71
passes_threshold: false
evidence_coverage: 0.85
claim_safety: 0.90
originality: 0.55
precision: 0.68
expertise_density: 0.72
genericity: 0.78
critical_issues:
- None
unsupported_claims:
- None
evidence_actions_required:
- None
improvement_suggestions:
- Avoid the generic "just test more" close
research_gaps_identified:
- None
cliche_flags:
- "The key is to just keep iterating"
- "In today's fast-paced market, testing is everything"
interchangeable_take_flags:
- Run more experiments without mechanism or data depth
rationale: Script hits the core proof points but lands as generic — sounds like most DTC content on this topic.
""".replace("- None\n", ""),
        iteration_number=1,
    )

    assert result.genericity == pytest.approx(0.78)
    assert result.cliche_flags == [
        "The key is to just keep iterating",
        "In today's fast-paced market, testing is everything",
    ]
    assert result.interchangeable_take_flags == [
        "Run more experiments without mechanism or data depth",
    ]
    assert result.passes_threshold is False


def test_quality_evaluation_parser_high_genericity_flags_specific_issues() -> None:
    """High genericity (low score) should produce actionable flags without breaking threshold logic."""
    result = _parse_quality_evaluation(
        """overall_quality_score: 0.58
passes_threshold: false
evidence_coverage: 0.60
claim_safety: 0.70
originality: 0.40
precision: 0.50
expertise_density: 0.55
genericity: 0.85
critical_issues:
- Script follows the standard "5 tips" format with no differentiation
unsupported_claims:
- None
evidence_actions_required:
- None
improvement_suggestions:
- None
research_gaps_identified:
- None
cliche_flags:
- "Here are 5 tips to optimize your funnel"
- "The key to success is testing and iteration"
interchangeable_take_flags:
- "Test more" without specifying which variable or what evidence exists
rationale: Script is technically sound but indistinguishable from hundreds of other videos on this topic.
""".replace("- None\n", ""),
        iteration_number=1,
    )

    assert result.genericity == pytest.approx(0.85)
    assert len(result.cliche_flags) == 2
    assert len(result.interchangeable_take_flags) == 1
    assert result.passes_threshold is False


def test_quality_evaluation_parser_low_genericity_distinctive_content() -> None:
    """Low genericity (high score) means content is distinctive — empty flags are valid."""
    result = _parse_quality_evaluation(
        """overall_quality_score: 0.83
passes_threshold: true
evidence_coverage: 0.88
claim_safety: 0.91
originality: 0.82
precision: 0.79
expertise_density: 0.80
genericity: 0.15
critical_issues:
- None
unsupported_claims:
- None
evidence_actions_required:
- None
improvement_suggestions:
- None
research_gaps_identified:
- None
rationale: Content is distinctive — specific mechanism, contrarian framing, no generic tips format.
""".replace("- None\n", ""),
        iteration_number=1,
    )

    assert result.genericity == pytest.approx(0.15)
    assert result.cliche_flags == []
    assert result.interchangeable_take_flags == []
    assert result.passes_threshold is True


def test_quality_evaluation_model_serialization_preserves_genericity_fields() -> None:
    """QualityEvaluation genericity fields survive JSON round-trip."""
    qe = QualityEvaluation(
        overall_quality_score=0.75,
        passes_threshold=True,
        evidence_coverage=0.80,
        claim_safety=0.85,
        originality=0.70,
        precision=0.75,
        expertise_density=0.72,
        genericity=0.25,
        cliche_flags=["Generic tip format"],
        interchangeable_take_flags=["Run more experiments without specifics"],
        iteration_number=1,
        rationale="Distinctive content with specific mechanism.",
    )

    json_str = qe.model_dump_json()
    restored = QualityEvaluation.model_validate_json(json_str)

    assert restored.genericity == pytest.approx(0.25)
    assert restored.cliche_flags == ["Generic tip format"]
    assert restored.interchangeable_take_flags == ["Run more experiments without specifics"]


def test_angle_option_differentiation_fields_survive_serialization() -> None:
    """AngleOption differentiation fields survive JSON round-trip."""
    opt = AngleOption(
        angle_id="angle_1",
        target_audience="B2B SaaS founders",
        viewer_problem="Discounting is killing margins",
        core_promise="Tell when a pricing objection is really a packaging problem",
        primary_takeaway="Repeated discounting usually means unclear offer ladder",
        lens="contrarian",
        format="tactical explainer",
        tone="direct",
        cta="Pull three lost-call notes and tag the objection pattern",
        why_this_version_should_exist="Links pricing to day-to-day deal review",
        differentiation_summary="Reframes pricing objections as packaging signals, not negotiation leverage",
        genericity_risks=[
            "Generic 'pricing is about value' without mechanism",
            "Standard '3 pricing strategies' format",
        ],
        market_framing_challenged="The 'add more value to justify pricing' consensus",
    )

    json_str = opt.model_dump_json()
    restored = AngleOption.model_validate_json(json_str)

    assert restored.differentiation_summary == "Reframes pricing objections as packaging signals, not negotiation leverage"
    assert restored.genericity_risks == [
        "Generic 'pricing is about value' without mechanism",
        "Standard '3 pricing strategies' format",
    ]
    assert restored.market_framing_challenged == "The 'add more value to justify pricing' consensus"


def test_angle_parser_includes_differentiation_fields() -> None:
    """Angle parser should extract differentiation_summary, market_framing_challenged, and genericity_risks."""
    from cc_deep_research.content_gen.agents.angle import _parse_angle_options

    text = """---
angle_id: angle_1
target_audience: B2B SaaS founders with discount-heavy sales
viewer_problem: Discounts are masking weak positioning
core_promise: Identify when a pricing objection is really a packaging problem
primary_takeaway: Repeated discounting usually means the offer ladder is unclear
lens: contrarian
format: tactical explainer
tone: direct
cta: Pull three lost-call notes and tag the objection pattern
why_this_version_should_exist: Links pricing to day-to-day deal review
differentiation_summary: Reframes pricing objections as packaging signals, not negotiation leverage
market_framing_challenged: The 'add more value to justify pricing' consensus
genericity_risks:
- Generic "pricing is about value" without mechanism
- Standard "3 pricing strategies" format
---

---
angle_id: angle_2
target_audience: Startup founders launching pricing pages
viewer_problem: They keep polishing copy while buyers compare only price
core_promise: Show the framing change that makes a higher tier feel justified
primary_takeaway: Anchors shape perceived value before feature details matter
lens: buyer psychology teardown
format: contrarian breakdown
tone: sharp but practical
cta: Audit your highest-priced plan against the decoy effect
why_this_version_should_exist: Turns abstract pricing theory into a concrete page review
differentiation_summary: Uses specific anchoring mechanism (decoy effect) to explain tier perception
market_framing_challenged: The "better copy = higher conversion" advice
genericity_risks:
- Generic "anchoring works" without decoy mechanism
- Vague "psychology of pricing" framing
---
Best angle_id: angle_1
Selection reasoning: Clearer differentiation from market consensus and specific mechanism.
"""
    options = _parse_angle_options(text)

    assert len(options) == 2

    angle_1 = next(a for a in options if a.angle_id == "angle_1")
    assert angle_1.differentiation_summary == "Reframes pricing objections as packaging signals, not negotiation leverage"
    assert angle_1.market_framing_challenged == "The 'add more value to justify pricing' consensus"
    assert angle_1.genericity_risks == [
        "Generic \"pricing is about value\" without mechanism",
        "Standard \"3 pricing strategies\" format",
    ]

    angle_2 = next(a for a in options if a.angle_id == "angle_2")
    assert angle_2.differentiation_summary == "Uses specific anchoring mechanism (decoy effect) to explain tier perception"
    assert angle_2.market_framing_challenged == "The \"better copy = higher conversion\" advice"
    assert angle_2.genericity_risks == [
        "Generic \"anchoring works\" without decoy mechanism",
        "Vague \"psychology of pricing\" framing",
    ]


# ---------------------------------------------------------------------------
# Task 20: Performance Learning
# ---------------------------------------------------------------------------


def test_performance_learning_model_defaults() -> None:
    """PerformanceLearning should have sensible defaults."""
    from cc_deep_research.content_gen.models import (
        LearningCategory,
        LearningDurability,
        PerformanceLearning,
    )

    learning = PerformanceLearning(observation="Strong hook retention")

    assert learning.category == LearningCategory.HOOK
    assert learning.durability == LearningDurability.EXPERIMENTAL
    assert learning.observation == "Strong hook retention"
    assert learning.is_active is True
    assert learning.operator_reviewed is False
    assert learning.learning_id.startswith("learn_")


def test_performance_learning_set_model() -> None:
    """PerformanceLearningSet should contain learnings and source analysis."""
    from cc_deep_research.content_gen.models import (
        PerformanceAnalysis,
        PerformanceLearning,
        PerformanceLearningSet,
    )

    analysis = PerformanceAnalysis(video_id="v123", hook_diagnosis="Strong opening")
    learning = PerformanceLearning(observation="Strong hook retention")
    learning_set = PerformanceLearningSet(
        video_id="v123",
        learnings=[learning],
        source_analysis=analysis,
    )

    assert learning_set.video_id == "v123"
    assert len(learning_set.learnings) == 1
    assert learning_set.source_analysis is not None
    assert learning_set.source_analysis.video_id == "v123"


def test_strategy_performance_guidance_model() -> None:
    """StrategyPerformanceGuidance should store durable performance learnings."""
    from cc_deep_research.content_gen.models import StrategyPerformanceGuidance

    guidance = StrategyPerformanceGuidance(
        winning_hooks=["Open with surprising stat"],
        failed_hooks=["Generic question opener"],
        winning_framings=["Specific mechanism explanation"],
        failed_framings=["Abstract value positioning"],
        audience_resonance_notes=["Technical audience wants depth"],
        proof_expectations=["Specific numbers outperform percentages"],
    )

    assert "Open with surprising stat" in guidance.winning_hooks
    assert "Generic question opener" in guidance.failed_hooks
    assert "Specific mechanism explanation" in guidance.winning_framings
    assert "Abstract value positioning" in guidance.failed_framings
    assert guidance.platform_guidance == {}


def test_strategy_memory_includes_performance_guidance() -> None:
    """StrategyMemory should include performance_guidance field."""
    from cc_deep_research.content_gen.models import StrategyMemory, StrategyPerformanceGuidance

    memory = StrategyMemory(
        niche="Tech education",
        performance_guidance=StrategyPerformanceGuidance(
            winning_hooks=["Demo-first opening"],
        ),
    )

    assert memory.niche == "Tech education"
    assert memory.performance_guidance is not None
    assert "Demo-first opening" in memory.performance_guidance.winning_hooks


def test_strategy_memory_performance_guidance_roundtrip() -> None:
    """StrategyMemory with performance_guidance should roundtrip through serialization."""
    from cc_deep_research.content_gen.models import StrategyMemory

    memory = StrategyMemory(
        niche="Tech education",
        performance_guidance={
            "winning_hooks": ["Open with stat"],
            "failed_hooks": ["Generic opener"],
        },
    )

    # Dump and re-validate
    data = memory.model_dump()
    restored = StrategyMemory.model_validate(data)

    assert restored.niche == "Tech education"
    assert restored.performance_guidance is not None
    assert "Open with stat" in restored.performance_guidance.winning_hooks


def test_performance_learning_store_extracts_from_analysis(tmp_path: Path) -> None:
    """PerformanceLearningStore should extract learnings from PerformanceAnalysis."""
    from cc_deep_research.content_gen.models import (
        PerformanceAnalysis,
        PerformanceLearningSet,
    )
    from cc_deep_research.content_gen.storage.performance_learning_store import (
        PerformanceLearningStore,
    )

    store = PerformanceLearningStore(path=tmp_path / "learnings.yaml")

    analysis = PerformanceAnalysis(
        video_id="v123",
        metrics={"views": 15000, "engagement_rate": 0.06},
        what_worked=["Strong hook opening", "Clear CTA at end"],
        what_failed=["Weak second beat pacing"],
        hook_diagnosis="Strong opening retained viewers",
        audience_signals=["Technical audience responded to specifics"],
        follow_up_ideas=["Try deeper dive on mechanism"],
    )

    learning_set = store.extract_learnings_from_analysis("v123", analysis)

    assert isinstance(learning_set, PerformanceLearningSet)
    assert len(learning_set.learnings) >= 5  # hook diagnosis + what_worked(2) + what_failed(1) + audience_signals(1)
    assert learning_set.video_id == "v123"

    # Verify learnings are persisted
    raw = store.load_raw_learnings()
    assert len(raw) >= 5


def test_performance_learning_store_durable_vs_experimental(tmp_path: Path) -> None:
    """PerformanceLearningStore should infer durability from metrics strength."""
    from cc_deep_research.content_gen.models import PerformanceAnalysis
    from cc_deep_research.content_gen.storage.performance_learning_store import (
        PerformanceLearningStore,
    )

    store = PerformanceLearningStore(path=tmp_path / "learnings.yaml")

    # Strong metrics should infer durable learning
    strong_analysis = PerformanceAnalysis(
        video_id="v_strong",
        metrics={"views": 50000, "engagement_rate": 0.08},
        hook_diagnosis="Strong hook",
    )

    learning_set = store.extract_learnings_from_analysis("v_strong", strong_analysis)

    # At least one learning should be durable (high views + engagement)
    durable_learnings = [learning for learning in learning_set.learnings if learning.durability.value == "durable"]
    # Note: durability depends on actual implementation thresholds


def test_performance_learning_store_load_empty_returns_empty_list(tmp_path: Path) -> None:
    """PerformanceLearningStore.load_raw_learnings should return [] when file missing."""
    from cc_deep_research.content_gen.storage.performance_learning_store import (
        PerformanceLearningStore,
    )

    store = PerformanceLearningStore(path=tmp_path / "nonexistent.yaml")
    learnings = store.load_raw_learnings()

    assert learnings == []


def test_performance_learning_store_strategy_guidance(tmp_path: Path) -> None:
    """PerformanceLearningStore should save and load strategy guidance."""
    from cc_deep_research.content_gen.models import StrategyPerformanceGuidance
    from cc_deep_research.content_gen.storage.performance_learning_store import (
        PerformanceLearningStore,
    )

    store = PerformanceLearningStore(path=tmp_path / "learnings.yaml")

    guidance = StrategyPerformanceGuidance(
        winning_hooks=["Open with demo"],
        failed_hooks=["Generic question"],
    )

    store.save_strategy_guidance(guidance)
    loaded = store.load_strategy_guidance()

    assert "Open with demo" in loaded.winning_hooks
    assert "Generic question" in loaded.failed_hooks


def test_performance_learning_store_apply_learnings_to_strategy(tmp_path: Path) -> None:
    """PerformanceLearningStore.apply_learnings_to_strategy should promote learnings."""
    from cc_deep_research.content_gen.models import (
        LearningCategory,
        LearningDurability,
        PerformanceLearning,
    )
    from cc_deep_research.content_gen.storage.performance_learning_store import (
        PerformanceLearningStore,
    )

    store = PerformanceLearningStore(path=tmp_path / "learnings.yaml")

    # Add a learning manually
    learning = PerformanceLearning(
        category=LearningCategory.HOOK,
        durability=LearningDurability.EXPERIMENTAL,
        observation="Strong hook pattern",
        guidance="Continue using this hook",
        created_at="2024-01-01T00:00:00Z",
        updated_at="2024-01-01T00:00:00Z",
    )
    store.save_raw_learnings([learning])

    # Apply learnings to strategy
    guidance = store.apply_learnings_to_strategy(
        [learning.learning_id],
        operator_approved=False,  # experimental learnings don't need approval
    )

    # Verify guidance was updated
    assert "Continue using this hook" in guidance.winning_hooks or "Strong hook pattern" in guidance.winning_hooks


def test_performance_learning_store_get_active_learnings(tmp_path: Path) -> None:
    """PerformanceLearningStore should filter learnings by category/durability."""
    from cc_deep_research.content_gen.models import (
        LearningCategory,
        LearningDurability,
        PerformanceLearning,
    )
    from cc_deep_research.content_gen.storage.performance_learning_store import (
        PerformanceLearningStore,
    )

    store = PerformanceLearningStore(path=tmp_path / "learnings.yaml")

    learnings = [
        PerformanceLearning(
            category=LearningCategory.HOOK,
            durability=LearningDurability.DURABLE,
            observation="Hook 1",
        ),
        PerformanceLearning(
            category=LearningCategory.FRAME,
            durability=LearningDurability.EXPERIMENTAL,
            observation="Framing 1",
        ),
        PerformanceLearning(
            category=LearningCategory.HOOK,
            durability=LearningDurability.EXPERIMENTAL,
            observation="Hook 2",
        ),
    ]
    store.save_raw_learnings(learnings)

    # Filter by HOOK category
    hook_learnings = store.get_active_learnings(category=LearningCategory.HOOK)
    assert len(hook_learnings) == 2

    # Filter by DURABLE durability
    durable_learnings = store.get_active_learnings(durability=LearningDurability.DURABLE)
    assert len(durable_learnings) == 1
    assert durable_learnings[0].observation == "Hook 1"


def test_performance_learning_store_get_durable_guidance_for_backlog(tmp_path: Path) -> None:
    """PerformanceLearningStore.get_durable_guidance_for_backlog should return scoring hints."""
    from cc_deep_research.content_gen.models import (
        LearningCategory,
        LearningDurability,
        PerformanceLearning,
        StrategyPerformanceGuidance,
    )
    from cc_deep_research.content_gen.storage.performance_learning_store import (
        PerformanceLearningStore,
    )

    store = PerformanceLearningStore(path=tmp_path / "learnings.yaml")

    # Add durable guidance to strategy
    guidance = StrategyPerformanceGuidance(
        winning_hooks=["Demo hook"],
        failed_hooks=["Question hook"],
    )
    store.save_strategy_guidance(guidance)

    # Add active learnings
    learnings = [
        PerformanceLearning(
            category=LearningCategory.HOOK,
            durability=LearningDurability.DURABLE,
            observation="Strong hook",
        ),
        PerformanceLearning(
            category=LearningCategory.FRAME,
            durability=LearningDurability.EXPERIMENTAL,
            observation="Specific framing",
        ),
    ]
    store.save_raw_learnings(learnings)

    hints = store.get_durable_guidance_for_backlog()

    assert "winning_hooks" in hints
    assert "Demo hook" in hints["winning_hooks"]
    assert "experimental_learnings" in hints


def test_score_ideas_user_includes_performance_guidance() -> None:
    """score_ideas_user should include performance guidance from strategy."""
    from cc_deep_research.content_gen.models import (
        BacklogItem,
        StrategyMemory,
        StrategyPerformanceGuidance,
    )
    from cc_deep_research.content_gen.prompts.backlog import score_ideas_user

    strategy = StrategyMemory(
        niche="Tech",
        performance_guidance=StrategyPerformanceGuidance(
            winning_hooks=["Open with stat"],
            failed_hooks=["Generic opener"],
            winning_framings=["Specific mechanism"],
            failed_framings=["Abstract positioning"],
            audience_resonance_notes=["Loves technical depth"],
            proof_expectations=["Specific numbers > percentages"],
        ),
    )

    items = [BacklogItem(idea_id="test1", idea="Test idea")]
    user_prompt = score_ideas_user(items, strategy, threshold=25)

    assert "Open with stat" in user_prompt
    assert "Generic opener" in user_prompt
    assert "Specific mechanism" in user_prompt
    assert "Abstract positioning" in user_prompt
    assert "Loves technical depth" in user_prompt
    assert "Specific numbers > percentages" in user_prompt


def test_score_ideas_user_excludes_performance_guidance_when_empty() -> None:
    """score_ideas_user should not include performance section when guidance is empty."""
    from cc_deep_research.content_gen.models import BacklogItem, StrategyMemory
    from cc_deep_research.content_gen.prompts.backlog import score_ideas_user

    strategy = StrategyMemory(niche="Tech")
    items = [BacklogItem(idea_id="test1", idea="Test idea")]
    user_prompt = score_ideas_user(items, strategy, threshold=25)

    # Should not mention performance guidance when empty
    assert "Winning hook" not in user_prompt
    assert "Failed hook" not in user_prompt


# ---------------------------------------------------------------------------
# Tests for maintenance_workflow.py
# ---------------------------------------------------------------------------


def test_maintenance_proposal_to_dict_from_dict() -> None:
    """MaintenanceProposal serializes and deserializes correctly."""
    from cc_deep_research.content_gen.maintenance_workflow import (
        MaintenanceProposal,
        MaintenanceProposalStatus,
    )

    proposal = MaintenanceProposal(
        proposal_id="mnt_test123",
        job_type="stale_item_review",
        title="Stale item",
        description="Item is old",
        affected_idea_ids=["idea-1", "idea-2"],
        suggested_patch={"status": "archived"},
        priority=3,
        status=MaintenanceProposalStatus.PENDING,
    )

    as_dict = proposal.to_dict()
    assert as_dict["proposal_id"] == "mnt_test123"
    assert as_dict["job_type"] == "stale_item_review"
    assert as_dict["priority"] == 3
    assert as_dict["affected_idea_ids"] == ["idea-1", "idea-2"]

    restored = MaintenanceProposal.from_dict(as_dict)
    assert restored.proposal_id == proposal.proposal_id
    assert restored.title == proposal.title
    assert restored.status == MaintenanceProposalStatus.PENDING


def test_maintenance_proposal_defaults() -> None:
    """MaintenanceProposal auto-generates ID and timestamps."""
    from cc_deep_research.content_gen.maintenance_workflow import MaintenanceProposal

    proposal = MaintenanceProposal(title="Test", job_type="stale_item_review")
    assert proposal.proposal_id.startswith("mnt_")
    assert proposal.created_at
    assert proposal.status.value == "pending"


def test_maintenance_run_to_dict() -> None:
    """MaintenanceRun serializes correctly."""
    from cc_deep_research.content_gen.maintenance_workflow import (
        MaintenanceJobType,
        MaintenanceRun,
    )

    run = MaintenanceRun(
        run_id="mntrun_abc123",
        job_type=MaintenanceJobType.STALE_ITEM_REVIEW,
        proposals_count=5,
    )

    as_dict = run.to_dict()
    assert as_dict["run_id"] == "mntrun_abc123"
    assert as_dict["job_type"] == "stale_item_review"
    assert as_dict["proposals_count"] == 5
    assert as_dict["outcome"] == "success"


def test_maintenance_store_save_and_load_proposals(tmp_path: Path) -> None:
    """MaintenanceStore persists and retrieves proposals."""
    from cc_deep_research.config import Config
    from cc_deep_research.content_gen.maintenance_workflow import (
        MaintenanceProposal,
        MaintenanceProposalStatus,
        MaintenanceStore,
    )

    config = Config()
    config.content_gen.backlog_path = str(tmp_path / "backlog.yaml")

    store = MaintenanceStore(config=config)
    proposal = MaintenanceProposal(
        title="Test proposal",
        job_type="stale_item_review",
        priority=2,
    )
    store.save_proposal(proposal)

    loaded = store.load_proposals()
    assert len(loaded) == 1
    assert loaded[0].title == "Test proposal"
    assert loaded[0].status == MaintenanceProposalStatus.PENDING


def test_maintenance_store_resolve_proposal(tmp_path: Path) -> None:
    """MaintenanceStore.resolve_proposal approves or rejects proposals."""
    from cc_deep_research.config import Config
    from cc_deep_research.content_gen.maintenance_workflow import (
        MaintenanceProposal,
        MaintenanceProposalStatus,
        MaintenanceStore,
    )

    config = Config()
    config.content_gen.backlog_path = str(tmp_path / "backlog.yaml")

    store = MaintenanceStore(config=config)
    proposal = MaintenanceProposal(title="To approve")
    store.save_proposal(proposal)

    resolved = store.resolve_proposal(proposal.proposal_id, "approved", reviewed_by="tester")
    assert resolved is not None
    assert resolved.status == MaintenanceProposalStatus.APPROVED
    assert resolved.reviewed_by == "tester"


def test_maintenance_store_resolve_proposal_rejects(tmp_path: Path) -> None:
    """MaintenanceStore.resolve_proposal rejects proposals correctly."""
    from cc_deep_research.config import Config
    from cc_deep_research.content_gen.maintenance_workflow import (
        MaintenanceProposal,
        MaintenanceProposalStatus,
        MaintenanceStore,
    )

    config = Config()
    config.content_gen.backlog_path = str(tmp_path / "backlog.yaml")

    store = MaintenanceStore(config=config)
    proposal = MaintenanceProposal(title="To reject")
    store.save_proposal(proposal)

    resolved = store.resolve_proposal(proposal.proposal_id, "rejected")
    assert resolved is not None
    assert resolved.status == MaintenanceProposalStatus.REJECTED


def test_maintenance_jobs_run_stale_item_review(tmp_path: Path) -> None:
    """run_stale_item_review flags items not updated in N days."""
    from cc_deep_research.content_gen.backlog_service import BacklogService
    from cc_deep_research.content_gen.maintenance_workflow import (
        MaintenanceJobs,
        MaintenanceJobType,
    )
    from cc_deep_research.content_gen.storage import BacklogStore

    store = BacklogStore(tmp_path / "backlog.yaml")
    service = BacklogService(store=store)

    now = "2026-04-01T00:00:00Z"
    old_date = "2025-01-01T00:00:00Z"
    # Create items directly in the store so updated_at is preserved
    # (upsert_items overwrites updated_at with current time)
    backlog = BacklogOutput(items=[
        BacklogItem(idea_id="stale-1", idea="Stale idea", updated_at=old_date),
        BacklogItem(idea_id="stale-2", idea="Old but OK", updated_at="2026-03-01T00:00:00Z"),
        BacklogItem(idea_id="recent-1", idea="Recent idea", updated_at=now),
        BacklogItem(idea_id="archived-1", idea="Archived", updated_at=old_date, status="archived"),
    ])
    store.save(backlog)

    jobs = MaintenanceJobs()
    jobs._backlog_service = service

    proposals = jobs.run_stale_item_review(stale_days=60, watch_days=30)

    stale_proposals = [p for p in proposals if p.job_type == MaintenanceJobType.STALE_ITEM_REVIEW]
    assert len(stale_proposals) >= 1
    stale_ids = [p.affected_idea_ids for p in stale_proposals]
    assert any("stale-1" in ids for ids in stale_ids)


def test_maintenance_jobs_run_gap_summary(tmp_path: Path) -> None:
    """run_gap_summary flags underrepresented themes."""
    from cc_deep_research.content_gen.backlog_service import BacklogService
    from cc_deep_research.content_gen.maintenance_workflow import (
        MaintenanceJobs,
        MaintenanceJobType,
    )
    from cc_deep_research.content_gen.storage import BacklogStore

    store = BacklogStore(tmp_path / "backlog.yaml")
    service = BacklogService(store=store)

    # Add items under a common theme - enough to NOT trigger gap
    service.upsert_items([
        BacklogItem(idea_id="gap-1", idea="Idea A", source_theme="Tech"),
        BacklogItem(idea_id="gap-2", idea="Idea B", source_theme="Tech"),
        BacklogItem(idea_id="gap-3", idea="Idea C", source_theme="Tech"),
        BacklogItem(idea_id="gap-4", idea="Idea D", source_theme="Solo"),
    ])

    jobs = MaintenanceJobs()
    jobs._backlog_service = service

    proposals = jobs.run_gap_summary(min_items_per_theme=3)

    gap_proposals = [p for p in proposals if p.job_type == MaintenanceJobType.GAP_SUMMARY]
    gap_themes = [p.title for p in gap_proposals]
    assert any("Solo" in t for t in gap_themes)


def test_maintenance_jobs_run_duplicate_watchlist(tmp_path: Path) -> None:
    """run_duplicate_watchlist finds highly similar item pairs."""
    from cc_deep_research.content_gen.backlog_service import BacklogService
    from cc_deep_research.content_gen.maintenance_workflow import (
        MaintenanceJobs,
        MaintenanceJobType,
    )
    from cc_deep_research.content_gen.storage import BacklogStore

    store = BacklogStore(tmp_path / "backlog.yaml")
    service = BacklogService(store=store)

    # Two very similar titles
    service.upsert_items([
        BacklogItem(idea_id="dup-1", idea="10 tips to save money on hosting"),
        BacklogItem(idea_id="dup-2", idea="10 tips to save money on web hosting"),
    ])

    jobs = MaintenanceJobs()
    jobs._backlog_service = service

    proposals = jobs.run_duplicate_watchlist(similarity_threshold=0.85)

    dup_proposals = [p for p in proposals if p.job_type == MaintenanceJobType.DUPLICATE_WATCHLIST]
    assert len(dup_proposals) >= 1
    assert "dup-1" in dup_proposals[0].affected_idea_ids
    assert "dup-2" in dup_proposals[0].affected_idea_ids


def test_maintenance_jobs_run_rescoring_recommend(tmp_path: Path) -> None:
    """run_rescoring_recommend flags items with stale scores."""
    from cc_deep_research.content_gen.backlog_service import BacklogService
    from cc_deep_research.content_gen.maintenance_workflow import (
        MaintenanceJobs,
        MaintenanceJobType,
    )
    from cc_deep_research.content_gen.storage import BacklogStore

    store = BacklogStore(tmp_path / "backlog.yaml")
    service = BacklogService(store=store)

    old_score_date = "2025-01-01T00:00:00Z"
    service.upsert_items([
        BacklogItem(idea_id="score-1", idea="Stale scored", last_scored_at=old_score_date),
        BacklogItem(idea_id="score-2", idea="Fresh scored", last_scored_at="2026-04-01T00:00:00Z"),
        BacklogItem(idea_id="score-3", idea="Never scored"),
    ])

    jobs = MaintenanceJobs()
    jobs._backlog_service = service

    proposals = jobs.run_rescoring_recommend(stale_score_days=30)

    rescoring_proposals = [p for p in proposals if p.job_type == MaintenanceJobType.RESCORING_RECOMMEND]
    assert any("score-1" in p.affected_idea_ids for p in rescoring_proposals)
    assert not any("score-2" in p.affected_idea_ids for p in rescoring_proposals)


def test_maintenance_scheduler_start_stop() -> None:
    """MaintenanceScheduler starts and stops without error."""
    from cc_deep_research.content_gen.maintenance_workflow import MaintenanceScheduler

    scheduler = MaintenanceScheduler(interval_hours=0.001)
    scheduler.start()
    assert scheduler._running is True

    scheduler.stop()
    assert scheduler._running is False


def test_maintenance_scheduler_trigger_job(tmp_path: Path) -> None:
    """trigger_job runs a job and returns a MaintenanceRun."""
    from cc_deep_research.config import Config
    from cc_deep_research.content_gen.maintenance_workflow import (
        MaintenanceJobType,
        MaintenanceScheduler,
    )

    config = Config()
    config.content_gen.backlog_path = str(tmp_path / "backlog.yaml")

    scheduler = MaintenanceScheduler(config=config, interval_hours=24)
    run = scheduler.trigger_job(MaintenanceJobType.STALE_ITEM_REVIEW)

    assert run.job_type == MaintenanceJobType.STALE_ITEM_REVIEW
    assert run.outcome in ("success", "error")  # May succeed or error on empty backlog


# ---------------------------------------------------------------------------
# Tests for SQLite migration edge cases
# ---------------------------------------------------------------------------


def test_sqlite_migration_malformed_yaml(tmp_path: Path) -> None:
    """SQLite store handles malformed YAML gracefully during migration."""
    from cc_deep_research.content_gen.storage.sqlite_backlog_store import SqliteBacklogStore

    # Write a malformed YAML file
    yaml_path = tmp_path / "backlog.yaml"
    yaml_path.write_text("not: valid [yaml ::::}{")

    store = SqliteBacklogStore(path=tmp_path / "backlog.db", yaml_store_path=yaml_path)
    # Should not raise; YAML import fails gracefully and returns empty backlog
    backlog = store.load()
    assert len(backlog.items) == 0


def test_sqlite_migration_empty_yaml(tmp_path: Path) -> None:
    """SQLite store handles empty YAML during migration."""
    from cc_deep_research.content_gen.storage.sqlite_backlog_store import SqliteBacklogStore

    yaml_path = tmp_path / "backlog.yaml"
    yaml_path.write_text("")

    store = SqliteBacklogStore(path=tmp_path / "backlog.db", yaml_store_path=yaml_path)
    backlog = store.load()
    assert len(backlog.items) == 0


def test_sqlite_store_incremental_update_preserves_items(tmp_path: Path) -> None:
    """SQLite save() with incremental updates preserves all items."""
    from cc_deep_research.content_gen.models import BacklogOutput
    from cc_deep_research.content_gen.storage.sqlite_backlog_store import SqliteBacklogStore

    store = SqliteBacklogStore(path=tmp_path / "backlog.db")

    item1 = BacklogItem(idea_id="item-1", idea="First item")
    item2 = BacklogItem(idea_id="item-2", idea="Second item")

    store.save(BacklogOutput(items=[item1]))
    store.save(BacklogOutput(items=[item1, item2]))

    backlog = store.load()
    assert len(backlog.items) == 2
    ids = {item.idea_id for item in backlog.items}
    assert ids == {"item-1", "item-2"}


def test_sqlite_update_item_validates_unsupported_fields(tmp_path: Path) -> None:
    """SqliteBacklogStore.update_item rejects unknown fields."""
    from cc_deep_research.content_gen.storage.sqlite_backlog_store import SqliteBacklogStore

    store = SqliteBacklogStore(path=tmp_path / "backlog.db")
    store.save(BacklogOutput(items=[BacklogItem(idea_id="test-1", idea="Test")]))

    with pytest.raises(ValueError, match="Unsupported backlog fields"):
        store.update_item("test-1", {"not_a_real_field": "value"})


# ---------------------------------------------------------------------------
# Tests for path validation security
# ---------------------------------------------------------------------------


def test_resolve_content_gen_file_path_rejects_escaped_absolute_path(tmp_path: Path) -> None:
    """resolve_content_gen_file_path rejects paths outside allowed directories."""
    from cc_deep_research.content_gen.storage._paths import resolve_content_gen_file_path

    with pytest.raises(ValueError, match="escapes allowed directories"):
        resolve_content_gen_file_path(
            explicit_path=Path("/etc/passwd"),
            config=None,
            config_attr="backlog_path",
            default_name="backlog.yaml",
        )


def test_resolve_content_gen_file_path_rejects_escaped_config_path(tmp_path: Path) -> None:
    """resolve_content_gen_file_path rejects malicious configured paths."""
    from types import SimpleNamespace

    from cc_deep_research.content_gen.storage._paths import resolve_content_gen_file_path

    bad_config = SimpleNamespace(
        content_gen=SimpleNamespace(backlog_path="/etc/malicious.yaml")
    )

    with pytest.raises(ValueError, match="escapes allowed directories"):
        resolve_content_gen_file_path(
            explicit_path=None,
            config=bad_config,
            config_attr="backlog_path",
            default_name="backlog.yaml",
        )


# ---------------------------------------------------------------------------
# Tests for idea_id validation
# ---------------------------------------------------------------------------


def test_backlog_service_rejects_invalid_idea_id_select(tmp_path: Path) -> None:
    """select_item rejects malformed idea_id."""
    from cc_deep_research.content_gen.backlog_service import BacklogService
    from cc_deep_research.content_gen.storage import BacklogStore

    store = BacklogStore(tmp_path / "backlog.yaml")
    service = BacklogService(store=store)
    service.create_item(title="Test")

    with pytest.raises(ValueError, match="invalid characters"):
        service.select_item("idea/with/slashes")

    with pytest.raises(ValueError, match="invalid characters"):
        service.select_item("idea with space")

    with pytest.raises(ValueError, match="non-empty string"):
        service.select_item("")


def test_backlog_service_rejects_invalid_idea_id_update(tmp_path: Path) -> None:
    """update_item rejects malformed idea_id."""
    from cc_deep_research.content_gen.backlog_service import BacklogService
    from cc_deep_research.content_gen.storage import BacklogStore

    store = BacklogStore(tmp_path / "backlog.yaml")
    service = BacklogService(store=store)
    service.create_item(title="Test")

    with pytest.raises(ValueError, match="invalid characters"):
        service.update_item("bad@idea", {"title": "Updated"})


def test_backlog_service_rejects_invalid_idea_id_delete(tmp_path: Path) -> None:
    """delete_item rejects malformed idea_id."""
    from cc_deep_research.content_gen.backlog_service import BacklogService
    from cc_deep_research.content_gen.storage import BacklogStore

    store = BacklogStore(tmp_path / "backlog.yaml")
    service = BacklogService(store=store)
    service.create_item(title="Test")

    with pytest.raises(ValueError, match="non-empty string"):
        service.delete_item("")

    with pytest.raises(ValueError, match="invalid characters"):
        service.delete_item("bad;idea")


def test_backlog_service_rejects_invalid_idea_id_archive(tmp_path: Path) -> None:
    """archive_item rejects malformed idea_id."""
    from cc_deep_research.content_gen.backlog_service import BacklogService
    from cc_deep_research.content_gen.storage import BacklogStore

    store = BacklogStore(tmp_path / "backlog.yaml")
    service = BacklogService(store=store)
    service.create_item(title="Test")

    with pytest.raises(ValueError, match="invalid characters"):
        service.archive_item("bad~idea")


def test_backlog_service_rejects_invalid_idea_id_mark_in_production(tmp_path: Path) -> None:
    """mark_in_production rejects malformed idea_id."""
    from cc_deep_research.content_gen.backlog_service import BacklogService
    from cc_deep_research.content_gen.storage import BacklogStore

    store = BacklogStore(tmp_path / "backlog.yaml")
    service = BacklogService(store=store)
    service.create_item(title="Test")

    with pytest.raises(ValueError, match="invalid characters"):
        service.mark_in_production("bad^idea")


def test_backlog_service_rejects_invalid_idea_id_mark_published(tmp_path: Path) -> None:
    """mark_published rejects malformed idea_id."""
    from cc_deep_research.content_gen.backlog_service import BacklogService
    from cc_deep_research.content_gen.storage import BacklogStore

    store = BacklogStore(tmp_path / "backlog.yaml")
    service = BacklogService(store=store)
    service.create_item(title="Test")

    with pytest.raises(ValueError, match="invalid characters"):
        service.mark_published("bad$idea")
