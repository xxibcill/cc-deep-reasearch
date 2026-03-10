"""Tests for Claude CLI-backed analysis clients."""

import subprocess

import pytest

from cc_deep_research.agents.ai_analysis_service import AIAnalysisService
from cc_deep_research.agents.llm_analysis_client import LLMAnalysisClient


class TestLLMAnalysisClient:
    """Tests for the Claude CLI analysis client."""

    def test_init_requires_claude_cli(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """The client should fail fast when the Claude CLI is unavailable."""
        monkeypatch.delenv("CLAUDE_CLI_PATH", raising=False)
        monkeypatch.setattr("cc_deep_research.agents.llm_analysis_client.shutil.which", lambda _: None)

        with pytest.raises(ValueError, match="Claude Code CLI not found"):
            LLMAnalysisClient({})

    def test_extract_themes_uses_claude_cli(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Theme extraction should invoke `claude -p` and parse JSON output."""
        captured: dict[str, object] = {}

        def fake_run(
            command: list[str],
            *,
            capture_output: bool,  # noqa: ARG001
            text: bool,  # noqa: ARG001
            check: bool,  # noqa: ARG001
            timeout: int,  # noqa: ARG001
        ) -> subprocess.CompletedProcess[str]:
            captured["command"] = command
            captured["capture_output"] = capture_output
            captured["text"] = text
            captured["check"] = check
            captured["timeout"] = timeout
            return subprocess.CompletedProcess(
                args=command,
                returncode=0,
                stdout='{"themes":[{"name":"Theme A","description":"Desc","key_points":["Point"],"supporting_sources":["https://example.com"]}]}',
                stderr="",
            )

        monkeypatch.setattr(
            "cc_deep_research.agents.llm_analysis_client.subprocess.run",
            fake_run,
        )

        client = LLMAnalysisClient(
            {
                "claude_cli_path": "/usr/local/bin/claude",
                "model": "claude-sonnet-4-6",
                "timeout_seconds": 45,
            }
        )

        themes = client.extract_themes(
            sources=[
                {
                    "url": "https://example.com",
                    "title": "Example",
                    "content": "Evidence about a topic.",
                }
            ],
            query="test query",
            num_themes=1,
        )

        assert themes == [
            {
                "name": "Theme A",
                "description": "Desc",
                "key_points": ["Point"],
                "supporting_sources": ["https://example.com"],
            }
        ]
        command = captured["command"]
        assert isinstance(command, list)
        assert command[:-1] == [
            "/usr/local/bin/claude",
            "-p",
            "--model",
            "claude-sonnet-4-6",
            "--output-format",
            "text",
            "--no-session-persistence",
        ]
        assert isinstance(command[-1], str)
        assert 'Analyze the following research sources about "test query"' in command[-1]
        assert captured["capture_output"] is True
        assert captured["text"] is True
        assert captured["check"] is False
        assert captured["timeout"] == 45

    def test_request_raises_on_claude_failure(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """CLI failures should surface the stderr content."""

        def fake_run(
            command: list[str],
            *,
            capture_output: bool,  # noqa: ARG001
            text: bool,  # noqa: ARG001
            check: bool,  # noqa: ARG001
            timeout: int,  # noqa: ARG001
        ) -> subprocess.CompletedProcess[str]:
            return subprocess.CompletedProcess(
                args=command,
                returncode=1,
                stdout="",
                stderr="authentication failed",
            )

        monkeypatch.setattr(
            "cc_deep_research.agents.llm_analysis_client.subprocess.run",
            fake_run,
        )

        client = LLMAnalysisClient({"claude_cli_path": "/usr/local/bin/claude"})

        with pytest.raises(RuntimeError, match="authentication failed"):
            client.identify_gaps(
                sources=[{"url": "https://example.com", "title": "Example", "content": "Body"}],
                query="test query",
                themes=[{"name": "Theme"}],
            )


class TestAIAnalysisService:
    """Tests for AIAnalysisService CLI initialization behavior."""

    def test_api_mode_requires_claude_cli(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """API mode should raise if the CLI transport is unavailable."""
        monkeypatch.delenv("CLAUDE_CLI_PATH", raising=False)
        monkeypatch.delenv("CLAUDECODE", raising=False)  # Unset to allow CLI-based analysis
        monkeypatch.setattr("cc_deep_research.agents.llm_analysis_client.shutil.which", lambda _: None)

        with pytest.raises(ValueError, match="Claude Code CLI not found"):
            AIAnalysisService({"ai_integration_method": "api"})

    def test_hybrid_mode_falls_back_without_claude_cli(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Hybrid mode should keep heuristic fallback when the CLI is unavailable."""
        monkeypatch.delenv("CLAUDE_CLI_PATH", raising=False)
        monkeypatch.setattr("cc_deep_research.agents.llm_analysis_client.shutil.which", lambda _: None)

        service = AIAnalysisService({"ai_integration_method": "hybrid"})

        assert service._llm_client is None
