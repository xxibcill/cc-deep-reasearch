"""Tests for LLM route planner."""

import os
from unittest.mock import MagicMock, patch

import pytest

from cc_deep_research.config import Config, LLMConfig
from cc_deep_research.llm.base import LLMProviderType, LLMTransportType
from cc_deep_research.models import (
    LLMPlanModel,
    LLMRouteModel,
    QueryProfile,
    ResearchDepth,
    StrategyPlan,
    StrategyResult,
)
from cc_deep_research.orchestration.llm_route_planner import (
    LLMRoutePlanner,
    create_llm_plan,
)


def create_test_config(
    *,
    claude_cli_enabled: bool = True,
    openrouter_enabled: bool = False,
    openrouter_api_key: str | None = None,
    cerebras_enabled: bool = False,
    cerebras_api_key: str | None = None,
    fallback_order: list[str] | None = None,
) -> Config:
    """Create a test config with LLM settings."""
    config = Config()

    config.llm.claude_cli.enabled = claude_cli_enabled
    config.llm.openrouter.enabled = openrouter_enabled
    config.llm.openrouter.api_key = openrouter_api_key
    config.llm.cerebras.enabled = cerebras_enabled
    config.llm.cerebras.api_key = cerebras_api_key

    if fallback_order:
        config.llm.fallback_order = fallback_order

    return config


def create_test_strategy() -> StrategyResult:
    """Create a test strategy result."""
    return StrategyResult(
        query="test query",
        complexity="moderate",
        depth=ResearchDepth.STANDARD,
        profile=QueryProfile(
            intent="informational",
            is_time_sensitive=False,
            key_terms=["test"],
            target_source_classes=["news"],
        ),
        strategy=StrategyPlan(
            query_variations=3,
            max_sources=10,
            enable_cross_ref=False,
            enable_quality_scoring=True,
            tasks=["expand", "collect", "analyze", "report"],
            follow_up_bias="coverage",
            intent="informational",
            time_sensitive=False,
            key_terms=["test"],
            target_source_classes=["news"],
        ),
        tasks_needed=["expand", "collect", "analyze", "report"],
    )


