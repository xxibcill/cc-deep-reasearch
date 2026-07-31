"""Tests for the Codex LLM transport adapter."""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, patch

import pytest
from openai_codex import ServerBusyError, TransportClosedError
from pydantic import ValidationError

from cc_deep_research.config import Config, LLMCodexConfig, LLMConfig, LLMRouteDefaults
from cc_deep_research.llm.base import (
    LLMAuthenticationError,
    LLMProviderError,
    LLMProviderType,
    LLMRateLimitError,
    LLMRequest,
    LLMRoute,
    LLMTimeoutError,
    LLMTransportType,
)
from cc_deep_research.llm.codex import CodexTransport
from cc_deep_research.llm.codex_runtime import (
    CodexNotAuthenticatedError,
    CodexTurnResult,
)
from cc_deep_research.llm.registry import LLMRouteRegistry
from cc_deep_research.llm.router import LLMRouter
from cc_deep_research.orchestration.llm_route_planner import LLMRoutePlanner


class FakeCodexRuntime:
    def __init__(self) -> None:
        self.is_authenticated = True
        self.runtime_status = "ready"
        self.can_attempt_start = False
        self.run_turn = AsyncMock(
            return_value=CodexTurnResult(
                content="Normalized response",
                model="gpt-5.6-sol",
                turn_id="turn-123",
                duration_ms=321,
                finish_reason="completed",
                input_tokens=10,
                output_tokens=5,
                total_tokens=15,
                cached_input_tokens=2,
                reasoning_output_tokens=1,
            )
        )


def _codex_route(
    *,
    enabled: bool = True,
    model: str = "codex-default",
) -> LLMRoute:
    return LLMRoute(
        transport=LLMTransportType.CODEX_APP_SERVER,
        provider=LLMProviderType.CODEX,
        model=model,
        enabled=enabled,
        timeout_seconds=180,
        extra={
            "model": None if model == "codex-default" else model,
            "reasoning_effort": "high",
        },
    )


@pytest.mark.asyncio
async def test_execute_maps_codex_turn_to_normalized_response() -> None:
    runtime = FakeCodexRuntime()
    transport = CodexTransport(_codex_route(), runtime=runtime)
    request = LLMRequest(
        prompt="Analyze this",
        system_prompt="Return JSON.",
        temperature=0.4,
        max_tokens=800,
        metadata={"operation": "analysis", "session_id": "session-1"},
    )

    with patch("cc_deep_research.llm.codex.append_usage_entry"):
        response = await transport.execute(request)

    runtime.run_turn.assert_awaited_once_with(
        prompt="Analyze this",
        model=None,
        developer_instructions="Return JSON.",
        reasoning_effort="high",
        timeout_seconds=180,
    )
    assert response.content == "Normalized response"
    assert response.model == "gpt-5.6-sol"
    assert response.provider == LLMProviderType.CODEX
    assert response.transport == LLMTransportType.CODEX_APP_SERVER
    assert response.usage == {
        "prompt_tokens": 10,
        "completion_tokens": 5,
        "total_tokens": 15,
    }
    assert response.finish_reason == "stop"
    assert response.metadata["turn_id"] == "turn-123"
    assert response.metadata["cached_input_tokens"] == 2
    assert response.metadata["unsupported_parameters"] == ["temperature", "max_tokens"]


@pytest.mark.parametrize(
    ("enabled", "authenticated", "runtime_status", "expected"),
    [
        (False, True, "ready", False),
        (True, True, "ready", True),
        (True, False, "stopped", True),
        (True, False, "ready", False),
        (True, False, "error", True),
    ],
)
def test_is_available_uses_enabled_and_cached_runtime_state(
    enabled: bool,
    authenticated: bool,
    runtime_status: str,
    expected: bool,
) -> None:
    runtime = FakeCodexRuntime()
    runtime.is_authenticated = authenticated
    runtime.runtime_status = runtime_status
    runtime.can_attempt_start = runtime_status in {"stopped", "starting", "error"}

    transport = CodexTransport(_codex_route(enabled=enabled), runtime=runtime)

    assert transport.is_available() is expected


