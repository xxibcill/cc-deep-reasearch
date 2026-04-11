"""LLM router for unified transport selection and execution."""

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING, Any

from cc_deep_research.llm.anthropic import AnthropicAPITransport
from cc_deep_research.llm.base import (
    BaseLLMTransport,
    LLMError,
    LLMProviderType,
    LLMRequest,
    LLMResponse,
    LLMRoute,
    LLMTransportType,
)
from cc_deep_research.llm.cerebras import CerebrasTransport
from cc_deep_research.llm.openrouter import OpenRouterTransport

if TYPE_CHECKING:
    from cc_deep_research.llm.registry import LLMRouteRegistry
    from cc_deep_research.monitoring import ResearchMonitor

# Reason codes and severity levels (use string literals to avoid circular import)
REASON_FALLBACK = "fallback"
SEVERITY_WARNING = "warning"


class LLMRouter:
    """Resolve per-agent routes and execute normalized LLM requests."""

    def __init__(
        self,
        registry: LLMRouteRegistry,
        *,
        monitor: ResearchMonitor | None = None,
        telemetry_callback: Callable[[dict[str, Any]], None] | None = None,
    ) -> None:
        self._registry = registry
        self._monitor = monitor
        self._telemetry_callback = telemetry_callback
        self._transport_cache: dict[tuple[str, str, str], BaseLLMTransport] = {}

    @staticmethod
    def _preview_text(value: str | None, *, max_chars: int = 240) -> str | None:
        if not value:
            return None
        compact = " ".join(value.split())
        if len(compact) <= max_chars:
            return compact
        return compact[:max_chars].rstrip() + "..."

    def get_transport(self, agent_id: str) -> BaseLLMTransport | None:
        """Return the primary transport configured for the agent."""
        route = self._registry.get_route(agent_id)
        if route is None:
            return None
        return self._get_transport_for_route(route)

    def _get_transport_for_route(self, route: LLMRoute) -> BaseLLMTransport | None:
        if route.transport == LLMTransportType.HEURISTIC:
            return None

        cache_key = (
            route.transport.value,
            route.model,
            repr(sorted(route.extra.items())),
        )
        transport = self._transport_cache.get(cache_key)
        if transport is not None:
            return transport

        transport = self._create_transport(route)
        if transport is not None:
            self._transport_cache[cache_key] = transport
        return transport

    def _create_transport(self, route: LLMRoute) -> BaseLLMTransport | None:
        if route.transport == LLMTransportType.OPENROUTER_API:
            return OpenRouterTransport(route, telemetry_callback=self._telemetry_callback)
        if route.transport == LLMTransportType.CEREBRAS_API:
            return CerebrasTransport(route, telemetry_callback=self._telemetry_callback)
        if route.transport == LLMTransportType.ANTHROPIC_API:
            return AnthropicAPITransport(
                route,
                telemetry_callback=self._telemetry_callback,
            )
        return None

    async def execute(
        self,
        agent_id: str,
        prompt: str,
        *,
        system_prompt: str | None = None,
        model: str | None = None,
        temperature: float = 0.3,
        max_tokens: int = 4096,
        metadata: dict[str, Any] | None = None,
    ) -> LLMResponse:
        """Execute a request using the agent's resolved route with fallback."""
        request = LLMRequest(
            prompt=prompt,
            system_prompt=system_prompt,
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
            metadata=metadata or {},
        )
        operation = str(request.metadata.get("operation", "router_execute"))

        attempted: list[LLMTransportType] = []
        planned_route = self._registry.get_route(agent_id)
        routes = self._build_candidate_routes(agent_id=agent_id, planned_route=planned_route)

        for route in routes:
            if route is None:
                continue
            if route.transport in attempted:
                continue
            attempted.append(route.transport)

            if route.transport == LLMTransportType.HEURISTIC:
                break

            transport = (
                self.get_transport(agent_id)
                if planned_route is not None and route.transport == planned_route.transport
                else self._get_transport_for_route(route)
            )
            if transport is None or not transport.is_available():
                continue

            if planned_route is not None and route.transport != planned_route.transport:
                self._record_route_fallback(
                    agent_id=agent_id,
                    original_route=planned_route,
                    fallback_route=route,
                    reason="primary_route_unavailable_or_failed",
                )
            else:
                self._record_route_decision(
                    agent_id=agent_id,
                    route=route,
                    operation=operation,
                    rejected_routes=routes,
                    reason_code="route_selected",
                )

            self._record_route_request(
                agent_id=agent_id,
                route=route,
                operation=operation,
                prompt_preview=self._preview_text(prompt),
            )
            try:
                response = await transport.execute(request)
            except LLMError as exc:
                self._record_route_completion(
                    agent_id=agent_id,
                    route=route,
                    operation=operation,
                    success=False,
                    duration_ms=0,
                    metadata={"error": str(exc)},
                )
                continue
            except Exception as exc:  # pragma: no cover - defensive boundary
                self._record_route_completion(
                    agent_id=agent_id,
                    route=route,
                    operation=operation,
                    success=False,
                    duration_ms=0,
                    metadata={"error": f"{type(exc).__name__}: {exc}"},
                )
                continue

            self._record_route_completion(
                agent_id=agent_id,
                route=route,
                operation=operation,
                success=True,
                duration_ms=response.latency_ms,
                prompt_tokens=response.usage.get("prompt_tokens", 0),
                completion_tokens=response.usage.get("completion_tokens", 0),
                metadata={
                    "finish_reason": response.finish_reason,
                    "response_preview": self._preview_text(response.content),
                },
            )
            return response

        heuristic_response = self._heuristic_fallback(request)
        self._record_route_completion(
            agent_id=agent_id,
            route=LLMRoute(
                transport=LLMTransportType.HEURISTIC,
                provider=LLMProviderType.HEURISTIC,
                model="heuristic",
            ),
            operation=operation,
            success=True,
            duration_ms=0,
            metadata={"fallback_reason": "No transport available"},
        )
        return heuristic_response

    def _record_route_request(
        self,
        *,
        agent_id: str,
        route: LLMRoute,
        operation: str,
        prompt_preview: str | None = None,
    ) -> str | None:
        if self._monitor is not None:
            request_event_id = self._monitor.record_llm_route_request(
                agent_id=agent_id,
                transport=route.transport.value,
                provider=route.provider.value,
                model=route.model,
                operation=operation,
                prompt_preview=prompt_preview,
            )
        else:
            request_event_id = None
        self._emit_event(
            "route_request",
            agent_id=agent_id,
            transport=route.transport.value,
            provider=route.provider.value,
            model=route.model,
            operation=operation,
            prompt_preview=prompt_preview,
        )
        return request_event_id

    def _record_route_completion(
        self,
        *,
        agent_id: str,
        route: LLMRoute,
        operation: str,
        success: bool,
        duration_ms: int,
        prompt_tokens: int = 0,
        completion_tokens: int = 0,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        if self._monitor is not None:
            self._monitor.record_llm_route_completion(
                agent_id=agent_id,
                transport=route.transport.value,
                provider=route.provider.value,
                model=route.model,
                operation=operation,
                duration_ms=duration_ms,
                success=success,
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                **(metadata or {}),
            )
        self._emit_event(
            "route_completion",
            agent_id=agent_id,
            transport=route.transport.value,
            provider=route.provider.value,
            model=route.model,
            operation=operation,
            success=success,
            latency_ms=duration_ms,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            **(metadata or {}),
        )

    def _record_route_fallback(
        self,
        *,
        agent_id: str,
        original_route: LLMRoute,
        fallback_route: LLMRoute,
        reason: str,
    ) -> None:
        if self._monitor is not None:
            self._monitor.record_llm_route_fallback(
                agent_id=agent_id,
                original_transport=original_route.transport.value,
                fallback_transport=fallback_route.transport.value,
                reason=reason,
            )
            # Emit degradation event for trace contract
            self._monitor.emit_degradation_detected(
                reason_code=REASON_FALLBACK,
                severity=SEVERITY_WARNING,
                scope="transport",
                recoverable=True,
                mitigation=f"Using {fallback_route.transport.value} instead of {original_route.transport.value}",
                impact=f"LLM transport degraded from {original_route.transport.value} to {fallback_route.transport.value}",
                actor_id=agent_id,
            )
            self._monitor.emit_decision_made(
                decision_type="fallback",
                reason_code=reason,
                chosen_option=fallback_route.transport.value,
                rejected_options=[original_route.transport.value],
                inputs={
                    "agent_id": agent_id,
                    "operation": "route_fallback",
                    "provider": fallback_route.provider.value,
                    "model": fallback_route.model,
                },
                actor_id=agent_id,
                phase="llm",
                operation="llm.route_fallback",
            )
        self._emit_event(
            "route_fallback",
            agent_id=agent_id,
            original_transport=original_route.transport.value,
            fallback_transport=fallback_route.transport.value,
            reason=reason,
        )

    def _record_route_decision(
        self,
        *,
        agent_id: str,
        route: LLMRoute,
        operation: str,
        rejected_routes: list[LLMRoute | None],
        reason_code: str,
    ) -> None:
        """Emit an explicit routing decision for the selected transport."""
        if self._monitor is None:
            return

        self._monitor.emit_decision_made(
            decision_type="routing",
            reason_code=reason_code,
            chosen_option=route.transport.value,
            rejected_options=[
                candidate.transport.value
                for candidate in rejected_routes
                if candidate is not None and candidate.transport != route.transport
            ],
            inputs={
                "agent_id": agent_id,
                "operation": operation,
                "provider": route.provider.value,
                "model": route.model,
            },
            actor_id=agent_id,
            phase="llm",
            operation=f"llm.route.{operation}",
        )

    def _emit_event(self, event_type: str, **payload: Any) -> None:
        if self._telemetry_callback is None:
            return
        try:
            self._telemetry_callback({"event_type": event_type, **payload})
        except Exception:
            return

    def _heuristic_fallback(self, request: LLMRequest) -> LLMResponse:
        return LLMResponse(
            content="",
            model="heuristic",
            provider=LLMProviderType.HEURISTIC,
            transport=LLMTransportType.HEURISTIC,
            latency_ms=0,
            finish_reason="heuristic_fallback",
            metadata={
                "operation": request.metadata.get("operation", "unknown"),
                "fallback_reason": "No LLM transport available",
            },
        )

    def is_available(self, agent_id: str) -> bool:
        try:
            route = self._registry.get_available_route(agent_id, check_nested_session=True)
        except TypeError:
            route = self._registry.get_available_route(agent_id)
        if route is None:
            return False
        if route.transport == LLMTransportType.HEURISTIC:
            return False
        transport = self._get_transport_for_route(route)
        return transport is not None and transport.is_available()

    def clear_cache(self) -> None:
        self._transport_cache.clear()

    def _build_candidate_routes(
        self,
        *,
        agent_id: str,
        planned_route: LLMRoute | None,
    ) -> list[LLMRoute | None]:
        routes: list[LLMRoute | None] = [planned_route]
        for transport in self._registry.get_fallback_order():
            if planned_route is not None and transport == planned_route.transport:
                continue
            route = self._get_route_for_transport(agent_id=agent_id, transport=transport)
            routes.append(route)
        return routes

    def _get_route_for_transport(
        self,
        *,
        agent_id: str,
        transport: LLMTransportType,
    ) -> LLMRoute | None:
        if hasattr(self._registry, "get_route_for_transport"):
            return self._registry.get_route_for_transport(transport)
        try:
            return self._registry.get_available_route(transport)
        except TypeError:
            return self._registry.get_available_route(agent_id)


__all__ = ["LLMRouter"]
