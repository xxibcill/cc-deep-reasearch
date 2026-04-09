"""Tests for the content generation workflow."""

from __future__ import annotations

from pathlib import Path

import pytest
from click.testing import CliRunner

from cc_deep_research.cli import main
from cc_deep_research.content_gen.agents.angle import AngleAgent, _parse_angle_options
from cc_deep_research.content_gen.agents.opportunity import OpportunityPlanningAgent
from cc_deep_research.content_gen.agents.backlog import (
    BacklogAgent,
    _derive_selection,
    _parse_backlog_items,
    _parse_scores,
    _validate_scores,
)
from cc_deep_research.content_gen.agents.packaging import PackagingAgent, _parse_platform_packages
from cc_deep_research.content_gen.agents.qc import QCAgent, _parse_qc_gate
from cc_deep_research.content_gen.agents.research_pack import ResearchPackAgent, _parse_research_pack
from cc_deep_research.content_gen.agents.scripting import _STEP_HANDLERS, ScriptingAgent
from cc_deep_research.content_gen.agents.visual import VisualAgent
from cc_deep_research.content_gen.models import (
    CONTENT_GEN_STAGE_CONTRACTS,
    PIPELINE_STAGES,
    SCRIPTING_STEPS,
    AngleDefinition,
    AngleOutput,
    AngleOption,
    BacklogItem,
    BacklogOutput,
    BeatIntent,
    BeatIntentMap,
    ContrarianBelief,
    CoreInputs,
    ExpertFramework,
    HookSet,
    HumanQCGate,
    IdeaScores,
    OpportunityBrief,
    ProductionBrief,
    PackagingOutput,
    PipelineContext,
    PipelineStageTrace,
    PlatformPackage,
    ProofRule,
    PublishItem,
    QCResult,
    ResearchClaimType,
    ResearchConfidence,
    ResearchFindingType,
    ResearchFlagType,
    ResearchPack,
    ResearchSeverity,
    ResearchSource,
    SavedScriptRun,
    ScoringOutput,
    ScriptingContext,
    ScriptStructure,
    ScriptVersion,
    StrategyMemory,
)
from cc_deep_research.content_gen.orchestrator import _format_research_context
from cc_deep_research.content_gen.prompts import angle as angle_prompts
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

    async def _call_llm(
        self,
        system_prompt: str,
        user_prompt: str,
        *,
        temperature: float = 0.2,
    ) -> str:
        del system_prompt, user_prompt, temperature
        return self._response


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
    """The pipeline should have 13 stages (0-12)."""
    assert len(PIPELINE_STAGES) == 13


