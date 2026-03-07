"""Research orchestrator using agent teams.

This module provides the TeamResearchOrchestrator class that coordinates
research operations using multiple specialized agents working together.
"""

import asyncio
import uuid
from collections.abc import Callable
from typing import Any

from cc_deep_research.agents import (
    AGENT_TYPE_ANALYZER,
    AGENT_TYPE_COLLECTOR,
    AGENT_TYPE_DEEP_ANALYZER,
    AGENT_TYPE_EXPANDER,
    AGENT_TYPE_LEAD,
    AGENT_TYPE_REPORTER,
    AGENT_TYPE_VALIDATOR,
    AnalyzerAgent,
    DeepAnalyzerAgent,
    QueryExpanderAgent,
    ReporterAgent,
    ResearchLeadAgent,
    SourceCollectorAgent,
    ValidatorAgent,
)
from cc_deep_research.config import Config
from cc_deep_research.coordination import AgentPool, MessageBus
from cc_deep_research.models import (
    AnalysisResult,
    IterationHistoryRecord,
    QueryFamily,
    ResearchDepth,
    ResearchSession,
    SearchOptions,
    SearchResult,
    SearchResultItem,
    StrategyResult,
    ValidationResult,
)
from cc_deep_research.monitoring import ResearchMonitor
from cc_deep_research.teams import AgentSpec, ResearchTeam, TeamConfig


