"""Top-level execution flow for research sessions."""

from __future__ import annotations

import uuid
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from cc_deep_research.config import Config
from cc_deep_research.models.analysis import (
    AnalysisResult,
    IterationHistoryRecord,
    StrategyResult,
    ValidationResult,
)
from cc_deep_research.models.checkpoint import CheckpointOperation, CheckpointPhase
from cc_deep_research.models.search import QueryFamily, ResearchDepth, SearchResultItem
from cc_deep_research.models.session import ResearchSession
from cc_deep_research.monitoring import (
    STOP_REASON_DEGRADED_EXECUTION,
    STOP_REASON_LIMIT_REACHED,
    STOP_REASON_LOW_QUALITY,
    STOP_REASON_SUCCESS,
    ResearchMonitor,
)
from cc_deep_research.orchestration.phases import PhaseRunner
from cc_deep_research.orchestration.session_builder import SessionBuilder


def _strategy_checkpoint_output(result: StrategyResult) -> dict[str, Any]:
    """Build strategy checkpoint payloads without assuming legacy fields."""
    strategy = getattr(result, "strategy", None)
    return {
        "summary": getattr(result, "summary", None),
        "strategy_type": getattr(strategy, "strategy_type", None),
    }


class ResearchExecutionService:
    """Run the top-level research session flow."""

    def __init__(
        self,
        *,
        config: Config,
        monitor: ResearchMonitor,
        phase_runner: PhaseRunner,
        session_builder: SessionBuilder,
        configured_providers: Callable[[], list[str]],
        parallel_mode: bool,
        num_researchers: int,
    ) -> None:
        self._config = config
        self._monitor = monitor
        self._phase_runner = phase_runner
        self._session_builder = session_builder
        self._configured_providers = configured_providers
        self._parallel_mode = parallel_mode
        self._num_researchers = num_researchers

    async def execute(
        self,
        *,
        query: str,
        depth: ResearchDepth,
        min_sources: int | None,
        phase_hook: Callable[[str, str], None] | None,
        cancellation_check: Callable[[], None] | None = None,
        on_session_started: Callable[[str], None] | None = None,
        hooks: ResearchExecutionHooks,
    ) -> ResearchSession:
        """Execute a full research session using injected callbacks."""
        hooks.reset_session_state()
        start_time = datetime.utcnow()
        self._check_cancelled(cancellation_check)
        session_id = self._initialize_session(
            query=query,
            depth=depth,
            on_session_started=on_session_started,
        )

        try:
            await self._phase_runner.run_phase(
                phase_hook=phase_hook,
                phase_key="team_init",
                description="Initializing agent team",
                operation=hooks.initialize_team,
                cancellation_check=cancellation_check,
                input_ref={"parallel_mode": self._parallel_mode, "num_researchers": self._num_researchers},
            )
            strategy = await self._phase_runner.run_phase(
                phase_hook=phase_hook,
                phase_key="strategy",
                description="Analyzing research strategy",
                operation=lambda: hooks.analyze_strategy(query, depth),
                cancellation_check=cancellation_check,
                input_ref={"query": query, "depth": depth.value},
                output_transformer=_strategy_checkpoint_output,
            )
            raw_query_families = await self._phase_runner.run_phase(
                phase_hook=phase_hook,
                phase_key="query_expansion",
                description="Expanding search queries",
                operation=lambda: hooks.expand_queries(query, strategy, depth),
                cancellation_check=cancellation_check,
                input_ref={"query": query, "depth": depth.value},
                output_transformer=lambda result: {
                    "family_count": len(result),
                },
            )
            strategy.strategy.query_families = hooks.normalize_query_families(
                original_query=query,
                strategy=strategy,
                raw_families=raw_query_families,
            )
            sources = await self._phase_runner.run_phase(
                phase_hook=phase_hook,
                phase_key="source_collection",
                description="Collecting sources from providers",
                operation=lambda: hooks.collect_sources(
                    query_families=strategy.strategy.query_families,
                    depth=depth,
                    min_sources=min_sources,
                ),
                cancellation_check=cancellation_check,
                input_ref={
                    "query_family_count": len(strategy.strategy.query_families),
                    "depth": depth.value,
                    "min_sources": min_sources,
                },
                output_transformer=lambda result: {
                    "source_count": len(result),
                },
            )
            analysis, validation, sources, iteration_history = await hooks.run_analysis_workflow(
                query=query,
                depth=depth,
                strategy=strategy,
                sources=sources,
                min_sources=min_sources,
                phase_hook=phase_hook,
                cancellation_check=cancellation_check,
            )
            self._check_cancelled(cancellation_check)
            session = self._session_builder.build(
                session_id=session_id,
                query=query,
                depth=depth,
                sources=sources,
                started_at=start_time,
                strategy=strategy,
                analysis=analysis,
                validation=validation,
                iteration_history=iteration_history,
                build_metadata=hooks.build_metadata,
            )
            hooks.log_session_summary(
                source_count=len(sources),
                finding_count=len(analysis.key_findings),
                validation=validation,
            )
            self._phase_runner.notify_phase(
                phase_hook,
                phase_key="complete",
                description="Research complete",
            )
            terminal_status = self._resolve_terminal_status(session)
            self._monitor.finalize_session(
                total_sources=len(sources),
                providers=self._configured_providers(),
                total_time_ms=int(session.execution_time_seconds * 1000),
                status=terminal_status,
                stop_reason=self._resolve_stop_reason(
                    validation=validation,
                    iteration_history=iteration_history,
                ),
            )

            # Emit final session completion checkpoint
            self._monitor.emit_checkpoint(
                phase=CheckpointPhase.SESSION_COMPLETE.value,
                operation=CheckpointOperation.FINALIZE.value,
                output_ref={
                    "session_id": session_id,
                    "source_count": len(sources),
                    "finding_count": len(analysis.key_findings),
                    "status": terminal_status,
                },
                replayable=True,
            )

            return session
        except Exception as exc:
            # Emit interrupted checkpoint on failure
            self._monitor.emit_checkpoint(
                phase=CheckpointPhase.SESSION_INTERRUPTED.value,
                operation=CheckpointOperation.INTERRUPT.value,
                output_ref={
                    "error_type": type(exc).__name__,
                    "error_message": str(exc),
                    "status": "interrupted",
                },
                replayable=False,
                replayable_reason=f"Session interrupted: {type(exc).__name__}",
            )
            raise
        finally:
            self._phase_runner.notify_phase(
                phase_hook,
                phase_key="cleanup",
                description="Cleaning up team resources",
            )
            await hooks.shutdown_team()

    def _initialize_session(
        self,
        *,
        query: str,
        depth: ResearchDepth,
        on_session_started: Callable[[str], None] | None,
    ) -> str:
        """Initialize monitor state for a new research session."""
        self._monitor.section("Research Session")
        self._monitor.log(f"Query: {query}")
        self._monitor.log(f"Depth: {depth.value}")

        session_id = f"research-{uuid.uuid4().hex[:12]}"
        self._monitor.log(f"Session ID: {session_id}")
        self._monitor.set_session(
            session_id=session_id,
            query=query,
            depth=depth.value,
            parallel_mode=self._parallel_mode,
            configured_researchers=self._num_researchers,
        )

        # Emit session start checkpoint
        self._monitor.emit_checkpoint(
            phase=CheckpointPhase.SESSION_START.value,
            operation=CheckpointOperation.INITIALIZE.value,
            input_ref={
                "query": query,
                "depth": depth.value,
                "parallel_mode": self._parallel_mode,
                "num_researchers": self._num_researchers,
            },
            replayable=True,
        )

        self._monitor.record_reasoning_summary(
            stage="session",
            summary="Research session initialized",
            agent_id="orchestrator",
        )
        if on_session_started is not None:
            on_session_started(session_id)
        return session_id

    def _check_cancelled(self, cancellation_check: Callable[[], None] | None) -> None:
        """Raise when a stop request has been issued for this run."""
        if cancellation_check is None:
            return
        cancellation_check()

    def _resolve_stop_reason(
        self,
        *,
        validation: ValidationResult | None,
        iteration_history: list[IterationHistoryRecord],
    ) -> str:
        """Map the completed run to a stable stop reason."""
        if iteration_history and iteration_history[-1].stop_reason:
            return self._monitor.normalize_stop_reason(iteration_history[-1].stop_reason)

        if validation and validation.needs_follow_up:
            if not validation.follow_up_queries:
                return STOP_REASON_LOW_QUALITY
            return STOP_REASON_DEGRADED_EXECUTION

        if (
            self._config.research.enable_iterative_search
            and iteration_history
            and len(iteration_history) >= self._config.research.max_iterations
        ):
            return STOP_REASON_LIMIT_REACHED

        return STOP_REASON_SUCCESS

    def _resolve_terminal_status(self, session: ResearchSession) -> str:
        """Decide whether a completed workflow should be reported as completed or failed."""
        if session.total_sources > 0:
            return "completed"

        metadata = session.metadata
        providers = metadata.get("providers", {})
        execution = metadata.get("execution", {})
        provider_status = str(providers.get("status", ""))
        degraded_reasons = [
            str(reason)
            for reason in execution.get("degraded_reasons", [])
            if isinstance(reason, str)
        ]

        if provider_status == "unavailable":
            return "failed"
        if any(reason.startswith("All initialized providers failed") for reason in degraded_reasons):
            return "failed"
        return "completed"


@dataclass(slots=True)
class ResearchExecutionHooks:
    """Stable hook bundle used by the execution service."""

    reset_session_state: Callable[[], None]
    initialize_team: Callable[[], Awaitable[None]]
    analyze_strategy: Callable[[str, ResearchDepth], Awaitable[StrategyResult]]
    expand_queries: Callable[[str, StrategyResult, ResearchDepth], Awaitable[list[QueryFamily]]]
    normalize_query_families: Callable[..., list[QueryFamily]]
    collect_sources: Callable[..., Awaitable[list[SearchResultItem]]]
    run_analysis_workflow: Callable[
        ...,
        Awaitable[
            tuple[
                AnalysisResult,
                ValidationResult | None,
                list[SearchResultItem],
                list[IterationHistoryRecord],
            ]
        ],
    ]
    build_metadata: Callable[..., dict[str, Any]]
    log_session_summary: Callable[..., None]
    shutdown_team: Callable[[], Awaitable[None]]
