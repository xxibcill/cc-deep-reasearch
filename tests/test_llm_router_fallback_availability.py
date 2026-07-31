"""Regression tests for fallback-aware LLM router availability."""

from unittest.mock import MagicMock, call, patch

from cc_deep_research.llm.base import (
    LLMProviderType,
    LLMRoute,
    LLMTransportType,
)
from cc_deep_research.llm.router import LLMRouter


class _FallbackRegistry:
    def __init__(
        self,
        primary: LLMRoute,
        fallbacks: list[LLMTransportType],
        routes: dict[LLMTransportType, LLMRoute],
    ) -> None:
        self._primary = primary
        self._fallbacks = fallbacks
        self._routes = routes

    def get_route(self, _agent_id: str) -> LLMRoute:
        return self._primary

    def get_fallback_order(self) -> list[LLMTransportType]:
        return list(self._fallbacks)

    def get_route_for_transport(self, transport: LLMTransportType) -> LLMRoute:
        return self._routes[transport]


def _route(
    transport: LLMTransportType,
    provider: LLMProviderType,
    model: str,
) -> LLMRoute:
    return LLMRoute(
        transport=transport,
        provider=provider,
        model=model,
    )


def test_is_available_checks_runtime_available_fallback_after_codex_primary() -> None:
    codex_route = _route(
        LLMTransportType.CODEX_APP_SERVER,
        LLMProviderType.CODEX,
        "codex-default",
    )
    openrouter_route = _route(
        LLMTransportType.OPENROUTER_API,
        LLMProviderType.OPENROUTER,
        "openai/gpt-4.1-mini",
    )
    registry = _FallbackRegistry(
        primary=codex_route,
        fallbacks=[
            LLMTransportType.CODEX_APP_SERVER,
            LLMTransportType.OPENROUTER_API,
            LLMTransportType.HEURISTIC,
        ],
        routes={
            LLMTransportType.OPENROUTER_API: openrouter_route,
            LLMTransportType.HEURISTIC: _route(
                LLMTransportType.HEURISTIC,
                LLMProviderType.HEURISTIC,
                "heuristic",
            ),
        },
    )
    router = LLMRouter(registry)
    unavailable_codex = MagicMock()
    unavailable_codex.is_available.return_value = False
    available_openrouter = MagicMock()
    available_openrouter.is_available.return_value = True

    with patch.object(
        router,
        "_get_transport_for_route",
        side_effect=[unavailable_codex, available_openrouter],
    ) as get_transport:
        assert router.is_available("content_gen_scripting") is True

    assert get_transport.call_args_list == [call(codex_route), call(openrouter_route)]
    unavailable_codex.is_available.assert_called_once_with()
    available_openrouter.is_available.assert_called_once_with()