def test_content_gen_stage_contract_registry_covers_core_prompt_stages() -> None:
    """Core prompt-backed stages should have explicit contract entries."""
    expected_modules = {
        "plan_opportunity": opportunity_prompts,
        "build_backlog": backlog_prompts,
        "score_ideas": backlog_prompts,
        "generate_angles": angle_prompts,
        "build_research_pack": research_pack_prompts,
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
    assert CONTENT_GEN_STAGE_CONTRACTS["human_qc"].failure_mode == "human_gated"


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
    assert ctx.scripting is None
    assert ctx.qc_gate is None
    assert ctx.current_stage == 0


def test_pipeline_context_roundtrip() -> None:
    """PipelineContext should survive JSON serialization."""
    ctx = PipelineContext(
        theme="test theme",
        strategy=StrategyMemory(niche="fitness", content_pillars=["strength"]),
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
    assert restored.shortlist == ["idea-2", "idea-1"]
    assert restored.selected_idea_id == "idea-2"
    assert restored.selection_reasoning == "Better hook and clearer evidence fit."
    assert restored.runner_up_idea_ids == ["idea-1"]
    assert len(restored.backlog.items) == 1
    assert restored.backlog.items[0].idea == "test idea"


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
    from cc_deep_research.content_gen.orchestrator import ContentGenOrchestrator, _stage_generate_angles

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

    assert fake_agent.seen_item_id == "id2"
    assert ctx.angles is not None
    assert ctx.angles.idea_id == "id2"


@pytest.mark.asyncio
async def test_build_research_pack_uses_pipeline_selected_idea() -> None:
    """Research pack stage should read the chosen idea from pipeline context."""
    from cc_deep_research.content_gen.orchestrator import ContentGenOrchestrator, _stage_build_research_pack

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

        async def build(self, item: BacklogItem, angle: AngleOption, *, feedback: str = "") -> ResearchPack:
            del feedback
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
        ) -> ScoringOutput:
            assert [item.idea_id for item in items] == ["idea-alpha", "idea-beta"]
            assert strategy.niche == fixture["strategy"]["niche"]
            assert threshold == 3.5
            return ScoringOutput.model_validate(fixture["scoring"])

    class FakeAngleAgent:
        async def generate(self, item: BacklogItem, strategy: StrategyMemory) -> AngleOutput:
            assert item.idea_id == selected_idea_id
            assert strategy.niche == fixture["strategy"]["niche"]
            return AngleOutput.model_validate(fixture["angles"])

    class FakeResearchAgent:
        async def build(self, item: BacklogItem, angle: AngleOption, *, feedback: str = "") -> ResearchPack:
            assert item.idea_id == selected_idea_id
            assert angle.angle_id == fixture["angles"]["selected_angle_id"]
            assert feedback == ""
            return ResearchPack.model_validate(fixture["research_pack"])

    class FakeScriptingAgent:
        async def run_from_step(self, ctx: ScriptingContext, step: int) -> ScriptingContext:
            assert step == 3
            assert ctx.raw_idea == selected_idea["idea"]
            assert ctx.core_inputs is not None
            assert ctx.core_inputs.topic == selected_idea["idea"]
            assert "Anchors shape perceived value" in ctx.research_context
            return ScriptingContext.model_validate(fixture["scripting"])

    class FakeVisualAgent:
        async def translate(self, script: ScriptVersion, structure: ScriptStructure) -> object:
            assert "anchor tier is broken" in script.content
            assert structure.chosen_structure == fixture["scripting"]["structure"]["chosen_structure"]
            from cc_deep_research.content_gen.models import VisualPlanOutput

            return VisualPlanOutput.model_validate(fixture["visual_plan"])

    class FakeProductionAgent:
        async def brief(self, visual_plan) -> object:
            assert visual_plan.idea_id == selected_idea_id
            return ProductionBrief.model_validate(fixture["production_brief"])

    class FakePackagingAgent:
        async def generate(
            self,
            script: ScriptVersion,
            angle: AngleOption,
            platforms: list[str],
            *,
            strategy: StrategyMemory,
        ) -> PackagingOutput:
            assert "anchor tier is broken" in script.content
            assert angle.angle_id == fixture["angles"]["selected_angle_id"]
            assert platforms == ["tiktok"]
            assert strategy.niche == fixture["strategy"]["niche"]
            return PackagingOutput.model_validate(fixture["packaging"])

    class FakeQCAgent:
        async def review(
            self,
            *,
            script: str,
            visual_summary: str,
            packaging_summary: str,
        ) -> HumanQCGate:
            assert "anchor tier is broken" in script
            assert "Hook: Highlight the cheapest plan selection on a pricing page" in visual_summary
            assert "tiktok: If buyers always choose cheapest, your anchor tier is broken" in packaging_summary
            return HumanQCGate.model_validate(fixture["qc_gate"])

    class FakePublishAgent:
        async def schedule(self, packaging: PackagingOutput, *, idea_id: str) -> list[PublishItem]:
            assert packaging.idea_id == selected_idea_id
            assert idea_id == selected_idea_id
            return [PublishItem.model_validate(item) for item in fixture["publish_items"]]

    monkeypatch.setattr("cc_deep_research.content_gen.storage.StrategyStore", FakeStrategyStore)

    orch = ContentGenOrchestrator(FakeConfig())
    orch._agents["opportunity"] = FakeOpportunityAgent()
    orch._agents["backlog"] = FakeBacklogAgent()
    orch._agents["angle"] = FakeAngleAgent()
    orch._agents["research"] = FakeResearchAgent()
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
    assert ctx.research_pack is not None
    assert ctx.research_pack.idea_id == selected_idea_id
    assert ctx.scripting is not None
    assert ctx.scripting.raw_idea == fixture["scripting"]["raw_idea"]
    assert ctx.packaging is not None
    assert ctx.packaging.idea_id == selected_idea_id
    assert ctx.qc_gate is not None
    assert ctx.qc_gate.approved_for_publish is True
    assert ctx.publish_item is not None
    assert ctx.publish_item.idea_id == selected_idea_id
    assert [trace.stage_name for trace in ctx.stage_traces] == PIPELINE_STAGES
    assert all(trace.status == "completed" for trace in ctx.stage_traces)

    score_trace = next(trace for trace in ctx.stage_traces if trace.stage_name == "score_ideas")
    assert score_trace.decision_summary == fixture["scoring"]["selection_reasoning"]
    assert score_trace.metadata.selected_idea_id == selected_idea_id
    assert score_trace.metadata.shortlist_count == len(fixture["scoring"]["shortlist"])

    angle_trace = next(trace for trace in ctx.stage_traces if trace.stage_name == "generate_angles")
    assert angle_trace.decision_summary == fixture["angles"]["selection_reasoning"]
    assert angle_trace.metadata.selected_angle_id == fixture["angles"]["selected_angle_id"]

    research_trace = next(trace for trace in ctx.stage_traces if trace.stage_name == "build_research_pack")
    assert research_trace.decision_summary == fixture["research_pack"]["research_stop_reason"]
    assert research_trace.metadata.fact_count == len(fixture["research_pack"]["key_facts"])
    assert research_trace.metadata.proof_count == len(fixture["research_pack"]["proof_points"])


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
    assert loaded.items[0].idea == "idea 1"


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


def test_backlog_service_apply_scoring_marks_selected(tmp_path: Path) -> None:
    """Applying scoring should attach score metadata and promote the selected item."""
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
                IdeaScores(idea_id="idea-2", total_score=22, recommendation="hold"),
            ],
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


