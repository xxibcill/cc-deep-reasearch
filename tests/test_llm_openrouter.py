"""Tests for OpenRouter LLM transport adapter."""

import json
from unittest.mock import MagicMock, patch

import httpx
import pytest

from cc_deep_research.llm.base import (
    LLMAuthenticationError,
    LLMError,
    LLMProviderError,
    LLMProviderType,
    LLMRateLimitError,
    LLMRequest,
    LLMRoute,
    LLMTimeoutError,
    LLMTransportType,
)
from cc_deep_research.llm.openrouter import OpenRouterTransport


def create_route(
    *,
    api_key: str = "test-api-key",
    base_url: str = "https://openrouter.ai/api/v1",
    model: str = "anthropic/claude-sonnet-4",
    timeout_seconds: int = 120,
    extra_headers: dict | None = None,
) -> LLMRoute:
    """Create a test LLMRoute with OpenRouter configuration."""
    extra = {
        "api_key": api_key,
        "base_url": base_url,
    }
    if extra_headers:
        extra["extra_headers"] = extra_headers

    return LLMRoute(
        transport=LLMTransportType.OPENROUTER_API,
        provider=LLMProviderType.OPENROUTER,
        model=model,
        timeout_seconds=timeout_seconds,
        extra=extra,
    )


def create_mock_response(
    status_code: int = 200,
    json_data: dict | None = None,
    headers: dict | None = None,
    text: str = "",
) -> MagicMock:
    """Create a mock httpx Response."""
    response = MagicMock(spec=httpx.Response)
    response.status_code = status_code
    response.headers = headers or {}
    response.text = text

    if json_data is not None:
        response.json.return_value = json_data
    else:
        response.json.return_value = {}

    return response


class MockAsyncClient:
    """Mock httpx.AsyncClient for testing."""

    def __init__(self, response: MagicMock | Exception | None = None):
        self._response = response

    async def __aenter__(self) -> "MockAsyncClient":
        return self

    async def __aexit__(self, *args: object) -> None:
        pass

    async def post(self, url: str, json: dict, headers: dict) -> MagicMock:
        if isinstance(self._response, Exception):
            raise self._response
        return self._response


