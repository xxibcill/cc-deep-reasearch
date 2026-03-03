"""Research orchestrator using agent teams.

This module provides the TeamResearchOrchestrator class that coordinates
research operations using multiple specialized agents working together.
"""

import asyncio
import uuid
from typing import Any

from cc_deep_research.agents import (
    AGENT_TYPE_ANALYZER,
    AGENT_TYPE_COLLECTOR,
    AGENT_TYPE_EXPANDER,
    AGENT_TYPE_LEAD,
    AGENT_TYPE_REPORTER,
    AGENT_TYPE_VALIDATOR,
    AnalyzerAgent,
    QueryExpanderAgent,
    ReporterAgent,
    ResearchLeadAgent,
    SourceCollectorAgent,
    ValidatorAgent,
)
from cc_deep_research.agents.reporter import ReporterAgent as ReporterAgentImpl
from cc_deep_research.agents.validator import ValidatorAgent as ValidatorAgentImpl
from cc_deep_research.config import Config
from cc_deep_research.models import ResearchDepth, ResearchSession, SearchOptions
from cc_deep_research.monitoring import ResearchMonitor
from cc_deep_research.teams import AgentSpec, TeamConfig, ResearchTeam


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
    5. Validate quality (validator agent)
    6. Generate reports (reporter agent)
    """

    def __init__(
        self,
        config: Config,
        monitor: ResearchMonitor | None = None,
    ) -> None:
        """Initialize the research orchestrator.

        Args:
            config: Application configuration.
            monitor: Optional research monitor for progress tracking.
        """
        self._config = config
        self._monitor = monitor or ResearchMonitor(enabled=False)
        self._team: ResearchTeam | None = None
        self._agents: dict[str, Any] = {}

    async def execute_research(
        self,
        query: str,
        depth: ResearchDepth,
        min_sources: int | None = None,
    ) -> ResearchSession:
        """Execute a research query using the agent team.

        Args:
            query: Research query string.
            depth: Research depth mode (quick/standard/deep).
            min_sources: Minimum number of sources (optional).

        Returns:
            ResearchSession with complete research results.

        Raises:
            TeamExecutionError: If research execution fails.
        """
        self._monitor.section("Research Session")
        self._monitor.log(f"Query: {query}")
        self._monitor.log(f"Depth: {depth.value}")

        # Create session ID
        session_id = f"research-{uuid.uuid4().hex[:12]}"
        self._monitor.log(f"Session ID: {session_id}")

        # Initialize team
        await self._initialize_team()

        # Phase 1: Analyze query and determine strategy
        strategy = await self._phase_analyze_strategy(query, depth)

        # Phase 2: Expand queries if needed
        queries = await self._phase_expand_queries(query, strategy, depth)

        # Phase 3: Collect sources
        sources = await self._phase_collect_sources(
            queries,
            depth,
            min_sources,
        )

        # Phase 4: Analyze findings
        analysis = await self._phase_analyze_findings(
            sources,
            query,
            strategy,
        )

        # Phase 5: Validate quality (if enabled)
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
            metadata={
                "strategy": strategy,
                "analysis": analysis,
                "validation": validation,
            },
        )

        # Mark session as completed
        from datetime import datetime
        session.completed_at = datetime.utcnow()

        # Summary
        self._monitor.section("Summary")
        self._monitor.log(f"Total sources: {len(sources)}")
        self._monitor.log(f"Key findings: {len(analysis.get('key_findings', []))}")
        if validation:
            self._monitor.log(f"Quality score: {validation['quality_score']:.2f}")

        # Cleanup
        await self._shutdown_team()

        return session

    async def _initialize_team(self) -> None:
        """Initialize the research team with agents.

        Creates a team with specialized agents for different
        aspects of research.
        """
        if self._team is not None:
            return  # Already initialized

        self._monitor.section("Team Initialization")

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

        lead = self._agents[AGENT_TYPE_LEAD]
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

        expander = self._agents[AGENT_TYPE_EXPANDER]
        queries = expander.expand_query(query, depth)

        self._monitor.log(f"Generated {len(queries)} query variations")

        return queries

    async def _phase_collect_sources(
        self,
        queries: list[str],
        depth: ResearchDepth,
        min_sources: int | None,
    ) -> list:
        """Phase 3: Collect sources from providers.

        Args:
            queries: List of queries to search.
            depth: Research depth mode.
            min_sources: Minimum sources required.

        Returns:
            List of search result items.
        """
        self._monitor.section("Source Collection")

        collector = self._agents[AGENT_TYPE_COLLECTOR]

        # Initialize providers
        await collector.initialize_providers()

        # Determine max results
        max_results = self._config.research.min_sources.__dict__[depth.value]

        # Collect sources
        options = SearchOptions(
            max_results=max_results,
            search_depth=depth,
            monitor=self._monitor.is_enabled(),
        )

        if len(queries) == 1:
            sources = await collector.collect_sources(queries[0], options)
        else:
            sources = await collector.collect_multiple_queries(queries, options)

        self._monitor.log(f"Collected {len(sources)} sources")

        return sources

    async def _phase_analyze_findings(
        self,
        sources: list,
        query: str,
        strategy: dict[str, Any],
    ) -> dict[str, Any]:
        """Phase 4: Analyze collected findings.

        Args:
            sources: List of collected sources.
            query: Original research query.
            strategy: Research strategy.

        Returns:
            Analysis results dictionary.
        """
        self._monitor.section("Analysis")

        analyzer = self._agents[AGENT_TYPE_ANALYZER]
        analysis = analyzer.analyze_sources(sources, query)

        self._monitor.log(f"Key findings: {len(analysis['key_findings'])}")
        self._monitor.log(f"Themes identified: {len(analysis['themes'])}")
        self._monitor.log(f"Gaps: {len(analysis['gaps'])}")

        return analysis

    async def _phase_validate_research(
        self,
        query: str,
        sources: list,
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

        validator = self._agents[AGENT_TYPE_VALIDATOR]
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

    async def _shutdown_team(self) -> None:
        """Shutdown the research team.

        Cleans up all team resources and agents.
        """
        if self._team:
            await self._team.shutdown()
            self._team = None
            self._monitor.section("Team Shutdown")
            self._monitor.log("Team shut down successfully")


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
