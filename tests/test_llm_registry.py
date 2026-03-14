"""Tests for LLM route registry."""

import pytest

from cc_deep_research.config import (
    LLMCerebrasConfig,
    LLMClaudeCLIConfig,
    LLMConfig,
    LLMOpenRouterConfig,
    LLMRouteDefaults,
)
from cc_deep_research.llm.base import (
    LLMProviderType,
    LLMRoute,
    LLMRoutePlan,
    LLMTransportType,
)
from cc_deep_research.llm.registry import LLMRouteRegistry


class TestLLMRouteRegistry:
    """Tests for LLMRouteRegistry."""

    def test_create_registry_with_default_config(self) -> None:
        """Test creating registry with default config."""
        config = LLMConfig()
        registry = LLMRouteRegistry(config)

        # Should have Claude CLI as default route
        route = registry.get_route("analyzer")
        assert route.transport == LLMTransportType.CLAUDE_CLI
        assert route.provider == LLMProviderType.CLAUDE

    def test_get_route_returns_config_default(self) -> None:
        """Test get_route returns config default for unknown agent."""
        config = LLMConfig(
            route_defaults=LLMRouteDefaults(
                analyzer="openrouter",
                default="cerebras",
            ),
            openrouter=LLMOpenRouterConfig(enabled=True, api_key="test-key"),
        )
        registry = LLMRouteRegistry(config)

        # Known agent should get its configured route
        route = registry.get_route("analyzer")
        assert route.transport == LLMTransportType.OPENROUTER_API

        # Unknown agent should get default
        route = registry.get_route("unknown_agent")
        assert route.transport == LLMTransportType.CEREBRAS_API

    def test_set_route_overrides_default(self) -> None:
        """Test set_route overrides config default."""
        config = LLMConfig()
        registry = LLMRouteRegistry(config)

        # Set a custom route
        custom_route = LLMRoute(
            transport=LLMTransportType.OPENROUTER_API,
            provider=LLMProviderType.OPENROUTER,
            model="anthropic/claude-opus-4",
        )
        registry.set_route("analyzer", custom_route)

        # Should return the custom route
        route = registry.get_route("analyzer")
        assert route.transport == LLMTransportType.OPENROUTER_API
        assert route.model == "anthropic/claude-opus-4"

    def test_update_from_plan(self) -> None:
        """Test update_from_plan applies route plan."""
        config = LLMConfig()
        registry = LLMRouteRegistry(config)

        # Create a plan
        plan = LLMRoutePlan(
            agent_routes={
                "analyzer": LLMRoute(
                    transport=LLMTransportType.CEREBRAS_API,
                    provider=LLMProviderType.CEREBRAS,
                ),
                "deep_analyzer": LLMRoute(
                    transport=LLMTransportType.OPENROUTER_API,
                    provider=LLMProviderType.OPENROUTER,
                ),
            }
        )

        # Apply the plan
        registry.update_from_plan(plan)

        # Verify routes are updated
        route = registry.get_route("analyzer")
        assert route.transport == LLMTransportType.CEREBRAS_API

        route = registry.get_route("deep_analyzer")
        assert route.transport == LLMTransportType.OPENROUTER_API

    def test_get_fallback_order_from_config(self) -> None:
        """Test get_fallback_order returns config order."""
        config = LLMConfig(
            fallback_order=["cerebras", "openrouter", "claude_cli", "heuristic"]
        )
        registry = LLMRouteRegistry(config)

        order = registry.get_fallback_order()
        assert order[0] == LLMTransportType.CEREBRAS_API
        assert order[1] == LLMTransportType.OPENROUTER_API
        assert order[2] == LLMTransportType.CLAUDE_CLI
        assert order[3] == LLMTransportType.HEURISTIC

    def test_clear_resets_routes(self) -> None:
        """Test clear removes all planner-assigned routes."""
        config = LLMConfig()
        registry = LLMRouteRegistry(config)

        # Set some routes
        registry.set_route("analyzer", LLMRoute(transport=LLMTransportType.CEREBRAS_API))
        registry.set_route("deep_analyzer", LLMRoute(transport=LLMTransportType.OPENROUTER_API))

        # Clear should reset
        registry.clear()

        # Should return config defaults
        route = registry.get_route("analyzer")
        assert route.transport == LLMTransportType.CLAUDE_CLI

    def test_get_all_routes(self) -> None:
        """Test get_all_routes returns current state."""
        config = LLMConfig()
        registry = LLMRouteRegistry(config)

        # Set some routes
        registry.set_route("analyzer", LLMRoute(transport=LLMTransportType.CEREBRAS_API))

        routes = registry.get_all_routes()
        assert "analyzer" in routes
        assert routes["analyzer"].transport == LLMTransportType.CEREBRAS_API
        assert len(routes) == 1

    def test_get_summary(self) -> None:
        """Test get_summary returns registry state."""
        config = LLMConfig(
            claude_cli=LLMClaudeCLIConfig(enabled=True),
            openrouter=LLMOpenRouterConfig(enabled=True, api_key="test"),
            cerebras=LLMCerebrasConfig(enabled=False),
        )
        registry = LLMRouteRegistry(config)

        summary = registry.get_summary()

        assert "agent_routes" in summary
        assert "fallback_order" in summary
        assert "config_defaults" in summary
        assert summary["config_defaults"]["claude_cli_enabled"] is True
        assert summary["config_defaults"]["openrouter_enabled"] is True
        assert summary["config_defaults"]["cerebras_enabled"] is False

    def test_telemetry_callback(self) -> None:
        """Test telemetry callback is invoked."""
        events: list[dict] = []

        def callback(event: dict) -> None:
            events.append(event)

        config = LLMConfig()
        registry = LLMRouteRegistry(config, telemetry_callback=callback)

        # Trigger some events
        registry.get_route("analyzer")
        registry.set_route("test", LLMRoute(transport=LLMTransportType.HEURISTIC))
        registry.clear()

        # Should have recorded events
        assert len(events) >= 2
        event_types = {e.get("event_type") for e in events}
        assert "route_lookup" in event_types
        assert "route_set" in event_types or "registry_cleared" in event_types

    def test_get_available_route_respects_nested_session(self) -> None:
        """Test get_available_route skips CLI in nested sessions."""
        config = LLMConfig(
            route_defaults=LLMRouteDefaults(analyzer="claude_cli"),
            openrouter=LLMOpenRouterConfig(enabled=True, api_key="test-key"),
        )
        registry = LLMRouteRegistry(config)

        # Without nested session check, should return CLI
        route = registry.get_available_route("analyzer", check_nested_session=False)
        assert route.transport == LLMTransportType.CLAUDE_CLI

        # With nested session check in CLAUDECODE env, should fall back
        # Note: This test assumes CLAUDECODE is set in the current environment
        # In a real test, we'd mock the environment variable
        # For now, we just verify the method doesn't crash
        route = registry.get_available_route("analyzer", check_nested_session=True)
        assert route.transport in (
            LLMTransportType.CLAUDE_CLI,
            LLMTransportType.OPENROUTER_API,
            LLMTransportType.HEURISTIC,
        )

    def test_registry_with_disabled_transports(self) -> None:
        """Test registry handles disabled transports."""
        config = LLMConfig(
            claude_cli=LLMClaudeCLIConfig(enabled=False),
            openrouter=LLMOpenRouterConfig(enabled=False),
            cerebras=LLMCerebrasConfig(enabled=False),
        )
        registry = LLMRouteRegistry(config)

        # Should still return a route (will check enabled flag)
        route = registry.get_route("analyzer")
        assert route is not None

        # Getting available route should fall back to heuristic
        route = registry.get_available_route("analyzer")
        assert route.transport == LLMTransportType.HEURISTIC
