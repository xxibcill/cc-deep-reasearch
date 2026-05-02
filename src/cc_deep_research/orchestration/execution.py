"""Top-level execution flow for research sessions."""

from __future__ import annotations

import uuid
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import datetime
from typing import Any, cast

from cc_deep_research.agents import QueryExpanderAgent, ResearchLeadAgent, SourceCollectorAgent
from cc_deep_research.config import Config
from cc_deep_research.models import PlannerIterationDecision
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
from cc_deep_research.orchestration.analysis_workflow import AnalysisWorkflow
from cc_deep_research.orchestration.phases import PhaseRunner
from cc_deep_research.orchestration.planning import ResearchPlanningService
from cc_deep_research.orchestration.runtime import OrchestratorRuntime
from cc_deep_research.orchestration.session_builder import SessionBuilder
from cc_deep_research.orchestration.session_state import OrchestratorSessionState
from cc_deep_research.orchestration.source_collection import SourceCollectionService
from cc_deep_research.orchestration.agent_access import AgentAccess


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
        concurrent_source_collection: bool,
        max_concurrent_sources: int,
        # Collaborators for hook construction (optional for backward compatibility)
        runtime: OrchestratorRuntime | None = None,
        session_state: OrchestratorSessionState | None = None,
        planning: ResearchPlanningService | None = None,
        source_collection: SourceCollectionService | None = None,
        analysis_workflow: AnalysisWorkflow | None = None,
    ) -> None:
        self._config = config
        self._monitor = monitor
        self._phase_runner = phase_runner
        self._session_builder = session_builder
        self._configured_providers = configured_providers
        self._concurrent_source_collection = concurrent_source_collection
        self._max_concurrent_sources = max_concurrent_sources
        self._runtime = runtime
        self._session_state = session_state
        self._planning = planning
        self._source_collection = source_collection
        self._analysis_workflow = analysis_workflow

    def _build_hooks(
        self,
        agent_access: AgentAccess | None = None,
        analysis_workflow_run_callback: Callable[..., Awaitable[tuple[AnalysisResult, ValidationResult | None, list[SearchResultItem], list[IterationHistoryRecord]]]] | None = None,
    ) -> ResearchExecutionHooks:
        """Build the hook bundle from collaborators owned by the orchestrator.

        Requires runtime and session_state to be set.
        Raises RuntimeError if collaborators needed for self-built hooks are missing.
        """
        if self._runtime is None or self._session_state is None:
            raise RuntimeError(
                "runtime and session_state collaborators are required to build hooks automatically"
            )

        runtime = self._runtime
        if agent_access is None:
            agent_access = AgentAccess(lambda: runtime.agents)

        analysis_callback = analysis_workflow_run_callback
        if analysis_callback is None and self._analysis_workflow is not None:
            analysis_callback = self._make_analysis_workflow_callback(agent_access)

        if analysis_callback is None:
            raise RuntimeError("analysis_workflow_run_callback is required when analysis_workflow is not available")

        session_state = self._session_state
        analysis_workflow = self._analysis_workflow

        return ResearchExecutionHooks(
            reset_session_state=lambda: session_state.reset(list(self._config.search.providers)),
            initialize_team=self._initialize_team,
            analyze_strategy=self._phase_analyze_strategy,
            expand_queries=self._phase_expand_queries,
            normalize_query_families=self._normalize_query_families,
            collect_sources=self._collect_sources,
            run_analysis_workflow=analysis_callback,
            build_metadata=self._build_session_metadata,
            log_session_summary=self._log_session_summary,
            shutdown_team=self._shutdown_team,
        )

    def _make_analysis_workflow_callback(
        self, agent_access: AgentAccess
    ) -> Callable[..., Awaitable[tuple[AnalysisResult, ValidationResult | None, list[SearchResultItem], list[IterationHistoryRecord]]]]:
        """Build the analysis workflow callback from the analysis workflow and phase runner."""
        assert self._analysis_workflow is not None, "analysis_workflow required for hook-based execution"
        analysis_workflow = self._analysis_workflow

        async def callback(
            query: str,
            depth: ResearchDepth,
            strategy: StrategyResult,
            sources: list[SearchResultItem],
            min_sources: int | None,
            phase_hook: Callable[[str, str], None] | None,
            cancellation_check: Callable[[], None] | None = None,
        ) -> tuple[AnalysisResult, ValidationResult | None, list[SearchResultItem], list[IterationHistoryRecord]]:
            return await analysis_workflow.run(
                query=query,
                depth=depth,
                strategy=strategy,
                sources=sources,
                min_sources=min_sources,
                phase_hook=phase_hook,
                cancellation_check=cancellation_check,
                run_single_pass=self._make_single_pass_callback(agent_access),
                collect_follow_up_sources=self._make_collect_follow_up_callback(agent_access),
                plan_iteration=self._make_plan_iteration_callback(agent_access),
            )

        return callback

    def _make_single_pass_callback(
        self, agent_access: AgentAccess
    ) -> Callable[..., Awaitable[tuple[AnalysisResult, ValidationResult | None]]]:
        phase_runner = self._phase_runner
        analysis_workflow = self._analysis_workflow

        async def callback(
            query: str,
            depth: ResearchDepth,
            strategy: StrategyResult,
            sources: list[SearchResultItem],
            phase_hook: Callable[[str, str], None] | None,
            cancellation_check: Callable[[], None] | None = None,
        ) -> tuple[AnalysisResult, ValidationResult | None]:
            async def analyze_findings(src: list[SearchResultItem], q: str, _: StrategyResult) -> AnalysisResult:
                return agent_access.analyzer().analyze_sources(src, q)

            async def deep_analyze(src: list[SearchResultItem], q: str, _: AnalysisResult) -> AnalysisResult:
                result_dict = agent_access.deep_analyzer().deep_analyze(src, q)
                return AnalysisResult(
                    key_findings=result_dict.get("key_findings", []),
                    themes=result_dict.get("themes", []),
                    themes_detailed=result_dict.get("themes_detailed", []),
                    consensus_points=result_dict.get("consensus_points", []),
                    contention_points=result_dict.get("disagreement_points", []),
                    cross_reference_claims=result_dict.get("cross_reference_claims", []),
                    gaps=result_dict.get("gaps", []),
                    source_count=result_dict.get("source_count", 0),
                    analysis_method=result_dict.get("analysis_method", "empty"),
                    deep_analysis_complete=result_dict.get("deep_analysis_complete", False),
                    analysis_passes=result_dict.get("analysis_passes", 0),
                    patterns=result_dict.get("patterns", []),
                    disagreement_points=result_dict.get("disagreement_points", []),
                    implications=result_dict.get("implications", []),
                    comprehensive_synthesis=result_dict.get("comprehensive_synthesis", ""),
                )

            async def validate_research(q: str, d: ResearchDepth, src: list[SearchResultItem], a: AnalysisResult) -> ValidationResult:
                from cc_deep_research.models.session import ResearchSession
                session = ResearchSession(session_id="validation", query=q, sources=src)
                return agent_access.validator().validate_research(
                    session, a, query=q, min_sources_override=None
                )

            return await phase_runner.run_analysis_pass(
                phase_hook=phase_hook,
                query=query,
                depth=depth,
                strategy=strategy,
                sources=sources,
                cancellation_check=cancellation_check,
                analyze_findings=analyze_findings,
                deep_analyze=deep_analyze,
                validate_research=validate_research,
                log_validation_results=analysis_workflow.log_validation_results,  # type: ignore[union-attr]
                workflow_config=None,
            )

        return callback

    def _make_collect_follow_up_callback(
        self, agent_access: AgentAccess
    ) -> Callable[..., Awaitable[list[SearchResultItem]]]:
        runtime = self._runtime
        source_collection = self._source_collection
        concurrent = self._concurrent_source_collection

        async def callback(
            existing_sources: list[SearchResultItem],
            follow_up_queries: list[str],
            depth: ResearchDepth,
            min_sources: int | None,
        ) -> list[SearchResultItem]:
            assert runtime is not None and source_collection is not None, "runtime and source_collection required"
            runtime_state = runtime.current_state()
            agent_pool = runtime_state if runtime_state and runtime_state.parallel_pool_initialized else None
            new_sources = await source_collection.collect_follow_up_sources(
                collector=agent_access.collector(),
                agent_pool=agent_pool,
                follow_up_queries=follow_up_queries,
                depth=depth,
                min_sources=min_sources,
                prefer_parallel=concurrent,
            )
            return source_collection.merge_sources(
                existing_sources=existing_sources,
                new_sources=new_sources,
            )

        return callback

    def _make_plan_iteration_callback(
        self, agent_access: AgentAccess
    ) -> Callable[..., PlannerIterationDecision]:
        def callback(
            *,
            query: str,
            strategy: StrategyResult,
            analysis: AnalysisResult,
            validation: ValidationResult | None,
            sources: list[SearchResultItem],
            iteration: int,
            max_iterations: int,
            min_sources: int | None,
            iteration_history: list[IterationHistoryRecord],
        ) -> PlannerIterationDecision:
            return agent_access.planner().decide_research_iteration(
                query=query,
                strategy=strategy,
                analysis=analysis,
                validation=validation,
                sources=sources,
                iteration=iteration,
                max_iterations=max_iterations,
                min_sources=min_sources,
                iteration_history=iteration_history,
                enable_iterative_search=self._config.research.enable_iterative_search,
            )

        return callback

    async def _initialize_team(self) -> None:
        assert self._runtime is not None, "runtime required - hooks must be built via _build_hooks()"
        await self._runtime.initialize()

    def _phase_analyze_strategy(self, query: str, depth: ResearchDepth) -> Awaitable[StrategyResult]:
        # These methods are only called from hooks built after runtime init via _build_hooks()
        assert self._runtime is not None, "runtime required - hooks must be built via _build_hooks()"
        assert self._planning is not None, "planning required for hook-based execution"
        agents = self._runtime.agents
        lead = cast(ResearchLeadAgent, agents["lead"])
        return self._planning.analyze_strategy(
            lead=lead,
            query=query,
            depth=depth,
        )

    def _phase_expand_queries(
        self, query: str, strategy: StrategyResult, depth: ResearchDepth
    ) -> Awaitable[list[QueryFamily]]:
        assert self._runtime is not None, "runtime required - hooks must be built via _build_hooks()"
        assert self._planning is not None, "planning required for hook-based execution"
        agents = self._runtime.agents
        expander = cast(QueryExpanderAgent, agents["expander"])
        return self._planning.expand_queries(
            expander=expander,
            query=query,
            strategy=strategy,
            depth=depth,
        )

    @staticmethod
    def _normalize_query_families(
        *,
        original_query: str,
        strategy: StrategyResult,
        raw_families: list[QueryFamily | str],
    ) -> list[QueryFamily]:
        from cc_deep_research.orchestration.helpers import normalize_query_families as normalized
        return normalized(
            original_query=original_query,
            strategy=strategy,
            raw_families=raw_families,
        )

    def _collect_sources(
        self,
        *,
        query_families: list[QueryFamily],
        depth: ResearchDepth,
        min_sources: int | None,
    ) -> Awaitable[list[SearchResultItem]]:
        assert self._runtime is not None, "runtime required - hooks must be built via _build_hooks()"
        assert self._source_collection is not None, "source_collection required for hook-based execution"
        runtime_state = self._runtime.current_state()
        agent_pool = runtime_state if runtime_state and runtime_state.parallel_pool_initialized else None
        agents = self._runtime.agents
        # collector is only used when parallel collection is not available or fails
        collector: SourceCollectorAgent | None = agents.get("collector") if agents else None
        return self._source_collection.collect_with_fallback(
            collector=collector,  # type: ignore[arg-type]  # SourceCollectorAgent satisfies _SequentialCollector structurally
            agent_pool=agent_pool,
            query_families=query_families,
            depth=depth,
            min_sources=min_sources,
            prefer_parallel=self._concurrent_source_collection,
        )

    def _build_session_metadata(
        self,
        *,
        depth: ResearchDepth,
        sources: list[SearchResultItem],
        strategy: StrategyResult,
        analysis: AnalysisResult,
        validation: ValidationResult | None,
        iteration_history: list[IterationHistoryRecord],
    ) -> dict[str, Any]:
        assert self._session_state is not None, "session_state required for hook-based execution"
        return self._session_state.build_metadata(
            depth=depth,
            sources=sources,
            strategy=strategy,
            analysis=analysis,
            validation=validation,
            iteration_history=iteration_history,
            parallel_requested=self._concurrent_source_collection,
        )

    def _log_session_summary(
        self,
        *,
        source_count: int,
        finding_count: int,
        validation: ValidationResult | None,
    ) -> None:
        self._phase_runner.log_session_summary(
            source_count=source_count,
            finding_count=finding_count,
            validation=validation,
        )

    async def _shutdown_team(self) -> None:
        assert self._runtime is not None, "runtime required - hooks must be built via _build_hooks()"
        await self._runtime.shutdown()

    async def execute(
        self,
        *,
        query: str,
        depth: ResearchDepth,
        min_sources: int | None,
        phase_hook: Callable[[str, str], None] | None,
        cancellation_check: Callable[[], None] | None = None,
        on_session_started: Callable[[str], None] | None = None,
        hooks: ResearchExecutionHooks | None = None,
    ) -> ResearchSession:
        """Execute a full research session.

        When hooks is None, builds them from owned collaborators (deepened boundary).
        When hooks is provided, uses them directly (backward-compatible facade).
        """
        hooks_built_here = hooks is None
        hooks = hooks if hooks is not None else self._build_hooks()

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
                input_ref={"concurrent_source_collection": self._concurrent_source_collection, "max_concurrent_sources": self._max_concurrent_sources},
            )

            # Re-build hooks now that runtime state is populated (agents available)
            # Only needed when we built hooks ourselves (deepened boundary path)
            if hooks_built_here:
                hooks = self._build_hooks()

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
            concurrent_source_collection=self._concurrent_source_collection,
            configured_researchers=self._max_concurrent_sources,
        )

        # Emit session start checkpoint
        self._monitor.emit_checkpoint(
            phase=CheckpointPhase.SESSION_START.value,
            operation=CheckpointOperation.INITIALIZE.value,
            input_ref={
                "query": query,
                "depth": depth.value,
                "concurrent_source_collection": self._concurrent_source_collection,
                "max_concurrent_sources": self._max_concurrent_sources,
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
