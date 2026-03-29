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
    AngleOption,
    AngleOutput,
    BacklogItem,
    BacklogOutput,
    BeatVisual,
    HumanQCGate,
    IdeaScores,
    PackagingOutput,
    PipelineContext,
    PlatformPackage,
    ProductionBrief,
    PublishItem,
    QCResult,
    ResearchPack,
    ScoringOutput,
    ScriptingContext,
    ScriptVersion,
    StrategyMemory,
    VisualPlanOutput,
)


class _FakeScriptingAgent(ScriptingAgent):
    def __init__(self, response: str) -> None:
        self._response = response
        self.last_user_prompt = ""

    async def _call_llm(self, system_prompt: str, user_prompt: str, *, temperature: float = 0.3) -> str:
        del system_prompt, temperature
        self.last_user_prompt = user_prompt
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
async def test_define_angle_raises_on_missing_core_inputs() -> None:
    """Step 2 should raise ValueError (not AssertionError) when core_inputs is None."""
    agent = _FakeScriptingAgent("Angle: test\nContent Type: Contrarian\nCore Tension: x")
    ctx = ScriptingContext(raw_idea="idea")

    with pytest.raises(ValueError, match="core_inputs"):
        await agent.define_angle(ctx)


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
