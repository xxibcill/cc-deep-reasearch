"""Research orchestrator for the local staged pipeline."""

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING, Any

from cc_deep_research.config import Config
from cc_deep_research.models import (
    AnalysisResult,
    IterationHistoryRecord,
    PlannerIterationDecision,
    StrategyResult,
    ValidationResult,
)
from cc_deep_research.models.search import (
    QueryFamily,
    ResearchDepth,
    SearchResultItem,
)
from cc_deep_research.models.session import ResearchSession
from cc_deep_research.monitoring import ResearchMonitor
from cc_deep_research.orchestration import (
    AgentAccess,
    AnalysisWorkflow,
    OrchestratorRuntime,
    OrchestratorRuntimeState,
    OrchestratorSessionState,
    PhaseRunner,
    ResearchExecutionHooks,
    ResearchExecutionService,
    ResearchPlanningService,
    SessionBuilder,
    SourceCollectionService,
)
from cc_deep_research.orchestration.helpers import build_follow_up_queries, normalize_query_families
from cc_deep_research.prompts import PromptRegistry

if TYPE_CHECKING:
    from cc_deep_research.themes import WorkflowConfig


class TeamResearchOrchestrator:
    """Orchestrate the local research pipeline across specialist components.

    The current runtime is local-only. The orchestrator executes Python agent
    objects directly and optionally fans out source collection into parallel
    local researcher tasks. The coordination wrappers kept here are scaffolding,
    not a full external team runtime.
    """

    def __init__(
        self,
        config: Config,
        monitor: ResearchMonitor | None = None,
        parallel_mode: bool | None = None,
        num_researchers: int | None = None,
        prompt_registry: PromptRegistry | None = None,
        workflow_config: WorkflowConfig | None = None,
    ) -> None:
        """Initialize the research orchestrator.

        Args:
            config: Application configuration.
            monitor: Optional research monitor for progress tracking.
            parallel_mode: Whether to enable parallel researcher execution.
                          If None, uses config.search_team.parallel_execution.
            num_researchers: Number of parallel researchers to spawn.
                          If None, uses config.search_team.num_researchers.
            prompt_registry: Optional prompt registry with overrides applied.
            workflow_config: Optional theme workflow configuration for customizing phases.
        """
        self._config = config
        self._monitor = monitor or ResearchMonitor(enabled=False)
        self._prompt_registry = prompt_registry or PromptRegistry()
        self._workflow_config = workflow_config
        self._agents: dict[str, Any] = {}
        self._runtime_state: OrchestratorRuntimeState | None = None
        # Use config defaults if not specified
        self._parallel_mode = (
            parallel_mode if parallel_mode is not None else config.search_team.parallel_execution
        )
        self._num_researchers = num_researchers or config.search_team.num_researchers
        self._agent_access = AgentAccess(lambda: self._agents)
        self._session_state = OrchestratorSessionState(configured_providers=[])
        self._session_builder = SessionBuilder()
        self._source_collection = SourceCollectionService(
            config=config,
            monitor=self._monitor,
            session_state=self._session_state,
            num_researchers=self._num_researchers,
        )
        self._analysis_workflow = AnalysisWorkflow(config=config, monitor=self._monitor)
        self._planning = ResearchPlanningService(
            monitor=self._monitor,
            config=self._config,
            session_state=self._session_state,
        )
        self._phase_runner = PhaseRunner(monitor=self._monitor)
        self._runtime = OrchestratorRuntime(
            config=config,
            monitor=self._monitor,
            parallel_mode=self._parallel_mode,
            num_researchers=self._num_researchers,
            llm_event_callback=self._session_state.handle_llm_router_event,
            prompt_registry=self._prompt_registry,
        )
        self._execution = ResearchExecutionService(
            config=config,
            monitor=self._monitor,
            phase_runner=self._phase_runner,
            session_builder=self._session_builder,
            configured_providers=lambda: list(self._config.search.providers),
            parallel_mode=self._parallel_mode,
            num_researchers=self._num_researchers,
        )
    async def execute_research(
        self,
        query: str,
        depth: ResearchDepth,
        min_sources: int | None = None,
        phase_hook: Callable[[str, str], None] | None = None,
        cancellation_check: Callable[[], None] | None = None,
        on_session_started: Callable[[str], None] | None = None,
    ) -> ResearchSession:
        """Execute a research query using the local specialist pipeline.

        Args:
            query: Research query string.
            depth: Research depth mode (quick/standard/deep).
            min_sources: Minimum number of sources (optional).
            phase_hook: Optional callback for phase progress updates.

        Returns:
            ResearchSession with complete research results.

        Raises:
            TeamExecutionError: If research execution fails.
        """
        return await self._execution.execute(
            query=query,
            depth=depth,
            min_sources=min_sources,
            phase_hook=phase_hook,
            cancellation_check=cancellation_check,
            on_session_started=on_session_started,
            hooks=self._build_execution_hooks(),
        )

    def _reset_session_metadata_state(self) -> None:
        """Reset per-session metadata tracking before execution begins."""
        self._session_state.reset(list(self._config.search.providers))

    def _build_execution_hooks(self) -> ResearchExecutionHooks:
        """Build the current execution hook bundle for the orchestration flow."""
        return ResearchExecutionHooks(
            reset_session_state=self._reset_session_metadata_state,
            initialize_team=self._initialize_team,
            analyze_strategy=self._phase_analyze_strategy,
            expand_queries=self._phase_expand_queries,
            normalize_query_families=self._normalize_query_families,
            collect_sources=self._collect_sources,
            run_analysis_workflow=self._run_analysis_workflow,
            build_metadata=self._build_session_metadata,
            log_session_summary=self._log_session_summary,
            shutdown_team=self._shutdown_team,
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
        """Build the stable session metadata contract for persisted sessions."""
        return self._session_state.build_metadata(
            depth=depth,
            sources=sources,
            strategy=strategy,
            analysis=analysis,
            validation=validation,
            iteration_history=iteration_history,
            parallel_requested=self._parallel_mode,
        )

    async def _collect_sources(
        self,
        *,
        query_families: list[QueryFamily],
        depth: ResearchDepth,
        min_sources: int | None,
    ) -> list[SearchResultItem]:
        """Collect sources using the configured execution mode."""
        agent_pool = self._runtime_state if self._runtime_state and self._runtime_state.parallel_pool_initialized else None
        return await self._source_collection.collect_with_fallback(
            collector=self._agent_access.collector(),
            agent_pool=agent_pool,
            query_families=query_families,
            depth=depth,
            min_sources=min_sources,
            prefer_parallel=self._parallel_mode,
        )

    def _log_session_summary(
        self,
        *,
        source_count: int,
        finding_count: int,
        validation: ValidationResult | None,
    ) -> None:
        """Log the final research-session summary."""
        self._phase_runner.log_session_summary(
            source_count=source_count,
            finding_count=finding_count,
            validation=validation,
        )

    async def _initialize_team(self) -> None:
        """Initialize the research team with agents.

        Creates a team with specialized agents for different
        aspects of research.
        """
        runtime_state = await self._runtime.initialize()
        self._apply_runtime_state(runtime_state)
        self._planning = ResearchPlanningService(
            monitor=self._monitor,
            config=self._config,
            registry=runtime_state.llm_registry,
            session_state=self._session_state,
        )
        # Record prompt configuration in session state
        self._session_state.set_prompt_metadata(runtime_state.prompt_registry)

    async def _phase_analyze_strategy(
        self,
        query: str,
        depth: ResearchDepth,
    ) -> StrategyResult:
        """Phase 1: Analyze query and determine research strategy.

        Args:
            query: Research query.
            depth: Research depth mode.

        Returns:
            Typed strategy result.
        """
        return await self._planning.analyze_strategy(
            lead=self._agent_access.lead(),
            query=query,
            depth=depth,
        )

    async def _phase_expand_queries(
        self,
        query: str,
        strategy: StrategyResult,
        depth: ResearchDepth,
    ) -> list[QueryFamily]:
        """Phase 2: Expand queries for comprehensive coverage.

        Args:
            query: Original query.
            strategy: Research strategy.
            depth: Research depth mode.

        Returns:
            List of labeled query families.
        """
        return await self._planning.expand_queries(
            expander=self._agent_access.expander(),
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
        """Normalize expansion output into typed query-family models."""
        return normalize_query_families(
            original_query=original_query,
            strategy=strategy,
            raw_families=raw_families,
        )

    async def _phase_collect_sources(
        self,
        query_families: list[QueryFamily],
        depth: ResearchDepth,
        _min_sources: int | None,
    ) -> list[SearchResultItem]:
        """Phase 3: Collect sources from providers.

        Args:
            query_families: Query variations to search.
            depth: Research depth mode.
            _min_sources: Minimum sources required.

        Returns:
            List of search result items.
        """
        return await self._source_collection.collect_sources(
            collector=self._agent_access.collector(),
            query_families=query_families,
            depth=depth,
        )

    async def _phase_analyze_findings(
        self,
        sources: list[SearchResultItem],
        query: str,
        _strategy: StrategyResult,
    ) -> AnalysisResult:
        """Phase 4: Analyze collected findings.

        Args:
            sources: List of collected sources.
            query: Original research query.
            _strategy: Research strategy.

        Returns:
            Analysis results dictionary.
        """
        return await self._analysis_workflow.analyze_findings(
            analyzer=self._agent_access.analyzer(),
            sources=sources,
            query=query,
        )

    async def _phase_deep_analysis(
        self,
        sources: list[SearchResultItem],
        query: str,
        analysis: AnalysisResult,  # noqa: ARG002
    ) -> AnalysisResult:
        """Phase 4.5: Multi-pass deep analysis (deep mode only).

        Args:
            sources: List of collected sources.
            query: Original research query.
            analysis: Existing analysis results.

        Returns:
            Deep analysis results dictionary.
        """
        return await self._analysis_workflow.deep_analysis(
            deep_analyzer=self._agent_access.deep_analyzer(),
            sources=sources,
            query=query,
        )

    async def _run_analysis_workflow(
        self,
        query: str,
        depth: ResearchDepth,
        strategy: StrategyResult,
        sources: list[SearchResultItem],
        min_sources: int | None,
        phase_hook: Callable[[str, str], None] | None,
        cancellation_check: Callable[[], None] | None = None,
    ) -> tuple[
        AnalysisResult,
        ValidationResult | None,
        list[SearchResultItem],
        list[IterationHistoryRecord],
    ]:
        """Run analysis, validation, and iterative follow-up search."""
        return await self._analysis_workflow.run(
            query=query,
            depth=depth,
            strategy=strategy,
            sources=sources,
            min_sources=min_sources,
            phase_hook=phase_hook,
            cancellation_check=cancellation_check,
            run_single_pass=self._run_single_analysis_pass,
            collect_follow_up_sources=self._run_follow_up_collection,
            plan_iteration=self._plan_research_iteration,
        )

    async def _run_single_analysis_pass(
        self,
        query: str,
        depth: ResearchDepth,
        strategy: StrategyResult,
        sources: list[SearchResultItem],
        phase_hook: Callable[[str, str], None] | None,
        cancellation_check: Callable[[], None] | None = None,
    ) -> tuple[AnalysisResult, ValidationResult | None]:
        """Run one analysis pass over the current source set."""
        return await self._phase_runner.run_analysis_pass(
            phase_hook=phase_hook,
            query=query,
            depth=depth,
            strategy=strategy,
            sources=sources,
            cancellation_check=cancellation_check,
            analyze_findings=self._phase_analyze_findings,
            deep_analyze=self._phase_deep_analysis,
            validate_research=self._phase_validate_research,
            log_validation_results=self._log_validation_results,
            workflow_config=self._workflow_config,
        )

    def _get_follow_up_queries(
        self,
        query: str,
        analysis: AnalysisResult | dict[str, Any],
        validation: ValidationResult | dict[str, Any] | None,
    ) -> list[str]:
        """Return follow-up queries for the next iteration, if needed."""
        return build_follow_up_queries(
            query=query,
            analysis=analysis,
            validation=validation,
            enable_iterative_search=self._config.research.enable_iterative_search,
        )

    def _plan_research_iteration(
        self,
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
        """Delegate loop control to the planner agent."""
        return self._agent_access.planner().decide_research_iteration(
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

    async def _run_follow_up_collection(
        self,
        existing_sources: list[SearchResultItem],
        follow_up_queries: list[str],
        depth: ResearchDepth,
        min_sources: int | None,
    ) -> list[SearchResultItem]:
        """Collect follow-up sources and merge them with existing sources."""
        agent_pool = self._runtime_state if self._runtime_state and self._runtime_state.parallel_pool_initialized else None
        new_sources = await self._source_collection.collect_follow_up_sources(
            collector=self._agent_access.collector(),
            agent_pool=agent_pool,
            follow_up_queries=follow_up_queries,
            depth=depth,
            min_sources=min_sources,
            prefer_parallel=self._parallel_mode,
        )

        self._monitor.section("Iterative Follow-up Search")
        self._monitor.log(f"Follow-up queries: {len(follow_up_queries)}")
        merged_sources = self._merge_sources(existing_sources, new_sources)
        self._monitor.log(
            f"Merged sources: {len(existing_sources)} existing + {len(new_sources)} new -> {len(merged_sources)} unique"
        )
        return merged_sources

    def _merge_sources(
        self,
        existing_sources: list[SearchResultItem],
        new_sources: list[SearchResultItem],
    ) -> list[SearchResultItem]:
        """Merge and deduplicate sources while preserving ranking."""
        return self._source_collection.merge_sources(
            existing_sources=existing_sources,
            new_sources=new_sources,
        )

    async def _phase_validate_research(
        self,
        query: str,
        depth: ResearchDepth,
        sources: list[SearchResultItem],
        analysis: AnalysisResult,
    ) -> ValidationResult:
        """Phase 5: Validate research quality.

        Args:
            sources: List of collected sources.
            analysis: Analysis results.

        Returns:
            Validation results dictionary.
        """
        return await self._analysis_workflow.validate_research(
            validator=self._agent_access.validator(),
            query=query,
            depth=depth,
            sources=sources,
            analysis=analysis,
        )

    def _log_validation_results(self, validation: ValidationResult) -> None:
        """Log validation results.

        Args:
            validation: Validation results dictionary.
        """
        if validation:
            self._analysis_workflow.log_validation_results(validation)

    async def _shutdown_team(self) -> None:
        """Shutdown the research team.

        Cleans up all team resources and agents.
        """
        await self._runtime.shutdown()
        self._clear_runtime_state()

    def _apply_runtime_state(self, runtime_state: OrchestratorRuntimeState) -> None:
        """Mirror runtime state into compatibility attributes used by tests and helpers."""
        self._runtime_state = runtime_state
        self._agents = runtime_state.agents

    def _clear_runtime_state(self) -> None:
        """Clear compatibility attributes after runtime shutdown."""
        self._runtime_state = None
        self._agents = {}


class OrchestratorError(Exception):
    """Base exception for orchestrator errors."""

    pass


class TeamExecutionError(OrchestratorError):
    """Exception raised when team execution fails."""

    def __init__(
        self,
        message: str,
        query: str | None = None,
        original_error: Exception | None = None,
    ) -> None:
        super().__init__(message)
        self.query = query
        self.original_error = original_error


__all__ = [
    "TeamResearchOrchestrator",
    "OrchestratorError",
    "TeamExecutionError",
]
