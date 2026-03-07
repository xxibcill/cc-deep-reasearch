"""Tests for agent team functionality."""

import pytest

from cc_deep_research.agents.research_lead import ResearchLeadAgent
from cc_deep_research.config import Config
from cc_deep_research.models import ResearchDepth
from cc_deep_research.teams import AgentSpec, ResearchTeam, TeamConfig, TeamCreationError


class TestAgentSpec:
    """Tests for AgentSpec dataclass."""

    def test_agent_spec_creation(self) -> None:
        """Test that AgentSpec can be created with required parameters."""
        spec = AgentSpec(
            name="test-agent",
            description="Test agent description",
            agent_type="test",
        )
        assert spec.name == "test-agent"
        assert spec.description == "Test agent description"
        assert spec.agent_type == "test"
        assert spec.model == "claude-sonnet-4-6"  # Default

    def test_agent_spec_with_custom_model(self) -> None:
        """Test that AgentSpec accepts custom model."""
        spec = AgentSpec(
            name="test-agent",
            description="Test agent",
            agent_type="test",
            model="claude-opus-4-6",
        )
        assert spec.model == "claude-opus-4-6"


class TestTeamConfig:
    """Tests for TeamConfig dataclass."""

    def test_team_config_creation(self) -> None:
        """Test that TeamConfig can be created."""
        config = TeamConfig(
            team_name="test-team",
            team_description="Test team",
        )
        assert config.team_name == "test-team"
        assert config.team_description == "Test team"
        assert config.timeout_seconds == 300  # Default
        assert config.parallel_execution is True  # Default
        assert config.agents == []  # Default

    def test_team_config_with_agents(self) -> None:
        """Test that TeamConfig accepts agent list."""
        agents = [
            AgentSpec("agent1", "Agent 1", "type1"),
            AgentSpec("agent2", "Agent 2", "type2"),
        ]
        config = TeamConfig(
            team_name="test-team",
            team_description="Test team",
            agents=agents,
        )
        assert len(config.agents) == 2


class TestResearchTeam:
    """Tests for ResearchTeam class."""

    def test_team_initialization(self) -> None:
        """Test that ResearchTeam can be initialized."""
        team_config = TeamConfig(
            team_name="test-team",
            team_description="Test team",
        )
        app_config = Config()
        team = ResearchTeam(team_config, app_config)

        assert not team.is_active
        assert team.team_name == "test-team"

    def test_get_agent_specs(self) -> None:
        """Test getting agent specifications from team."""
        agents = [
            AgentSpec("agent1", "Agent 1", "type1"),
            AgentSpec("agent2", "Agent 2", "type2"),
        ]
        team_config = TeamConfig(
            team_name="test-team",
            team_description="Test team",
            agents=agents,
        )
        app_config = Config()
        team = ResearchTeam(team_config, app_config)

        specs = team.get_agent_specs()
        assert len(specs) == 2
        assert specs[0].name == "agent1"

    def test_get_agent_by_type(self) -> None:
        """Test getting agent by type."""
        agents = [
            AgentSpec("collector", "Collector", "collector"),
            AgentSpec("analyzer", "Analyzer", "analyzer"),
        ]
        team_config = TeamConfig(
            team_name="test-team",
            team_description="Test team",
            agents=agents,
        )
        app_config = Config()
        team = ResearchTeam(team_config, app_config)

        collector = team.get_agent_by_type("collector")
        assert collector is not None
        assert collector.name == "collector"

        non_existent = team.get_agent_by_type("reporter")
        assert non_existent is None

    @pytest.mark.asyncio
    async def test_team_create_and_shutdown(self) -> None:
        """Test team create and shutdown lifecycle."""
        team_config = TeamConfig(
            team_name="test-team",
            team_description="Test team",
        )
        app_config = Config()
        team = ResearchTeam(team_config, app_config)

        # Create team
        await team.create()
        assert team.is_active

        # Shutdown team
        await team.shutdown()
        assert not team.is_active


class TestResearchLeadAgent:
    """Tests for deterministic query intent classification."""

    @pytest.mark.parametrize(
        ("query", "expected_intent", "expected_sources", "time_sensitive"),
        [
            (
                "Compare Nvidia and AMD data center strategy",
                "comparative",
                ["official_docs", "market_analysis"],
                False,
            ),
            (
                "Latest FDA guidance on GLP-1 compounding",
                "time-sensitive",
                ["news", "official_docs"],
                True,
            ),
            (
                "What evidence supports creatine for cognitive performance",
                "evidence-seeking",
                ["academic"],
                False,
            ),
            (
                "How does retrieval augmented generation work",
                "informational",
                ["news"],
                False,
            ),
        ],
    )
    def test_analyze_query_classifies_intent_and_source_classes(
        self,
        query: str,
        expected_intent: str,
        expected_sources: list[str],
        time_sensitive: bool,
    ) -> None:
        agent = ResearchLeadAgent({})

        strategy = agent.analyze_query(query, ResearchDepth.STANDARD)

        assert strategy.profile.intent == expected_intent
        assert strategy.strategy.intent == expected_intent
        assert strategy.profile.is_time_sensitive is time_sensitive
        assert strategy.strategy.time_sensitive is time_sensitive
        assert strategy.profile.target_source_classes == expected_sources
        assert strategy.strategy.target_source_classes == expected_sources

    def test_analyze_query_detects_time_sensitivity_from_explicit_date_without_year_whitelist(
        self,
    ) -> None:
        agent = ResearchLeadAgent({})

        strategy = agent.analyze_query(
            "What changed in SEC climate disclosure rules in March 2027",
            ResearchDepth.STANDARD,
        )

        assert strategy.profile.intent == "time-sensitive"
        assert strategy.profile.is_time_sensitive is True
        assert "news" in strategy.strategy.target_source_classes
        assert "official_docs" in strategy.strategy.target_source_classes

    def test_analyze_query_adds_compare_task_for_comparative_queries(self) -> None:
        agent = ResearchLeadAgent({})

        strategy = agent.analyze_query(
            "Compare Anthropic versus OpenAI enterprise pricing",
            ResearchDepth.DEEP,
        )

        assert "compare" in strategy.tasks_needed
        assert strategy.strategy.follow_up_bias == "comparison_evidence"


class TestTeamCreationError:
    """Tests for TeamCreationError."""

    def test_team_creation_error(self) -> None:
        """Test that TeamCreationError can be raised."""
        with pytest.raises(TeamCreationError) as exc_info:
            raise TeamCreationError(
                message="Test error",
                team_name="test-team",
            )

        error = exc_info.value
        assert str(error) == "Test error"
        assert error.team_name == "test-team"
