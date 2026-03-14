"""LLM route planner for strategy-based route selection.

This module implements the planner component that selects LLM routes
for agents based on transport availability and task requirements.
"""

from __future__ import annotations

import os
import shutil
from typing import TYPE_CHECKING

from cc_deep_research.config import Config, LLMConfig
from cc_deep_research.llm.base import LLMRoute, LLMRoutePlan
from cc_deep_research.models import (
    LLMPlanModel,
    LLMProviderType,
    LLMRouteModel,
    LLMTransportType,
    StrategyResult,
)

if TYPE_CHECKING:
    from cc_deep_research.llm.registry import LLMRouteRegistry


class LLMRoutePlanner:
    """Plans LLM routes for agents based on availability and strategy.

    This planner inspects transport availability and creates per-agent
    route plans that can be used by the session-scoped registry.
    """

    # Known agent IDs that need LLM routes
    KNOWN_AGENT_IDS = frozenset([
        "analyzer",
        "deep_analyzer",
        "report_quality_evaluator",
        "reporter",
        "validator",
        "default",
    ])

    # Agents that benefit from fast API transports (low latency)
    FAST_API_PREFERRED_AGENTS = frozenset([
        "analyzer",
        "deep_analyzer",
        "validator",
    ])

    def __init__(self, config: Config) -> None:
        """Initialize the route planner.

        Args:
            config: Application configuration.
        """
        self._config = config
        self._llm_config = config.llm

    def plan_routes(self, strategy: StrategyResult) -> LLMPlanModel:
        """Create a per-agent LLM route plan based on availability.

        Args:
            strategy: The strategy result from planning.

        Returns:
            LLMPlanModel with per-agent route assignments.
        """
        availability = self._inspect_availability()

        # Build the fallback order based on availability
        fallback_order = self._build_fallback_order(availability)

        # Select default route (first available from fallback)
        default_route = self._select_default_route(availability, fallback_order)

        # Assign routes to specific agents
        agent_routes: dict[str, LLMRouteModel] = {}

        for agent_id in self.KNOWN_AGENT_IDS:
            if agent_id == "default":
                continue

            # Check if config has a specific preference
            config_preference = self._llm_config.get_route_for_agent(agent_id)

            # Determine route for this agent
            route = self._select_route_for_agent(
                agent_id=agent_id,
                config_preference=config_preference,
                availability=availability,
                fallback_order=fallback_order,
            )

            if route:
                agent_routes[agent_id] = route

        return LLMPlanModel(
            agent_routes=agent_routes,
            fallback_order=fallback_order,
            default_route=default_route,
        )

    def _inspect_availability(self) -> dict[LLMTransportType, bool]:
        """Inspect availability of each transport.

        Returns:
            Dictionary mapping transport types to availability.
        """
        availability: dict[LLMTransportType, bool] = {}

        # Check Claude CLI availability
        availability[LLMTransportType.CLAUDE_CLI] = self._check_claude_cli_available()

        # Check OpenRouter availability
        availability[LLMTransportType.OPENROUTER_API] = self._check_openrouter_available()

        # Check Cerebras availability
        availability[LLMTransportType.CEREBRAS_API] = self._check_cerebras_available()

        # Heuristic is always available as fallback
        availability[LLMTransportType.HEURISTIC] = True

        return availability

    def _check_claude_cli_available(self) -> bool:
        """Check if Claude CLI transport is available.

        Claude CLI is available when:
        1. The CLI executable exists
        2. We're not running inside a nested Claude Code session

        Returns:
            True if Claude CLI is available.
        """
        if not self._llm_config.claude_cli.enabled:
            return False

        # Check for nested session constraint
        if os.environ.get("CLAUDECODE"):
            return False

        # Check for CLI executable
        cli_path = self._llm_config.claude_cli.path
        if cli_path:
            return shutil.which(cli_path) is not None

        # Fall back to checking 'claude' in PATH
        return shutil.which("claude") is not None

    def _check_openrouter_available(self) -> bool:
        """Check if OpenRouter transport is available.

        OpenRouter is available when:
        1. It's enabled in config
        2. An API key is configured

        Returns:
            True if OpenRouter is available.
        """
        if not self._llm_config.openrouter.enabled:
            return False

        return bool(self._llm_config.openrouter.api_key)

    def _check_cerebras_available(self) -> bool:
        """Check if Cerebras transport is available.

        Cerebras is available when:
        1. It's enabled in config
        2. An API key is configured

        Returns:
            True if Cerebras is available.
        """
        if not self._llm_config.cerebras.enabled:
            return False

        return bool(self._llm_config.cerebras.api_key)

    def _build_fallback_order(
        self,
        availability: dict[LLMTransportType, bool],
    ) -> list[LLMTransportType]:
        """Build the fallback order based on availability.

        Args:
            availability: Transport availability map.

        Returns:
            Ordered list of available transports.
        """
        # Start with configured fallback order
        configured_order = self._llm_config.fallback_order

        # Map string names to enum values
        name_to_transport = {
            "claude_cli": LLMTransportType.CLAUDE_CLI,
            "openrouter": LLMTransportType.OPENROUTER_API,
            "cerebras": LLMTransportType.CEREBRAS_API,
            "heuristic": LLMTransportType.HEURISTIC,
        }

        # Build ordered list of available transports
        fallback: list[LLMTransportType] = []
        for name in configured_order:
            transport = name_to_transport.get(name)
            if transport and availability.get(transport, False):
                fallback.append(transport)

        # Ensure heuristic is always included as last resort
        if LLMTransportType.HEURISTIC not in fallback:
            fallback.append(LLMTransportType.HEURISTIC)

        return fallback

    def _select_default_route(
        self,
        availability: dict[LLMTransportType, bool],
        fallback_order: list[LLMTransportType],
    ) -> LLMRouteModel:
        """Select the default route from available transports.

        Args:
            availability: Transport availability map.
            fallback_order: Ordered list of available transports.

        Returns:
            Default route model.
        """
        # Use first available transport
        for transport in fallback_order:
            route_model = self._create_route_model(transport)
            if route_model.enabled:
                return route_model

        # Fall back to heuristic if nothing else available
        return LLMRouteModel(
            transport=LLMTransportType.HEURISTIC,
            provider=LLMProviderType.HEURISTIC,
            model="heuristic",
            enabled=True,
        )

    def _select_route_for_agent(
        self,
        agent_id: str,
        config_preference: str,
        availability: dict[LLMTransportType, bool],
        fallback_order: list[LLMTransportType],
    ) -> LLMRouteModel | None:
        """Select a route for a specific agent.

        Args:
            agent_id: The agent identifier.
            config_preference: Configured preference for this agent.
            availability: Transport availability map.
            fallback_order: Ordered list of available transports.

        Returns:
            Route model for the agent, or None if using default.
        """
        # Map preference name to transport type
        name_to_transport = {
            "claude_cli": LLMTransportType.CLAUDE_CLI,
            "openrouter": LLMTransportType.OPENROUTER_API,
            "cerebras": LLMTransportType.CEREBRAS_API,
            "heuristic": LLMTransportType.HEURISTIC,
        }

        preferred_transport = name_to_transport.get(config_preference)

        # Check if preferred transport is available
        if preferred_transport and availability.get(preferred_transport, False):
            return self._create_route_model(preferred_transport)

        # For fast-API-preferring agents, prefer API transports
        if agent_id in self.FAST_API_PREFERRED_AGENTS:
            # Try Cerebras first (fastest), then OpenRouter
            for transport in [
                LLMTransportType.CEREBRAS_API,
                LLMTransportType.OPENROUTER_API,
            ]:
                if availability.get(transport, False):
                    return self._create_route_model(transport)

        # Fall back to first available
        for transport in fallback_order:
            if availability.get(transport, False):
                return self._create_route_model(transport)

        return None

    def _create_route_model(
        self,
        transport: LLMTransportType,
    ) -> LLMRouteModel:
        """Create a route model for a transport type.

        Args:
            transport: The transport type.

        Returns:
            Route model with appropriate configuration.
        """
        if transport == LLMTransportType.CLAUDE_CLI:
            return LLMRouteModel(
                transport=LLMTransportType.CLAUDE_CLI,
                provider=LLMProviderType.CLAUDE,
                model=self._llm_config.claude_cli.model,
                enabled=True,
            )

        if transport == LLMTransportType.OPENROUTER_API:
            return LLMRouteModel(
                transport=LLMTransportType.OPENROUTER_API,
                provider=LLMProviderType.OPENROUTER,
                model=self._llm_config.openrouter.model,
                enabled=True,
            )

        if transport == LLMTransportType.CEREBRAS_API:
            return LLMRouteModel(
                transport=LLMTransportType.CEREBRAS_API,
                provider=LLMProviderType.CEREBRAS,
                model=self._llm_config.cerebras.model,
                enabled=True,
            )

        # Heuristic fallback
        return LLMRouteModel(
            transport=LLMTransportType.HEURISTIC,
            provider=LLMProviderType.HEURISTIC,
            model="heuristic",
            enabled=True,
        )

    def update_registry_from_plan(
        self,
        plan: LLMPlanModel,
        registry: "LLMRouteRegistry",
    ) -> None:
        """Update the session registry from the plan.

        Args:
            plan: The LLM plan from the planner.
            registry: The session-scoped route registry.
        """
        runtime_plan = LLMRoutePlan(
            agent_routes={
                agent_id: LLMRoute(
                    transport=route_model.transport,
                    provider=route_model.provider,
                    model=route_model.model,
                    enabled=route_model.enabled,
                )
                for agent_id, route_model in plan.agent_routes.items()
            },
            fallback_order=list(plan.fallback_order),
            default_route=LLMRoute(
                transport=plan.default_route.transport,
                provider=plan.default_route.provider,
                model=plan.default_route.model,
                enabled=plan.default_route.enabled,
            ),
        )
        runtime_plan.agent_routes["default"] = runtime_plan.default_route
        if callable(getattr(type(registry), "update_from_plan", None)):
            registry.update_from_plan(runtime_plan)
            return
        for agent_id, route in runtime_plan.agent_routes.items():
            registry.set_route(agent_id, route)


def create_llm_plan(
    config: Config,
    strategy: StrategyResult,
) -> LLMPlanModel:
    """Create an LLM route plan for a research session.

    This is a convenience function that creates a planner and
    generates a route plan.

    Args:
        config: Application configuration.
        strategy: Strategy result from planning.

    Returns:
        LLMPlanModel with per-agent route assignments.
    """
    planner = LLMRoutePlanner(config)
    return planner.plan_routes(strategy)


__all__ = [
    "LLMRoutePlanner",
    "create_llm_plan",
]
