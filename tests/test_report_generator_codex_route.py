"""Focused coverage for routed report generation through Codex."""

from __future__ import annotations

import asyncio
from typing import Any

import pytest

from cc_deep_research.agents.reporter import ReporterAgent
from cc_deep_research.config import Config
from cc_deep_research.llm.codex_runtime import CodexTurnResult
from cc_deep_research.models import ResearchDepth, ResearchSession, SearchResultItem
from cc_deep_research.reporting import ReportGenerator


class RecordingCodexRuntime:
    def __init__(self, response_content: str) -> None:
        self.is_authenticated = True
        self.can_attempt_start = False
        self._response_content = response_content
        self.calls: list[dict[str, Any]] = []

    async def run_turn(
        self,
        *,
        prompt: str,
        model: str | None,
        developer_instructions: str | None,
        reasoning_effort: str | None,
        timeout_seconds: int,
    ) -> CodexTurnResult:
        self.calls.append(
            {
                "prompt": prompt,
                "model": model,
                "developer_instructions": developer_instructions,
                "reasoning_effort": reasoning_effort,
                "timeout_seconds": timeout_seconds,
            }
        )
        return CodexTurnResult(
            content=self._response_content,
            model=model or "gpt-5.6-sol",
            turn_id="turn-reporter",
            duration_ms=23,
            finish_reason="completed",
            input_tokens=100,
            output_tokens=200,
            total_tokens=300,
        )


def _report_config(*, reporter_route: str = "codex") -> Config:
    config = Config()
    config.llm.codex.enabled = True
    config.llm.codex.model = "gpt-5.6-sol"
    config.llm.codex.reasoning_effort = "high"
    config.llm.route_defaults.reporter = reporter_route
    config.research.quality.enable_report_quality_evaluation = False
    config.research.quality.enable_report_refinement = False
    return config


def _analysis() -> dict[str, Any]:
    return {
        "key_findings": [],
        "themes": [],
        "themes_detailed": [],
        "consensus_points": [],
        "contention_points": [],
        "gaps": [],
        "analysis_method": "basic_keyword",
    }


def _session(*, planned_codex: bool = False) -> ResearchSession:
    metadata: dict[str, Any] = {}
    if planned_codex:
        metadata = {
            "llm_routes": {
                "planned_routes": {
                    "reporter": {
                        "transport": "codex_app_server",
                        "provider": "codex",
                        "model": "gpt-5.6-sol",
                        "source": "planner",
                    }
                }
            }
        }
    return ResearchSession(
        session_id="reporter-route",
        query="How should report routing work?",
        depth=ResearchDepth.STANDARD,
        sources=[
            SearchResultItem(
                url="https://example.com/evidence",
                title="Primary evidence",
                snippet="Evidence used by the canonical report.",
            )
        ],
        metadata=metadata,
    )


@pytest.mark.parametrize("planned_codex", [False, True])
def test_codex_reporter_route_executes_with_injected_runtime(
    planned_codex: bool,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    config = _report_config(reporter_route="anthropic" if planned_codex else "codex")
    session = _session(planned_codex=planned_codex)
    analysis = _analysis()
    deterministic = ReporterAgent({}).generate_markdown_report(session, analysis)
    codex_report = deterministic.replace(
        "Analysis reviewed 1 sources.",
        "Codex produced this routed report from the canonical evidence.",
    )
    runtime = RecordingCodexRuntime(codex_report)
    monkeypatch.setattr(
        "cc_deep_research.llm.codex.append_usage_entry",
        lambda _entry: None,
    )

    report = ReportGenerator(
        config,
        codex_runtime=runtime,  # type: ignore[arg-type]
    ).generate_markdown_report(session, analysis)

    assert report == codex_report
    assert len(runtime.calls) == 1
    assert runtime.calls[0]["model"] == "gpt-5.6-sol"
    assert runtime.calls[0]["reasoning_effort"] == "high"
    assert runtime.calls[0]["developer_instructions"]
    assert "CANONICAL REPORT" in str(runtime.calls[0]["prompt"])
    assert session.metadata["llm_routes"]["actual_routes"]["reporter"] == {
        "transport": "codex_app_server",
        "provider": "codex",
        "model": "gpt-5.6-sol",
        "source": "actual",
    }


def test_heuristic_reporter_route_preserves_deterministic_report() -> None:
    config = _report_config(reporter_route="heuristic")
    session = _session()
    analysis = _analysis()
    generator = ReportGenerator(config)
    deterministic = generator._reporter.generate_markdown_report(session, analysis)

    report = generator.generate_markdown_report(session, analysis)

    assert report == deterministic
    assert session.metadata["llm_routes"]["actual_routes"]["reporter"] == {
        "transport": "heuristic",
        "provider": "heuristic",
        "model": "heuristic",
        "source": "actual",
    }


@pytest.mark.asyncio
async def test_async_reporter_route_keeps_owner_loop_responsive(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    config = _report_config()
    session = _session()
    analysis = _analysis()
    deterministic = ReporterAgent({}).generate_markdown_report(session, analysis)
    runtime = RecordingCodexRuntime(deterministic)
    monkeypatch.setattr(
        "cc_deep_research.llm.codex.append_usage_entry",
        lambda _entry: None,
    )
    generator = ReportGenerator(
        config,
        codex_runtime=runtime,  # type: ignore[arg-type]
    )

    report = await asyncio.wait_for(
        generator.generate_markdown_report_async(session, analysis),
        timeout=1,
    )

    assert report == deterministic
    assert len(runtime.calls) == 1


@pytest.mark.asyncio
async def test_sync_reporter_call_on_active_loop_falls_back_without_deadlock() -> None:
    config = _report_config()
    session = _session()
    analysis = _analysis()
    deterministic = ReporterAgent({}).generate_markdown_report(session, analysis)
    runtime = RecordingCodexRuntime(deterministic)
    generator = ReportGenerator(
        config,
        codex_runtime=runtime,  # type: ignore[arg-type]
    )

    report = generator.generate_markdown_report(session, analysis)

    assert report == deterministic
    assert runtime.calls == []


def test_invalid_codex_report_falls_back_to_deterministic_structure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    config = _report_config()
    session = _session()
    analysis = _analysis()
    deterministic = ReporterAgent({}).generate_markdown_report(session, analysis)
    invalid_report = deterministic.replace("[1]", "[citation]").replace(
        "https://example.com/evidence",
        "https://example.com/omitted",
    )
    runtime = RecordingCodexRuntime(invalid_report)
    generator = ReportGenerator(
        config,
        codex_runtime=runtime,  # type: ignore[arg-type]
    )
    monkeypatch.setattr(
        "cc_deep_research.llm.codex.append_usage_entry",
        lambda _entry: None,
    )

    report = generator.generate_markdown_report(session, analysis)

    assert report == deterministic
    assert len(runtime.calls) == 1
    assert session.metadata["llm_routes"]["actual_routes"]["reporter"] == {
        "transport": "heuristic",
        "provider": "heuristic",
        "model": "heuristic",
        "source": "actual",
    }