@pytest.mark.asyncio
async def test_authentication_error_maps_to_shared_taxonomy() -> None:
    runtime = FakeCodexRuntime()
    runtime.run_turn.side_effect = CodexNotAuthenticatedError("Connect ChatGPT first")
    transport = CodexTransport(_codex_route(), runtime=runtime)

    with pytest.raises(LLMAuthenticationError) as raised:
        await transport.execute(LLMRequest(prompt="Hello"))

    assert raised.value.provider == LLMProviderType.CODEX
    assert raised.value.transport == LLMTransportType.CODEX_APP_SERVER


@pytest.mark.asyncio
async def test_timeout_maps_to_shared_taxonomy() -> None:
    runtime = FakeCodexRuntime()
    runtime.run_turn.side_effect = TimeoutError()
    transport = CodexTransport(_codex_route(), runtime=runtime)

    with pytest.raises(LLMTimeoutError) as raised:
        await transport.execute(LLMRequest(prompt="Hello"))

    assert raised.value.timeout_seconds == 180


@pytest.mark.asyncio
async def test_server_busy_maps_to_rate_limit_error() -> None:
    runtime = FakeCodexRuntime()
    runtime.run_turn.side_effect = ServerBusyError(
        -32000,
        "server overloaded",
        {"codex_error_info": "server_overloaded"},
    )
    transport = CodexTransport(_codex_route(), runtime=runtime)

    with pytest.raises(LLMRateLimitError):
        await transport.execute(LLMRequest(prompt="Hello"))


@pytest.mark.asyncio
async def test_transport_error_details_are_not_exposed() -> None:
    runtime = FakeCodexRuntime()
    runtime.run_turn.side_effect = TransportClosedError(
        "secret stderr and local configuration details"
    )
    transport = CodexTransport(_codex_route(), runtime=runtime)

    with pytest.raises(LLMProviderError) as raised:
        await transport.execute(LLMRequest(prompt="Hello"))

    assert str(raised.value) == "Codex runtime is unavailable."
    assert "secret" not in str(raised.value)


@pytest.mark.asyncio
async def test_cancellation_propagates_without_provider_wrapping() -> None:
    runtime = FakeCodexRuntime()
    runtime.run_turn.side_effect = asyncio.CancelledError()
    transport = CodexTransport(_codex_route(), runtime=runtime)

    with pytest.raises(asyncio.CancelledError):
        await transport.execute(LLMRequest(prompt="Hello"))


def test_router_factory_injects_shared_codex_runtime() -> None:
    runtime = FakeCodexRuntime()
    registry = AsyncMock()
    router = LLMRouter(registry, codex_runtime=runtime)

    transport = router._create_transport(_codex_route())

    assert isinstance(transport, CodexTransport)
    assert transport._runtime is runtime


def test_codex_config_validates_provider_controls() -> None:
    config = LLMCodexConfig.model_validate(
        {
            "enabled": True,
            "model": None,
            "reasoning_effort": "xhigh",
            "timeout_seconds": 900,
        }
    )

    assert config.enabled is True
    assert config.reasoning_effort == "xhigh"
    assert config.timeout_seconds == 900

    with pytest.raises(ValidationError):
        LLMCodexConfig.model_validate({"timeout_seconds": 29})

    with pytest.raises(ValidationError):
        LLMCodexConfig.model_validate({"reasoning_effort": "unsupported"})


def test_registry_and_planner_preserve_codex_runtime_settings() -> None:
    llm_config = LLMConfig(
        codex=LLMCodexConfig(
            enabled=True,
            model="gpt-5.6-sol",
            reasoning_effort="high",
            timeout_seconds=240,
        ),
        route_defaults=LLMRouteDefaults(analyzer="codex"),
        fallback_order=["codex", "heuristic"],
    )
    registry = LLMRouteRegistry(llm_config)

    route = registry.get_route("analyzer")

    assert llm_config.get_enabled_transports() == ["codex", "heuristic"]
    assert route.transport == LLMTransportType.CODEX_APP_SERVER
    assert route.provider == LLMProviderType.CODEX
    assert route.model == "gpt-5.6-sol"
    assert route.timeout_seconds == 240
    assert route.extra == {
        "model": "gpt-5.6-sol",
        "reasoning_effort": "high",
    }

    planner = LLMRoutePlanner(Config(llm=llm_config))
    route_model = planner._create_route_model(LLMTransportType.CODEX_APP_SERVER)
    runtime_route = planner._build_runtime_route(
        transport=route_model.transport,
        provider=route_model.provider,
        model=route_model.model,
        enabled=route_model.enabled,
    )

    assert planner._check_codex_available() is True
    assert runtime_route == route
