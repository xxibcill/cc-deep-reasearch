"""Tests for the content generation workflow."""

from __future__ import annotations

from pathlib import Path

import pytest
from click.testing import CliRunner

from cc_deep_research.cli import main
from cc_deep_research.content_gen.agents.scripting import _STEP_HANDLERS, ScriptingAgent
from cc_deep_research.content_gen.prompts import scripting as scripting_prompts
from cc_deep_research.content_gen.models import (
    PIPELINE_STAGES,
    SCRIPTING_STEPS,
    AngleDefinition,
    AngleOption,
    AngleOutput,
    BacklogItem,
    BacklogOutput,
    BeatVisual,
    CoreInputs,
    HumanQCGate,
    IdeaScores,
    PackagingOutput,
    PipelineContext,
    PlatformPackage,
    ProductionBrief,
    PublishItem,
    QCResult,
    ResearchPack,
    SavedScriptRun,
    ScoringOutput,
    ScriptingContext,
    ScriptVersion,
    StrategyMemory,
    VisualPlanOutput,
)
from cc_deep_research.content_gen.orchestrator import _format_research_context
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
    """The pipeline should have 12 stages (0-11)."""
    assert len(PIPELINE_STAGES) == 12


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
        raw_idea="content idea",
        tightened=ScriptVersion(content="Tight script", word_count=2),
        annotated_script=ScriptVersion(
            content='Hook: "Line one"\n[Cut]',
            word_count=4,
        ),
    )

    result = await agent.run_qc(ctx)

    assert 'Annotated Script:\nHook: "Line one"\n[Cut]' in agent.last_user_prompt
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