class TestOpenRouterTransport:
    """Tests for OpenRouterTransport."""

    def test_transport_type(self) -> None:
        """Test transport_type property."""
        transport = OpenRouterTransport(create_route())
        assert transport.transport_type == LLMTransportType.OPENROUTER_API

    def test_provider_type(self) -> None:
        """Test provider_type property."""
        transport = OpenRouterTransport(create_route())
        assert transport.provider_type == LLMProviderType.OPENROUTER

    def test_is_available_with_api_key(self) -> None:
        """Test is_available returns True with API key."""
        transport = OpenRouterTransport(create_route(api_key="test-key"))
        assert transport.is_available() is True

    def test_is_available_without_api_key(self) -> None:
        """Test is_available returns False without API key."""
        route = LLMRoute(
            transport=LLMTransportType.OPENROUTER_API,
            provider=LLMProviderType.OPENROUTER,
            extra={},
        )
        transport = OpenRouterTransport(route)
        assert transport.is_available() is False

    def test_is_available_with_empty_api_key(self) -> None:
        """Test is_available returns False with empty API key."""
        transport = OpenRouterTransport(create_route(api_key=""))
        assert transport.is_available() is False

    def test_api_key_from_parameter(self) -> None:
        """Test API key can be passed as parameter."""
        route = LLMRoute(
            transport=LLMTransportType.OPENROUTER_API,
            provider=LLMProviderType.OPENROUTER,
            extra={},
        )
        transport = OpenRouterTransport(route, api_key="param-key")
        assert transport.is_available() is True

    @pytest.mark.asyncio
    async def test_execute_success(self) -> None:
        """Test successful execute request."""
        mock_response = create_mock_response(
            status_code=200,
            json_data={
                "id": "resp-123",
                "model": "anthropic/claude-sonnet-4",
                "choices": [
                    {
                        "message": {"content": "Test response content"},
                        "finish_reason": "stop",
                    }
                ],
                "usage": {
                    "prompt_tokens": 10,
                    "completion_tokens": 5,
                    "total_tokens": 15,
                },
            },
        )

        transport = OpenRouterTransport(create_route())

        with patch.object(
            httpx, "AsyncClient", return_value=MockAsyncClient(mock_response)
        ):
            request = LLMRequest(
                prompt="Test prompt",
                metadata={"operation": "test_op"},
            )
            response = await transport.execute(request)

        assert response.content == "Test response content"
        assert response.model == "anthropic/claude-sonnet-4"
        assert response.provider == LLMProviderType.OPENROUTER
        assert response.transport == LLMTransportType.OPENROUTER_API
        assert response.finish_reason == "stop"
        assert response.usage["prompt_tokens"] == 10
        assert response.usage["completion_tokens"] == 5
        assert response.usage["total_tokens"] == 15

    @pytest.mark.asyncio
    async def test_execute_with_system_prompt(self) -> None:
        """Test execute with system prompt."""
        captured_payload: dict = {}

        class CapturingMockClient(MockAsyncClient):
            async def post(self, url: str, json: dict, headers: dict) -> MagicMock:
                captured_payload.update(json)
                return await super().post(url, json, headers)

        mock_response = create_mock_response(
            status_code=200,
            json_data={
                "id": "resp-123",
                "model": "anthropic/claude-sonnet-4",
                "choices": [
                    {
                        "message": {"content": "Response"},
                        "finish_reason": "stop",
                    }
                ],
                "usage": {},
            },
        )

        transport = OpenRouterTransport(create_route())

        with patch.object(
            httpx, "AsyncClient", return_value=CapturingMockClient(mock_response)
        ):
            request = LLMRequest(
                prompt="User prompt",
                system_prompt="System instructions",
            )
            await transport.execute(request)

        assert len(captured_payload["messages"]) == 2
        assert captured_payload["messages"][0]["role"] == "system"
        assert captured_payload["messages"][0]["content"] == "System instructions"
        assert captured_payload["messages"][1]["role"] == "user"
        assert captured_payload["messages"][1]["content"] == "User prompt"

    @pytest.mark.asyncio
    async def test_execute_with_model_override(self) -> None:
        """Test execute with model override."""
        captured_payload: dict = {}

        class CapturingMockClient(MockAsyncClient):
            async def post(self, url: str, json: dict, headers: dict) -> MagicMock:
                captured_payload.update(json)
                mock_response = create_mock_response(
                    status_code=200,
                    json_data={
                        "id": "resp-123",
                        "model": json["model"],
                        "choices": [
                            {
                                "message": {"content": "Response"},
                                "finish_reason": "stop",
                            }
                        ],
                        "usage": {},
                    },
                )
                return mock_response

        transport = OpenRouterTransport(create_route(model="default-model"))

        with patch.object(httpx, "AsyncClient", return_value=CapturingMockClient(None)):
            request = LLMRequest(
                prompt="Test prompt",
                model="override-model",
            )
            response = await transport.execute(request)

        assert captured_payload["model"] == "override-model"
        assert response.model == "override-model"

    @pytest.mark.asyncio
    async def test_execute_authentication_error_401(self) -> None:
        """Test execute raises LLMAuthenticationError on 401."""
        mock_response = create_mock_response(status_code=401)
        transport = OpenRouterTransport(create_route())

        with patch.object(
            httpx, "AsyncClient", return_value=MockAsyncClient(mock_response)
        ):
            request = LLMRequest(prompt="Test prompt")

            with pytest.raises(LLMAuthenticationError) as exc_info:
                await transport.execute(request)

        assert exc_info.value.provider == LLMProviderType.OPENROUTER
        assert exc_info.value.transport == LLMTransportType.OPENROUTER_API

    @pytest.mark.asyncio
    async def test_execute_rate_limit_error_429(self) -> None:
        """Test execute raises LLMRateLimitError on 429."""
        mock_response = create_mock_response(
            status_code=429, headers={"Retry-After": "60"}
        )
        transport = OpenRouterTransport(create_route())

        with patch.object(
            httpx, "AsyncClient", return_value=MockAsyncClient(mock_response)
        ):
            request = LLMRequest(prompt="Test prompt")

            with pytest.raises(LLMRateLimitError) as exc_info:
                await transport.execute(request)

        assert exc_info.value.retry_after_seconds == 60
        assert exc_info.value.provider == LLMProviderType.OPENROUTER

    @pytest.mark.asyncio
    async def test_execute_rate_limit_without_retry_after(self) -> None:
        """Test execute raises LLMRateLimitError without retry_after."""
        mock_response = create_mock_response(status_code=429, headers={})
        transport = OpenRouterTransport(create_route())

        with patch.object(
            httpx, "AsyncClient", return_value=MockAsyncClient(mock_response)
        ):
            request = LLMRequest(prompt="Test prompt")

            with pytest.raises(LLMRateLimitError) as exc_info:
                await transport.execute(request)

        assert exc_info.value.retry_after_seconds is None

    @pytest.mark.asyncio
    async def test_execute_provider_error_400(self) -> None:
        """Test execute raises LLMProviderError on 400."""
        mock_response = create_mock_response(
            status_code=400,
            json_data={"error": {"message": "Invalid request parameter"}},
        )
        transport = OpenRouterTransport(create_route())

        with patch.object(
            httpx, "AsyncClient", return_value=MockAsyncClient(mock_response)
        ):
            request = LLMRequest(prompt="Test prompt")

            with pytest.raises(LLMProviderError) as exc_info:
                await transport.execute(request)

        assert exc_info.value.status_code == 400
        assert "Invalid request parameter" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_execute_provider_error_500(self) -> None:
        """Test execute raises LLMProviderError on 500."""
        mock_response = create_mock_response(
            status_code=500,
            json_data={"error": "Internal server error"},
            text='{"error": "Internal server error"}',
        )
        transport = OpenRouterTransport(create_route())

        with patch.object(
            httpx, "AsyncClient", return_value=MockAsyncClient(mock_response)
        ):
            request = LLMRequest(prompt="Test prompt")

            with pytest.raises(LLMProviderError) as exc_info:
                await transport.execute(request)

        assert exc_info.value.status_code == 500

    @pytest.mark.asyncio
    async def test_execute_timeout_error(self) -> None:
        """Test execute raises LLMTimeoutError on timeout."""
        transport = OpenRouterTransport(create_route(timeout_seconds=30))

        with patch.object(
            httpx,
            "AsyncClient",
            return_value=MockAsyncClient(
                httpx.TimeoutException("Request timed out")
            ),
        ):
            request = LLMRequest(prompt="Test prompt")

            with pytest.raises(LLMTimeoutError) as exc_info:
                await transport.execute(request)

        assert exc_info.value.timeout_seconds == 30
        assert exc_info.value.provider == LLMProviderType.OPENROUTER

    @pytest.mark.asyncio
    async def test_execute_request_error(self) -> None:
        """Test execute raises LLMError on request error."""

        class MockConnectError(httpx.ConnectError):
            def __init__(self) -> None:
                super().__init__("Connection failed")

        transport = OpenRouterTransport(create_route())

        with patch.object(
            httpx, "AsyncClient", return_value=MockAsyncClient(MockConnectError())
        ):
            request = LLMRequest(prompt="Test prompt")

            with pytest.raises(LLMError) as exc_info:
                await transport.execute(request)

        assert "Connection failed" in str(exc_info.value)
        assert exc_info.value.provider == LLMProviderType.OPENROUTER

    @pytest.mark.asyncio
    async def test_execute_without_api_key(self) -> None:
        """Test execute raises LLMAuthenticationError without API key."""
        route = LLMRoute(
            transport=LLMTransportType.OPENROUTER_API,
            provider=LLMProviderType.OPENROUTER,
            extra={},
        )
        transport = OpenRouterTransport(route)

        request = LLMRequest(prompt="Test prompt")

        with pytest.raises(LLMAuthenticationError) as exc_info:
            await transport.execute(request)

        assert "not configured" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_execute_malformed_json_response(self) -> None:
        """Test execute raises LLMProviderError on malformed JSON."""
        mock_response = create_mock_response(status_code=200)
        mock_response.json.side_effect = json.JSONDecodeError("Invalid", "", 0)
        transport = OpenRouterTransport(create_route())

        with patch.object(
            httpx, "AsyncClient", return_value=MockAsyncClient(mock_response)
        ):
            request = LLMRequest(prompt="Test prompt")

            with pytest.raises(LLMProviderError) as exc_info:
                await transport.execute(request)

        assert "Failed to parse" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_execute_empty_choices(self) -> None:
        """Test execute raises LLMProviderError on empty choices."""
        mock_response = create_mock_response(
            status_code=200,
            json_data={
                "id": "resp-123",
                "choices": [],
            },
        )
        transport = OpenRouterTransport(create_route())

        with patch.object(
            httpx, "AsyncClient", return_value=MockAsyncClient(mock_response)
        ):
            request = LLMRequest(prompt="Test prompt")

            with pytest.raises(LLMProviderError) as exc_info:
                await transport.execute(request)

        assert "no choices" in str(exc_info.value).lower()

    @pytest.mark.asyncio
    async def test_execute_with_telemetry_callback(self) -> None:
        """Test execute calls telemetry callback."""
        events: list[dict] = []

        def telemetry_callback(event: dict) -> None:
            events.append(event)

        mock_response = create_mock_response(
            status_code=200,
            json_data={
                "id": "resp-123",
                "model": "anthropic/claude-sonnet-4",
                "choices": [
                    {
                        "message": {"content": "Response"},
                        "finish_reason": "stop",
                    }
                ],
                "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
            },
        )

        transport = OpenRouterTransport(
            create_route(), telemetry_callback=telemetry_callback
        )

        with patch.object(
            httpx, "AsyncClient", return_value=MockAsyncClient(mock_response)
        ):
            request = LLMRequest(prompt="Test prompt", metadata={"operation": "test"})
            await transport.execute(request)

        # Should have started and completed events
        assert len(events) >= 2
        event_types = {e.get("event_type") for e in events}
        assert "llm_request_started" in event_types
        assert "llm_request_completed" in event_types

    @pytest.mark.asyncio
    async def test_execute_with_extra_headers(self) -> None:
        """Test execute includes extra headers."""
        captured_headers: dict = {}

        class HeaderCapturingClient(MockAsyncClient):
            async def post(self, url: str, json: dict, headers: dict) -> MagicMock:
                captured_headers.update(headers)
                return await super().post(url, json, headers)

        mock_response = create_mock_response(
            status_code=200,
            json_data={
                "id": "resp-123",
                "model": "anthropic/claude-sonnet-4",
                "choices": [
                    {
                        "message": {"content": "Response"},
                        "finish_reason": "stop",
                    }
                ],
                "usage": {},
            },
        )

        transport = OpenRouterTransport(
            create_route(extra_headers={"X-Custom-Header": "custom-value"})
        )

        with patch.object(
            httpx, "AsyncClient", return_value=HeaderCapturingClient(mock_response)
        ):
            request = LLMRequest(prompt="Test prompt")
            await transport.execute(request)

        assert captured_headers.get("X-Custom-Header") == "custom-value"
        assert "Bearer" in captured_headers.get("Authorization", "")

    def test_build_payload_includes_all_params(self) -> None:
        """Test _build_payload includes all request parameters."""
        route = create_route(model="default-model")
        transport = OpenRouterTransport(route)

        request = LLMRequest(
            prompt="Test prompt",
            system_prompt="System instructions",
            model="override-model",
            temperature=0.7,
            max_tokens=2000,
        )

        payload = transport._build_payload(request, "override-model")

        assert payload["model"] == "override-model"
        assert payload["temperature"] == 0.7
        assert payload["max_tokens"] == 2000
        assert len(payload["messages"]) == 2
        assert payload["messages"][0]["role"] == "system"
        assert payload["messages"][1]["role"] == "user"

    def test_build_payload_without_system_prompt(self) -> None:
        """Test _build_payload without system prompt."""
        transport = OpenRouterTransport(create_route())

        request = LLMRequest(prompt="Test prompt")

        payload = transport._build_payload(request, "test-model")

        assert len(payload["messages"]) == 1
        assert payload["messages"][0]["role"] == "user"

    def test_extract_error_message_with_dict(self) -> None:
        """Test _extract_error_message with dict error."""
        transport = OpenRouterTransport(create_route())

        mock_response = create_mock_response(
            json_data={"error": {"message": "Error message from API"}}
        )

        error_msg = transport._extract_error_message(mock_response)
        assert error_msg == "Error message from API"

    def test_extract_error_message_with_string_error(self) -> None:
        """Test _extract_error_message with string error."""
        transport = OpenRouterTransport(create_route())

        mock_response = create_mock_response(json_data={"error": "Simple error string"})

        error_msg = transport._extract_error_message(mock_response)
        assert error_msg == "Simple error string"

    def test_extract_error_message_with_invalid_json(self) -> None:
        """Test _extract_error_message with invalid JSON falls back to text."""
        transport = OpenRouterTransport(create_route())

        mock_response = create_mock_response(text="Raw error text")
        mock_response.json.side_effect = json.JSONDecodeError("Invalid", "", 0)

        error_msg = transport._extract_error_message(mock_response)
        assert error_msg == "Raw error text"

    def test_extract_error_message_with_empty_response(self) -> None:
        """Test _extract_error_message with empty response."""
        transport = OpenRouterTransport(create_route())

        mock_response = create_mock_response(text="")
        mock_response.json.side_effect = json.JSONDecodeError("Invalid", "", 0)

        error_msg = transport._extract_error_message(mock_response)
        assert error_msg == "Unknown error"

    def test_parse_retry_after_valid(self) -> None:
        """Test _parse_retry_after with valid header."""
        transport = OpenRouterTransport(create_route())

        mock_response = create_mock_response(headers={"Retry-After": "120"})

        retry_after = transport._parse_retry_after(mock_response)
        assert retry_after == 120

    def test_parse_retry_after_invalid(self) -> None:
        """Test _parse_retry_after with invalid header."""
        transport = OpenRouterTransport(create_route())

        mock_response = create_mock_response(headers={"Retry-After": "not-a-number"})

        retry_after = transport._parse_retry_after(mock_response)
        assert retry_after is None

    def test_parse_retry_after_missing(self) -> None:
        """Test _parse_retry_after with missing header."""
        transport = OpenRouterTransport(create_route())

        mock_response = create_mock_response(headers={})

        retry_after = transport._parse_retry_after(mock_response)
        assert retry_after is None
