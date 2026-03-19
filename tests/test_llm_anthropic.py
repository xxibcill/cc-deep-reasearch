"""Tests for Anthropic LLM transport and environment loading."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from cc_deep_research.llm import env
from cc_deep_research.llm.anthropic import AnthropicAPITransport
from cc_deep_research.llm.base import (
    LLMProviderType,
    LLMRoute,
    LLMTransportType,
)

# Environment Loading Tests


def test_get_api_key_from_auth_token(monkeypatch: pytest.MonkeyPatch) -> None:
    """ANTHROPIC_AUTH_TOKEN takes priority."""
    monkeypatch.setenv("ANTHROPIC_AUTH_TOKEN", "auth-token-value")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "api-key-value")

    assert env.get_anthropic_api_key() == "auth-token-value"


def test_get_api_key_fallback(monkeypatch: pytest.MonkeyPatch) -> None:
    """Falls back to ANTHROPIC_API_KEY when AUTH_TOKEN not set."""
    monkeypatch.delenv("ANTHROPIC_AUTH_TOKEN", raising=False)
    monkeypatch.setenv("ANTHROPIC_API_KEY", "api-key-value")

    assert env.get_anthropic_api_key() == "api-key-value"


def test_get_base_url(monkeypatch: pytest.MonkeyPatch) -> None:
    """Get base URL from environment."""
    monkeypatch.setenv("ANTHROPIC_BASE_URL", "https://custom.api.com")

    assert env.get_anthropic_base_url() == "https://custom.api.com"


def test_get_model(monkeypatch: pytest.MonkeyPatch) -> None:
    """Get model from environment."""
    monkeypatch.setenv("ANTHROPIC_MODEL", "claude-opus-4-6")

    assert env.get_anthropic_model() == "claude-opus-4-6"


def test_get_timeout_ms(monkeypatch: pytest.MonkeyPatch) -> None:
    """Converts ms to seconds."""
    monkeypatch.setenv("API_TIMEOUT_MS", "60000")

    assert env.get_api_timeout_ms() == 60


def test_get_max_tokens(monkeypatch: pytest.MonkeyPatch) -> None:
    """Get max tokens from environment."""
    monkeypatch.setenv("ANTHROPIC_MAX_TOKENS", "1024")

    assert env.get_anthropic_max_tokens() == 1024


def test_get_max_tokens_default(monkeypatch: pytest.MonkeyPatch) -> None:
    """Default max tokens is 512."""
    monkeypatch.delenv("ANTHROPIC_MAX_TOKENS", raising=False)

    assert env.get_anthropic_max_tokens() == 512


# Transport Config Tests


def test_transport_type() -> None:
    """Transport type is ANTHROPIC_API."""
    route = LLMRoute(
        transport=LLMTransportType.ANTHROPIC_API,
        provider=LLMProviderType.ANTHROPIC,
    )
    transport = AnthropicAPITransport(route)

    assert transport.transport_type == LLMTransportType.ANTHROPIC_API


def test_provider_type() -> None:
    """Provider type is ANTHROPIC."""
    route = LLMRoute(
        transport=LLMTransportType.ANTHROPIC_API,
        provider=LLMProviderType.ANTHROPIC,
    )
    transport = AnthropicAPITransport(route)

    assert transport.provider_type == LLMProviderType.ANTHROPIC


def test_is_available_with_api_key(monkeypatch: pytest.MonkeyPatch) -> None:
    """Transport is available when API key is configured."""
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")

    route = LLMRoute(
        transport=LLMTransportType.ANTHROPIC_API,
        provider=LLMProviderType.ANTHROPIC,
    )
    transport = AnthropicAPITransport(route)

    assert transport.is_available() is True


def test_is_available_without_api_key(monkeypatch: pytest.MonkeyPatch) -> None:
    """Transport is not available when API key is not configured."""
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("ANTHROPIC_AUTH_TOKEN", raising=False)

    route = LLMRoute(
        transport=LLMTransportType.ANTHROPIC_API,
        provider=LLMProviderType.ANTHROPIC,
    )
    transport = AnthropicAPITransport(route)

    assert transport.is_available() is False


# Response Text Extraction Tests


def test_extract_single_text_block() -> None:
    """Extract single text block from response."""
    route = LLMRoute(
        transport=LLMTransportType.ANTHROPIC_API,
        provider=LLMProviderType.ANTHROPIC,
    )
    transport = AnthropicAPITransport(route)

    # Mock response with single text block
    mock_response = MagicMock()
    mock_response.content = [MagicMock(type="text", text="Hello, world!")]

    result = transport._extract_text_content(mock_response)
    assert result == "Hello, world!"


def test_extract_multiple_text_blocks() -> None:
    """Extract and join multiple text blocks with newlines."""
    route = LLMRoute(
        transport=LLMTransportType.ANTHROPIC_API,
        provider=LLMProviderType.ANTHROPIC,
    )
    transport = AnthropicAPITransport(route)

    # Mock response with multiple text blocks
    mock_response = MagicMock()
    mock_response.content = [
        MagicMock(type="text", text="First block"),
        MagicMock(type="text", text="Second block"),
    ]

    result = transport._extract_text_content(mock_response)
    assert result == "First block\nSecond block"


def test_extract_no_text_raises_error() -> None:
    """Raises RuntimeError when no text content found."""
    route = LLMRoute(
        transport=LLMTransportType.ANTHROPIC_API,
        provider=LLMProviderType.ANTHROPIC,
    )
    transport = AnthropicAPITransport(route)

    # Mock response with no text blocks
    mock_response = MagicMock()
    mock_response.content = [MagicMock(type="image")]

    with pytest.raises(RuntimeError, match="No text content found"):
        transport._extract_text_content(mock_response)


def test_extract_skips_non_text_blocks() -> None:
    """Skips non-text blocks and extracts only text."""
    route = LLMRoute(
        transport=LLMTransportType.ANTHROPIC_API,
        provider=LLMProviderType.ANTHROPIC,
    )
    transport = AnthropicAPITransport(route)

    # Mock response with mixed content
    mock_response = MagicMock()
    mock_response.content = [
        MagicMock(type="image"),
        MagicMock(type="text", text="Text content"),
        MagicMock(type="tool_use"),
    ]

    result = transport._extract_text_content(mock_response)
    assert result == "Text content"


# Error Wrapping Tests


def test_authentication_error_wrapped(monkeypatch: pytest.MonkeyPatch) -> None:
    """AuthenticationError is wrapped in LLMAuthenticationError."""
    from anthropic import AuthenticationError

    from cc_deep_research.llm.base import LLMAuthenticationError

    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")

    route = LLMRoute(
        transport=LLMTransportType.ANTHROPIC_API,
        provider=LLMProviderType.ANTHROPIC,
    )
    transport = AnthropicAPITransport(route)

    with patch.object(transport._client, "messages") as mock_messages:
        # Create a mock response
        mock_response = MagicMock()
        mock_response.status_code = 401
        mock_messages.create.side_effect = AuthenticationError(
            "Invalid API key",
            response=mock_response,
            body=None,
        )

        import asyncio

        from cc_deep_research.llm.base import LLMRequest

        request = LLMRequest(prompt="Hello")

        with pytest.raises(LLMAuthenticationError):
            asyncio.run(transport.execute(request))


def test_rate_limit_error_wrapped(monkeypatch: pytest.MonkeyPatch) -> None:
    """RateLimitError is wrapped in LLMRateLimitError."""
    from anthropic import RateLimitError

    from cc_deep_research.llm.base import LLMRateLimitError

    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")

    route = LLMRoute(
        transport=LLMTransportType.ANTHROPIC_API,
        provider=LLMProviderType.ANTHROPIC,
    )
    transport = AnthropicAPITransport(route)

    with patch.object(transport._client, "messages") as mock_messages:
        # Create a mock response
        mock_response = MagicMock()
        mock_response.status_code = 429
        mock_messages.create.side_effect = RateLimitError(
            "Rate limit exceeded",
            response=mock_response,
            body=None,
        )

        import asyncio

        from cc_deep_research.llm.base import LLMRequest

        request = LLMRequest(prompt="Hello")

        with pytest.raises(LLMRateLimitError):
            asyncio.run(transport.execute(request))


def test_api_error_wrapped(monkeypatch: pytest.MonkeyPatch) -> None:
    """APIError is wrapped in LLMProviderError."""
    from anthropic import APIError

    from cc_deep_research.llm.base import LLMProviderError

    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")

    route = LLMRoute(
        transport=LLMTransportType.ANTHROPIC_API,
        provider=LLMProviderType.ANTHROPIC,
    )
    transport = AnthropicAPITransport(route)

    with patch.object(transport._client, "messages") as mock_messages:
        # Create a mock request
        mock_request = MagicMock()
        mock_messages.create.side_effect = APIError(
            "Internal server error",
            request=mock_request,
            body=None,
        )

        import asyncio

        from cc_deep_research.llm.base import LLMRequest

        request = LLMRequest(prompt="Hello")

        with pytest.raises(LLMProviderError):
            asyncio.run(transport.execute(request))
