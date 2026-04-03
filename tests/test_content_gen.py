"""Tests for the content generation workflow."""

from __future__ import annotations

from pathlib import Path

import pytest
from click.testing import CliRunner

from cc_deep_research.cli import main
from cc_deep_research.content_gen.agents.scripting import _STEP_HANDLERS, ScriptingAgent
from cc_deep_research.content_gen.models import (
    PIPELINE_STAGES,
    SCRIPTING_STEPS,
    AngleDefinition,
    AngleOption,
    BacklogItem,
    BacklogOutput,
    BeatIntent,
    BeatIntentMap,
    CoreInputs,
    HookSet,
    HumanQCGate,
    IdeaScores,
    OpportunityBrief,
    PackagingOutput,
    PipelineContext,
    PipelineStageTrace,
    PlatformPackage,
    PublishItem,
    QCResult,
    ResearchPack,
    SavedScriptRun,
    ScoringOutput,
    ScriptingContext,
    ScriptStructure,
    ScriptVersion,
    StrategyMemory,
)
from cc_deep_research.content_gen.orchestrator import _format_research_context
from cc_deep_research.content_gen.prompts import scripting as scripting_prompts
from cc_deep_research.llm.base import LLMProviderType, LLMResponse, LLMTransportType


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


def test_pipeline_context_default_values() -> None:
    """PipelineContext should have sensible defaults."""
    ctx = PipelineContext()
    assert ctx.pipeline_id  # auto-generated
    assert ctx.strategy is None
    assert ctx.backlog is None
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
    )
    json_str = ctx.model_dump_json()
    restored = PipelineContext.model_validate_json(json_str)
    assert restored.theme == "test theme"
    assert restored.strategy is not None
    assert restored.strategy.niche == "fitness"
    assert len(restored.backlog.items) == 1
    assert restored.backlog.items[0].idea == "test idea"


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
        hold=["id3"],
        killed=["id4"],
    )
    scoring_summary = orch._summarize_output(3, ctx)
    assert "produce=2" in scoring_summary
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

    ctx.backlog = None
    ctx.scoring = ScoringOutput(produce_now=[])
    prereqs_met, reason = orch._check_prerequisites(4, ctx)
    assert not prereqs_met
    assert "scoring/produce_now missing" in reason


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
    recorded_events: list[tuple[int, str, str]] = []

    def on_stage_completed(stage_idx: int, status: str, detail: str) -> None:
        recorded_events.append((stage_idx, status, detail))

    ctx = PipelineContext(theme="test")
    await orch._run_stage(3, ctx, None, stage_completed_callback=on_stage_completed)

    assert len(recorded_events) == 1
    idx, status, detail = recorded_events[0]
    assert idx == 3
    assert status == "skipped"
    assert "backlog missing" in detail


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
    recorded_events: list[tuple[int, str, str]] = []

    def on_stage_completed(stage_idx: int, status: str, detail: str) -> None:
        recorded_events.append((stage_idx, status, detail))

    ctx = PipelineContext(theme="test")
    await orch._run_stage(0, ctx, None, stage_completed_callback=on_stage_completed)

    assert len(recorded_events) == 1
    idx, status, detail = recorded_events[0]
    assert idx == 0
    assert status == "completed"
    assert detail == ""


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


from cc_deep_research.content_gen.agents.backlog import (
    _parse_backlog_items,
    _parse_scores,
    _validate_scores,
)
from cc_deep_research.content_gen.prompts.backlog import build_backlog_user


def test_parse_backlog_items_handles_malformed_response() -> None:
    """Parsing should return empty list for garbage input."""
    result = _parse_backlog_items("This is not a valid backlog response")
    assert result == []


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


def test_parse_scores_handles_malformed_response() -> None:
    """Parsing should return empty list for garbage input."""
    items = [BacklogItem(idea_id="id1", idea="test")]
    result = _parse_scores("Not a valid scoring response", items)
    assert result == []


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
    from cc_deep_research.content_gen.models import OpportunityBrief

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


def test_build_backlog_user_works_without_opportunity_brief() -> None:
    """Prompt should work normally when OpportunityBrief is None."""
    user_prompt = build_backlog_user(
        theme="test",
        strategy=StrategyMemory(niche="tech"),
        count=10,
        opportunity_brief=None,
    )

    assert "Theme: test" in user_prompt
    assert "Target count: 10 ideas" in user_prompt
    assert "Niche: tech" in user_prompt
    assert "Goal" not in user_prompt
    assert "Primary audience" not in user_prompt


def test_backlog_output_with_zero_items() -> None:
    """BacklogOutput with empty items should be valid and clear."""
    output = BacklogOutput(items=[], rejected_count=0, rejection_reasons=[])
    assert output.items == []
    assert len(output.items) == 0


def test_scoring_output_with_zero_scores() -> None:
    """ScoringOutput with empty scores should be valid and clear."""
    output = ScoringOutput(scores=[], produce_now=[], hold=[], killed=[])
    assert output.scores == []
    assert len(output.produce_now) == 0
    assert len(output.hold) == 0
    assert len(output.killed) == 0


# ---------------------------------------------------------------------------
# Opportunity planning
# ---------------------------------------------------------------------------


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
    """Parser should fall back to the provided theme when LLM omits it."""
    from cc_deep_research.content_gen.agents.opportunity import _parse_opportunity_brief

    brief = _parse_opportunity_brief("Goal: something\n", "fallback theme")
    assert brief.theme == "fallback theme"


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
