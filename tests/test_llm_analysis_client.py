"""Tests for Claude CLI-backed analysis clients."""

import subprocess
from io import StringIO

import pytest

from cc_deep_research.agents.ai_analysis_service import AIAnalysisService
from cc_deep_research.agents.llm_analysis_client import LLMAnalysisClient


class FakePopen:
    """Fake Popen for testing subprocess streaming."""

    def __init__(
        self,
        args,
        stdout=None,
        stderr=None,
        text=False,  # noqa: ARG002
        returncode=0,
        stdout_data="",
        stderr_data="",
    ):
        self.args = args
        self.returncode = returncode
        self.pid = 12345
        # Create file-like objects for stdout/stderr
        self._stdout_data = stdout_data
        self._stderr_data = stderr_data
        self.stdout = StringIO(stdout_data) if stdout else None
        self.stderr = StringIO(stderr_data) if stderr else None

    def wait(self, timeout=None):  # noqa: ARG002
        """Simulate process wait."""
        return self.returncode

    def kill(self):
        """Simulate process kill."""
        pass

    def communicate(self, timeout=None):  # noqa: ARG002
        """Simulate communicate for blocking mode."""
        return (self._stdout_data, self._stderr_data)


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

        stdout_data = '{"themes":[{"name":"Theme A","description":"Desc","key_points":["Point"],"supporting_sources":["https://example.com"]}]}'

        def fake_popen(
            command: list[str],
            stdout=None,
            stderr=None,
            text=False,
            bufsize=-1,  # noqa: ARG001
        ):
            captured["command"] = command
            captured["stdout"] = stdout
            captured["stderr"] = stderr
            captured["text"] = text
            return FakePopen(
                command,
                stdout=stdout,
                stderr=stderr,
                text=text,
                returncode=0,
                stdout_data=stdout_data,
                stderr_data="",
            )

        monkeypatch.setattr(
            "cc_deep_research.agents.llm_analysis_client.subprocess.Popen",
            fake_popen,
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
        assert captured["stdout"] == subprocess.PIPE
        assert captured["stderr"] == subprocess.PIPE
        assert captured["text"] is True

    def test_request_raises_on_claude_failure(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """CLI failures should surface the stderr content."""

        def fake_popen(
            command: list[str],
            stdout=None,
            stderr=None,
            text=False,
            bufsize=-1,  # noqa: ARG001
        ):
            return FakePopen(
                command,
                stdout=stdout,
                stderr=stderr,
                text=text,
                returncode=1,
                stdout_data="",
                stderr_data="authentication failed",
            )

        monkeypatch.setattr(
            "cc_deep_research.agents.llm_analysis_client.subprocess.Popen",
            fake_popen,
        )

        client = LLMAnalysisClient({"claude_cli_path": "/usr/local/bin/claude"})

        with pytest.raises(RuntimeError, match="authentication failed"):
            client.identify_gaps(
                sources=[{"url": "https://example.com", "title": "Example", "content": "Body"}],
                query="test query",
                themes=[{"name": "Theme"}],
            )

    def test_request_emits_subprocess_events(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Subprocess events should be emitted when monitor is configured."""
        from cc_deep_research.monitoring import ResearchMonitor

        stdout_data = '{"themes":[]}'

        def fake_popen(
            command: list[str],
            stdout=None,
            stderr=None,
            text=False,
            bufsize=-1,  # noqa: ARG001
        ):
            return FakePopen(
                command,
                stdout=stdout,
                stderr=stderr,
                text=text,
                returncode=0,
                stdout_data=stdout_data,
                stderr_data="",
            )

        monkeypatch.setattr(
            "cc_deep_research.agents.llm_analysis_client.subprocess.Popen",
            fake_popen,
        )

        monitor = ResearchMonitor(enabled=False, persist=False)
        monitor.set_session("test-session", "query", "standard")

        client = LLMAnalysisClient(
            {"claude_cli_path": "/usr/local/bin/claude"},
            monitor=monitor,
        )

        client.extract_themes(
            sources=[{"url": "https://example.com", "title": "Example", "content": "Body"}],
            query="test query",
            num_themes=1,
        )

        # Find subprocess events
        subprocess_events = [
            e for e in monitor._telemetry_events
            if e["category"] == "llm" and "subprocess" in e["event_type"]
        ]

        # Should have scheduled, started, and completed events
        event_types = {e["event_type"] for e in subprocess_events}
        assert "subprocess.scheduled" in event_types
        assert "subprocess.started" in event_types
        assert "subprocess.completed" in event_types

    def test_request_emits_timeout_event(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Timeout should emit subprocess.timeout event."""
        from cc_deep_research.monitoring import ResearchMonitor

        class TimeoutPopen(FakePopen):
            def __init__(self, *args, **kwargs):
                super().__init__(*args, **kwargs)
                self._killed = False

            def wait(self, timeout=None):
                if timeout is not None and not self._killed:
                    raise subprocess.TimeoutExpired(cmd=self.args, timeout=timeout)
                return self.returncode

            def kill(self):
                self._killed = True

        def fake_popen(
            command: list[str],
            stdout=None,
            stderr=None,
            text=False,
            bufsize=-1,  # noqa: ARG001
        ):
            return TimeoutPopen(
                command,
                stdout=stdout,
                stderr=stderr,
                text=text,
                returncode=0,
                stdout_data="",
                stderr_data="",
            )

        monkeypatch.setattr(
            "cc_deep_research.agents.llm_analysis_client.subprocess.Popen",
            fake_popen,
        )

        monitor = ResearchMonitor(enabled=False, persist=False)
        monitor.set_session("test-session", "query", "standard")

        client = LLMAnalysisClient(
            {"claude_cli_path": "/usr/local/bin/claude", "timeout_seconds": 0},
            monitor=monitor,
        )

        with pytest.raises(RuntimeError, match="timed out"):
            client.extract_themes(
                sources=[{"url": "https://example.com", "title": "Example", "content": "Body"}],
                query="test query",
                num_themes=1,
            )

        # Find timeout event
        timeout_events = [
            e for e in monitor._telemetry_events
            if e["event_type"] == "subprocess.timeout"
        ]

        assert len(timeout_events) == 1
        assert timeout_events[0]["status"] == "timeout"

    def test_request_emits_failed_event_on_error(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Non-zero exit should emit subprocess.failed event."""
        from cc_deep_research.monitoring import ResearchMonitor

        def fake_popen(
            command: list[str],
            stdout=None,
            stderr=None,
            text=False,
            bufsize=-1,  # noqa: ARG001
        ):
            return FakePopen(
                command,
                stdout=stdout,
                stderr=stderr,
                text=text,
                returncode=1,
                stdout_data="",
                stderr_data="error occurred",
            )

        monkeypatch.setattr(
            "cc_deep_research.agents.llm_analysis_client.subprocess.Popen",
            fake_popen,
        )

        monitor = ResearchMonitor(enabled=False, persist=False)
        monitor.set_session("test-session", "query", "standard")

        client = LLMAnalysisClient(
            {"claude_cli_path": "/usr/local/bin/claude"},
            monitor=monitor,
        )

        with pytest.raises(RuntimeError, match="error occurred"):
            client.extract_themes(
                sources=[{"url": "https://example.com", "title": "Example", "content": "Body"}],
                query="test query",
                num_themes=1,
            )

        # Find failed event
        failed_events = [
            e for e in monitor._telemetry_events
            if e["event_type"] == "subprocess.failed"
        ]

        assert len(failed_events) == 1
        assert failed_events[0]["status"] == "failed"
        assert failed_events[0]["metadata"]["exit_code"] == 1

    def test_request_streams_stdout_and_stderr_chunks(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Chunk events should include ordered stdout and stderr content."""
        from cc_deep_research.monitoring import ResearchMonitor

        stdout_data = "line one\nline two\nline three\n"
        stderr_data = "warn one\nwarn two\n"

        def fake_popen(
            command: list[str],
            stdout=None,
            stderr=None,
            text=False,
            bufsize=-1,  # noqa: ARG001
        ):
            return FakePopen(
                command,
                stdout=stdout,
                stderr=stderr,
                text=text,
                returncode=0,
                stdout_data=stdout_data,
                stderr_data=stderr_data,
            )

        monkeypatch.setattr(
            "cc_deep_research.agents.llm_analysis_client.subprocess.Popen",
            fake_popen,
        )

        monitor = ResearchMonitor(enabled=False, persist=False)
        parent_event_id = monitor.set_session("test-session", "query", "standard")

        client = LLMAnalysisClient(
            {"claude_cli_path": "/usr/local/bin/claude"},
            monitor=monitor,
        )

        client.extract_themes(
            sources=[{"url": "https://example.com", "title": "Example", "content": "Body"}],
            query="test query",
            num_themes=1,
        )

        scheduled_event = next(
            event
            for event in monitor._telemetry_events
            if event["event_type"] == "subprocess.scheduled"
        )
        stdout_events = [
            event
            for event in monitor._telemetry_events
            if event["event_type"] == "subprocess.stdout_chunk"
        ]
        stderr_events = [
            event
            for event in monitor._telemetry_events
            if event["event_type"] == "subprocess.stderr_chunk"
        ]

        assert scheduled_event["parent_event_id"] == parent_event_id
        assert [event["metadata"]["chunk_index"] for event in stdout_events] == [0, 1, 2]
        assert [event["metadata"]["chunk_index"] for event in stderr_events] == [0, 1]
        assert stdout_events[0]["metadata"]["content"] == "line one\n"
        assert stderr_events[0]["metadata"]["content"] == "warn one\n"
        assert all(event["parent_event_id"] == scheduled_event["event_id"] for event in stdout_events)
        assert all(event["parent_event_id"] == scheduled_event["event_id"] for event in stderr_events)


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

    def test_service_passes_monitor_to_llm_client(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """The analysis service should wire the monitor into the CLI client."""
        from cc_deep_research.monitoring import ResearchMonitor

        captured: dict[str, object] = {}

        class FakeClient:
            def __init__(self, config, monitor=None):
                captured["config"] = config
                captured["monitor"] = monitor

        monkeypatch.delenv("CLAUDECODE", raising=False)
        monkeypatch.setattr(
            "cc_deep_research.agents.llm_analysis_client.LLMAnalysisClient",
            FakeClient,
        )

        monitor = ResearchMonitor(enabled=False, persist=False)
        service = AIAnalysisService({"ai_integration_method": "api"}, monitor=monitor)

        assert isinstance(service._llm_client, FakeClient)
        assert captured["monitor"] is monitor
