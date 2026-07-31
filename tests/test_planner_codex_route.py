"""Planner-workflow coverage for the shared Codex routing boundary."""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any, cast

import pytest

import cc_deep_research.research_runs.service as research_run_service_module
from cc_deep_research.config import (
    Config,
    LLMCodexConfig,
    LLMConfig,
    LLMRouteDefaults,
)
from cc_deep_research.llm.codex import CodexTransport
from cc_deep_research.llm.codex_runtime import CodexRuntime, CodexTurnResult
from cc_deep_research.models import (
    AnalysisResult,
    ResearchDepth,
    ResearchPlan,
    ResearchSession,
    ResearchSubtask,
    SearchResultItem,
)
from cc_deep_research.orchestration.planner_orchestrator import (
    PlannerResearchOrchestrator,
)
from cc_deep_research.reporting import ReportGenerator
from cc_deep_research.research_runs import (
    ResearchOutputFormat,
    ResearchRunReport,
    ResearchRunRequest,
    ResearchRunResult,
    ResearchRunService,
    ResearchWorkflow,
)


class AvailableCodexRuntime:
    """Minimal authenticated runtime double used by transport availability checks."""

    is_authenticated = True
    can_attempt_start = True


class RecordingCodexRuntime(AvailableCodexRuntime):
    """Return valid semantic-analysis payloads and record every routed turn."""

    def __init__(self) -> None:
        self.prompts: list[str] = []

    async def run_turn(self, *, prompt: str, **_kwargs: Any) -> CodexTurnResult:
        self.prompts.append(prompt)
        content = json.dumps(
            {
                "themes": [
                    {
                        "name": "Shared routing",
                        "description": "The planner uses the configured shared LLM route.",
                        "key_points": ["Codex handled the semantic analysis request."],
                        "supporting_sources": ["https://example.com/source"],
                    }
                ],
                "consensus_points": [],
                "disagreement_points": [],
                "gaps": [],
                "findings": [
                    {
                        "title": "Planner uses Codex",
                        "description": "The injected runtime completed the analysis.",
                        "evidence": ["https://example.com/source"],
                        "confidence": "High",
                    }
                ],
            }
        )
        return CodexTurnResult(
            content=content,
            model="gpt-5.6-sol",
            turn_id=f"turn-{len(self.prompts)}",
            duration_ms=1,
            finish_reason="completed",
        )


def _codex_config() -> Config:
    return Config(
        llm=LLMConfig(
            codex=LLMCodexConfig(enabled=True, model="gpt-5.6-sol"),
            route_defaults=LLMRouteDefaults(analyzer="codex"),
            fallback_order=["codex", "heuristic"],
        )
    )


def _session() -> ResearchSession:
    return ResearchSession(
        session_id="planner-session",
        query="planner routing",
        depth=ResearchDepth.STANDARD,
        started_at=datetime(2024, 1, 1, 12, 0, 0),
        completed_at=datetime(2024, 1, 1, 12, 1, 0),
    )


@pytest.mark.asyncio
async def test_planner_analyzer_uses_injected_codex_runtime() -> None:
    runtime = cast(CodexRuntime, AvailableCodexRuntime())
    config = _codex_config()
    orchestrator = PlannerResearchOrchestrator(
        config=config,
        codex_runtime=runtime,
    )

    await orchestrator._initialize_agents(ResearchDepth.STANDARD)

    analyzer = orchestrator._agents["analyzer"]
    analyzer_router = analyzer._ai_service._llm_router
    assert analyzer._ai_service._config == config.research.model_dump(mode="python")
    assert analyzer_router is orchestrator._llm_router

    transport = analyzer_router.get_transport("analyzer")
    assert isinstance(transport, CodexTransport)
    assert transport._runtime is runtime


@pytest.mark.asyncio
async def test_planner_analyze_handler_executes_through_injected_codex_runtime(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "cc_deep_research.llm.codex.append_usage_entry",
        lambda _entry: None,
    )
    runtime_double = RecordingCodexRuntime()
    runtime = cast(CodexRuntime, runtime_double)
    orchestrator = PlannerResearchOrchestrator(
        config=_codex_config(),
        codex_runtime=runtime,
    )
    await orchestrator._initialize_agents(ResearchDepth.STANDARD)

    source = SearchResultItem(
        url="https://example.com/source",
        title="Planner routing evidence",
        content=(
            "This source provides detailed evidence that is long enough to trigger "
            "semantic analysis through the configured language model route. "
        )
        * 4,
    )
    task = ResearchSubtask(
        id="analyze",
        title="Analyze routing",
        description="Analyze the collected evidence.",
        task_type="analyze",
        dependencies=["search"],
    )
    plan = ResearchPlan(
        plan_id="plan-codex",
        query="Does the planner use Codex?",
        summary="Verify planner routing.",
        subtasks=[task],
    )

    result = await orchestrator._handle_analyze_task(
        task=task,
        plan=plan,
        dependency_outputs={"search": {"sources": [source]}},
    )

    analysis = result["analysis"]
    assert isinstance(analysis, AnalysisResult)
    assert analysis.analysis_method == "ai_semantic"
    assert analysis.key_findings[0].title == "Planner uses Codex"
    assert len(runtime_double.prompts) == 4


def test_research_run_service_passes_runtime_to_planner_workflow(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, Any] = {}
    runtime = cast(CodexRuntime, AvailableCodexRuntime())
    session = _session()

    class StubPlannerOrchestrator:
        def __init__(self, **kwargs: Any) -> None:
            captured["planner_kwargs"] = kwargs

        async def execute_research(self, **_kwargs: Any) -> ResearchSession:
            return session

    def output_materializer(**kwargs: Any) -> ResearchRunResult:
        return ResearchRunResult(
            session=kwargs["session"],
            report=ResearchRunReport(
                format=ResearchOutputFormat.MARKDOWN,
                content="# Planner report",
                media_type="text/markdown",
            ),
        )

    monkeypatch.setattr(
        research_run_service_module,
        "PlannerResearchOrchestrator",
        StubPlannerOrchestrator,
    )
    service = ResearchRunService(
        config_loader=_codex_config,
        output_materializer=output_materializer,
        codex_runtime=runtime,
    )

    service.run(
        ResearchRunRequest(
            query=session.query,
            workflow=ResearchWorkflow.PLANNER,
        ),
        reporter=cast(ReportGenerator, object()),
    )

    planner_kwargs = captured["planner_kwargs"]
    assert planner_kwargs["codex_runtime"] is runtime
