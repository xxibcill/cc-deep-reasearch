"""Cerebras API transport adapter for LLM routing layer.

This module implements the Cerebras API transport for the LLM routing
architecture, providing high-speed inference through Cerebras's
wafer-scale accelerator infrastructure.
"""

from __future__ import annotations

import json
import time
from typing import Any, Callable

import httpx

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
    LLMTimeoutError,
    LLMTransportType,
)


class CerebrasTransport(BaseLLMTransport):
    """Cerebras API transport adapter for LLM operations.

    This transport executes LLM requests through the Cerebras API,
    leveraging their high-speed inference infrastructure for fast
    response times on supported models.

    Attributes:
        _api_key: Cerebras API key.
        _base_url: Cerebras API base URL.
        _timeout_seconds: Request timeout in seconds.
        _model: Default model identifier.
    """

    def __init__(
        self,
        route: LLMRoute,
        *,
        api_key: str | None = None,
        telemetry_callback: Callable[[dict[str, Any]], None] | None = None,
    ) -> None:
        """Initialize the Cerebras transport.

        Args:
            route: The route configuration for this transport.
            api_key: Optional API key override (uses route.extra if not provided).
            telemetry_callback: Optional callback for LLM-level telemetry.
        """
        super().__init__(route, telemetry_callback=telemetry_callback)

        # Get API key from parameter, route extra, or environment
        self._api_key = api_key or route.extra.get("api_key")
        self._base_url = route.extra.get("base_url", "https://api.cerebras.ai/v1")
        self._timeout_seconds = route.timeout_seconds
        self._model = route.model

    @property
    def transport_type(self) -> LLMTransportType:
        """Return the transport type for this adapter."""
        return LLMTransportType.CEREBRAS_API

    @property
    def provider_type(self) -> LLMProviderType:
        """Return the provider type for this adapter."""
        return LLMProviderType.CEREBRAS

    def is_available(self) -> bool:
        """Check if Cerebras transport is available.

        Returns:
            True if an API key is configured.
        """
        return self._api_key is not None and len(self._api_key) > 0

    async def execute(self, request: LLMRequest) -> LLMResponse:
        """Execute an LLM request through Cerebras API.

        Args:
            request: The normalized LLM request.

        Returns:
            The normalized LLM response.

        Raises:
            LLMTimeoutError: If the request times out.
            LLMAuthenticationError: If authentication fails.
            LLMRateLimitError: If rate limit is exceeded.
            LLMProviderError: If the provider returns an error.
        """
        if not self._api_key:
            raise LLMAuthenticationError(
                "Cerebras API key not configured",
                provider=LLMProviderType.CEREBRAS,
                transport=LLMTransportType.CEREBRAS_API,
            )

        start_time = time.time()
        model = request.model or self._model

        # Build the request payload in OpenAI-compatible format
        payload = self._build_payload(request, model)
        headers = self._build_headers()

        self._emit_telemetry(
            "llm_request_started",
            {
                "operation": request.metadata.get("operation", "unknown"),
                "model": model,
                "timeout_seconds": self._timeout_seconds,
            },
        )

        try:
            async with httpx.AsyncClient(timeout=self._timeout_seconds) as client:
                response = await client.post(
                    f"{self._base_url}/chat/completions",
                    json=payload,
                    headers=headers,
                )

            duration_ms = int((time.time() - start_time) * 1000)

            # Handle HTTP errors
            if response.status_code == 401:
                self._emit_telemetry(
                    "llm_request_failed",
                    {
                        "operation": request.metadata.get("operation", "unknown"),
                        "error_type": "authentication",
                        "status_code": 401,
                        "latency_ms": duration_ms,
                    },
                )
                raise LLMAuthenticationError(
                    "Cerebras authentication failed: invalid API key",
                    provider=LLMProviderType.CEREBRAS,
                    transport=LLMTransportType.CEREBRAS_API,
                )

            if response.status_code == 429:
                retry_after = self._parse_retry_after(response)
                self._emit_telemetry(
                    "llm_request_failed",
                    {
                        "operation": request.metadata.get("operation", "unknown"),
                        "error_type": "rate_limit",
                        "status_code": 429,
                        "latency_ms": duration_ms,
                        "retry_after_seconds": retry_after,
                    },
                )
                raise LLMRateLimitError(
                    "Cerebras rate limit exceeded",
                    retry_after_seconds=retry_after,
                    provider=LLMProviderType.CEREBRAS,
                    transport=LLMTransportType.CEREBRAS_API,
                )

            if response.status_code >= 400:
                error_message = self._extract_error_message(response)
                self._emit_telemetry(
                    "llm_request_failed",
                    {
                        "operation": request.metadata.get("operation", "unknown"),
                        "error_type": "provider_error",
                        "status_code": response.status_code,
                        "latency_ms": duration_ms,
                        "error_message": error_message[:200],
                    },
                )
                raise LLMProviderError(
                    f"Cerebras API error ({response.status_code}): {error_message}",
                    status_code=response.status_code,
                    provider=LLMProviderType.CEREBRAS,
                    transport=LLMTransportType.CEREBRAS_API,
                )

            # Parse successful response
            return self._parse_response(response, model, duration_ms, request)

        except httpx.TimeoutException as exc:
            duration_ms = int((time.time() - start_time) * 1000)
            self._emit_telemetry(
                "llm_request_timeout",
                {
                    "operation": request.metadata.get("operation", "unknown"),
                    "timeout_seconds": self._timeout_seconds,
                    "latency_ms": duration_ms,
                },
            )
            raise LLMTimeoutError(
                f"Cerebras request timed out after {self._timeout_seconds} seconds",
                timeout_seconds=self._timeout_seconds,
                provider=LLMProviderType.CEREBRAS,
                transport=LLMTransportType.CEREBRAS_API,
                original_error=exc,
            ) from exc

        except httpx.RequestError as exc:
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
                f"Cerebras request failed: {exc}",
                provider=LLMProviderType.CEREBRAS,
                transport=LLMTransportType.CEREBRAS_API,
                original_error=exc,
            ) from exc

    def _build_payload(self, request: LLMRequest, model: str) -> dict[str, Any]:
        """Build the API request payload.

        Args:
            request: The normalized LLM request.
            model: The model to use.

        Returns:
            The payload dictionary.
        """
        messages = []

        if request.system_prompt:
            messages.append({"role": "system", "content": request.system_prompt})

        messages.append({"role": "user", "content": request.prompt})

        payload: dict[str, Any] = {
            "model": model,
            "messages": messages,
            "temperature": request.temperature,
            "max_tokens": request.max_tokens,
        }

        return payload

    def _build_headers(self) -> dict[str, str]:
        """Build the API request headers.

        Returns:
            Headers dictionary.
        """
        return {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }

    def _parse_retry_after(self, response: httpx.Response) -> int | None:
        """Parse Retry-After header from response.

        Args:
            response: The HTTP response.

        Returns:
            Retry-after seconds if present, None otherwise.
        """
        retry_after = response.headers.get("Retry-After")
        if retry_after:
            try:
                return int(retry_after)
            except ValueError:
                pass
        return None

    def _extract_error_message(self, response: httpx.Response) -> str:
        """Extract error message from response body.

        Args:
            response: The HTTP response.

        Returns:
            Error message string.
        """
        try:
            data = response.json()
            if "error" in data:
                error = data["error"]
                if isinstance(error, dict):
                    return error.get("message", str(error))
                return str(error)
            return response.text[:500] or "Unknown error"
        except (json.JSONDecodeError, KeyError):
            return response.text[:500] or "Unknown error"

    def _parse_response(
        self,
        response: httpx.Response,
        model: str,
        duration_ms: int,
        request: LLMRequest,
    ) -> LLMResponse:
        """Parse a successful API response.

        Args:
            response: The HTTP response.
            model: The model used.
            duration_ms: Request duration in milliseconds.
            request: The original request.

        Returns:
            Normalized LLM response.

        Raises:
            LLMProviderError: If response parsing fails.
        """
        try:
            data = response.json()
        except json.JSONDecodeError as exc:
            raise LLMProviderError(
                "Failed to parse Cerebras response as JSON",
                status_code=response.status_code,
                provider=LLMProviderType.CEREBRAS,
                transport=LLMTransportType.CEREBRAS_API,
                original_error=exc,
            ) from exc

        # Extract content from choices
        choices = data.get("choices", [])
        if not choices:
            raise LLMProviderError(
                "Cerebras response contains no choices",
                status_code=response.status_code,
                provider=LLMProviderType.CEREBRAS,
                transport=LLMTransportType.CEREBRAS_API,
            )

        content = ""
        finish_reason = None
        if choices:
            choice = choices[0]
            message = choice.get("message", {})
            content = message.get("content", "")
            finish_reason = choice.get("finish_reason")

        # Extract usage information
        usage_data = data.get("usage", {})
        usage = {
            "prompt_tokens": usage_data.get("prompt_tokens", 0),
            "completion_tokens": usage_data.get("completion_tokens", 0),
            "total_tokens": usage_data.get("total_tokens", 0),
        }

        # Get actual model from response (may differ from requested)
        actual_model = data.get("model", model)

        self._emit_telemetry(
            "llm_request_completed",
            {
                "operation": request.metadata.get("operation", "unknown"),
                "model": actual_model,
                "latency_ms": duration_ms,
                "prompt_tokens": usage["prompt_tokens"],
                "completion_tokens": usage["completion_tokens"],
                "finish_reason": finish_reason,
            },
        )

        return LLMResponse(
            content=content,
            model=actual_model,
            provider=LLMProviderType.CEREBRAS,
            transport=LLMTransportType.CEREBRAS_API,
            usage=usage,
            latency_ms=duration_ms,
            finish_reason=finish_reason,
            metadata={
                "operation": request.metadata.get("operation", "unknown"),
                "response_id": data.get("id"),
            },
        )


__all__ = ["CerebrasTransport"]
