"""Tests for the CLI research command delegation."""

from __future__ import annotations

from click.testing import CliRunner

from cc_deep_research.cli import main
from cc_deep_research.cli import research as research_module
from cc_deep_research.config import Config
from cc_deep_research.models import ResearchSession
from cc_deep_research.research_runs import (
    PreparedResearchRun,
    ResearchOutputFormat,
    ResearchRunReport,
    ResearchRunResult,
)


def test_research_command_delegates_to_shared_run_service(monkeypatch) -> None:
    """The Click command should convert flags and delegate execution to the shared service."""
    captured: dict[str, object] = {}

    class FakeService:
        def prepare(self, request):
            captured["request"] = request
            return PreparedResearchRun(request=request, config=Config())

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

    def test_cli_research_accepts_min_sources(self) -> None:
        """Verify --sources option is accepted."""
        runner = CliRunner()
        result = runner.invoke(
            main,
            ["research", "--help"],
        )

        assert result.exit_code == 0
        assert "--sources" in result.output or "-s" in result.output
