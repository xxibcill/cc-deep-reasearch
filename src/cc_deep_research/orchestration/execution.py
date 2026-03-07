"""Top-level execution flow for research sessions."""

from __future__ import annotations

import uuid
from collections.abc import Awaitable, Callable
from datetime import datetime
from typing import Any

from cc_deep_research.models import (
    AnalysisResult,
    IterationHistoryRecord,
    QueryFamily,
    ResearchDepth,
    ResearchSession,
    SearchResultItem,
    StrategyResult,
    ValidationResult,
)
from cc_deep_research.monitoring import ResearchMonitor
from cc_deep_research.orchestration.phases import PhaseRunner
from cc_deep_research.orchestration.session_builder import SessionBuilder


class ResearchExecutionService:
    """Run the top-level research session flow."""

    def __init__(
        self,
        *,
        monitor: ResearchMonitor,
        phase_runner: PhaseRunner,
        session_builder: SessionBuilder,
        configured_providers: Callable[[], list[str]],
        parallel_mode: bool,
        num_researchers: int,
    ) -> None:
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
        reset_session_state: Callable[[], None],
        initialize_team: Callable[[], Awaitable[None]],
        analyze_strategy: Callable[[str, ResearchDepth], Awaitable[StrategyResult]],
        expand_queries: Callable[[str, StrategyResult, ResearchDepth], Awaitable[list[QueryFamily]]],
        normalize_query_families: Callable[..., list[QueryFamily]],
        collect_sources: Callable[..., Awaitable[list[SearchResultItem]]],
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
        ],
        build_metadata: Callable[..., dict[str, Any]],
        log_session_summary: Callable[..., None],
        shutdown_team: Callable[[], Awaitable[None]],
    ) -> ResearchSession:
        """Execute a full research session using injected callbacks."""
        reset_session_state()
        start_time = datetime.utcnow()
        session_id = self._initialize_session(query=query, depth=depth)

        try:
            await self._phase_runner.run_phase(
                phase_hook=phase_hook,
                phase_key="team_init",
                description="Initializing agent team",
                operation=initialize_team,
            )
            strategy = await self._phase_runner.run_phase(
                phase_hook=phase_hook,
                phase_key="strategy",
                description="Analyzing research strategy",
                operation=lambda: analyze_strategy(query, depth),
            )
            raw_query_families = await self._phase_runner.run_phase(
                phase_hook=phase_hook,
                phase_key="query_expansion",
                description="Expanding search queries",
                operation=lambda: expand_queries(query, strategy, depth),
            )
            strategy.strategy.query_families = normalize_query_families(
                original_query=query,
                strategy=strategy,
                raw_families=raw_query_families,
            )
            queries = [family.query for family in strategy.strategy.query_families]
            sources = await self._phase_runner.run_phase(
                phase_hook=phase_hook,
                phase_key="source_collection",
                description="Collecting sources from providers",
                operation=lambda: collect_sources(
                    queries=queries,
                    depth=depth,
                    min_sources=min_sources,
                ),
            )
            analysis, validation, sources, iteration_history = await run_analysis_workflow(
                query=query,
                depth=depth,
                strategy=strategy,
                sources=sources,
                min_sources=min_sources,
                phase_hook=phase_hook,
            )
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
                build_metadata=build_metadata,
            )
            log_session_summary(
                source_count=len(sources),
                finding_count=len(analysis.key_findings),
                validation=validation,
            )
            self._phase_runner.notify_phase(
                phase_hook,
                phase_key="complete",
                description="Research complete",
            )
            self._monitor.finalize_session(
                total_sources=len(sources),
                providers=self._configured_providers(),
                total_time_ms=int(session.execution_time_seconds * 1000),
                status="completed",
            )
            return session
        finally:
            self._phase_runner.notify_phase(
                phase_hook,
                phase_key="cleanup",
                description="Cleaning up team resources",
            )
            await shutdown_team()

    def _initialize_session(self, *, query: str, depth: ResearchDepth) -> str:
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
        self._monitor.record_reasoning_summary(
            stage="session",
            summary="Research session initialized",
            agent_id="orchestrator",
        )
        return session_id