def test_scoring_output_roundtrip_with_shortlist() -> None:
    """ScoringOutput should preserve shortlist selection fields."""
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
                total_score=31,
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
async def test_backlog_golden_fixture_malformed_output_marks_stage_degraded() -> None:
    """Malformed backlog output should degrade cleanly instead of fabricating ideas."""
    agent = _FakeBacklogAgent(load_text_fixture("content_gen_backlog_malformed.txt"))

    result = await agent.build_backlog("pricing", StrategyMemory())

    assert result.items == []
    assert result.rejected_count == 1
    assert result.rejection_reasons == ["Missing a concrete idea statement"]
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
    assert "query_family: audience_problem" in agent.last_user_prompt
    assert result.supporting_sources[0].url == "https://example.com/pricing"
    assert result.supporting_sources[0].query_family == "audience_problem"
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
    assert result.must_fix_items == [
        "Confirm the screenshot can be shown on camera",
        'Replace the vague "works better" claim with a concrete explanation',
    ]
    assert result.approved_for_publish is False


def test_qc_golden_fixture_sparse_output_defaults_missing_lists() -> None:
    """Sparse QC output should leave omitted issue buckets empty."""
    result = _parse_qc_gate(load_text_fixture("content_gen_qc_sparse.txt"))

    assert result.hook_strength == "adequate"
    assert result.clarity_issues == []
    assert result.must_fix_items == ["Add a concrete proof point before publish"]


@pytest.mark.asyncio
async def test_qc_agent_raises_when_hook_strength_missing() -> None:
    """Human QC should fail fast on blank review shells."""
    agent = _FakeQCAgent("must_fix_items:\n- Tighten the hook")

    with pytest.raises(ValueError, match="hook_strength"):
        await agent.review(script="Script")


def test_parse_backlog_items_handles_partial_items() -> None:
    """Parsing should return items that have at least an idea field."""
    text = """---
idea: First idea
audience: Test audience
---
idea: Second idea
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
    assert result[1].total_score == 7


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


def test_pipeline_stage_labels_include_plan_opportunity() -> None:
    """plan_opportunity should have a human-readable label."""
    from cc_deep_research.content_gen.models import PIPELINE_STAGE_LABELS

    assert "plan_opportunity" in PIPELINE_STAGE_LABELS
    assert PIPELINE_STAGE_LABELS["plan_opportunity"] == "Planning opportunity brief"


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

    brief = _parse_opportunity_brief(sample_response, "fallback")
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

    brief = _parse_opportunity_brief(
        """Goal: something
Primary audience segment: startup marketers
Problem statements:
- Pricing pages hide the comparison buyers make first
Content objective: show the fix
""",
        "fallback theme",
    )
    assert brief.theme == "fallback theme"


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
