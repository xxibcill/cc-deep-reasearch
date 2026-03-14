"""Session-scoped LLM route registry for agent-level routing."""

from __future__ import annotations

from typing import Any, Callable

from cc_deep_research.config import LLMConfig
from cc_deep_research.llm.base import (
    LLMProviderType,
    LLMRoute,
    LLMRoutePlan,
    LLMTransportType,
)


class LLMRouteRegistry:
    """Session-scoped registry for LLM routes.

    The registry provides late-bound route lookup for agents, allowing
    the planner to update routes after planning without mutating agent
    constructors.

    Example:
        ```python
        registry = LLMRouteRegistry(config)

        # Get default route for an agent
        route = registry.get_route("analyzer")

        # Update route after planning
        plan = LLMRoutePlan(
            agent_routes={
                "analyzer": LLMRoute(
                    transport=LLMTransportType.OPENROUTER_API,
                    provider=LLMProviderType.OPENROUTER,
                )
            }
        )
        registry.update_from_plan(plan)

        # Now analyzer uses OpenRouter
        route = registry.get_route("analyzer")
        ```
    """

    def __init__(
        self,
        config: LLMConfig,
        *,
        telemetry_callback: Callable[[dict[str, Any]], None] | None = None,
    ) -> None:
        """Initialize the route registry.

        Args:
            config: The LLM configuration.
            telemetry_callback: Optional callback for emitting telemetry events.
        """
        self._config = config
        self._telemetry_callback = telemetry_callback
        self._agent_routes: dict[str, LLMRoute] = {}
        self._fallback_order = self._build_fallback_order()

    def _build_fallback_order(self) -> list[LLMTransportType]:
        """Build the fallback order from config."""
        transport_map = {
            "claude_cli": LLMTransportType.CLAUDE_CLI,
            "openrouter": LLMTransportType.OPENROUTER_API,
            "cerebras": LLMTransportType.CEREBRAS_API,
            "heuristic": LLMTransportType.HEURISTIC,
        }
        order = []
        for name in self._config.fallback_order:
            if name in transport_map:
                order.append(transport_map[name])
        return order

    def _build_route_from_transport(self, transport: LLMTransportType) -> LLMRoute:
        """Build a route configuration for a transport type."""
        if transport == LLMTransportType.CLAUDE_CLI:
            return LLMRoute(
                transport=LLMTransportType.CLAUDE_CLI,
                provider=LLMProviderType.CLAUDE,
                model=self._config.claude_cli.model,
                timeout_seconds=self._config.claude_cli.timeout_seconds,
                enabled=self._config.claude_cli.enabled,
                extra={"path": self._config.claude_cli.path},
            )
        elif transport == LLMTransportType.OPENROUTER_API:
            return LLMRoute(
                transport=LLMTransportType.OPENROUTER_API,
                provider=LLMProviderType.OPENROUTER,
                model=self._config.openrouter.model,
                timeout_seconds=self._config.openrouter.timeout_seconds,
                enabled=self._config.openrouter.enabled
                and bool(self._config.openrouter.api_key),
                extra={
                    "api_key": self._config.openrouter.api_key,
                    "base_url": self._config.openrouter.base_url,
                    "extra_headers": self._config.openrouter.extra_headers,
                },
            )
        elif transport == LLMTransportType.CEREBRAS_API:
            return LLMRoute(
                transport=LLMTransportType.CEREBRAS_API,
                provider=LLMProviderType.CEREBRAS,
                model=self._config.cerebras.model,
                timeout_seconds=self._config.cerebras.timeout_seconds,
                enabled=self._config.cerebras.enabled
                and bool(self._config.cerebras.api_key),
                extra={
                    "api_key": self._config.cerebras.api_key,
                    "base_url": self._config.cerebras.base_url,
                },
            )
        else:
            return LLMRoute(
                transport=LLMTransportType.HEURISTIC,
                provider=LLMProviderType.HEURISTIC,
                model="heuristic",
                enabled=True,
            )

    def _get_default_route_for_agent(self, agent_id: str) -> LLMRoute:
        """Get the default route for an agent from config."""
        transport_name = self._config.get_route_for_agent(agent_id)
        transport_map = {
            "claude_cli": LLMTransportType.CLAUDE_CLI,
            "openrouter": LLMTransportType.OPENROUTER_API,
            "cerebras": LLMTransportType.CEREBRAS_API,
            "heuristic": LLMTransportType.HEURISTIC,
        }
        transport = transport_map.get(transport_name, LLMTransportType.CLAUDE_CLI)
        return self._build_route_from_transport(transport)

    def get_route(self, agent_id: str) -> LLMRoute:
        """Get the route for a specific agent.

        Args:
            agent_id: The agent identifier.

        Returns:
            The route for the agent, checking for planner-assigned routes first,
            then falling back to config defaults.
        """
        if agent_id in self._agent_routes:
            route = self._agent_routes[agent_id]
            self._emit_telemetry(
                "route_lookup",
                {
                    "agent_id": agent_id,
                    "transport": route.transport.value,
                    "provider": route.provider.value,
                    "source": "planner",
                },
            )
            return route

        if "default" in self._agent_routes:
            route = self._agent_routes["default"]
            self._emit_telemetry(
                "route_lookup",
                {
                    "agent_id": agent_id,
                    "transport": route.transport.value,
                    "provider": route.provider.value,
                    "source": "planner_default",
                },
            )
            return route

        route = self._get_default_route_for_agent(agent_id)
        self._emit_telemetry(
            "route_lookup",
            {
                "agent_id": agent_id,
                "transport": route.transport.value,
                "provider": route.provider.value,
                "source": "config",
            },
        )
        return route

    def set_route(self, agent_id: str, route: LLMRoute) -> None:
        """Set the route for a specific agent.

        Args:
            agent_id: The agent identifier.
            route: The route to assign.
        """
        self._agent_routes[agent_id] = route
        self._emit_telemetry(
            "route_set",
            {
                "agent_id": agent_id,
                "transport": route.transport.value,
                "provider": route.provider.value,
            },
        )

    def update_from_plan(self, plan: LLMRoutePlan) -> None:
        """Update routes from a planner-emitted route plan.

        Args:
            plan: The route plan from the planner.
        """
        for agent_id, route in plan.agent_routes.items():
            self._agent_routes[agent_id] = route

        # Update fallback order if specified
        if plan.fallback_order:
            self._fallback_order = list(plan.fallback_order)

        self._emit_telemetry(
            "plan_applied",
            {
                "agent_count": len(plan.agent_routes),
                "agents": list(plan.agent_routes.keys()),
            },
        )

    def get_fallback_order(self) -> list[LLMTransportType]:
        """Get the current fallback order.

        Returns:
            List of transport types in fallback order.
        """
        return list(self._fallback_order)

    def get_route_for_transport(self, transport: LLMTransportType) -> LLMRoute:
        """Build a route for a specific transport using current config."""
        return self._build_route_from_transport(transport)

    def get_available_route(
        self, agent_id: str, *, check_nested_session: bool = False
    ) -> LLMRoute:
        """Return the first available route for an agent."""
        primary_route = self.get_route(agent_id)

        if primary_route.is_available(check_nested_session=check_nested_session):
            return primary_route

        for transport in self._fallback_order:
            if transport == primary_route.transport:
                continue
            route = self._build_route_from_transport(transport)
            if route.is_available(check_nested_session=check_nested_session):
                self._emit_telemetry(
                    "route_fallback",
                    {
                        "agent_id": agent_id,
                        "original_transport": primary_route.transport.value,
                        "fallback_transport": route.transport.value,
                    },
                )
                return route

        return LLMRoute(
            transport=LLMTransportType.HEURISTIC,
            provider=LLMProviderType.HEURISTIC,
            model="heuristic",
            enabled=True,
        )

    def clear(self) -> None:
        """Clear all planner-assigned routes.

        This is useful for resetting the registry between sessions.
        """
        self._agent_routes.clear()
        self._emit_telemetry("registry_cleared", {})

    def get_all_routes(self) -> dict[str, LLMRoute]:
        """Get all currently assigned routes.

        Returns:
            Dictionary mapping agent IDs to their assigned routes.
        """
        return dict(self._agent_routes)

    def _emit_telemetry(self, event_type: str, data: dict[str, Any]) -> None:
        """Emit a telemetry event if a callback is configured.

        Args:
            event_type: The type of telemetry event.
            data: The event data.
        """
        if self._telemetry_callback:
            try:
                self._telemetry_callback(
                    {
                        "event_type": event_type,
                        "source": "llm_route_registry",
                        **data,
                    }
                )
            except Exception:
                pass  # Don't fail operations due to telemetry errors

    def get_summary(self) -> dict[str, Any]:
        """Get a summary of the current registry state.

        Returns:
            Dictionary with registry state information.
        """
        return {
            "agent_routes": {
                agent_id: {
                    "transport": route.transport.value,
                    "provider": route.provider.value,
                    "model": route.model,
                    "enabled": route.enabled,
                }
                for agent_id, route in self._agent_routes.items()
            },
            "fallback_order": [t.value for t in self._fallback_order],
            "config_defaults": {
                "claude_cli_enabled": self._config.claude_cli.enabled,
                "openrouter_enabled": self._config.openrouter.enabled,
                "cerebras_enabled": self._config.cerebras.enabled,
            },
        }
