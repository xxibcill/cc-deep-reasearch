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