class TestLLMRoutePlanner:
    """Tests for LLMRoutePlanner."""

    def test_plan_routes_creates_plan(self) -> None:
        """Test that plan_routes creates a valid plan."""
        config = create_test_config()
        strategy = create_test_strategy()

        planner = LLMRoutePlanner(config)
        plan = planner.plan_routes(strategy)

        assert isinstance(plan, LLMPlanModel)
        assert plan.default_route is not None
        assert len(plan.fallback_order) > 0

    def test_plan_routes_with_all_transports_available(self) -> None:
        """Test plan with all transports available."""
        config = create_test_config(
            claude_cli_enabled=True,
            openrouter_enabled=True,
            openrouter_api_key="test-key",
            cerebras_enabled=True,
            cerebras_api_key="test-key",
        )
        strategy = create_test_strategy()

        planner = LLMRoutePlanner(config)

        with patch.object(planner, "_check_claude_cli_available", return_value=True):
            plan = planner.plan_routes(strategy)

        assert plan.default_route.transport in [
            LLMTransportType.CLAUDE_CLI,
            LLMTransportType.OPENROUTER_API,
            LLMTransportType.CEREBRAS_API,
        ]

    def test_plan_routes_without_claude_cli(self) -> None:
        """Test plan when Claude CLI is unavailable."""
        config = create_test_config(
            claude_cli_enabled=True,
            openrouter_enabled=True,
            openrouter_api_key="test-key",
        )
        strategy = create_test_strategy()

        planner = LLMRoutePlanner(config)

        with patch.object(planner, "_check_claude_cli_available", return_value=False):
            plan = planner.plan_routes(strategy)

        # Should fall back to OpenRouter
        assert plan.default_route.transport != LLMTransportType.CLAUDE_CLI

    def test_plan_routes_nested_session_constraint(self) -> None:
        """Test that nested session blocks Claude CLI."""
        config = create_test_config()
        strategy = create_test_strategy()

        planner = LLMRoutePlanner(config)

        with patch.dict(os.environ, {"CLAUDECODE": "1"}):
            available = planner._check_claude_cli_available()

        assert available is False

    def test_plan_routes_claude_cli_available(self) -> None:
        """Test Claude CLI availability check."""
        config = create_test_config()
        strategy = create_test_strategy()

        planner = LLMRoutePlanner(config)

        # Clear CLAUDECODE env var
        with patch.dict(os.environ, {}, clear=True):
            with patch("shutil.which", return_value="/usr/bin/claude"):
                available = planner._check_claude_cli_available()

        assert available is True

    def test_plan_routes_claude_cli_no_executable(self) -> None:
        """Test Claude CLI unavailable when no executable."""
        config = create_test_config()
        strategy = create_test_strategy()

        planner = LLMRoutePlanner(config)

        with patch.dict(os.environ, {}, clear=True):
            with patch("shutil.which", return_value=None):
                available = planner._check_claude_cli_available()

        assert available is False

    def test_plan_routes_openrouter_available(self) -> None:
        """Test OpenRouter availability check."""
        config = create_test_config(
            openrouter_enabled=True,
            openrouter_api_key="test-key",
        )

        planner = LLMRoutePlanner(config)
        available = planner._check_openrouter_available()

        assert available is True

    def test_plan_routes_openrouter_no_key(self) -> None:
        """Test OpenRouter unavailable without API key."""
        config = create_test_config(
            openrouter_enabled=True,
            openrouter_api_key=None,
        )

        planner = LLMRoutePlanner(config)
        available = planner._check_openrouter_available()

        assert available is False

    def test_plan_routes_openrouter_disabled(self) -> None:
        """Test OpenRouter unavailable when disabled."""
        config = create_test_config(
            openrouter_enabled=False,
            openrouter_api_key="test-key",
        )

        planner = LLMRoutePlanner(config)
        available = planner._check_openrouter_available()

        assert available is False

    def test_plan_routes_cerebras_available(self) -> None:
        """Test Cerebras availability check."""
        config = create_test_config(
            cerebras_enabled=True,
            cerebras_api_key="test-key",
        )

        planner = LLMRoutePlanner(config)
        available = planner._check_cerebras_available()

        assert available is True

    def test_plan_routes_cerebras_no_key(self) -> None:
        """Test Cerebras unavailable without API key."""
        config = create_test_config(
            cerebras_enabled=True,
            cerebras_api_key=None,
        )

        planner = LLMRoutePlanner(config)
        available = planner._check_cerebras_available()

        assert available is False

    def test_plan_routes_fallback_order_respects_config(self) -> None:
        """Test that fallback order respects configured order."""
        config = create_test_config(
            openrouter_enabled=True,
            openrouter_api_key="test-key",
            cerebras_enabled=True,
            cerebras_api_key="test-key",
            fallback_order=["cerebras", "openrouter", "claude_cli", "heuristic"],
        )
        strategy = create_test_strategy()

        planner = LLMRoutePlanner(config)

        with patch.object(planner, "_check_claude_cli_available", return_value=True):
            plan = planner.plan_routes(strategy)

        # Cerebras should be first in fallback
        assert plan.fallback_order[0] == LLMTransportType.CEREBRAS_API

    def test_plan_routes_assigns_agent_routes(self) -> None:
        """Test that agent routes are assigned."""
        config = create_test_config(
            openrouter_enabled=True,
            openrouter_api_key="test-key",
        )
        strategy = create_test_strategy()

        planner = LLMRoutePlanner(config)

        with patch.object(planner, "_check_claude_cli_available", return_value=True):
            plan = planner.plan_routes(strategy)

        # Should have routes for known agents
        assert "analyzer" in plan.agent_routes
        assert "deep_analyzer" in plan.agent_routes

    def test_plan_routes_fast_api_preferred_when_only_api_available(self) -> None:
        """Test that API transports are preferred for fast agents when only API is available."""
        config = create_test_config(
            claude_cli_enabled=False,
            openrouter_enabled=True,
            openrouter_api_key="test-key",
            cerebras_enabled=False,
        )
        strategy = create_test_strategy()

        planner = LLMRoutePlanner(config)
        plan = planner.plan_routes(strategy)

        # Analyzer should get OpenRouter since it only API transport available
        analyzer_route = plan.get_route_for_agent("analyzer")
        assert analyzer_route.transport == LLMTransportType.OPENROUTER_API

    def test_plan_routes_heuristic_always_included(self) -> None:
        """Test that heuristic is always in fallback order."""
        config = create_test_config()
        strategy = create_test_strategy()

        planner = LLMRoutePlanner(config)
        plan = planner.plan_routes(strategy)

        assert LLMTransportType.HEURISTIC in plan.fallback_order

    def test_plan_routes_only_available_transports(self) -> None:
        """Test that only available transports are in fallback order."""
        config = create_test_config(
            claude_cli_enabled=False,
            openrouter_enabled=False,
            cerebras_enabled=False,
        )
        strategy = create_test_strategy()

        planner = LLMRoutePlanner(config)
        plan = planner.plan_routes(strategy)

        # Only heuristic should be available
        assert plan.fallback_order == [LLMTransportType.HEURISTIC]
        assert plan.default_route.transport == LLMTransportType.HEURISTIC

    def test_update_registry_from_plan(self) -> None:
        """Test updating registry from plan."""
        config = create_test_config(
            openrouter_enabled=True,
            openrouter_api_key="test-key",
        )
        strategy = create_test_strategy()

        planner = LLMRoutePlanner(config)

        with patch.object(planner, "_check_claude_cli_available", return_value=True):
            plan = planner.plan_routes(strategy)

        # Create mock registry
        mock_registry = MagicMock()

        planner.update_registry_from_plan(plan, mock_registry)

        # Verify set_route was called for each agent
        assert mock_registry.set_route.call_count >= 2

    def test_get_route_for_agent_returns_default(self) -> None:
        """Test that unknown agents get default route."""
        config = create_test_config()
        strategy = create_test_strategy()

        planner = LLMRoutePlanner(config)
        plan = planner.plan_routes(strategy)

        route = plan.get_route_for_agent("unknown_agent")
        assert route == plan.default_route