class TeamResearchOrchestrator:
    """Orchestrates research using a team of specialized agents.

    This class provides:
    - Team initialization with specialized research agents
    - Task decomposition and assignment
    - Coordination of agent execution
    - Results aggregation and validation
    - Research session management

    The orchestrator manages the full research workflow:
    1. Analyze query and determine strategy (lead agent)
    2. Expand queries for comprehensive coverage (expander agent)
    3. Collect sources from providers (collector agent)
    4. Analyze findings (analyzer agent)
    5. Deep analysis (deep_analyzer agent - deep mode only)
    6. Validate quality (validator agent)
    7. Generate reports (reporter agent)
    """

    def __init__(
        self,
        config: Config,
        monitor: ResearchMonitor | None = None,
        parallel_mode: bool | None = None,
        num_researchers: int | None = None,
    ) -> None:
        """Initialize the research orchestrator.

        Args:
            config: Application configuration.
            monitor: Optional research monitor for progress tracking.
            parallel_mode: Whether to enable parallel researcher execution.
                          If None, uses config.search_team.parallel_execution.
            num_researchers: Number of parallel researchers to spawn.
                          If None, uses config.search_team.num_researchers.
        """
        self._config = config
        self._monitor = monitor or ResearchMonitor(enabled=False)
        self._team: ResearchTeam | None = None
        self._agents: dict[str, Any] = {}
        # Use config defaults if not specified
        self._parallel_mode = (
            parallel_mode if parallel_mode is not None else config.search_team.parallel_execution
        )
        self._num_researchers = num_researchers or config.search_team.num_researchers
        self._message_bus: MessageBus | None = None
        self._agent_pool: AgentPool | None = None
        self._content_cache: dict[str, str] = {}
        self._session_provider_metadata: dict[str, Any] = {}
        self._session_execution_degradations: list[str] = []
        self._used_parallel_collection = False

    async def execute_research(
        self,
        query: str,
        depth: ResearchDepth,
        min_sources: int | None = None,
        phase_hook: Callable[[str, str], None] | None = None,
    ) -> ResearchSession:
        """Execute a research query using the agent team.

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
        from datetime import datetime

        # Track actual start time for accurate execution time calculation
        start_time = datetime.utcnow()
        self._reset_session_metadata_state()

        self._monitor.section("Research Session")
        self._monitor.log(f"Query: {query}")
        self._monitor.log(f"Depth: {depth.value}")

        # Create session ID
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

        # Initialize team
        self._notify_phase(
            phase_hook,
            phase_key="team_init",
            description="Initializing agent team",
        )
        team_init_event = self._monitor.start_operation(
            name="team_init",
            category="phase",
            description="Initializing agent team",
        )
        self._monitor.emit_event(
            event_type="phase.started",
            category="phase",
            name="team_init",
            status="started",
            metadata={"description": "Initializing agent team"},
        )
        await self._initialize_team()
        self._monitor.end_operation(team_init_event, success=True)

        # Phase 1: Analyze query and determine strategy
        self._notify_phase(
            phase_hook,
            phase_key="strategy",
            description="Analyzing research strategy",
        )
        strategy_event = self._monitor.start_operation(
            name="strategy",
            category="phase",
            description="Analyzing research strategy",
        )
        self._monitor.emit_event(
            event_type="phase.started",
            category="phase",
            name="strategy",
            status="started",
            metadata={"description": "Analyzing research strategy"},
        )
        strategy = await self._phase_analyze_strategy(query, depth)
        self._monitor.end_operation(strategy_event, success=True)

        # Phase 2: Expand queries if needed
        self._notify_phase(
            phase_hook,
            phase_key="query_expansion",
            description="Expanding search queries",
        )
        query_expansion_event = self._monitor.start_operation(
            name="query_expansion",
            category="phase",
            description="Expanding search queries",
        )
        self._monitor.emit_event(
            event_type="phase.started",
            category="phase",
            name="query_expansion",
            status="started",
            metadata={"description": "Expanding search queries"},
        )
        raw_query_families = await self._phase_expand_queries(query, strategy, depth)
        query_families = self._normalize_query_families(
            original_query=query,
            strategy=strategy,
            raw_families=raw_query_families,
        )
        strategy.strategy.query_families = query_families
        queries = [family.query for family in query_families]
        self._monitor.end_operation(query_expansion_event, success=True)

        # Phase 3: Collect sources (parallel or sequential)
        self._notify_phase(
            phase_hook,
            phase_key="source_collection",
            description="Collecting sources from providers",
        )
        source_collection_event = self._monitor.start_operation(
            name="source_collection",
            category="phase",
            description="Collecting sources from providers",
        )
        self._monitor.emit_event(
            event_type="phase.started",
            category="phase",
            name="source_collection",
            status="started",
            metadata={"description": "Collecting sources from providers"},
        )

        # Use parallel or sequential mode based on configuration
        if self._parallel_mode and self._agent_pool:
            try:
                sources = await self._phase_parallel_research(
                    queries,
                    depth,
                    min_sources,
                )
            except Exception as e:
                # Fall back to sequential mode on error
                self._monitor.log(f"Parallel execution failed: {e}")
                self._monitor.log("Falling back to sequential mode")
                self._note_execution_degradation(
                    f"Parallel source collection fell back to sequential mode: {e}"
                )
                sources = await self._phase_collect_sources(
                    queries,
                    depth,
                    min_sources,
                )
        else:
            sources = await self._phase_collect_sources(
                queries,
                depth,
                min_sources,
            )
        self._monitor.end_operation(source_collection_event, success=True)

        analysis, validation, sources, iteration_history = await self._run_analysis_workflow(
            query=query,
            depth=depth,
            strategy=strategy,
            sources=sources,
            min_sources=min_sources,
            phase_hook=phase_hook,
        )

        # Create and return session
        session = ResearchSession(
            session_id=session_id,
            query=query,
            depth=depth,
            sources=sources,
            started_at=start_time,
            completed_at=datetime.utcnow(),
            metadata=self._build_session_metadata(
                depth=depth,
                strategy=strategy,
                analysis=analysis,
                validation=validation,
                iteration_history=iteration_history,
            ),
        )

        # Summary
        self._monitor.section("Summary")
        self._monitor.log(f"Total sources: {len(sources)}")
        self._monitor.log(f"Key findings: {len(analysis.key_findings)}")
        if validation:
            self._monitor.log(f"Quality score: {validation.quality_score:.2f}")

        # Cleanup
        self._notify_phase(
            phase_hook,
            phase_key="cleanup",
            description="Cleaning up team resources",
        )
        await self._shutdown_team()
        self._notify_phase(
            phase_hook,
            phase_key="complete",
            description="Research complete",
        )
        self._monitor.finalize_session(
            total_sources=len(sources),
            providers=self._config.search.providers,
            total_time_ms=int(session.execution_time_seconds * 1000),
            status="completed",
        )

        return session

    def _reset_session_metadata_state(self) -> None:
        """Reset per-session metadata tracking before execution begins."""
        self._session_provider_metadata = {
            "configured": list(self._config.search.providers),
            "available": [],
            "warnings": [],
        }
        self._session_execution_degradations = []
        self._used_parallel_collection = False

    def _note_execution_degradation(self, reason: str) -> None:
        """Record a session-level degradation reason once."""
        if reason not in self._session_execution_degradations:
            self._session_execution_degradations.append(reason)

    def _set_provider_metadata(
        self,
        *,
        available: list[str],
        warnings: list[str],
    ) -> None:
        """Record provider-resolution metadata for the current session."""
        self._session_provider_metadata = {
            "configured": list(self._config.search.providers),
            "available": list(available),
            "warnings": list(warnings),
        }
        for warning in warnings:
            self._note_execution_degradation(warning)

    def _build_session_metadata(
        self,
        *,
        depth: ResearchDepth,
        strategy: StrategyResult,
        analysis: AnalysisResult,
        validation: ValidationResult | None,
        iteration_history: list[IterationHistoryRecord],
    ) -> dict[str, Any]:
        """Build the stable session metadata contract for persisted sessions."""
        deep_analysis_complete = analysis.deep_analysis_complete
        deep_analysis_method = analysis.analysis_method
        deep_analysis_requested = depth == ResearchDepth.DEEP
        deep_analysis_reason: str | None = None

        if deep_analysis_requested and not deep_analysis_complete:
            deep_analysis_reason = "Deep analysis produced no deep-analysis output."
        elif deep_analysis_requested and deep_analysis_method == "shallow_keyword":
            deep_analysis_reason = (
                "Deep analysis used shallow fallback output because source content was limited."
            )

        if deep_analysis_reason:
            self._note_execution_degradation(deep_analysis_reason)

        return {
            "strategy": strategy.model_dump(mode="python"),
            "analysis": analysis.model_dump(mode="python"),
            "validation": validation.model_dump(mode="python") if validation else {},
            "iteration_history": [
                record.model_dump(mode="python") for record in iteration_history
            ],
            "providers": self._session_provider_metadata,
            "execution": {
                "parallel_requested": self._parallel_mode,
                "parallel_used": self._used_parallel_collection,
                "degraded": bool(self._session_execution_degradations),
                "degraded_reasons": self._session_execution_degradations,
            },
            "deep_analysis": {
                "requested": deep_analysis_requested,
                "completed": deep_analysis_complete,
                "reason": deep_analysis_reason,
            },
        }

    @staticmethod
    def _notify_phase(
        phase_hook: Callable[[str, str], None] | None,
        phase_key: str,
        description: str,
    ) -> None:
        """Emit a phase notification when a hook is configured."""
        if phase_hook is None:
            return
        phase_hook(phase_key, description)

    async def _initialize_team(self) -> None:
        """Initialize the research team with agents.

        Creates a team with specialized agents for different
        aspects of research.
        """
        if self._team is not None:
            return  # Already initialized

        self._monitor.section("Team Initialization")

        # Initialize coordination layer for parallel mode
        if self._parallel_mode:
            self._message_bus = MessageBus()
            self._agent_pool = AgentPool(
                num_agents=self._num_researchers,
                config=self._config,
                timeout=self._config.search_team.timeout_seconds,
            )
            await self._agent_pool.initialize()
            self._monitor.log(f"Parallel mode: {self._num_researchers} researchers")
        else:
            self._monitor.log("Sequential mode")

        # Create agent specifications
        agent_specs = [
            AgentSpec(
                name="research-lead",
                description="Orchestrates research strategy",
                agent_type=AGENT_TYPE_LEAD,
                model=self._config.research_agent.model,
            ),
            AgentSpec(
                name="source-collector",
                description="Collects sources from providers",
                agent_type=AGENT_TYPE_COLLECTOR,
                model=self._config.research_agent.model,
            ),
            AgentSpec(
                name="query-expander",
                description="Expands queries for coverage",
                agent_type=AGENT_TYPE_EXPANDER,
                model=self._config.research_agent.model,
            ),
            AgentSpec(
                name="analyzer",
                description="Analyzes collected information",
                agent_type=AGENT_TYPE_ANALYZER,
                model=self._config.research_agent.model,
            ),
            AgentSpec(
                name="reporter",
                description="Generates research reports",
                agent_type=AGENT_TYPE_REPORTER,
                model=self._config.research_agent.model,
            ),
            AgentSpec(
                name="validator",
                description="Validates research quality",
                agent_type=AGENT_TYPE_VALIDATOR,
                model=self._config.research_agent.model,
            ),
        ]

        # Create team configuration
        team_config = TeamConfig(
            team_name="research-team",
            team_description="Team for coordinated web research",
            agents=agent_specs,
            timeout_seconds=self._config.search_team.timeout_seconds,
            parallel_execution=self._config.search_team.parallel_execution,
        )

        # Initialize team
        self._team = ResearchTeam(team_config, self._config)

        # Initialize individual agents (for local execution)
        # Build analyzer config with AI integration settings
        analyzer_config = {
            "ai_integration_method": self._config.research.ai_integration_method,
            "model": self._config.research_agent.model,
            "deep_analysis_tokens": self._config.research.deep_analysis_tokens,
            "ai_num_themes": self._config.research.ai_num_themes,
            "ai_deep_num_themes": self._config.research.ai_deep_num_themes,
            "ai_temperature": self._config.research.ai_temperature,
            "usage_callback": self._monitor.record_llm_usage,
        }

        self._agents = {
            AGENT_TYPE_LEAD: ResearchLeadAgent({}),
            AGENT_TYPE_COLLECTOR: SourceCollectorAgent(self._config, monitor=self._monitor),
            AGENT_TYPE_EXPANDER: QueryExpanderAgent({}),
            AGENT_TYPE_ANALYZER: AnalyzerAgent(analyzer_config),
            AGENT_TYPE_DEEP_ANALYZER: DeepAnalyzerAgent(
                {
                    **analyzer_config,
                    "deep_analysis_passes": self._config.research.deep_analysis_passes,
                }
            ),
            AGENT_TYPE_REPORTER: ReporterAgent({}),
            AGENT_TYPE_VALIDATOR: ValidatorAgent(
                {
                    "min_sources": self._config.research.min_sources.__dict__["deep"],
                    "require_diverse_domains": True,
                }
            ),
        }

        self._monitor.log(f"Team created with {len(agent_specs)} agents")
        self._monitor.record_reasoning_summary(
            stage="team_init",
            summary=f"Initialized {len(agent_specs)} specialist agents",
            agent_id="orchestrator",
            agent_types=[spec.agent_type for spec in agent_specs],
        )

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
        self._monitor.section("Strategy Analysis")

        lead: ResearchLeadAgent = self._agents[AGENT_TYPE_LEAD]
        strategy = lead.analyze_query(query, depth)

        self._monitor.log(f"Complexity: {strategy.complexity}")
        self._monitor.log(f"Tasks: {len(strategy.tasks_needed)}")
        self._monitor.log(f"Query variations: {strategy.strategy.query_variations}")
        self._monitor.record_reasoning_summary(
            stage="strategy",
            summary=(
                f"Complexity {strategy.complexity} with "
                f"{len(strategy.tasks_needed)} tasks and "
                f"{strategy.strategy.query_variations} query variations"
            ),
            agent_id=AGENT_TYPE_LEAD,
        )

        return strategy

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
        self._monitor.section("Query Expansion")

        variations = strategy.strategy.query_variations

        if variations <= 1:
            self._monitor.log("Query expansion not needed (quick mode)")
            strategy.strategy.query_families = [
                QueryFamily(
                    query=query,
                    family="baseline",
                    intent_tags=["baseline", strategy.strategy.intent],
                )
            ]
            return strategy.strategy.query_families

        expander: QueryExpanderAgent = self._agents[AGENT_TYPE_EXPANDER]
        raw_families = expander.expand_query(
            query,
            depth,
            max_variations=variations,
            strategy=strategy.strategy.model_dump(mode="python"),
        )
        query_families = self._normalize_query_families(
            original_query=query,
            strategy=strategy,
            raw_families=raw_families,
        )
        strategy.strategy.query_families = query_families

        self._monitor.log(f"Generated {len(query_families)} query variations")
        self._monitor.record_reasoning_summary(
            stage="query_expansion",
            summary=f"Expanded to {len(query_families)} queries",
            agent_id=AGENT_TYPE_EXPANDER,
            queries=[family.query for family in query_families],
        )

        return query_families

    @staticmethod
    def _normalize_query_families(
        *,
        original_query: str,
        strategy: StrategyResult,
        raw_families: list[QueryFamily | str],
    ) -> list[QueryFamily]:
        """Normalize expansion output into typed query-family models."""
        normalized_families: list[QueryFamily] = []
        for item in raw_families:
            if isinstance(item, QueryFamily):
                normalized_families.append(item)
            else:
                family = "baseline" if item == original_query else "baseline"
                normalized_families.append(
                    QueryFamily(
                        query=str(item),
                        family=family,
                        intent_tags=[family, strategy.strategy.intent],
                    )
                )
        return normalized_families

    async def _phase_collect_sources(
        self,
        queries: list[str],
        depth: ResearchDepth,
        _min_sources: int | None,
    ) -> list[SearchResultItem]:
        """Phase 3: Collect sources from providers.

        Args:
            queries: List of queries to search.
            depth: Research depth mode.
            _min_sources: Minimum sources required.

        Returns:
            List of search result items.
        """
        self._monitor.section("Source Collection")

        collector: SourceCollectorAgent = self._agents[AGENT_TYPE_COLLECTOR]

        # Initialize providers
        await collector.initialize_providers()
        provider_warnings = collector.get_provider_warnings()
        self._set_provider_metadata(
            available=collector.get_available_providers(),
            warnings=provider_warnings,
        )
        for warning in provider_warnings:
            self._monitor.log(f"Provider warning: {warning}")

        # Determine max results
        max_results = self._config.research.min_sources.__dict__[depth.value]

        # Collect sources with raw content enabled
        options = SearchOptions(
            max_results=max_results,
            search_depth=depth,
            monitor=self._monitor.is_enabled(),
            include_raw_content=True,
        )

        if len(queries) == 1:
            sources = await collector.collect_sources(queries[0], options)
        else:
            sources = await collector.collect_multiple_queries(queries, options)

        self._monitor.log(f"Collected {len(sources)} sources")
        self._monitor.record_reasoning_summary(
            stage="source_collection",
            summary=f"Collected {len(sources)} unique sources",
            agent_id=AGENT_TYPE_COLLECTOR,
            query_count=len(queries),
        )

        # Fetch full content for top sources
        sources = await self._fetch_content_for_top_sources(sources, depth)

        # Log content availability
        sources_with_content = sum(1 for s in sources if s.content and len(s.content) > 500)
        self._monitor.log(f"Sources with full content: {sources_with_content}/{len(sources)}")

        return sources

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
        self._monitor.section("Analysis")

        analyzer: AnalyzerAgent = self._agents[AGENT_TYPE_ANALYZER]
        analysis = analyzer.analyze_sources(sources, query)

        self._monitor.log(f"Key findings: {len(analysis.key_findings)}")
        self._monitor.log(f"Themes identified: {len(analysis.themes)}")
        self._monitor.log(f"Gaps: {len(analysis.gaps)}")
        self._monitor.record_reasoning_summary(
            stage="analysis",
            summary=(
                f"Generated {len(analysis.key_findings)} findings, "
                f"{len(analysis.themes)} themes, {len(analysis.gaps)} gaps"
            ),
            agent_id=AGENT_TYPE_ANALYZER,
        )

        return analysis

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
        self._monitor.section("Deep Analysis")

        deep_analyzer: DeepAnalyzerAgent = self._agents[AGENT_TYPE_DEEP_ANALYZER]
        deep_analysis = AnalysisResult.model_validate(
            deep_analyzer.deep_analyze(sources, query)
        )

        self._monitor.log(f"Deep analysis passes: {deep_analysis.analysis_passes}")
        self._monitor.log(f"Deep themes: {len(deep_analysis.themes)}")
        self._monitor.log(f"Consensus points: {len(deep_analysis.consensus_points)}")
        self._monitor.log(f"Disagreement points: {len(deep_analysis.disagreement_points)}")
        self._monitor.record_reasoning_summary(
            stage="deep_analysis",
            summary=(
                f"Deep analysis produced {len(deep_analysis.themes)} themes and "
                f"{len(deep_analysis.consensus_points)} consensus points"
            ),
            agent_id=AGENT_TYPE_DEEP_ANALYZER,
        )

        return deep_analysis

    async def _run_analysis_workflow(
        self,
        query: str,
        depth: ResearchDepth,
        strategy: StrategyResult,
        sources: list[SearchResultItem],
        min_sources: int | None,
        phase_hook: Callable[[str, str], None] | None,
    ) -> tuple[
        AnalysisResult,
        ValidationResult | None,
        list[SearchResultItem],
        list[IterationHistoryRecord],
    ]:
        """Run analysis, validation, and iterative follow-up search."""
        analysis = AnalysisResult()
        validation: ValidationResult | None = None
        iteration_history: list[IterationHistoryRecord] = []
        max_iterations = (
            self._config.research.max_iterations
            if self._config.research.enable_iterative_search
            else 1
        )

        for iteration in range(1, max_iterations + 1):
            analysis, validation = await self._run_single_analysis_pass(
                query=query,
                depth=depth,
                strategy=strategy,
                sources=sources,
                phase_hook=phase_hook,
            )

            iteration_history.append(
                IterationHistoryRecord(
                    iteration=iteration,
                    source_count=len(sources),
                    quality_score=validation.quality_score if validation else None,
                    gap_count=len(analysis.gaps),
                    follow_up_queries=validation.follow_up_queries if validation else [],
                )
            )

            if iteration >= max_iterations:
                break

            follow_up_queries = self._get_follow_up_queries(query, analysis, validation)
            if not follow_up_queries:
                break

            self._notify_phase(
                phase_hook,
                phase_key="iterative_search",
                description=f"Running follow-up research pass {iteration + 1}",
            )
            self._monitor.record_reasoning_summary(
                stage="iterative_search",
                summary=f"Running follow-up pass {iteration + 1} with {len(follow_up_queries)} queries",
                agent_id="orchestrator",
                follow_up_queries=follow_up_queries,
            )
            updated_sources = await self._run_follow_up_collection(
                existing_sources=sources,
                follow_up_queries=follow_up_queries,
                depth=depth,
                min_sources=min_sources,
            )

            if len(updated_sources) <= len(sources):
                self._monitor.log("Follow-up search produced no new sources; stopping iterations")
                break

            sources = updated_sources

        return analysis, validation, sources, iteration_history

    async def _run_single_analysis_pass(
        self,
        query: str,
        depth: ResearchDepth,
        strategy: StrategyResult,
        sources: list[SearchResultItem],
        phase_hook: Callable[[str, str], None] | None,
    ) -> tuple[AnalysisResult, ValidationResult | None]:
        """Run one analysis pass over the current source set."""
        self._notify_phase(
            phase_hook,
            phase_key="analysis",
            description="Analyzing findings",
        )
        analysis_event = self._monitor.start_operation(
            name="analysis",
            category="phase",
            description="Analyzing findings",
        )
        analysis = await self._phase_analyze_findings(sources, query, strategy)
        self._monitor.end_operation(analysis_event, success=True)

        if depth == ResearchDepth.DEEP:
            self._notify_phase(
                phase_hook,
                phase_key="deep_analysis",
                description="Performing deep multi-pass analysis",
            )
            deep_analysis_event = self._monitor.start_operation(
                name="deep_analysis",
                category="phase",
                description="Performing deep multi-pass analysis",
            )
            deep_analysis = await self._phase_deep_analysis(sources, query, analysis)
            analysis = analysis.model_copy(
                update=deep_analysis.model_dump(mode="python", exclude_unset=True)
            )
            self._monitor.end_operation(deep_analysis_event, success=True)

        self._notify_phase(
            phase_hook,
            phase_key="validation",
            description="Validating research quality",
        )
        validation_event = self._monitor.start_operation(
            name="validation",
            category="phase",
            description="Validating research quality",
        )
        if strategy.strategy.enable_quality_scoring:
            validation = await self._phase_validate_research(query, depth, sources, analysis)
            self._log_validation_results(validation)
        else:
            validation = None
        self._monitor.end_operation(validation_event, success=True)

        return analysis, validation

    def _get_follow_up_queries(
        self,
        query: str,
        analysis: AnalysisResult | dict[str, Any],
        validation: ValidationResult | dict[str, Any] | None,
    ) -> list[str]:
        """Return follow-up queries for the next iteration, if needed."""
        analysis_result = AnalysisResult.model_validate(analysis)
        validation_result = (
            ValidationResult.model_validate(validation) if validation is not None else None
        )

        if not self._config.research.enable_iterative_search:
            return []

        if validation_result and not validation_result.needs_follow_up:
            return []

        follow_up_queries: list[str] = []
        if validation_result:
            follow_up_queries.extend(validation_result.follow_up_queries)

        if not follow_up_queries:
            for gap in analysis_result.normalized_gaps():
                follow_up_queries.extend(gap.suggested_queries)
                follow_up_queries.append(f"{query} {gap.gap_description}")

        deduplicated: list[str] = []
        seen = set()
        for candidate in follow_up_queries:
            normalized = candidate.strip().lower()
            if normalized and normalized not in seen:
                seen.add(normalized)
                deduplicated.append(candidate.strip())
        return deduplicated[:8]

    async def _run_follow_up_collection(
        self,
        existing_sources: list[SearchResultItem],
        follow_up_queries: list[str],
        depth: ResearchDepth,
        min_sources: int | None,
    ) -> list[SearchResultItem]:
        """Collect follow-up sources and merge them with existing sources."""
        self._monitor.section("Iterative Follow-up Search")
        self._monitor.log(f"Follow-up queries: {len(follow_up_queries)}")

        if self._parallel_mode and self._agent_pool:
            new_sources = await self._phase_parallel_research(
                follow_up_queries,
                depth,
                min_sources,
            )
        else:
            new_sources = await self._phase_collect_sources(
                follow_up_queries,
                depth,
                min_sources,
            )

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
        from cc_deep_research.aggregation import ResultAggregator

        aggregator = ResultAggregator(
            deduplicate=True,
            sort_by_score=True,
            monitor=self._monitor.is_enabled(),
        )

        for source_set, provider in (
            (existing_sources, "existing"),
            (new_sources, "follow-up"),
        ):
            for source in source_set:
                aggregator.add_result(
                    SearchResult(
                        query="iterative-search",
                        results=[source],
                        provider=provider,
                    )
                )

        return aggregator.get_aggregated()

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
        self._monitor.section("Validation")

        # Create session for validation
        session = ResearchSession(
            session_id="validation",
            query=query,
            sources=sources,
        )

        validator: ValidatorAgent = self._agents[AGENT_TYPE_VALIDATOR]
        min_sources = self._config.research.min_sources.__dict__[depth.value]
        validation = validator.validate_research(
            session,
            analysis,
            query=query,
            min_sources_override=min_sources,
        )

        self._monitor.log(f"Quality score: {validation.quality_score:.2f}")
        self._monitor.log(f"Valid: {validation.is_valid}")
        self._monitor.record_reasoning_summary(
            stage="validation",
            summary=(
                f"Quality score {validation.quality_score:.2f}, valid={validation.is_valid}"
            ),
            agent_id=AGENT_TYPE_VALIDATOR,
        )

        if validation.issues:
            self._monitor.log(f"Issues: {len(validation.issues)}")

        if validation.warnings:
            self._monitor.log(f"Warnings: {len(validation.warnings)}")

        return validation

    def _log_validation_results(self, validation: ValidationResult) -> None:
        """Log validation results.

        Args:
            validation: Validation results dictionary.
        """
        if not validation:
            return

        if validation.issues:
            self._monitor.section("Validation Issues")
            for issue in validation.issues:
                self._monitor.log(f"  - {issue}")

        if validation.warnings:
            self._monitor.section("Validation Warnings")
            for warning in validation.warnings:
                self._monitor.log(f"  - {warning}")

        if validation.recommendations:
            self._monitor.section("Recommendations")
            for rec in validation.recommendations:
                self._monitor.log(f"  - {rec}")

    async def _fetch_content_for_top_sources(
        self,
        sources: list[SearchResultItem],
        depth: ResearchDepth,
    ) -> list[SearchResultItem]:
        """Fetch full content for top-scoring sources.

        Args:
            sources: List of collected sources.
            depth: Research depth mode.

        Returns:
            Sources with content filled in for top sources.
        """

        # Determine how many sources to fetch content for
        num_to_fetch = getattr(self._config.research, "top_sources_for_content", 15)
        if depth != ResearchDepth.DEEP:
            num_to_fetch = min(num_to_fetch, 10)

        # Sort by score and get top N
        sorted_sources = sorted(sources, key=lambda s: getattr(s, "score", 0) or 0, reverse=True)
        top_sources = sorted_sources[:num_to_fetch]

        if not top_sources:
            return sources

        self._monitor.log(f"Fetching full content for top {len(top_sources)} sources...")

        sources_needing_fetch = [
            source
            for source in sources
            if source in top_sources and not (source.content and len(source.content) > 500)
        ]

        await asyncio.gather(
            *(self._populate_source_content(source) for source in sources_needing_fetch),
            return_exceptions=True,
        )

        return sources

    async def _populate_source_content(self, source: SearchResultItem) -> None:
        """Populate a source with fetched content when available."""
        try:
            content = await self._fetch_page_content(source.url)
            if content and len(content) > 200:
                source.content = content
                title = source.title[:50] if source.title else source.url
                self._monitor.log(f"  ✓ Fetched content for: {title}...")
        except Exception as e:
            self._monitor.log(f"  ✗ Failed to fetch {source.url}: {e}")

    async def _fetch_page_content(self, url: str) -> str | None:
        """Fetch page content using web_reader MCP tool.

        Args:
            url: URL to fetch content from.

        Returns:
            Page content as string, or None if fetch fails.
        """
        cached_content = self._content_cache.get(url)
        if cached_content is not None:
            return cached_content

        try:
            import time

            start_time = time.time()
            # Import the web_reader MCP tool
            # Note: This uses the MCP tool that's available in the environment
            from mcp__web_reader__webReader import webReader  # type: ignore[import-not-found]

            result = webReader(
                url=url,
                timeout=15,
                return_format="markdown",
                retain_images=False,
            )

            # Extract content from the result
            if isinstance(result, dict) and "content" in result:
                content = str(result["content"])
                self._content_cache[url] = content
                self._monitor.record_tool_call(
                    tool_name="mcp.web_reader",
                    status="success",
                    duration_ms=int((time.time() - start_time) * 1000),
                    url=url,
                )
                return content
            elif isinstance(result, str):
                self._content_cache[url] = result
                self._monitor.record_tool_call(
                    tool_name="mcp.web_reader",
                    status="success",
                    duration_ms=int((time.time() - start_time) * 1000),
                    url=url,
                )
                return result
            else:
                self._monitor.record_tool_call(
                    tool_name="mcp.web_reader",
                    status="error",
                    duration_ms=int((time.time() - start_time) * 1000),
                    url=url,
                    error="No content returned",
                )
                return None
        except ImportError:
            self._monitor.log("web_reader MCP not available, skipping content fetch")
            return None
        except Exception as e:
            self._monitor.log(f"Error fetching page content: {e}")
            self._monitor.record_tool_call(
                tool_name="mcp.web_reader",
                status="error",
                duration_ms=0,
                url=url,
                error=str(e),
            )
            return None

    async def _shutdown_team(self) -> None:
        """Shutdown the research team.

        Cleans up all team resources and agents.
        """
        # Shutdown coordination layer for parallel mode
        if self._parallel_mode:
            if self._message_bus:
                await self._message_bus.shutdown()
            if self._agent_pool:
                await self._agent_pool.shutdown()
            self._monitor.log("Coordination layer shut down")

        if self._team:
            await self._team.shutdown()
            self._team = None
            self._monitor.section("Team Shutdown")
            self._monitor.log("Team shut down successfully")

        collector = self._agents.get(AGENT_TYPE_COLLECTOR)
        if isinstance(collector, SourceCollectorAgent):
            await collector.close_providers()

    async def _phase_parallel_research(
        self,
        queries: list[str],
        depth: ResearchDepth,
        min_sources: int | None,
    ) -> list[SearchResultItem]:
        """Phase 3 (Parallel): Collect sources using multiple researchers.

        Args:
            queries: List of queries to search.
            depth: Research depth mode.
            min_sources: Minimum sources required.

        Returns:
            Aggregated list of search result items.
        """
        self._monitor.section("Parallel Source Collection")

        if not self._agent_pool:
            msg = "Agent pool not initialized for parallel mode"
            raise RuntimeError(msg)

        # Determine max results per researcher
        max_results_per_researcher = (
            min_sources or self._config.research.min_sources.__dict__[depth.value]
        ) // self._num_researchers

        # Create Tavily provider with key rotation
        from cc_deep_research.key_rotation import KeyRotationManager

        provider_warnings: list[str] = []
        if not self._config.tavily.api_keys:
            provider_warnings.append(
                "Parallel source collection requires Tavily API keys, but none are configured."
            )
        if self._config.search.providers != ["tavily"]:
            provider_warnings.append(
                "Parallel source collection currently uses Tavily only, regardless of other configured providers."
            )
        self._set_provider_metadata(
            available=["tavily"] if self._config.tavily.api_keys else [],
            warnings=provider_warnings,
        )

        key_manager = KeyRotationManager(self._config.tavily.api_keys)
        from cc_deep_research.providers.tavily import TavilySearchProvider

        provider = TavilySearchProvider(
            api_key=key_manager.get_available_key(),
            max_results=max_results_per_researcher,
        )

        # Create researcher agent
        from cc_deep_research.agents import ResearcherAgent

        researcher = ResearcherAgent(self._config, provider, monitor=self._monitor)

        # Decompose queries into tasks
        tasks = self._decompose_tasks(queries)

        self._monitor.log(f"Decomposed {len(queries)} queries into {len(tasks)} tasks")
        for task in tasks:
            self._monitor.log_researcher_event(
                event_type="spawned",
                agent_id=task["task_id"],
                query=task["query"],
            )

        # Execute research in parallel
        researcher_timeout = getattr(self._config.search_team, "researcher_timeout", 120)

        results = await researcher.execute_multiple_tasks(
            tasks,
            timeout=researcher_timeout,
        )

        # Aggregate results
        all_sources: list[SearchResultItem] = []
        for result in results:
            if result["status"] == "success":
                all_sources.extend(result["sources"])
                self._monitor.log(
                    f"✓ Researcher {result['task_id']}: "
                    f"{result['source_count']} sources "
                    f"({result['execution_time_ms']:.0f}ms)"
                )
                self._monitor.log_researcher_event(
                    event_type="completed",
                    agent_id=result["task_id"],
                    source_count=result["source_count"],
                    duration_ms=int(result["execution_time_ms"]),
                    status="completed",
                )
                self._monitor.record_reasoning_summary(
                    stage="researcher_task",
                    summary=f"Executed query and gathered {result['source_count']} sources",
                    agent_id=result["task_id"],
                    query=result.get("query", ""),
                )
            else:
                self._monitor.log(
                    f"✗ Researcher {result['task_id']}: "
                    f"{result['status']} - {result.get('error', 'Unknown error')}"
                )
                self._monitor.log_researcher_event(
                    event_type="failed" if result["status"] != "timeout" else "timeout",
                    agent_id=result["task_id"],
                    status=result["status"],
                    error=result.get("error", "Unknown error"),
                )

        # Deduplicate and aggregate
        from cc_deep_research.aggregation import ResultAggregator

        aggregator = ResultAggregator(
            deduplicate=True,
            sort_by_score=True,
            monitor=self._monitor.is_enabled(),
        )

        # Wrap each source in SearchResult for the aggregator
        for source in all_sources:
            search_result = SearchResult(
                query="parallel-research",
                results=[source],
                provider="tavily",
            )
            aggregator.add_result(search_result)

        aggregated = aggregator.get_aggregated()
        self._used_parallel_collection = True

        self._monitor.log(f"Collected {len(aggregated)} unique sources (parallel)")

        # Fetch full content for top sources
        aggregated = await self._fetch_content_for_top_sources(aggregated, depth)

        return aggregated

    def _decompose_tasks(
        self,
        queries: list[str],
    ) -> list[dict[str, str]]:
        """Decompose research into parallel tasks.

        Args:
            queries: List of queries to decompose.

        Returns:
            List of task dictionaries.
        """
        tasks = []
        for i, query in enumerate(queries):
            tasks.append(
                {
                    "task_id": f"task-{i + 1}",
                    "query": query,
                }
            )

        return tasks

    async def _reflect_at(
        self,
        stage: str,
        question: str,
        context: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Perform strategic reflection at a decision point.

        Args:
            stage: Research stage where reflection occurs.
            question: Question or prompt for reflection.
            context: Optional context for the reflection.

        Returns:
            Reflection dictionary with analysis and decisions.
        """
        from cc_deep_research.coordination import Reflection

        reflection = Reflection(
            stage=stage,
            question=question,
            analysis="",
        )

        # Log reflection point
        self._monitor.section(f"Reflection: {stage}")
        self._monitor.log(f"Question: {question}")

        # In a real implementation, this would use AI to analyze
        # For now, we do a simple analysis
        reflection.analysis = f"Reflection at {stage}: {question}"
        reflection.decision = "Continue with current strategy"

        if context:
            self._monitor.log(f"Context: {context}")

        return {
            "stage": stage,
            "question": question,
            "analysis": reflection.analysis,
            "decision": reflection.decision,
        }


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
