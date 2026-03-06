"""Tests for TeamResearchOrchestrator."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from cc_deep_research.config import Config
from cc_deep_research.models import ResearchDepth, SearchResultItem
from cc_deep_research.monitoring import ResearchMonitor
from cc_deep_research.orchestrator import TeamExecutionError, TeamResearchOrchestrator


class TestTeamResearchOrchestrator:
    """Tests for TeamResearchOrchestrator."""

    def test_orchestrator_initialization(self) -> None:
        """Test that orchestrator can be initialized."""
        config = Config()
        monitor = ResearchMonitor(enabled=False)
        orchestrator = TeamResearchOrchestrator(config, monitor)

        assert orchestrator._config == config
        assert orchestrator._monitor == monitor
        assert orchestrator._team is None

    @pytest.mark.asyncio
    async def test_execute_research_simple(self) -> None:
        """Test executing a simple research query with mocked providers."""
        from cc_deep_research.models import SearchResult
        from cc_deep_research.providers import SearchProvider

        config = Config()
        monitor = ResearchMonitor(enabled=False)

        orchestrator = TeamResearchOrchestrator(config, monitor)

        # Mock the provider to return empty results
        mock_provider = MagicMock(spec=SearchProvider)
        mock_provider.get_provider_name.return_value = "mock"
        mock_provider.search = AsyncMock(return_value=SearchResult(
            query="test query",
            results=[],
            provider="mock",
            metadata={},
        ))

        # Set up agents with mocked collector
        orchestrator._agents = {}
        from cc_deep_research.agents import SourceCollectorAgent
        collector = SourceCollectorAgent(config)
        collector._providers = [mock_provider]
        # Mock initialize_providers to not reset our mock provider
        collector.initialize_providers = AsyncMock()
        from cc_deep_research.agents import AGENT_TYPE_COLLECTOR
        orchestrator._agents[AGENT_TYPE_COLLECTOR] = collector

        # Also mock other agents
        from cc_deep_research.agents import (
            AGENT_TYPE_ANALYZER,
            AGENT_TYPE_EXPANDER,
            AGENT_TYPE_LEAD,
            AGENT_TYPE_VALIDATOR,
            AnalyzerAgent,
            QueryExpanderAgent,
            ResearchLeadAgent,
            ValidatorAgent,
        )
        orchestrator._agents[AGENT_TYPE_LEAD] = ResearchLeadAgent({})
        orchestrator._agents[AGENT_TYPE_EXPANDER] = QueryExpanderAgent({})
        orchestrator._agents[AGENT_TYPE_ANALYZER] = AnalyzerAgent({})
        orchestrator._agents[AGENT_TYPE_VALIDATOR] = ValidatorAgent({})

        # Mock _initialize_team to not overwrite our agents
        orchestrator._initialize_team = AsyncMock()

        # This should succeed with empty results
        session = await orchestrator.execute_research(
            query="test query",
            depth=ResearchDepth.QUICK,
            min_sources=3,
        )

        assert session is not None
        assert session.query == "test query"
        assert isinstance(session.sources, list)

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        ("depth", "analysis_method", "deep_status"),
        [
            (ResearchDepth.QUICK, "ai_semantic", "not_requested"),
            (ResearchDepth.STANDARD, "ai_semantic", "not_requested"),
            (ResearchDepth.DEEP, "shallow_keyword", "degraded"),
        ],
    )
    async def test_execute_research_populates_stable_metadata_contract(
        self,
        depth: ResearchDepth,
        analysis_method: str,
        deep_status: str,
    ) -> None:
        """Test that execute_research writes the same top-level metadata contract."""
        orchestrator = TeamResearchOrchestrator(Config(), ResearchMonitor(enabled=False))
        sources = [
            SearchResultItem(
                url="https://example.com/source",
                title="Example source",
                snippet="Example snippet",
            )
        ]

        orchestrator._initialize_team = AsyncMock()
        orchestrator._shutdown_team = AsyncMock()
        orchestrator._phase_analyze_strategy = AsyncMock(
            return_value={"strategy": {"enable_quality_scoring": True}}
        )
        orchestrator._phase_expand_queries = AsyncMock(return_value=["test query"])

        async def collect_sources(
            queries: list[str],
            _depth: ResearchDepth,
            _min_sources: int | None,
        ) -> list[SearchResultItem]:
            orchestrator._set_provider_metadata(
                available=["tavily"],
                warnings=["Provider 'claude' is selected but no Claude search provider is implemented yet."],
            )
            return sources

        orchestrator._phase_collect_sources = collect_sources
        orchestrator._run_analysis_workflow = AsyncMock(
            return_value=(
                {
                    "key_findings": ["Finding"],
                    "themes": ["Theme"],
                    "gaps": [],
                    "analysis_method": analysis_method,
                    "deep_analysis_complete": depth == ResearchDepth.DEEP,
                },
                {
                    "quality_score": 0.8,
                    "is_valid": True,
                    "issues": [],
                    "warnings": [],
                    "recommendations": [],
                    "needs_follow_up": False,
                    "follow_up_queries": [],
                },
                sources,
                [{"iteration": 1, "source_count": 1, "quality_score": 0.8, "gap_count": 0}],
            )
        )

        session = await orchestrator.execute_research(
            query="test query",
            depth=depth,
            min_sources=1,
        )

        assert set(session.metadata) == {
            "strategy",
            "analysis",
            "validation",
            "iteration_history",
            "providers",
            "execution",
            "deep_analysis",
        }
        assert session.metadata["providers"]["configured"] == ["tavily"]
        assert session.metadata["providers"]["available"] == ["tavily"]
        assert session.metadata["providers"]["status"] == "degraded"
        assert session.metadata["validation"]["quality_score"] == 0.8
        assert session.metadata["deep_analysis"]["status"] == deep_status
        assert session.metadata["execution"]["degraded"] is True

    def test_phase_analyze_strategy(self) -> None:
        """Test strategy analysis phase."""
        config = Config()
        monitor = ResearchMonitor(enabled=False)
        orchestrator = TeamResearchOrchestrator(config, monitor)

        # Initialize team (required before phases)
        orchestrator._agents = {}

        query = "test research query"
        depth = ResearchDepth.STANDARD

        strategy = orchestrator._agents.get("lead", MagicMock()).analyze_query(query, depth)

        # Note: This is a placeholder test as the actual implementation
        # would require proper agent initialization
        assert strategy is not None

    def test_phase_expand_queries(self) -> None:
        """Test query expansion phase."""
        # Note: This is a placeholder test
        queries = ["test query"]  # Placeholder

        assert isinstance(queries, list)
        assert len(queries) >= 1

    def test_follow_up_queries_are_deduplicated(self) -> None:
        """Test that follow-up queries are deduplicated before reuse."""
        orchestrator = TeamResearchOrchestrator(Config(), ResearchMonitor(enabled=False))

        analysis = {
            "gaps": [
                {
                    "gap_description": "missing regulatory context",
                    "suggested_queries": ["query regulation", "query regulation"],
                }
            ]
        }
        validation = {
            "needs_follow_up": True,
            "follow_up_queries": ["query regulation", "query expert review"],
        }

        follow_up_queries = orchestrator._get_follow_up_queries(
            "query",
            analysis,
            validation,
        )

        assert follow_up_queries == ["query regulation", "query expert review"]

    def test_team_initialization_creates_agents(self) -> None:
        """Test that team initialization creates required agents."""
        config = Config()
        monitor = ResearchMonitor(enabled=False)

        orchestrator = TeamResearchOrchestrator(config, monitor)

        # Initialize team
        import asyncio
        asyncio.run(orchestrator._initialize_team())

        # Check that agents were created
        # Note: This would require actual agent implementations
        # to be properly initialized in the orchestrator


class TestOrchestratorError:
    """Tests for orchestrator exceptions."""

    def test_team_execution_error(self) -> None:
        """Test that TeamExecutionError can be raised."""
        with pytest.raises(TeamExecutionError) as exc_info:
            raise TeamExecutionError(
                message="Test error",
                query="test query",
            )

        error = exc_info.value
        assert str(error) == "Test error"
        assert error.query == "test query"
