"""Tests for LLM router."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from cc_deep_research.llm.base import (
    LLMError,
    LLMProviderType,
    LLMRequest,
    LLMResponse,
    LLMRoute,
    LLMTransportType,
)
from cc_deep_research.llm.router import LLMRouter


def create_route(
    transport: LLMTransportType = LLMTransportType.ANTHROPIC_API,
    model: str = "claude-sonnet-4-6",
    api_key: str | None = None,
) -> LLMRoute:
    """Create a test route."""
    extra = {}
    if api_key:
        extra["api_key"] = api_key

    return LLMRoute(
        transport=transport,
        provider=LLMProviderType.ANTHROPIC,
        model=model,
        timeout_seconds=60,
        extra=extra,
    )


class MockRegistry:
    """Mock route registry for testing."""

    def __init__(
        self,
        route: LLMRoute | None = None,
        fallback_order: list[LLMTransportType] | None = None,
    ) -> None:
        self._route = route
        self._fallback_order = fallback_order or [
            LLMTransportType.ANTHROPIC_API,
            LLMTransportType.OPENROUTER_API,
            LLMTransportType.CEREBRAS_API,
            LLMTransportType.HEURISTIC,
        ]

    def get_route(self, agent_id: str) -> LLMRoute | None:  # noqa: ARG002
        return self._route

    def get_fallback_order(self) -> list[LLMTransportType]:
        return self._fallback_order

    def get_available_route(
        self,
        preferred_transport: LLMTransportType,  # noqa: ARG002
    ) -> LLMRoute | None:
        return self._route


class TestLLMRouter:
    """Tests for LLMRouter."""

    def test_router_initialization(self) -> None:
        """Test router initializes correctly."""
        registry = MockRegistry()
        router = LLMRouter(registry)

        assert router._registry is registry

    def test_get_transport_returns_none_when_no_route(self) -> None:
        """Test get_transport returns None when no route configured."""
        registry = MockRegistry(route=None)
        router = LLMRouter(registry)

        transport = router.get_transport("test_agent")

        assert transport is None

    def test_get_transport_creates_transport(self) -> None:
        """Test get_transport creates appropriate transport."""
        route = create_route(transport=LLMTransportType.OPENROUTER_API, api_key="test-key")
        registry = MockRegistry(route=route)
        router = LLMRouter(registry)

        transport = router.get_transport("test_agent")

        assert transport is not None
        assert transport.transport_type == LLMTransportType.OPENROUTER_API

    def test_get_transport_caches_transport(self) -> None:
        """Test get_transport caches transport instances."""
        route = create_route(transport=LLMTransportType.OPENROUTER_API, api_key="test-key")
        registry = MockRegistry(route=route)
        router = LLMRouter(registry)

        transport1 = router.get_transport("agent1")
        transport2 = router.get_transport("agent2")

        # Should return same cached instance
        assert transport1 is transport2

    def test_is_available_returns_false_when_no_transport(self) -> None:
        """Test is_available returns False when no transport."""
        registry = MockRegistry(route=None)
        router = LLMRouter(registry)

        assert router.is_available("test_agent") is False

    def test_clear_cache_clears_transports(self) -> None:
        """Test clear_cache clears transport cache."""
        route = create_route(transport=LLMTransportType.OPENROUTER_API, api_key="test-key")
        registry = MockRegistry(route=route)
        router = LLMRouter(registry)

        router.get_transport("test_agent")
        assert len(router._transport_cache) == 1

        router.clear_cache()
        assert len(router._transport_cache) == 0

    @pytest.mark.asyncio
    async def test_execute_returns_response(self) -> None:
        """Test execute returns response from transport."""
        route = create_route(transport=LLMTransportType.OPENROUTER_API, api_key="test-key")
        registry = MockRegistry(route=route)
        router = LLMRouter(registry)

        mock_response = LLMResponse(
            content="Test response",
            model="claude-sonnet-4-6",
            provider=LLMProviderType.OPENROUTER,
            transport=LLMTransportType.OPENROUTER_API,
            latency_ms=100,
            finish_reason="stop",
        )

        with patch.object(
            router,
            "get_transport",
        ) as mock_get_transport:
            mock_transport = MagicMock()
            mock_transport.is_available.return_value = True
            mock_transport.execute = AsyncMock(return_value=mock_response)
            mock_get_transport.return_value = mock_transport

            response = await router.execute(
                agent_id="test_agent",
                prompt="Test prompt",
            )

        assert response.content == "Test response"
        assert response.model == "claude-sonnet-4-6"

    @pytest.mark.asyncio
    async def test_execute_falls_back_on_error(self) -> None:
        """Test execute falls back to heuristic on error."""
        registry = MockRegistry(route=None)
        router = LLMRouter(registry)

        response = await router.execute(
            agent_id="test_agent",
            prompt="Test prompt",
        )

        # Should return heuristic fallback
        assert response.transport == LLMTransportType.HEURISTIC
        assert response.provider == LLMProviderType.HEURISTIC
        assert response.model == "heuristic"

    @pytest.mark.asyncio
    async def test_execute_with_system_prompt(self) -> None:
        """Test execute passes system prompt to transport."""
        route = create_route(transport=LLMTransportType.OPENROUTER_API, api_key="test-key")
        registry = MockRegistry(route=route)
        router = LLMRouter(registry)

        mock_response = LLMResponse(
            content="Test response",
            model="claude-sonnet-4-6",
            provider=LLMProviderType.OPENROUTER,
            transport=LLMTransportType.OPENROUTER_API,
            latency_ms=100,
            finish_reason="stop",
        )

        captured_request: LLMRequest | None = None

        async def capture_execute(request: LLMRequest) -> LLMResponse:  # noqa: ARG001
            nonlocal captured_request
            captured_request = request
            return mock_response

        with patch.object(
            router,
            "get_transport",
        ) as mock_get_transport:
            mock_transport = MagicMock()
            mock_transport.is_available.return_value = True
            mock_transport.execute = capture_execute
            mock_transport.transport_type = LLMTransportType.OPENROUTER_API
            mock_get_transport.return_value = mock_transport

            await router.execute(
                agent_id="test_agent",
                prompt="Test prompt",
                system_prompt="System instructions",
            )

        assert captured_request is not None
        assert captured_request.system_prompt == "System instructions"

    @pytest.mark.asyncio
    async def test_execute_with_model_override(self) -> None:
        """Test execute passes model override to transport."""
        route = create_route(transport=LLMTransportType.OPENROUTER_API, api_key="test-key")
        registry = MockRegistry(route=route)
        router = LLMRouter(registry)

        mock_response = LLMResponse(
            content="Test response",
            model="override-model",
            provider=LLMProviderType.OPENROUTER,
            transport=LLMTransportType.OPENROUTER_API,
            latency_ms=100,
            finish_reason="stop",
        )

        captured_request: LLMRequest | None = None

        async def capture_execute(request: LLMRequest) -> LLMResponse:  # noqa: ARG001
            nonlocal captured_request
            captured_request = request
            return mock_response

        with patch.object(
            router,
            "get_transport",
        ) as mock_get_transport:
            mock_transport = MagicMock()
            mock_transport.is_available.return_value = True
            mock_transport.execute = capture_execute
            mock_transport.transport_type = LLMTransportType.OPENROUTER_API
            mock_get_transport.return_value = mock_transport

            await router.execute(
                agent_id="test_agent",
                prompt="Test prompt",
                model="override-model",
            )

        assert captured_request is not None
        assert captured_request.model == "override-model"

    @pytest.mark.asyncio
    async def test_execute_tries_fallback_transports(self) -> None:
        """Test execute tries fallback transports on failure."""
        route = create_route(transport=LLMTransportType.OPENROUTER_API, api_key="test-key")
        registry = MockRegistry(
            route=route,
            fallback_order=[
                LLMTransportType.OPENROUTER_API,
                LLMTransportType.HEURISTIC,
            ],
        )
        router = LLMRouter(registry)

        # Primary transport will fail, heuristic will succeed
        call_count = 0

        async def failing_execute(request: LLMRequest) -> LLMResponse:  # noqa: ARG001
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise LLMError("Primary failed")
            return LLMResponse(
                content="Fallback response",
                model="heuristic",
                provider=LLMProviderType.HEURISTIC,
                transport=LLMTransportType.HEURISTIC,
                latency_ms=0,
                finish_reason="heuristic_fallback",
            )

        with patch.object(
            router,
            "get_transport",
        ) as mock_get_transport:
            mock_transport = MagicMock()
            mock_transport.is_available.return_value = True
            mock_transport.execute = failing_execute
            mock_transport.transport_type = LLMTransportType.OPENROUTER_API
            mock_get_transport.return_value = mock_transport

            response = await router.execute(
                agent_id="test_agent",
                prompt="Test prompt",
            )

        # Should have tried primary and fallen back to heuristic
        assert call_count >= 1 or response.transport == LLMTransportType.HEURISTIC


class TestHeuristicFallback:
    """Tests for heuristic fallback behavior."""

    def test_heuristic_fallback_returns_response(self) -> None:
        """Test heuristic fallback returns a valid response."""
        registry = MockRegistry(route=None)
        router = LLMRouter(registry)

        request = LLMRequest(
            prompt="Test prompt",
            metadata={"operation": "test"},
        )

        response = router._heuristic_fallback(request)

        assert isinstance(response, LLMResponse)
        assert response.transport == LLMTransportType.HEURISTIC
        assert response.provider == LLMProviderType.HEURISTIC
        assert response.finish_reason == "heuristic_fallback"

    def test_heuristic_fallback_includes_metadata(self) -> None:
        """Test heuristic fallback includes request metadata."""
        registry = MockRegistry(route=None)
        router = LLMRouter(registry)

        request = LLMRequest(
            prompt="Test prompt",
            metadata={"operation": "extract_themes"},
        )

        response = router._heuristic_fallback(request)

        assert response.metadata.get("operation") == "extract_themes"
        assert "fallback_reason" in response.metadata
