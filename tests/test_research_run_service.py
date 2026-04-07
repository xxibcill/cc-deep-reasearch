"""Tests for the shared research run service."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

import pytest

from cc_deep_research.config import Config
from cc_deep_research.models import ResearchDepth, ResearchSession
from cc_deep_research.monitoring import ResearchMonitor
from cc_deep_research.research_runs import (
    AsyncioResearchRunExecutionAdapter,
    ResearchOutputFormat,
    ResearchRunCancelled,
    ResearchRunReport,
    ResearchRunRequest,
    ResearchRunResult,
    ResearchRunService,
)


class StubEventRouter:
    """Event router double for lifecycle assertions."""

    def __init__(self) -> None:
        self.started = 0
        self.stopped = 0
        self.active = False

    async def start(self) -> None:
        self.started += 1
        self.active = True

    async def stop(self) -> None:
        self.stopped += 1
        self.active = False

    def is_active(self) -> bool:
        return self.active


def _sample_session(query: str = "test query") -> ResearchSession:
    """Build a compact session fixture."""
    return ResearchSession(
        session_id="session-123",
        query=query,
        depth=ResearchDepth.STANDARD,
        started_at=datetime(2024, 1, 1, 12, 0, 0),
        completed_at=datetime(2024, 1, 1, 12, 5, 0),
    )


def test_run_executes_shared_workflow_and_materializes_result() -> None:
    """The shared service should own config, orchestration, and output materialization."""
    captured: dict[str, object] = {}
    session = _sample_session()
    router = StubEventRouter()

    class StubOrchestrator:
        def __init__(self, **kwargs) -> None:
            captured["orchestrator_kwargs"] = kwargs

        async def execute_research(
            self,
            *,
            query: str,
            depth: ResearchDepth,
            min_sources: int | None = None,
            phase_hook=None,
            **_kwargs,
        ) -> ResearchSession:
            captured["execute_args"] = {
                "query": query,
                "depth": depth,
                "min_sources": min_sources,
                "phase_hook": phase_hook,
            }
            if phase_hook is not None:
                phase_hook("phase", "Collecting sources")
            return session

    def output_materializer(**kwargs) -> ResearchRunResult:
        captured["materialize_kwargs"] = kwargs
        return ResearchRunResult(
            session=kwargs["session"],
            report=ResearchRunReport(
                format=ResearchOutputFormat.MARKDOWN,
                content="# Report",
                path=Path("report.md"),
                media_type="text/markdown",
            ),
        )

    service = ResearchRunService(
        config_loader=lambda: Config(),
        orchestrator_factory=StubOrchestrator,
        output_materializer=output_materializer,
    )
    request = ResearchRunRequest(
        query=session.query,
        depth=ResearchDepth.STANDARD,
        min_sources=3,
        search_providers=["CLAUDE"],
        parallel_mode=False,
        realtime_enabled=True,
    )
    adapter = AsyncioResearchRunExecutionAdapter()

    result = service.run(
        request,
        execution_adapter=adapter,
        event_router=router,
    )

    assert result.session_id == session.session_id
    assert router.started == 1
    assert router.stopped == 1

    orchestrator_kwargs = captured["orchestrator_kwargs"]
    assert isinstance(orchestrator_kwargs, dict)
    assert orchestrator_kwargs["parallel_mode"] is False
    assert orchestrator_kwargs["num_researchers"] is None
    assert orchestrator_kwargs["config"].search.providers == ["claude"]

    execute_args = captured["execute_args"]
    assert isinstance(execute_args, dict)
    assert execute_args["query"] == session.query
    assert execute_args["depth"] == ResearchDepth.STANDARD
    assert execute_args["min_sources"] == 3
    assert execute_args["phase_hook"] is None

    materialize_kwargs = captured["materialize_kwargs"]
    assert isinstance(materialize_kwargs, dict)
    assert materialize_kwargs["session"] is session
    assert materialize_kwargs["request"] == request
    assert isinstance(materialize_kwargs["monitor"], ResearchMonitor)
    assert materialize_kwargs["config"].search.providers == ["claude"]


def test_run_finalizes_failed_monitor_when_execution_raises() -> None:
    """Execution failures should still produce a failed session summary for callers."""
    monitor = ResearchMonitor(enabled=False, persist=False)

    class FailingOrchestrator:
        def __init__(self, *, monitor: ResearchMonitor, **_kwargs) -> None:
            self._monitor = monitor

        async def execute_research(self, **_kwargs) -> ResearchSession:
            self._monitor.set_session("session-123", "test query", "deep")
            raise RuntimeError("boom")

    service = ResearchRunService(
        config_loader=lambda: Config(),
        orchestrator_factory=FailingOrchestrator,
    )

    with pytest.raises(RuntimeError, match="boom"):
        service.run(
            ResearchRunRequest(query="test query", depth=ResearchDepth.DEEP),
            monitor=monitor,
        )

    assert any(
        event["event_type"] == "session.finished" and event["status"] == "failed"
        for event in monitor._telemetry_events
    )


def test_run_finalizes_interrupted_monitor_when_cancelled() -> None:
    """Operator cancellation should produce an interrupted terminal session event."""
    monitor = ResearchMonitor(enabled=False, persist=False)
    started_sessions: list[str] = []

    class CancellableOrchestrator:
        def __init__(self, *, monitor: ResearchMonitor, **_kwargs) -> None:
            self._monitor = monitor

        async def execute_research(
            self,
            *,
            query: str,
            depth: ResearchDepth,
            on_session_started=None,
            **_kwargs,
        ) -> ResearchSession:
            session_id = "session-cancelled"
            self._monitor.set_session(session_id, query, depth.value)
            if on_session_started is not None:
                on_session_started(session_id)
            raise ResearchRunCancelled("cancelled")

    service = ResearchRunService(
        config_loader=lambda: Config(),
        orchestrator_factory=CancellableOrchestrator,
    )

    with pytest.raises(ResearchRunCancelled):
        service.run(
            ResearchRunRequest(query="test query", depth=ResearchDepth.DEEP),
            monitor=monitor,
            on_session_started=started_sessions.append,
        )

    assert started_sessions == ["session-cancelled"]
    assert any(
        event["event_type"] == "session.finished" and event["status"] == "interrupted"
        for event in monitor._telemetry_events
    )


def test_prepare_builds_prompt_registry_from_request_overrides() -> None:
    """Prepared runs should carry normalized prompt overrides into execution state."""
    service = ResearchRunService(config_loader=lambda: Config())

    prepared = service.prepare(
        ResearchRunRequest(
            query="test query",
            agent_prompt_overrides={
                "analyzer": {
                    "prompt_prefix": "Prioritize primary sources.",
                }
            },
        )
    )

    assert prepared.prompt_registry.has_overrides() is True
    effective_overrides = prepared.prompt_registry.get_effective_overrides()
    assert effective_overrides["analyzer"] == {
        "prompt_prefix": "Prioritize primary sources.",
        "system_prompt": None,
    }


def test_run_preserves_missing_provider_configuration_metadata() -> None:
    """Requested providers that cannot initialize should still surface degraded session metadata."""
    captured: dict[str, object] = {}
    provider_warning = (
        "Provider 'claude' is selected but no Claude search provider is implemented yet."
    )
    session = _sample_session("provider config").model_copy(
        update={
            "metadata": {
                "providers": {
                    "configured": ["claude"],
                    "available": [],
                    "warnings": [provider_warning],
                },
                "execution": {
                    "parallel_requested": False,
                    "parallel_used": False,
                    "degraded": True,
                    "degraded_reasons": [provider_warning],
                },
            }
        },
        deep=True,
    )

    class StubOrchestrator:
        def __init__(self, **kwargs) -> None:
            captured["orchestrator_config"] = kwargs["config"]

        async def execute_research(self, **_kwargs) -> ResearchSession:
            return session

    def output_materializer(**kwargs) -> ResearchRunResult:
        captured["materialize_config"] = kwargs["config"]
        return ResearchRunResult(
            session=kwargs["session"],
            report=ResearchRunReport(
                format=ResearchOutputFormat.MARKDOWN,
                content="# Report",
                path=Path("report.md"),
                media_type="text/markdown",
            ),
        )

    service = ResearchRunService(
        config_loader=lambda: Config(),
        orchestrator_factory=StubOrchestrator,
        output_materializer=output_materializer,
    )

    result = service.run(
        ResearchRunRequest(
            query="provider config",
            depth=ResearchDepth.STANDARD,
            search_providers=["claude"],
        ),
        execution_adapter=AsyncioResearchRunExecutionAdapter(),
    )

    orchestrator_config = captured["orchestrator_config"]
    assert isinstance(orchestrator_config, Config)
    assert orchestrator_config.search.providers == ["claude"]
    materialize_config = captured["materialize_config"]
    assert isinstance(materialize_config, Config)
    assert materialize_config.search.providers == ["claude"]
    assert result.session.metadata["providers"]["status"] == "unavailable"
    assert result.session.metadata["providers"]["warnings"] == [provider_warning]
    assert result.session.metadata["execution"]["degraded"] is True
    assert result.session.metadata["execution"]["degraded_reasons"] == [provider_warning]
