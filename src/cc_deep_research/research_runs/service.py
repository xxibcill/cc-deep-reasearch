"""Shared service for end-to-end research run execution."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Protocol

from cc_deep_research.config import Config, load_config
from cc_deep_research.event_router import EventRouter
from cc_deep_research.models import ResearchSession
from cc_deep_research.monitoring import STOP_REASON_DEGRADED_EXECUTION, ResearchMonitor
from cc_deep_research.orchestrator import TeamResearchOrchestrator
from cc_deep_research.orchestration import PlannerResearchOrchestrator
from cc_deep_research.pdf_generator import PDFGenerator
from cc_deep_research.prompts import PromptRegistry
from cc_deep_research.reporting import ReportGenerator
from cc_deep_research.research_runs.models import (
    ResearchRunCancelled,
    ResearchRunRequest,
    ResearchRunResult,
    ResearchWorkflow,
)
from cc_deep_research.research_runs.options import (
    apply_research_request_config_overrides,
    create_prompt_registry_with_overrides,
)
from cc_deep_research.research_runs.output import materialize_research_run_output
from cc_deep_research.session_store import SessionStore

PhaseHook = Callable[[str, str], None]
CancellationCheck = Callable[[], None]
SessionStartedCallback = Callable[[str], None]


@dataclass(slots=True)
class PreparedResearchRun:
    """Resolved request state used to execute a shared research run."""

    request: ResearchRunRequest
    config: Config
    prompt_registry: PromptRegistry


class ResearchRunExecutionAdapter(Protocol):
    """Adapter interface for caller-specific execution UX."""

    def execute(
        self,
        *,
        execute_with_phase_hook: Callable[[PhaseHook | None], Awaitable[ResearchSession]],
    ) -> ResearchSession:
        """Execute the research workflow and return the completed session."""


class AsyncioResearchRunExecutionAdapter:
    """Default execution adapter that runs the workflow in-process."""

    def __init__(
        self,
        *,
        phase_hook: PhaseHook | None = None,
        runner: Callable[[Awaitable[ResearchSession]], ResearchSession] = asyncio.run,
    ) -> None:
        self._phase_hook = phase_hook
        self._runner = runner

    def execute(
        self,
        *,
        execute_with_phase_hook: Callable[[PhaseHook | None], Awaitable[ResearchSession]],
    ) -> ResearchSession:
        """Execute the coroutine with the configured phase hook."""
        return self._runner(execute_with_phase_hook(self._phase_hook))


@dataclass(slots=True)
class ResearchRunService:
    """Own the reusable end-to-end research execution flow."""

    config_loader: Callable[[], Config] = load_config
    config_override_applier: Callable[[Config, ResearchRunRequest], Config] = (
        apply_research_request_config_overrides
    )
    orchestrator_factory: Callable[..., TeamResearchOrchestrator] = TeamResearchOrchestrator
    output_materializer: Callable[..., ResearchRunResult] = materialize_research_run_output

    def prepare(
        self,
        request: ResearchRunRequest,
        *,
        config: Config | None = None,
    ) -> PreparedResearchRun:
        """Resolve a request into the config that will be used for execution."""
        base_config = config.model_copy(deep=True) if config is not None else self.config_loader()
        resolved_config = self.config_override_applier(base_config, request)
        prompt_registry = create_prompt_registry_with_overrides(request)
        return PreparedResearchRun(
            request=request,
            config=resolved_config,
            prompt_registry=prompt_registry,
        )

    def run(
        self,
        request: ResearchRunRequest,
        *,
        config: Config | None = None,
        monitor: ResearchMonitor | None = None,
        execution_adapter: ResearchRunExecutionAdapter | None = None,
        event_router: EventRouter | None = None,
        session_store: SessionStore | None = None,
        reporter: ReportGenerator | None = None,
        pdf_generator: PDFGenerator | None = None,
        cancellation_check: CancellationCheck | None = None,
        on_session_started: SessionStartedCallback | None = None,
    ) -> ResearchRunResult:
        """Prepare and execute a research run from a request."""
        prepared = self.prepare(request, config=config)
        return self.run_prepared(
            prepared,
            monitor=monitor,
            execution_adapter=execution_adapter,
            event_router=event_router,
            session_store=session_store,
            reporter=reporter,
            pdf_generator=pdf_generator,
            cancellation_check=cancellation_check,
            on_session_started=on_session_started,
        )

    def run_prepared(
        self,
        prepared: PreparedResearchRun,
        *,
        monitor: ResearchMonitor | None = None,
        execution_adapter: ResearchRunExecutionAdapter | None = None,
        event_router: EventRouter | None = None,
        session_store: SessionStore | None = None,
        reporter: ReportGenerator | None = None,
        pdf_generator: PDFGenerator | None = None,
        cancellation_check: CancellationCheck | None = None,
        on_session_started: SessionStartedCallback | None = None,
    ) -> ResearchRunResult:
        """Execute a pre-resolved research run."""
        active_monitor = monitor or ResearchMonitor(enabled=False)
        if prepared.request.realtime_enabled:
            active_monitor.set_event_router(event_router)

        # Select orchestrator based on workflow type
        if prepared.request.workflow == ResearchWorkflow.PLANNER:
            orchestrator = PlannerResearchOrchestrator(
                config=prepared.config,
                monitor=active_monitor,
            )
        else:
            orchestrator = self.orchestrator_factory(
                config=prepared.config,
                monitor=active_monitor,
                parallel_mode=prepared.request.parallel_mode,
                num_researchers=prepared.request.num_researchers,
                prompt_registry=prepared.prompt_registry,
            )
        adapter = execution_adapter or AsyncioResearchRunExecutionAdapter()

        try:
            session = adapter.execute(
                execute_with_phase_hook=lambda phase_hook: self._execute_session(
                    orchestrator=orchestrator,
                    request=prepared.request,
                    event_router=event_router,
                    phase_hook=phase_hook,
                    cancellation_check=cancellation_check,
                    on_session_started=on_session_started,
                )
            )
        except ResearchRunCancelled:
            self._finalize_cancelled_monitor(active_monitor)
            raise
        except Exception:
            self._finalize_failed_monitor(active_monitor)
            raise

        return self.output_materializer(
            session=session,
            config=prepared.config,
            request=prepared.request,
            monitor=active_monitor,
            session_store=session_store,
            reporter=reporter,
            pdf_generator=pdf_generator,
        )

    async def _execute_session(
        self,
        *,
        orchestrator: TeamResearchOrchestrator,
        request: ResearchRunRequest,
        event_router: EventRouter | None,
        phase_hook: PhaseHook | None,
        cancellation_check: CancellationCheck | None,
        on_session_started: SessionStartedCallback | None,
    ) -> ResearchSession:
        """Run the orchestrator and manage optional realtime startup."""
        router_started = False
        self._check_cancelled(cancellation_check)
        if request.realtime_enabled and event_router is not None and not event_router.is_active():
            await event_router.start()
            router_started = True

        try:
            self._check_cancelled(cancellation_check)
            return await orchestrator.execute_research(
                query=request.query,
                depth=request.depth,
                min_sources=request.min_sources,
                phase_hook=phase_hook,
                cancellation_check=cancellation_check,
                on_session_started=on_session_started,
            )
        finally:
            if router_started:
                await event_router.stop()

    def _check_cancelled(self, cancellation_check: CancellationCheck | None) -> None:
        """Raise when the caller has requested cancellation."""
        if cancellation_check is not None:
            cancellation_check()

    def _finalize_cancelled_monitor(self, monitor: ResearchMonitor) -> None:
        """Emit an interrupted summary when execution is stopped by an operator."""
        if monitor.session_id is None:
            return
        monitor.finalize_session(
            total_sources=0,
            providers=[],
            total_time_ms=0,
            status="interrupted",
            stop_reason=STOP_REASON_DEGRADED_EXECUTION,
        )

    def _finalize_failed_monitor(self, monitor: ResearchMonitor) -> None:
        """Emit a failed session summary when execution aborts mid-run."""
        if monitor.session_id is None:
            return
        monitor.finalize_session(
            total_sources=0,
            providers=[],
            total_time_ms=0,
            status="failed",
            stop_reason=STOP_REASON_DEGRADED_EXECUTION,
        )


__all__ = [
    "AsyncioResearchRunExecutionAdapter",
    "PreparedResearchRun",
    "ResearchRunExecutionAdapter",
    "ResearchRunService",
]