class TestCreateLLMPlan:
    """Tests for create_llm_plan convenience function."""

    def test_create_llm_plan_returns_plan(self) -> None:
        """Test that create_llm_plan returns a valid plan."""
        config = create_test_config()
        strategy = create_test_strategy()

        plan = create_llm_plan(config, strategy)

        assert isinstance(plan, LLMPlanModel)
        assert plan.default_route is not None

    def test_create_llm_plan_includes_agent_routes(self) -> None:
        """Test that plan includes agent routes."""
        config = create_test_config(
            openrouter_enabled=True,
            openrouter_api_key="test-key",
        )
        strategy = create_test_strategy()

        plan = create_llm_plan(config, strategy)

        assert "analyzer" in plan.agent_routes
        assert "deep_analyzer" in plan.agent_routes


class TestLLMRouteModel:
    """Tests for LLMRouteModel."""

    def test_default_values(self) -> None:
        """Test default values for route model."""
        route = LLMRouteModel()

        assert route.transport == LLMTransportType.CLAUDE_CLI
        assert route.provider == LLMProviderType.CLAUDE
        assert route.model == "claude-sonnet-4-6"
        assert route.enabled is True


class TestLLMPlanModel:
    """Tests for LLMPlanModel."""

    def test_get_route_for_agent_returns_assigned(self) -> None:
        """Test getting assigned route for agent."""
        plan = LLMPlanModel(
            agent_routes={
                "analyzer": LLMRouteModel(
                    transport=LLMTransportType.OPENROUTER_API,
                    provider=LLMProviderType.OPENROUTER,
                    model="test-model",
                )
            },
            default_route=LLMRouteModel(),
        )

        route = plan.get_route_for_agent("analyzer")

        assert route.transport == LLMTransportType.OPENROUTER_API
        assert route.model == "test-model"

    def test_get_route_for_agent_returns_default(self) -> None:
        """Test getting default route for unknown agent."""
        plan = LLMPlanModel(
            agent_routes={},
            default_route=LLMRouteModel(
                transport=LLMTransportType.CEREBRAS_API,
                provider=LLMProviderType.CEREBRAS,
                model="test-model",
            ),
        )

        route = plan.get_route_for_agent("unknown")

        assert route.transport == LLMTransportType.CEREBRAS_API

    def test_default_fallback_order(self) -> None:
        """Test default fallback order."""
        plan = LLMPlanModel()

        assert LLMTransportType.CLAUDE_CLI in plan.fallback_order
        assert LLMTransportType.HEURISTIC in plan.fallback_order
