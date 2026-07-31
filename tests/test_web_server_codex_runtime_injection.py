"""Runtime-identity tests for dashboard-created generation paths."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

import pytest

from cc_deep_research.config import Config
from cc_deep_research.content_gen._services import build_content_gen_services
from cc_deep_research.content_gen.agents.backlog_chat import BacklogChatAgent
from cc_deep_research.content_gen.agents.backlog_triage import BatchTriageAgent
from cc_deep_research.content_gen.agents.brief_assistant import BriefAssistantAgent
from cc_deep_research.content_gen.agents.brief_to_backlog import generate_backlog_from_brief
from cc_deep_research.content_gen.agents.execution_brief import ExecutionBriefAgent
from cc_deep_research.content_gen.agents.next_action import NextActionAgent
from cc_deep_research.content_gen.models import BriefRevision
from cc_deep_research.content_gen.pipeline import ContentGenPipeline
from cc_deep_research.content_gen.progress import PipelineRunJobRegistry
from cc_deep_research.event_router import EventRouter
from cc_deep_research.llm.runtime_context import LLMRuntimeContext
from cc_deep_research.monitoring import ResearchMonitor
from cc_deep_research.research_runs.service import ResearchRunService


@pytest.mark.parametrize(
    "agent_factory",
    [
        BriefAssistantAgent,
        BacklogChatAgent,
        BatchTriageAgent,
        NextActionAgent,
        ExecutionBriefAgent,
    ],
)
def test_route_level_content_agents_use_injected_runtime(
    agent_factory: Callable[..., Any],
) -> None:
    runtime = object()
    llm_runtime = LLMRuntimeContext(codex_runtime=runtime)  # type: ignore[arg-type]

    agent = agent_factory(Config(), llm_runtime=llm_runtime)

    assert agent._router._codex_runtime is runtime


@pytest.mark.parametrize(
    ("stage_name", "agent_name"),
    [
        ("opportunity", "opportunity"),
        ("backlog", "backlog"),
        ("angle", "thesis"),
        ("research", "research"),
        ("argument_map", "argument_map"),
        ("scripting", "scripting"),
        ("visual", "visual"),
        ("production", "production"),
        ("packaging", "packaging"),
        ("qc", "qc"),
        ("publish", "publish"),
    ],
)
def test_pipeline_stage_agents_use_injected_runtime(
    stage_name: str,
    agent_name: str,
) -> None:
    runtime = object()
    llm_runtime = LLMRuntimeContext(codex_runtime=runtime)  # type: ignore[arg-type]
    pipeline = ContentGenPipeline(Config(), llm_runtime=llm_runtime)

    stage = pipeline._create_stage(stage_name)
    agent = stage._create_agent(agent_name)

    assert agent._router._codex_runtime is runtime


def test_content_service_graph_owns_one_codex_runtime() -> None:
    runtime = object()
    llm_runtime = LLMRuntimeContext(codex_runtime=runtime)  # type: ignore[arg-type]

    services = build_content_gen_services(
        config=Config(),
        event_router=EventRouter(),
        job_registry=PipelineRunJobRegistry(),
        llm_runtime=llm_runtime,
    )

    assert services.llm_runtime is llm_runtime
    assert services.pipeline_service._llm_runtime is llm_runtime
    assert services.scripting_api_service._llm_runtime is llm_runtime


@pytest.mark.asyncio
async def test_brief_to_backlog_router_uses_injected_runtime(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from cc_deep_research.content_gen.agents import brief_to_backlog

    runtime = object()
    llm_runtime = LLMRuntimeContext(codex_runtime=runtime)  # type: ignore[arg-type]
    captured: dict[str, object] = {}

    def capture_router(
        _config: Config,
        *,
        llm_runtime: LLMRuntimeContext,
    ) -> object:
        captured["runtime"] = llm_runtime.codex_runtime
        return object()

    async def fake_llm_call(**_kwargs: object) -> str:
        return '{"reply_markdown":"ok","items":[],"warnings":[]}'

    monkeypatch.setattr(brief_to_backlog, "create_agent_llm_router", capture_router)
    monkeypatch.setattr(brief_to_backlog, "call_agent_llm_text", fake_llm_call)
    revision = BriefRevision(
        brief_id="brief-runtime",
        version=1,
        theme="Runtime identity",
        goal="Keep one authenticated runtime",
        primary_audience_segment="Operators",
        content_objective="Verify dependency ownership",
    )

    await generate_backlog_from_brief(
        revision,
        Config(),
        llm_runtime=llm_runtime,
    )

    assert captured["runtime"] is runtime


def test_research_service_binds_runtime_to_orchestrator_and_reporter() -> None:
    runtime = object()
    captured: dict[str, object] = {}

    def capture_output(**kwargs: object) -> Any:
        captured.update(kwargs)
        return object()

    service = ResearchRunService(
        output_materializer=capture_output,
        codex_runtime=runtime,
    )
    config = Config()
    monitor = ResearchMonitor(enabled=False)

    orchestrator = service.orchestrator_factory(
        config=config,
        monitor=monitor,
        concurrent_source_collection=False,
        max_concurrent_sources=1,
    )
    service.output_materializer(
        config=config,
        monitor=monitor,
        reporter=None,
    )

    assert orchestrator._runtime._codex_runtime is runtime
    assert captured["reporter"]._llm_router._codex_runtime is runtime
