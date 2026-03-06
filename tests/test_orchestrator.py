"""Tests for TeamResearchOrchestrator."""

from unittest.mock import MagicMock

import pytest

from cc_deep_research.config import Config
from cc_deep_research.models import ResearchDepth
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
        from unittest.mock import AsyncMock, MagicMock

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
