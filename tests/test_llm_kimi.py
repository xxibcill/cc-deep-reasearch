"""Tests for the direct Kimi LLM transport."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import httpx
import pytest

from cc_deep_research.llm.base import (
    LLMAuthenticationError,
    LLMProviderError,
    LLMProviderType,
    LLMRateLimitError,
    LLMRequest,
    LLMRoute,
    LLMTransportType,
)
from cc_deep_research.llm.kimi import KimiTransport


def create_kimi_route(
    *,
    api_key: str | None = "test-kimi-key",
    api_keys: list[str] | None = None,
    base_url: str = "https://api.moonshot.ai/v1",
    model: str = "kimi-k3",
    reasoning_effort: str = "max",
) -> LLMRoute:
    """Create a direct Kimi route for transport tests."""
    return LLMRoute(
        transport=LLMTransportType.KIMI_API,
        provider=LLMProviderType.KIMI,
        model=model,
        timeout_seconds=300,
        extra={
            "api_key": api_key,
            "api_keys": api_keys or [],
            "base_url": base_url,
            "reasoning_effort": reasoning_effort,
        },
    )


def create_mock_response(
    status_code: int = 200,
    *,
    json_data: dict | None = None,
    headers: dict[str, str] | None = None,
    text: str = "",
) -> MagicMock:
    """Create a response-shaped mock."""
    response = MagicMock(spec=httpx.Response)
    response.status_code = status_code
    response.headers = headers or {}
    response.text = text
    response.json.return_value = json_data or {}
    return response


class MockAsyncClient:
    """Minimal async client test double."""

    def __init__(self, responses: MagicMock | Exception | list[MagicMock | Exception]):
        self._responses = list(responses) if isinstance(responses, list) else [responses]
        self.requests: list[tuple[str, dict, dict]] = []

    async def __aenter__(self) -> MockAsyncClient:
        return self

    async def __aexit__(self, *args: object) -> None:
        return None

    async def post(self, url: str, json: dict, headers: dict) -> MagicMock:
        self.requests.append((url, json, headers))
        response = self._responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return response


def successful_response(content: str = "Kimi response") -> MagicMock:
    """Return a successful Kimi response fixture."""
    return create_mock_response(
        json_data={
            "id": "chatcmpl-kimi",
            "model": "kimi-k3",
            "choices": [
                {
                    "message": {
                        "role": "assistant",
                        "content": content,
                        "reasoning_content": "internal reasoning",
                    },
                    "finish_reason": "stop",
                }
            ],
            "usage": {
                "prompt_tokens": 12,
                "completion_tokens": 8,
                "total_tokens": 20,
                "cached_tokens": 4,
            },
        }
    )


class TestKimiTransport:
    """Direct Kimi transport behavior."""

    def test_provider_identity_and_availability(self) -> None:
        transport = KimiTransport(create_kimi_route())

        assert transport.transport_type == LLMTransportType.KIMI_API
        assert transport.provider_type == LLMProviderType.KIMI
        assert transport.is_available() is True

    def test_unavailable_without_api_key(self) -> None:
        transport = KimiTransport(create_kimi_route(api_key=None))

        assert transport.is_available() is False

    @pytest.mark.asyncio
    async def test_execute_uses_current_kimi_request_contract(self) -> None:
        client = MockAsyncClient(successful_response())
        transport = KimiTransport(create_kimi_route(base_url="https://api.moonshot.ai/v1/"))

        with patch.object(httpx, "AsyncClient", return_value=client):
            response = await transport.execute(
                LLMRequest(
                    prompt="Research this",
                    system_prompt="Be rigorous",
                    max_tokens=2048,
                    temperature=0.1,
                    metadata={"operation": "analysis"},
                )
            )

        url, payload, headers = client.requests[0]
        assert url == "https://api.moonshot.ai/v1/chat/completions"
        assert headers["Authorization"] == "Bearer test-kimi-key"
        assert payload == {
            "model": "kimi-k3",
            "messages": [
                {"role": "system", "content": "Be rigorous"},
                {"role": "user", "content": "Research this"},
            ],
            "max_completion_tokens": 2048,
            "reasoning_effort": "max",
        }
        assert response.content == "Kimi response"
        assert response.provider == LLMProviderType.KIMI
        assert response.transport == LLMTransportType.KIMI_API
        assert response.usage == {
            "prompt_tokens": 12,
            "completion_tokens": 8,
            "total_tokens": 20,
            "cached_tokens": 4,
        }
        assert response.metadata["response_id"] == "chatcmpl-kimi"
        assert "reasoning_content" not in response.metadata

    @pytest.mark.asyncio
    async def test_execute_rotates_after_rate_limit(self) -> None:
        client = MockAsyncClient(
            [
                create_mock_response(429, headers={"Retry-After": "10"}),
                successful_response("Rotated response"),
            ]
        )
        transport = KimiTransport(create_kimi_route(api_key="key-1", api_keys=["key-1", "key-2"]))

        with patch.object(httpx, "AsyncClient", return_value=client):
            response = await transport.execute(LLMRequest(prompt="Research this"))

        assert response.content == "Rotated response"
        assert client.requests[0][2]["Authorization"] == "Bearer key-1"
        assert client.requests[1][2]["Authorization"] == "Bearer key-2"

    @pytest.mark.asyncio
    async def test_non_k3_models_omit_k3_reasoning_effort(self) -> None:
        client = MockAsyncClient(successful_response())
        transport = KimiTransport(create_kimi_route(model="kimi-k2.6"))

        with patch.object(httpx, "AsyncClient", return_value=client):
            await transport.execute(LLMRequest(prompt="Research this"))

        assert "reasoning_effort" not in client.requests[0][1]

    @pytest.mark.asyncio
    async def test_execute_reports_authentication_errors(self) -> None:
        transport = KimiTransport(create_kimi_route())

        with (
            patch.object(
                httpx,
                "AsyncClient",
                return_value=MockAsyncClient(create_mock_response(401)),
            ),
            pytest.raises(LLMAuthenticationError) as exc_info,
        ):
            await transport.execute(LLMRequest(prompt="Research this"))

        assert exc_info.value.provider == LLMProviderType.KIMI
        assert exc_info.value.transport == LLMTransportType.KIMI_API

    @pytest.mark.asyncio
    async def test_execute_reports_rate_limit_after_all_keys(self) -> None:
        transport = KimiTransport(create_kimi_route())

        with (
            patch.object(
                httpx,
                "AsyncClient",
                return_value=MockAsyncClient(
                    create_mock_response(429, headers={"Retry-After": "7"})
                ),
            ),
            pytest.raises(LLMRateLimitError) as exc_info,
        ):
            await transport.execute(LLMRequest(prompt="Research this"))

        assert exc_info.value.retry_after_seconds == 7
        assert exc_info.value.provider == LLMProviderType.KIMI

    @pytest.mark.asyncio
    async def test_execute_reports_provider_error_message(self) -> None:
        transport = KimiTransport(create_kimi_route())

        with (
            patch.object(
                httpx,
                "AsyncClient",
                return_value=MockAsyncClient(
                    create_mock_response(
                        400,
                        json_data={"error": {"message": "Unsupported model"}},
                    )
                ),
            ),
            pytest.raises(LLMProviderError) as exc_info,
        ):
            await transport.execute(LLMRequest(prompt="Research this"))

        assert exc_info.value.status_code == 400
        assert "Unsupported model" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_execute_requires_api_key(self) -> None:
        transport = KimiTransport(create_kimi_route(api_key=None))

        with pytest.raises(LLMAuthenticationError):
            await transport.execute(LLMRequest(prompt="Research this"))
