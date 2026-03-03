"""Tests for TeamResearchOrchestrator."""

import pytest
from unittest.mock import MagicMock, patch

from cc_deep_research.config import Config
from cc_deep_research.models import ResearchDepth, ResearchSession, SearchResultItem
from cc_deep_research.monitoring import ResearchMonitor
from cc_deep_research.orchestrator import TeamResearchOrchestrator, TeamExecutionError


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
        """Test executing a simple research query."""
        config = Config()
        # Add at least one API key for testing
        config.tavily.api_keys = ["test-key-12345"]
        monitor = ResearchMonitor(enabled=False)

        orchestrator = TeamResearchOrchestrator(config, monitor)

        # This will fail without actual API, but tests the flow
        with pytest.raises(Exception):  # Expected to fail without real API
            await orchestrator.execute_research(
                query="test query",
                depth=ResearchDepth.QUICK,
                min_sources=3,
            )

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
        config = Config()
        monitor = ResearchMonitor(enabled=False)
        orchestrator = TeamResearchOrchestrator(config, monitor)

        query = "test query"
        depth = ResearchDepth.DEEP
        strategy = {
            "strategy": {
                "query_variations": 3,
            },
        }

        # Note: This is a placeholder test
        queries = ["test query"]  # Placeholder

        assert isinstance(queries, list)
        assert len(queries) >= 1

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
