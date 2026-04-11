"""Anthropic API transport adapter for LLM routing layer.

This module implements the Anthropic API transport for the LLM routing
architecture, providing direct API access to Anthropic models with support
for custom base URLs (proxy/gateway support) and comprehensive token usage
tracking.
"""

from __future__ import annotations

import time
from collections.abc import Callable
from typing import TYPE_CHECKING, Any, cast

from anthropic import Anthropic, APIError, AuthenticationError, RateLimitError

from cc_deep_research.llm.base import (
    BaseLLMTransport,
    LLMAuthenticationError,
    LLMError,
    LLMProviderError,
    LLMProviderType,
    LLMRateLimitError,
    LLMRequest,
    LLMResponse,
    LLMRoute,
    LLMTransportType,
)
from cc_deep_research.llm.env import (
    get_anthropic_api_key,
    get_anthropic_base_url,
    get_anthropic_max_tokens,
    get_anthropic_model,
    get_api_timeout_ms,
)
from cc_deep_research.llm.usage_tracker import TokenUsageEntry, append_usage_entry

if TYPE_CHECKING:
    pass


class AnthropicAPITransport(BaseLLMTransport):
    """Anthropic API transport adapter for LLM operations.

    This transport executes LLM requests through the Anthropic SDK,
    supporting custom base URLs for proxy/gateway support and
    comprehensive token usage tracking.

    Attributes:
        _api_key: Anthropic API key.
        _base_url: Anthropic API base URL.
        _timeout_seconds: Request timeout in seconds.
        _model: Default model identifier.
        _max_tokens: Default max tokens for responses.
        _client: Anthropic client instance.
    """

    def __init__(
        self,
        route: LLMRoute,
        *,
        telemetry_callback: Callable[[dict[str, Any]], None] | None = None,
    ) -> None:
        """Initialize the Anthropic transport.

        Args:
            route: The route configuration for this transport.
            telemetry_callback: Optional callback for LLM-level telemetry.
        """
        super().__init__(route, telemetry_callback=telemetry_callback)

        # Collect API keys from route extra or environment
        self._api_keys = self._collect_api_keys(
            route.extra.get("api_key"),
            route.extra.get("api_keys"),
        )

        # Get API key from route or environment
        self._api_key = self._api_keys[0] if self._api_keys else get_anthropic_api_key()

        # Get base URL from route or environment
        self._base_url = (
            route.extra.get("base_url") or get_anthropic_base_url() or "https://api.anthropic.com"
        )

        # Get timeout from route or environment
        self._timeout_seconds = route.timeout_seconds or get_api_timeout_ms() or 120

        # Get model from route or environment
        self._model = route.model or get_anthropic_model() or "claude-sonnet-4-6"

        # Get max tokens from route or environment
        self._max_tokens = route.extra.get("max_tokens") or get_anthropic_max_tokens()

        # Initialize client if API key is available
        self._client: Anthropic | None = None
        if self._api_key:
            self._client = Anthropic(
                api_key=self._api_key,
                base_url=self._base_url,
                timeout=self._timeout_seconds,
            )

    @property
    def transport_type(self) -> LLMTransportType:
        """Return the transport type for this adapter."""
        return LLMTransportType.ANTHROPIC_API

    @property
    def provider_type(self) -> LLMProviderType:
        """Return the provider type for this adapter."""
        return LLMProviderType.ANTHROPIC

    def is_available(self) -> bool:
        """Check if Anthropic transport is available.

        Returns:
            True if an API key is configured.
        """
        return self._api_key is not None and len(self._api_key) > 0

    async def execute(self, request: LLMRequest) -> LLMResponse:
        """Execute an LLM request through Anthropic API.

        Args:
            request: The normalized LLM request.

        Returns:
            The normalized LLM response.

        Raises:
            LLMAuthenticationError: If authentication fails.
            LLMRateLimitError: If rate limit is exceeded.
            LLMProviderError: If the provider returns an error.
            LLMError: For other errors.
        """
        if not self._api_key or not self._client:
            raise LLMAuthenticationError(
                "Anthropic API key not configured",
                provider=LLMProviderType.ANTHROPIC,
                transport=LLMTransportType.ANTHROPIC_API,
            )

        start_time = time.time()
        model = request.model or self._model
        max_tokens = request.max_tokens or self._max_tokens

        # Build messages
        messages = [{"role": "user", "content": request.prompt}]

        self._emit_telemetry(
            "llm_request_started",
            {
                "operation": request.metadata.get("operation", "unknown"),
                "model": model,
                "timeout_seconds": self._timeout_seconds,
                "max_tokens": max_tokens,
            },
        )

        try:
            # Make the API call
            response = self._client.messages.create(
                model=model,
                max_tokens=max_tokens,
                messages=cast(Any, messages),
                system=cast(Any, request.system_prompt) if request.system_prompt else None,  # type: ignore[arg-type]
                temperature=request.temperature,
            )

            duration_ms = int((time.time() - start_time) * 1000)

            # Extract text content
            content = self._extract_text_content(response)

            # Build usage info
            usage = {
                "prompt_tokens": response.usage.input_tokens,
                "completion_tokens": response.usage.output_tokens,
                "total_tokens": response.usage.input_tokens + response.usage.output_tokens,
            }

            # Create usage entry for tracking
            usage_entry = TokenUsageEntry(
                model=model,
                base_url=self._base_url,
                request_id=response.id,
                input_tokens=response.usage.input_tokens,
                output_tokens=response.usage.output_tokens,
                total_tokens=response.usage.input_tokens + response.usage.output_tokens,
                cache_creation_input_tokens=getattr(
                    response.usage, "cache_creation_input_tokens", 0
                )
                or 0,
                cache_read_input_tokens=getattr(response.usage, "cache_read_input_tokens", 0) or 0,
                max_tokens=max_tokens,
                latency_ms=duration_ms,
            )

            # Append usage entry to log
            append_usage_entry(usage_entry)

            # Calculate TPM metrics for console output
            avg_tpm = self._calculate_call_tpm(
                response.usage.output_tokens,
                duration_ms,
            )
            from cc_deep_research.llm.usage_tracker import calculate_rolling_tpm

            rolling_tpm = calculate_rolling_tpm()

            # Print console output
            self._print_usage_output(
                input_tokens=response.usage.input_tokens,
                output_tokens=response.usage.output_tokens,
                total_tokens=usage["total_tokens"],
                avg_tpm=avg_tpm,
                rolling_tpm=rolling_tpm,
            )

            self._emit_telemetry(
                "llm_request_completed",
                {
                    "operation": request.metadata.get("operation", "unknown"),
                    "model": model,
                    "latency_ms": duration_ms,
                    "prompt_tokens": usage["prompt_tokens"],
                    "completion_tokens": usage["completion_tokens"],
                    "finish_reason": response.stop_reason,
                },
            )

            return LLMResponse(
                content=content,
                model=model,
                provider=LLMProviderType.ANTHROPIC,
                transport=LLMTransportType.ANTHROPIC_API,
                usage=usage,
                latency_ms=duration_ms,
                finish_reason=response.stop_reason,
                metadata={
                    "operation": request.metadata.get("operation", "unknown"),
                    "response_id": response.id,
                    "cache_creation_input_tokens": usage_entry.cache_creation_input_tokens,
                    "cache_read_input_tokens": usage_entry.cache_read_input_tokens,
                },
            )

        except AuthenticationError as exc:
            duration_ms = int((time.time() - start_time) * 1000)
            self._emit_telemetry(
                "llm_request_failed",
                {
                    "operation": request.metadata.get("operation", "unknown"),
                    "error_type": "authentication",
                    "latency_ms": duration_ms,
                },
            )
            raise LLMAuthenticationError(
                f"Anthropic authentication failed: {exc}",
                provider=LLMProviderType.ANTHROPIC,
                transport=LLMTransportType.ANTHROPIC_API,
                original_error=exc,
            ) from exc

        except RateLimitError as exc:
            duration_ms = int((time.time() - start_time) * 1000)
            self._emit_telemetry(
                "llm_request_failed",
                {
                    "operation": request.metadata.get("operation", "unknown"),
                    "error_type": "rate_limit",
                    "latency_ms": duration_ms,
                },
            )
            raise LLMRateLimitError(
                f"Anthropic rate limit exceeded: {exc}",
                provider=LLMProviderType.ANTHROPIC,
                transport=LLMTransportType.ANTHROPIC_API,
                original_error=exc,
            ) from exc

        except APIError as exc:
            duration_ms = int((time.time() - start_time) * 1000)
            self._emit_telemetry(
                "llm_request_failed",
                {
                    "operation": request.metadata.get("operation", "unknown"),
                    "error_type": "provider_error",
                    "latency_ms": duration_ms,
                    "error_message": str(exc)[:200],
                },
            )
            raise LLMProviderError(
                f"Anthropic API error: {exc}",
                status_code=getattr(exc, "status_code", None),
                provider=LLMProviderType.ANTHROPIC,
                transport=LLMTransportType.ANTHROPIC_API,
                original_error=exc,
            ) from exc

        except Exception as exc:
            duration_ms = int((time.time() - start_time) * 1000)
            self._emit_telemetry(
                "llm_request_error",
                {
                    "operation": request.metadata.get("operation", "unknown"),
                    "error_type": type(exc).__name__,
                    "latency_ms": duration_ms,
                },
            )
            raise LLMError(
                f"Anthropic request failed: {exc}",
                provider=LLMProviderType.ANTHROPIC,
                transport=LLMTransportType.ANTHROPIC_API,
                original_error=exc,
            ) from exc

    def _extract_text_content(self, response: Any) -> str:
        """Extract text content from Anthropic response.

        Args:
            response: The Anthropic API response.

        Returns:
            The extracted text content.

        Raises:
            RuntimeError: If no text content is found.
        """
        text_blocks = []
        for block in response.content:
            if block.type == "text":
                text_blocks.append(block.text)

        if not text_blocks:
            raise RuntimeError("No text content found in Anthropic response")

        return "\n".join(text_blocks)

    @staticmethod
    def _collect_api_keys(*values: Any) -> list[str]:
        """Collect API keys while preserving first-seen order."""
        api_keys: list[str] = []
        seen: set[str] = set()

        for value in values:
            candidates = value if isinstance(value, list) else [value]
            for candidate in candidates:
                if not isinstance(candidate, str):
                    continue
                key = candidate.strip()
                if not key or key in seen:
                    continue
                seen.add(key)
                api_keys.append(key)

        return api_keys

    @staticmethod
    def _calculate_call_tpm(output_tokens: int, latency_ms: int) -> float:
        """Calculate average output TPM for a single call.

        Args:
            output_tokens: Number of output tokens.
            latency_ms: Latency in milliseconds.

        Returns:
            Tokens per minute for this call.
        """
        if latency_ms <= 0:
            return 0.0
        return (output_tokens / latency_ms) * 60000

    @staticmethod
    def _print_usage_output(
        *,
        input_tokens: int,
        output_tokens: int,
        total_tokens: int,
        avg_tpm: float,
        rolling_tpm: float,
    ) -> None:
        """Print usage output to console.

        Args:
            input_tokens: Input token count.
            output_tokens: Output token count.
            total_tokens: Total token count.
            avg_tpm: Average output TPM for this call.
            rolling_tpm: Rolling TPM over the last 60 seconds.
        """
        print(f"input tokens: {input_tokens}")
        print(f"output tokens: {output_tokens}")
        print(f"total tokens: {total_tokens}")
        print(f"average output TPM for this call: {avg_tpm:.2f}")
        print(f"rolling TPM over the last 60 seconds: {rolling_tpm:.2f}")


__all__ = ["AnthropicAPITransport"]
