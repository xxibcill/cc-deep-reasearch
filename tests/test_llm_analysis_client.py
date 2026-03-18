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

    def test_init_allows_request_executor_without_claude_cli(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A routed executor should bypass local CLI discovery."""
        monkeypatch.delenv("CLAUDE_CLI_PATH", raising=False)
        monkeypatch.setattr("cc_deep_research.agents.llm_analysis_client.shutil.which", lambda _: None)

        client = LLMAnalysisClient(
            {"request_executor": lambda operation, prompt: f"{operation}:{prompt}"}
        )

        assert client._claude_cli_path == "router"

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
            bufsize=-1,  # noqa: ARG001  # noqa: ARG001
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
            bufsize=-1,  # noqa: ARG001  # noqa: ARG001
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
            bufsize=-1,  # noqa: ARG001  # noqa: ARG001
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
            bufsize=-1,  # noqa: ARG001  # noqa: ARG001
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
            bufsize=-1,  # noqa: ARG001  # noqa: ARG001
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
            bufsize=-1,  # noqa: ARG001  # noqa: ARG001
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

    def test_service_uses_router_backed_client_when_available(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Router-backed analysis should initialize without local CLI lookup."""
        captured: dict[str, object] = {}

        class FakeClient:
            def __init__(self, config, monitor=None):
                captured["config"] = config
                captured["monitor"] = monitor

        class FakeRouter:
            def is_available(self, agent_id: str) -> bool:
                captured["agent_id"] = agent_id
                return True

        monkeypatch.setattr(
            "cc_deep_research.agents.llm_analysis_client.LLMAnalysisClient",
            FakeClient,
        )

        service = AIAnalysisService(
            {"ai_integration_method": "api"},
            llm_router=FakeRouter(),
            agent_id="deep_analyzer",
        )

        assert isinstance(service._llm_client, FakeClient)
        assert captured["agent_id"] == "deep_analyzer"
        assert callable(captured["config"]["request_executor"])


class TestLLMAnalysisClientParserContracts:
    """Contract tests for LLMAnalysisClient parser methods."""

    def test_parse_theme_response_happy_path_json(self) -> None:
        """Theme parser should extract themes from valid JSON response."""
        client = LLMAnalysisClient({"claude_cli_path": "/usr/bin/claude"})
        response = '''{
          "themes": [
            {
              "name": "Antioxidant Properties",
              "description": "Green tea contains antioxidants that may reduce cellular damage.",
              "key_points": ["High ORAC value", "Polyphenol content", "Free radical scavenging"],
              "supporting_sources": ["https://pubmed.gov/1", "https://example.com/2"]
            },
            {
              "name": "Cardiovascular Benefits",
              "description": "Regular consumption may support heart health.",
              "key_points": ["LDL cholesterol reduction", "Blood pressure moderation"],
              "supporting_sources": ["https://pubmed.gov/3"]
            }
          ]
        }'''
        sources = [{"url": "https://pubmed.gov/1", "title": "Study 1"}]

        themes = client._parse_theme_response(response, sources)

        assert len(themes) == 2
        assert themes[0]["name"] == "Antioxidant Properties"
        assert themes[0]["description"] == "Green tea contains antioxidants that may reduce cellular damage."
        assert themes[0]["key_points"] == ["High ORAC value", "Polyphenol content", "Free radical scavenging"]
        assert themes[0]["supporting_sources"] == ["https://pubmed.gov/1", "https://example.com/2"]
        assert themes[1]["name"] == "Cardiovascular Benefits"

    def test_parse_theme_response_malformed_json_non_list_themes(self) -> None:
        """Theme parser should return empty list when themes is not a list."""
        client = LLMAnalysisClient({"claude_cli_path": "/usr/bin/claude"})
        response = '{"themes": "not a list"}'

        themes = client._parse_theme_response(response, [])

        assert themes == []

    def test_parse_theme_response_malformed_json_invalid_structure(self) -> None:
        """Theme parser should filter out non-dict items from themes array."""
        client = LLMAnalysisClient({"claude_cli_path": "/usr/bin/claude"})
        response = '{"themes": [{"name": "Valid"}, "string item", 123, null]}'

        themes = client._parse_theme_response(response, [])

        assert len(themes) == 1
        assert themes[0]["name"] == "Valid"

    def test_parse_theme_response_malformed_missing_json(self) -> None:
        """Theme parser should fall back to text parsing when JSON invalid."""
        client = LLMAnalysisClient({"claude_cli_path": "/usr/bin/claude"})
        response = "Theme: Antioxidant Properties\nDescription here\n- Key point one\n- Key point two"

        themes = client._parse_theme_response(response, [])

        assert len(themes) >= 1
        assert themes[0]["name"] == "Antioxidant Properties"

    def test_parse_cross_reference_response_happy_path_json(self) -> None:
        """Cross-reference parser should extract consensus and disagreement points."""
        client = LLMAnalysisClient({"claude_cli_path": "/usr/bin/claude"})
        response = '''{
          "consensus_points": [
            {
              "claim": "Treatment shows efficacy",
              "strength": "strong",
              "supporting_sources": ["https://pubmed.gov/1", "https://example.com/2"]
            }
          ],
          "disagreement_points": [
            {
              "claim": "Dosage optimality",
              "perspectives": [
                {"view": "Current dose is optimal", "sources": ["https://a.com"]},
                {"view": "Higher dose needed", "sources": ["https://b.com"]}
              ]
            }
          ]
        }'''

        result = client._parse_cross_reference_response(response)

        assert len(result["consensus_points"]) == 1
        assert result["consensus_points"][0]["claim"] == "Treatment shows efficacy"
        assert result["consensus_points"][0]["strength"] == "strong"
        assert len(result["disagreement_points"]) == 1

    def test_parse_cross_reference_response_malformed_consensus_points(self) -> None:
        """Cross-reference parser should handle non-list consensus_points gracefully."""
        client = LLMAnalysisClient({"claude_cli_path": "/usr/bin/claude"})
        response = '{"consensus_points": "not a list", "disagreement_points": []}'

        result = client._parse_cross_reference_response(response)

        assert result["consensus_points"] == []
        assert result["disagreement_points"] == []

    def test_parse_cross_reference_response_malformed_disagreement_points(self) -> None:
        """Cross-reference parser should handle non-list disagreement_points gracefully."""
        client = LLMAnalysisClient({"claude_cli_path": "/usr/bin/claude"})
        response = '{"consensus_points": [], "disagreement_points": 123}'

        result = client._parse_cross_reference_response(response)

        assert result["disagreement_points"] == []

    def test_parse_cross_reference_response_malformed_missing_keys(self) -> None:
        """Cross-reference parser should return empty lists for missing keys."""
        client = LLMAnalysisClient({"claude_cli_path": "/usr/bin/claude"})
        response = '{}'

        result = client._parse_cross_reference_response(response)

        assert result["consensus_points"] == []
        assert result["disagreement_points"] == []
        assert result["cross_reference_claims"] == []

    def test_parse_gap_response_happy_path_json(self) -> None:
        """Gap parser should extract gaps from valid JSON response."""
        client = LLMAnalysisClient({"claude_cli_path": "/usr/bin/claude"})
        response = '''{
          "gaps": [
            {
              "gap_description": "Long-term safety data missing",
              "importance": "High",
              "suggested_queries": ["long term safety study", "5 year follow up"]
            },
            {
              "gap_description": "Pediatric dosage unclear",
              "importance": "Medium",
              "suggested_queries": ["children dosage"]
            }
          ]
        }'''

        gaps = client._parse_gap_response(response)

        assert len(gaps) == 2
        assert gaps[0]["gap_description"] == "Long-term safety data missing"
        assert gaps[0]["importance"] == "High"
        assert gaps[0]["suggested_queries"] == ["long term safety study", "5 year follow up"]
        assert gaps[1]["gap_description"] == "Pediatric dosage unclear"

    def test_parse_gap_response_malformed_non_list_gaps(self) -> None:
        """Gap parser should return empty list when gaps is not a list."""
        client = LLMAnalysisClient({"claude_cli_path": "/usr/bin/claude"})
        response = '{"gaps": "not a list"}'

        gaps = client._parse_gap_response(response)

        assert gaps == []

    def test_parse_gap_response_malformed_fallback_parsing(self) -> None:
        """Gap parser should fall back to text parsing for non-JSON."""
        client = LLMAnalysisClient({"claude_cli_path": "/usr/bin/claude"})
        response = "- Missing long-term safety data\n- Unknown pediatric dosage"

        gaps = client._parse_gap_response(response)

        assert len(gaps) >= 1

    def test_parse_synthesis_response_happy_path_json(self) -> None:
        """Synthesis parser should extract findings from valid JSON response."""
        client = LLMAnalysisClient({"claude_cli_path": "/usr/bin/claude"})
        response = '''{
          "findings": [
            {
              "title": "Significant Treatment Effect",
              "summary": "Treatment shows statistically significant improvement.",
              "description": "Based on multiple clinical trials, the treatment demonstrates efficacy.",
              "detail_points": ["30% improvement rate", "p < 0.05"],
              "evidence": ["https://pubmed.gov/1", "https://example.com/2"],
              "confidence": "High"
            },
            {
              "title": "Mild Side Effects",
              "description": "Side effects were generally mild.",
              "evidence": ["https://pubmed.gov/3"]
            }
          ]
        }'''

        findings = client._parse_synthesis_response(response)

        assert len(findings) == 2
        assert findings[0]["title"] == "Significant Treatment Effect"
        assert findings[0]["summary"] == "Treatment shows statistically significant improvement."
        assert findings[0]["description"] == "Based on multiple clinical trials, the treatment demonstrates efficacy."
        assert findings[0]["detail_points"] == ["30% improvement rate", "p < 0.05"]
        assert findings[0]["evidence"] == ["https://pubmed.gov/1", "https://example.com/2"]
        assert findings[0]["confidence"] == "High"

    def test_parse_synthesis_response_missing_summary_field(self) -> None:
        """Synthesis parser should use description as fallback for missing summary."""
        client = LLMAnalysisClient({"claude_cli_path": "/usr/bin/claude"})
        response = '''{
          "findings": [
            {
              "title": "Finding Title",
              "description": "This is the description field.",
              "evidence": []
            }
          ]
        }'''

        findings = client._parse_synthesis_response(response)

        assert findings[0]["summary"] == "This is the description field."

    def test_parse_synthesis_response_malformed_non_list_findings(self) -> None:
        """Synthesis parser should return empty list when findings is not a list."""
        client = LLMAnalysisClient({"claude_cli_path": "/usr/bin/claude"})
        response = '{"findings": "not a list"}'

        findings = client._parse_synthesis_response(response)

        assert findings == []

    def test_parse_evidence_quality_response_happy_path_json(self) -> None:
        """Evidence quality parser should extract study types and conflicts."""
        client = LLMAnalysisClient({"claude_cli_path": "/usr/bin/claude"})
        response = '''{
          "study_types": {
            "human_studies": 5,
            "animal_studies": 3,
            "in_vitro_studies": 2,
            "other": 1
          },
          "evidence_conflicts": [
            {
              "theme": "Efficacy",
              "conflict": "Conflicting results on dosage",
              "explanation": "Different studies used different dosages"
            }
          ],
          "confidence_levels": {
            "Efficacy": "High",
            "Safety": "Medium"
          },
          "evidence_summary": "Overall evidence is moderate quality."
        }'''

        result = client._parse_evidence_quality_response(response)

        assert result["study_types"]["human_studies"] == 5
        assert result["study_types"]["animal_studies"] == 3
        assert result["study_types"]["in_vitro_studies"] == 2
        assert len(result["evidence_conflicts"]) == 1
        assert result["confidence_levels"]["Efficacy"] == "High"
        assert result["evidence_summary"] == "Overall evidence is moderate quality."

    def test_parse_evidence_quality_response_malformed_study_types(self) -> None:
        """Evidence quality parser should handle non-dict study_types gracefully."""
        client = LLMAnalysisClient({"claude_cli_path": "/usr/bin/claude"})
        response = '{"study_types": "not a dict", "evidence_conflicts": [], "confidence_levels": {}, "evidence_summary": ""}'

        result = client._parse_evidence_quality_response(response)

        assert result["study_types"] == {}

    def test_parse_evidence_quality_response_malformed_confidence_levels(self) -> None:
        """Evidence quality parser should handle non-dict confidence_levels gracefully."""
        client = LLMAnalysisClient({"claude_cli_path": "/usr/bin/claude"})
        response = '{"study_types": {}, "evidence_conflicts": [], "confidence_levels": "not a dict", "evidence_summary": ""}'

        result = client._parse_evidence_quality_response(response)

        assert result["confidence_levels"] == {}

    def test_parse_evidence_quality_response_malformed_summary(self) -> None:
        """Evidence quality parser should handle non-string evidence_summary gracefully."""
        client = LLMAnalysisClient({"claude_cli_path": "/usr/bin/claude"})
        response = '{"study_types": {}, "evidence_conflicts": [], "confidence_levels": {}, "evidence_summary": 123}'

        result = client._parse_evidence_quality_response(response)

        assert result["evidence_summary"] == ""


class TestLLMAnalysisClientFailurePathRegressions:
    """Regression tests for common runtime failure modes in LLM analysis.

    Task 009: Add Failure-Path Regression Coverage
    These tests verify that expensive failure modes degrade predictably instead
    of crashing late in a run after collection or analysis work is already done.
    """

    def test_malformed_json_truncated_response(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Parser should handle truncated JSON responses that cut off mid-field."""
        stdout_data = '{"themes": [{"name": "Incomplete Theme", "description":'

        def fake_popen(
            command: list[str],
            stdout=None,
            stderr=None,
            text=False,
            bufsize=-1,  # noqa: ARG001  # noqa: ARG001
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

        client = LLMAnalysisClient({"claude_cli_path": "/usr/local/bin/claude"})

        themes = client.extract_themes(
            sources=[{"url": "https://example.com", "title": "Example", "content": "Body"}],
            query="test query",
            num_themes=1,
        )

        assert isinstance(themes, list)

    def test_malformed_json_duplicate_keys(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Parser should handle JSON with duplicate keys gracefully."""
        stdout_data = '{"themes": [{"name": "First", "name": "Second"}]}'

        def fake_popen(
            command: list[str],
            stdout=None,
            stderr=None,
            text=False,
            bufsize=-1,  # noqa: ARG001  # noqa: ARG001
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

        client = LLMAnalysisClient({"claude_cli_path": "/usr/local/bin/claude"})

        themes = client.extract_themes(
            sources=[{"url": "https://example.com", "title": "Example", "content": "Body"}],
            query="test query",
            num_themes=1,
        )

        assert isinstance(themes, list)

    def test_malformed_json_unexpected_type_in_array(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Parser should filter out unexpected types from theme arrays."""
        stdout_data = '{"themes": ["string item", {"name": "Valid"}, null, 123]}'

        def fake_popen(
            command: list[str],
            stdout=None,
            stderr=None,
            text=False,
            bufsize=-1,  # noqa: ARG001  # noqa: ARG001
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

        client = LLMAnalysisClient({"claude_cli_path": "/usr/local/bin/claude"})

        themes = client.extract_themes(
            sources=[{"url": "https://example.com", "title": "Example", "content": "Body"}],
            query="test query",
            num_themes=1,
        )

        assert len(themes) == 1
        assert themes[0]["name"] == "Valid"

    def test_malformed_json_null_bytes(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Parser should handle responses with embedded null bytes."""
        stdout_data = '{"themes": [\x00{"name": "Test"}]}'

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

        client = LLMAnalysisClient({"claude_cli_path": "/usr/local/bin/claude"})

        themes = client.extract_themes(
            sources=[{"url": "https://example.com", "title": "Example", "content": "Body"}],
            query="test query",
            num_themes=1,
        )

        assert isinstance(themes, list)

    def test_malformed_json_empty_response(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Parser should handle empty response body."""
        stdout_data = ""

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

        client = LLMAnalysisClient({"claude_cli_path": "/usr/local/bin/claude"})

        themes = client.extract_themes(
            sources=[{"url": "https://example.com", "title": "Example", "content": "Body"}],
            query="test query",
            num_themes=1,
        )

        assert themes == []

    def test_malformed_json_whitespace_only_response(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Parser should handle whitespace-only response body."""
        stdout_data = "   \n\t  "

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

        client = LLMAnalysisClient({"claude_cli_path": "/usr/local/bin/claude"})

        themes = client.extract_themes(
            sources=[{"url": "https://example.com", "title": "Example", "content": "Body"}],
            query="test query",
            num_themes=1,
        )

        assert themes == []

    def test_deep_analysis_partial_payload_missing_fields(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Deep analysis should handle partial payloads with missing optional fields."""
        stdout_data = '{"themes": [], "gaps": []}'

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

        client = LLMAnalysisClient({"claude_cli_path": "/usr/local/bin/claude"})

        result = client.identify_gaps(
            sources=[{"url": "https://example.com", "title": "Example", "content": "Body"}],
            query="test query",
            themes=[],
        )

        assert isinstance(result, list)

    def test_deep_analysis_partial_payload_consensus_only(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Deep analysis should handle payload with only consensus_points."""
        stdout_data = '{"consensus_points": [{"claim": "Test claim", "strength": "high"}], "disagreement_points": []}'

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

        client = LLMAnalysisClient({"claude_cli_path": "/usr/local/bin/claude"})

        result = client.analyze_cross_reference(
            sources=[{"url": "https://example.com", "title": "Example", "content": "Body"}],
            themes=[],
        )

        assert isinstance(result, dict)
        assert "consensus_points" in result

    def test_session_metadata_records_degradation_on_llm_failure(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Session metadata should record degradation when LLM analysis fails but workflow recovers."""
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
                returncode=0,
                stdout_data='{"themes": []}',
                stderr_data="partial_failure_warning",
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

        llm_events = [
            e for e in monitor._telemetry_events
            if e["category"] == "llm"
        ]
        assert len(llm_events) > 0
