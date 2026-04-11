"""Tests for the CLI research command delegation."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from click.testing import CliRunner

from cc_deep_research.cli import main
from cc_deep_research.cli import research as research_module
from cc_deep_research.config import Config
from cc_deep_research.models import ResearchDepth, ResearchSession, SearchResultItem
from cc_deep_research.prompts import PromptRegistry
from cc_deep_research.research_runs import (
    PreparedResearchRun,
    ResearchOutputFormat,
    ResearchRunReport,
    ResearchRunResult,
    ResearchRunService,
)
from cc_deep_research.session_store import SessionStore
from tests.helpers.fixture_loader import load_analysis_healthy, load_tavily_search_healthy


def _build_fixture_session(query: str) -> ResearchSession:
    """Build a deterministic fixture-backed session for CLI smoke coverage."""
    analysis = dict(load_analysis_healthy())
    analysis["themes_detailed"] = [
        {
            "name": theme.get("theme") or theme.get("name", "Unnamed Theme"),
            "description": theme.get("description", ""),
            "key_points": theme.get("detail_points", []) or theme.get("key_points", []),
            "supporting_sources": (
                [theme["supporting_sources"]]
                if isinstance(theme.get("supporting_sources"), int)
                else theme.get("supporting_sources", [])
            ),
        }
        for theme in analysis.get("themes_detailed", [])
        if isinstance(theme, dict)
    ]
    tavily_fixture = load_tavily_search_healthy()
    sources = [
        SearchResultItem(
            url=result["url"],
            title=result.get("title", ""),
            snippet=result.get("content", ""),
            content=result.get("raw_content"),
            score=float(result.get("score", 0.0)),
            source_metadata={
                "provider": "tavily",
                "query": query,
                "query_family": "baseline",
                "query_intent_tags": ["baseline"],
            },
        )
        for result in tavily_fixture["results"][:2]
    ]
    return ResearchSession(
        session_id="cli-fixture-session",
        query=query,
        depth=ResearchDepth.STANDARD,
        started_at=datetime(2024, 1, 1, 12, 0, 0),
        completed_at=datetime(2024, 1, 1, 12, 2, 0),
        sources=sources,
        metadata={
            "strategy": {
                "profile": {"intent": "informational"},
                "strategy": {
                    "query_families": [
                        {
                            "query": query,
                            "family": "baseline",
                            "intent_tags": ["baseline"],
                        }
                    ]
                },
            },
            "analysis": analysis,
            "validation": {
                "is_valid": True,
                "quality_score": 0.91,
                "warnings": [],
                "recommendations": [],
            },
            "providers": {
                "configured": ["tavily"],
                "available": ["tavily"],
                "warnings": [],
                "status": "ready",
            },
            "execution": {
                "parallel_requested": False,
                "parallel_used": False,
                "degraded": False,
                "degraded_reasons": [],
            },
            "deep_analysis": {
                "requested": False,
                "completed": False,
                "status": "not_requested",
            },
        },
    )


def test_research_command_delegates_to_shared_run_service(monkeypatch) -> None:
    """The Click command should convert flags and delegate execution to the shared service."""
    captured: dict[str, object] = {}

    class FakeService:
        def prepare(self, request):
            captured["request"] = request
            return PreparedResearchRun(
                request=request,
                config=Config(),
                prompt_registry=PromptRegistry(),
            )

        def run_prepared(self, prepared, **kwargs):
            captured["prepared"] = prepared
            captured["run_kwargs"] = kwargs
            return ResearchRunResult(
                session=ResearchSession(
                    session_id="session-123",
                    query=prepared.request.query,
                ),
                report=ResearchRunReport(
                    format=ResearchOutputFormat.MARKDOWN,
                    content="# Report",
                    media_type="text/markdown",
                ),
            )

    monkeypatch.setattr(research_module, "ResearchRunService", FakeService)

    runner = CliRunner()
    result = runner.invoke(
        main,
        [
            "research",
            "shared service query",
            "--quiet",
            "--no-team",
            "--tavily-only",
            "--format",
            "markdown",
        ],
    )

    assert result.exit_code == 0
    assert result.output.strip() == "# Report"

    request = captured["request"]
    assert request.query == "shared service query"
    assert request.parallel_mode is False
    assert request.search_providers == ["tavily"]

    run_kwargs = captured["run_kwargs"]
    assert run_kwargs["event_router"] is None
    assert isinstance(
        run_kwargs["execution_adapter"],
        research_module.TerminalResearchRunExecutionAdapter,
    )


class TestCLIFixtureSmoke:
    """CLI smoke tests for research command.

    These tests verify the CLI research command can be invoked
    with various options without errors.
    """

    def test_cli_research_materializes_fixture_backed_run(
        self,
        monkeypatch,
        tmp_path: Path,
    ) -> None:
        """The CLI should complete a deterministic fixture-backed run end-to-end."""
        config = Config()
        config.search.providers = ["tavily"]
        config.search_team.parallel_execution = False
        config.research.quality.enable_report_quality_evaluation = False
        config.research.quality.enable_report_refinement = False

        session = _build_fixture_session("quantum computing")

        class StubOrchestrator:
            def __init__(self, **_kwargs) -> None:
                pass

            async def execute_research(self, **_kwargs) -> ResearchSession:
                return session

        service = ResearchRunService(
            config_loader=lambda: config,
            orchestrator_factory=StubOrchestrator,
        )
        session_dir = tmp_path / "sessions"
        monkeypatch.setattr(research_module, "ResearchRunService", lambda: service)
        monkeypatch.setattr(
            "cc_deep_research.research_runs.output.SessionStore",
            lambda: SessionStore(session_dir),
        )

        report_path = tmp_path / "fixture-report.json"
        runner = CliRunner()
        result = runner.invoke(
            main,
            [
                "research",
                session.query,
                "--depth",
                "standard",
                "--format",
                "json",
                "--output",
                str(report_path),
                "--quiet",
                "--no-team",
                "--tavily-only",
            ],
        )

        assert result.exit_code == 0
        assert result.output == ""
        assert report_path.exists()

        report = json.loads(report_path.read_text(encoding="utf-8"))
        assert report["query"] == session.query
        assert report["total_sources"] == len(session.sources)
        assert report["metadata"]["providers"]["status"] == "ready"
        assert report["analysis"]["themes"]

        session_file = session_dir / f"{session.session_id}.json"
        assert session_file.exists()
        stored_session = json.loads(session_file.read_text(encoding="utf-8"))
        assert stored_session["query"] == session.query
        assert stored_session["metadata"]["analysis"]["themes"]

    def test_cli_research_help_includes_depth_options(self) -> None:
        """Verify help shows depth options."""
        runner = CliRunner()
        result = runner.invoke(main, ["research", "--help"])

        assert result.exit_code == 0
        assert "quick" in result.output
        assert "standard" in result.output
        assert "deep" in result.output

    def test_cli_research_help_includes_format_options(self) -> None:
        """Verify help shows format options."""
        runner = CliRunner()
        result = runner.invoke(main, ["research", "--help"])

        assert result.exit_code == 0
        assert "markdown" in result.output
        assert "json" in result.output
        assert "html" in result.output

    def test_cli_research_help_includes_provider_options(self) -> None:
        """Verify help shows provider options."""
        runner = CliRunner()
        result = runner.invoke(main, ["research", "--help"])

        assert result.exit_code == 0
        assert "--tavily-only" in result.output
        assert "--claude-only" in result.output
        assert "--no-team" in result.output

    def test_cli_research_help_clarifies_local_execution_semantics(self) -> None:
        """Verify help text describes local sequential and parallel behavior accurately."""
        runner = CliRunner()
        result = runner.invoke(main, ["research", "--help"])

        assert result.exit_code == 0
        normalized_output = " ".join(result.output.split())
        assert "sequentially instead of using parallel local tasks" in normalized_output
        assert "local roster metadata size (compatibility setting)" in normalized_output
        assert "Force parallel local source collection for this run" in normalized_output
        assert "Number of parallel local collection tasks (1-8)" in normalized_output

    def test_cli_research_accepts_min_sources(self) -> None:
        """Verify --sources option is accepted."""
        runner = CliRunner()
        result = runner.invoke(
            main,
            ["research", "--help"],
        )

        assert result.exit_code == 0
        assert "--sources" in result.output or "-s" in result.output
