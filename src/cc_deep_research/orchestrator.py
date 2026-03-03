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
from cc_deep_research.coordination import AgentPool, MessageBus, ResearchState
from cc_deep_research.models import ResearchDepth, ResearchSession, SearchOptions, SearchResult, SearchResultItem
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
        self._parallel_mode = parallel_mode if parallel_mode is not None else config.search_team.parallel_execution
        self._num_researchers = num_researchers or config.search_team.num_researchers
        self._message_bus: MessageBus | None = None
        self._agent_pool: AgentPool | None = None

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

        self._monitor.section("Research Session")
        self._monitor.log(f"Query: {query}")
        self._monitor.log(f"Depth: {depth.value}")

        # Create session ID
        session_id = f"research-{uuid.uuid4().hex[:12]}"
        self._monitor.log(f"Session ID: {session_id}")

        # Initialize team
        self._notify_phase(
            phase_hook,
            phase_key="team_init",
            description="Initializing agent team",
        )
        await self._initialize_team()

        # Phase 1: Analyze query and determine strategy
        self._notify_phase(
            phase_hook,
            phase_key="strategy",
            description="Analyzing research strategy",
        )
        strategy = await self._phase_analyze_strategy(query, depth)

        # Phase 2: Expand queries if needed
        self._notify_phase(
            phase_hook,
            phase_key="query_expansion",
            description="Expanding search queries",
        )
        queries = await self._phase_expand_queries(query, strategy, depth)

        # Phase 3: Collect sources (parallel or sequential)
        self._notify_phase(
            phase_hook,
            phase_key="source_collection",
            description="Collecting sources from providers",
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

        # Phase 4: Analyze findings
        self._notify_phase(
            phase_hook,
            phase_key="analysis",
            description="Analyzing findings",
        )
        analysis = await self._phase_analyze_findings(
            sources,
            query,
            strategy,
        )

        # Phase 4.5: Deep analysis (deep mode only)
        if depth == ResearchDepth.DEEP:
            self._notify_phase(
                phase_hook,
                phase_key="deep_analysis",
                description="Performing deep multi-pass analysis",
            )
            deep_analysis = await self._phase_deep_analysis(
                sources,
                query,
                analysis,
            )
            # Merge deep analysis results
            analysis.update(deep_analysis)

        # Phase 5: Validate quality (if enabled)
        self._notify_phase(
            phase_hook,
            phase_key="validation",
            description="Validating research quality",
        )
        if strategy.get("enable_quality_scoring", True):
            validation = await self._phase_validate_research(
                query,
                sources,
                analysis,
            )
            self._log_validation_results(validation)
        else:
            validation = None

        # Create and return session
        session = ResearchSession(
            session_id=session_id,
            query=query,
            depth=depth,
            sources=sources,
            started_at=start_time,
            completed_at=datetime.utcnow(),
            metadata={
                "strategy": strategy,
                "analysis": analysis,
                "validation": validation,
                "deep_analysis": analysis.get("deep_analysis_complete", False),
            },
        )

        # Summary
        self._monitor.section("Summary")
        self._monitor.log(f"Total sources: {len(sources)}")
        self._monitor.log(f"Key findings: {len(analysis.get('key_findings', []))}")
        if validation:
            self._monitor.log(f"Quality score: {validation['quality_score']:.2f}")

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

        return session

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
        self._agents = {
            AGENT_TYPE_LEAD: ResearchLeadAgent({}),
            AGENT_TYPE_COLLECTOR: SourceCollectorAgent(self._config),
            AGENT_TYPE_EXPANDER: QueryExpanderAgent({}),
            AGENT_TYPE_ANALYZER: AnalyzerAgent({}),
            AGENT_TYPE_DEEP_ANALYZER: DeepAnalyzerAgent(
                {
                    "deep_analysis_passes": self._config.research.deep_analysis_passes,
                }
            ),
            AGENT_TYPE_REPORTER: ReporterAgent({}),
            AGENT_TYPE_VALIDATOR: ValidatorAgent({}),
        }

        self._monitor.log(f"Team created with {len(agent_specs)} agents")

    async def _phase_analyze_strategy(
        self,
        query: str,
        depth: ResearchDepth,
    ) -> dict[str, Any]:
        """Phase 1: Analyze query and determine research strategy.

        Args:
            query: Research query.
            depth: Research depth mode.

        Returns:
            Strategy dictionary.
        """
        self._monitor.section("Strategy Analysis")

        lead: ResearchLeadAgent = self._agents[AGENT_TYPE_LEAD]
        strategy = lead.analyze_query(query, depth)

        self._monitor.log(f"Complexity: {strategy['complexity']}")
        self._monitor.log(f"Tasks: {len(strategy['tasks_needed'])}")
        self._monitor.log(f"Query variations: {strategy['strategy']['query_variations']}")

        return strategy

    async def _phase_expand_queries(
        self,
        query: str,
        strategy: dict[str, Any],
        depth: ResearchDepth,
    ) -> list[str]:
        """Phase 2: Expand queries for comprehensive coverage.

        Args:
            query: Original query.
            strategy: Research strategy.
            depth: Research depth mode.

        Returns:
            List of query variations.
        """
        self._monitor.section("Query Expansion")

        variations = strategy["strategy"]["query_variations"]

        if variations <= 1:
            self._monitor.log("Query expansion not needed (quick mode)")
            return [query]

        expander: QueryExpanderAgent = self._agents[AGENT_TYPE_EXPANDER]
        queries = expander.expand_query(query, depth)

        self._monitor.log(f"Generated {len(queries)} query variations")

        return queries

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

        collector = self._agents[AGENT_TYPE_COLLECTOR]

        # Initialize providers
        await collector.initialize_providers()

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
        _strategy: dict[str, Any],
    ) -> dict[str, Any]:
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

        self._monitor.log(f"Key findings: {len(analysis['key_findings'])}")
        self._monitor.log(f"Themes identified: {len(analysis['themes'])}")
        self._monitor.log(f"Gaps: {len(analysis['gaps'])}")

        return analysis

    async def _phase_deep_analysis(
        self,
        sources: list[SearchResultItem],
        query: str,
        analysis: dict[str, Any],  # noqa: ARG002
    ) -> dict[str, Any]:
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
        deep_analysis = deep_analyzer.deep_analyze(sources, query)

        self._monitor.log(f"Deep analysis passes: {deep_analysis['analysis_passes']}")
        self._monitor.log(f"Deep themes: {len(deep_analysis['themes'])}")
        self._monitor.log(f"Consensus points: {len(deep_analysis['consensus_points'])}")
        self._monitor.log(f"Disagreement points: {len(deep_analysis['disagreement_points'])}")

        return deep_analysis

    async def _phase_validate_research(
        self,
        query: str,
        sources: list[SearchResultItem],
        analysis: dict[str, Any],
    ) -> dict[str, Any]:
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
        validation = validator.validate_research(session, analysis)

        self._monitor.log(f"Quality score: {validation['quality_score']:.2f}")
        self._monitor.log(f"Valid: {validation['is_valid']}")

        if validation["issues"]:
            self._monitor.log(f"Issues: {len(validation['issues'])}")

        if validation["warnings"]:
            self._monitor.log(f"Warnings: {len(validation['warnings'])}")

        return validation

    def _log_validation_results(self, validation: dict[str, Any]) -> None:
        """Log validation results.

        Args:
            validation: Validation results dictionary.
        """
        if not validation:
            return

        if validation["issues"]:
            self._monitor.section("Validation Issues")
            for issue in validation["issues"]:
                self._monitor.log(f"  - {issue}")

        if validation["warnings"]:
            self._monitor.section("Validation Warnings")
            for warning in validation["warnings"]:
                self._monitor.log(f"  - {warning}")

        if validation["recommendations"]:
            self._monitor.section("Recommendations")
            for rec in validation["recommendations"]:
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
        sorted_sources = sorted(
            sources,
            key=lambda s: getattr(s, "score", 0) or 0,
            reverse=True
        )
        top_sources = sorted_sources[:num_to_fetch]

        if not top_sources:
            return sources

        self._monitor.log(f"Fetching full content for top {len(top_sources)} sources...")

        # Use web_reader MCP to fetch content
        sources_with_content = []
        sources_needing_fetch = []

        # Separate sources that already have content vs those that need it
        for source in sources:
            if source.content and len(source.content) > 500:
                sources_with_content.append(source)
            elif source in top_sources:
                sources_needing_fetch.append(source)
            else:
                sources_with_content.append(source)

        # Fetch content for top sources that need it
        for source in sources_needing_fetch:
            try:
                # Use web_reader MCP tool to fetch page content
                content = await self._fetch_page_content(source.url)
                if content and len(content) > 200:
                    # Update source content
                    source.content = content
                    self._monitor.log(f"  ✓ Fetched content for: {source.title[:50]}...")
            except Exception as e:
                self._monitor.log(f"  ✗ Failed to fetch {source.url}: {e}")

        # Combine sources, maintaining order with updated sources first
        result = sources_with_content + sources_needing_fetch

        return result

    async def _fetch_page_content(self, url: str) -> str | None:
        """Fetch page content using web_reader MCP tool.

        Args:
            url: URL to fetch content from.

        Returns:
            Page content as string, or None if fetch fails.
        """
        try:
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
                return str(result["content"])
            elif isinstance(result, str):
                return result
            else:
                return None
        except ImportError:
            self._monitor.log("web_reader MCP not available, skipping content fetch")
            return None
        except Exception as e:
            self._monitor.log(f"Error fetching page content: {e}")
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
            (min_sources or self._config.research.min_sources.__dict__[depth.value])
            // self._num_researchers
        )

        # Create Tavily provider with key rotation
        from cc_deep_research.key_rotation import KeyRotationManager

        key_manager = KeyRotationManager(self._config.tavily.api_keys)
        from cc_deep_research.providers.tavily import TavilySearchProvider

        provider = TavilySearchProvider(
            api_key=key_manager.get_available_key(),
            max_results=max_results_per_researcher,
        )

        # Create researcher agent
        from cc_deep_research.agents import ResearcherAgent

        researcher = ResearcherAgent(self._config, provider)

        # Decompose queries into tasks
        tasks = self._decompose_tasks(queries)

        self._monitor.log(f"Decomposed {len(queries)} queries into {len(tasks)} tasks")

        # Execute research in parallel
        researcher_timeout = getattr(
            self._config.search_team, "researcher_timeout", 120
        )

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
            else:
                self._monitor.log(
                    f"✗ Researcher {result['task_id']}: "
                    f"{result['status']} - {result.get('error', 'Unknown error')}"
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

        self._monitor.log(f"Collected {len(aggregated)} unique sources (parallel)")

        # Fetch full content for top sources
        aggregated = await self._fetch_content_for_top_sources(
            aggregated,
            depth
        )

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
            tasks.append({
                "task_id": f"task-{i + 1}",
                "query": query,
            })

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
