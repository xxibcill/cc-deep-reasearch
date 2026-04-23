"""Contract tests for content-gen JSON fixtures.

These tests verify that the JSON fixtures are valid and can be parsed
into the expected Pydantic model types.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from tests.helpers.fixture_loader import (
    load_content_gen_backlog_item,
    load_content_gen_managed_brief,
    load_content_gen_pipeline_context,
    load_content_gen_scoring_output,
    load_content_gen_scripting_result,
    load_content_gen_strategy_memory,
)


class TestContentGenFixtures:
    """Contract tests for content-gen fixtures."""

    def test_load_content_gen_pipeline_context(self) -> None:
        """Pipeline context fixture loads as valid dict."""
        data = load_content_gen_pipeline_context()
        assert isinstance(data, dict)
        assert data["pipeline_id"] == "p4-fixture-001"
        assert data["theme"] == "pricing anchors for enterprise SaaS"
        assert "strategy" in data
        assert "backlog" in data
        assert "scoring" in data

    def test_load_content_gen_backlog_item(self) -> None:
        """Backlog item fixture loads as valid dict."""
        data = load_content_gen_backlog_item()
        assert isinstance(data, dict)
        assert data["idea_id"] == "idea-fixture-001"
        assert data["category"] == "authority-building"
        assert data["risk_level"] == "medium"
        assert data["status"] == "backlog"

    def test_load_content_gen_scoring_output(self) -> None:
        """Scoring output fixture loads as valid dict."""
        data = load_content_gen_scoring_output()
        assert isinstance(data, dict)
        assert "scores" in data
        assert len(data["scores"]) == 2
        assert data["selected_idea_id"] == "idea-fixture-002"
        assert "shortlist" in data

    def test_load_content_gen_managed_brief(self) -> None:
        """Managed brief fixture loads as valid dict."""
        data = load_content_gen_managed_brief()
        assert isinstance(data, dict)
        assert data["brief_id"] == "mbrief-fixture-001"
        assert data["lifecycle_state"] == "draft"
        assert "current_revision" in data
        assert data["current_revision"]["revision_id"] == "rev-fixture-001"

    def test_load_content_gen_scripting_result(self) -> None:
        """Scripting result fixture loads as valid dict."""
        data = load_content_gen_scripting_result()
        assert isinstance(data, dict)
        assert data["idea_id"] == "idea-fixture-002"
        assert data["thesis"] != ""
        assert "beats" in data
        assert len(data["beats"]) == 3
        assert "qc" in data

    def test_load_content_gen_strategy_memory(self) -> None:
        """Strategy memory fixture loads as valid dict."""
        data = load_content_gen_strategy_memory()
        assert isinstance(data, dict)
        assert data["theme"] == "pricing anchors for enterprise SaaS"
        assert "niche" in data
        assert "pillars" in data
        assert "audience_segments" in data
        assert "hook_library" in data

    def test_fixtures_are_parseable_as_models(self) -> None:
        """Fixtures can be parsed into their respective Pydantic models."""
        from cc_deep_research.content_gen.models import (
            BacklogItem,
            BriefLifecycleState,
            ManagedOpportunityBrief,
            PipelineContext,
            ScoringOutput,
            ScriptingContext,
            StrategyMemory,
        )

        # PipelineContext
        ctx_data = load_content_gen_pipeline_context()
        ctx = PipelineContext.model_validate(ctx_data)
        assert ctx.pipeline_id == "p4-fixture-001"
        assert ctx.theme == "pricing anchors for enterprise SaaS"

        # BacklogItem
        item_data = load_content_gen_backlog_item()
        item = BacklogItem.model_validate(item_data)
        assert item.idea_id == "idea-fixture-001"

        # ScoringOutput
        scoring_data = load_content_gen_scoring_output()
        scoring = ScoringOutput.model_validate(scoring_data)
        assert len(scoring.scores) == 2
        assert scoring.selected_idea_id == "idea-fixture-002"

        # ManagedOpportunityBrief with nested current_revision
        brief_data = load_content_gen_managed_brief()
        brief = ManagedOpportunityBrief.model_validate(brief_data)
        assert brief.brief_id == "mbrief-fixture-001"
        assert brief.lifecycle_state == BriefLifecycleState.DRAFT
        assert brief.current_revision_id == "rev-fixture-001"

        # ScriptingContext
        script_data = load_content_gen_scripting_result()
        script = ScriptingContext.model_validate(script_data)
        assert script.idea_id == "idea-fixture-002"
        assert len(script.beats) == 3

        # StrategyMemory
        strat_data = load_content_gen_strategy_memory()
        strat = StrategyMemory.model_validate(strat_data)
        assert strat.theme == "pricing anchors for enterprise SaaS"
