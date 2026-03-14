"""OpenRouter API transport adapter for LLM routing layer.

This module implements the OpenRouter API transport for the LLM routing
architecture, providing direct API access to various LLM models through
OpenRouter's unified interface.
"""

from __future__ import annotations

import asyncio
import json
import time
from collections.abc import Callable
from datetime import datetime
from typing import TYPE_CHECKING, Any

import httpx

from cc_deep_research.key_rotation import AllKeysExhaustedError, KeyRotationManager
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

if TYPE_CHECKING:
    pass


class OpenRouterTransport(BaseLLMTransport):
    """OpenRouter API transport adapter for LLM operations.

    This transport executes LLM requests through the OpenRouter API,
    supporting multiple model providers through a unified interface.

    Attributes:
        _api_key: OpenRouter API key.
        _base_url: OpenRouter API base URL.
        _timeout_seconds: Request timeout in seconds.
        _model: Default model identifier.
        _extra_headers: Additional headers for requests.
    """

    def __init__(
        self,
        route: LLMRoute,
        *,
        api_key: str | None = None,
        telemetry_callback: Callable[[dict[str, Any]], None] | None = None,
    ) -> None:
        """Initialize the OpenRouter transport.

        Args:
            route: The route configuration for this transport.
            api_key: Optional API key override (uses route.extra if not provided).
            telemetry_callback: Optional callback for LLM-level telemetry.
        """
        super().__init__(route, telemetry_callback=telemetry_callback)

        self._api_keys = self._collect_api_keys(
            api_key,
            route.extra.get("api_key"),
            route.extra.get("api_keys"),
        )
        self._api_key = self._api_keys[0] if self._api_keys else None
        self._base_url = route.extra.get("base_url", "https://openrouter.ai/api/v1")
        self._timeout_seconds = route.timeout_seconds
        self._model = route.model
        self._extra_headers = route.extra.get("extra_headers", {})
        self._key_manager = (
            KeyRotationManager(api_keys=self._api_keys) if self._api_keys else None
        )
        self._key_rotation_lock = asyncio.Lock()

    @property
    def transport_type(self) -> LLMTransportType:
        """Return the transport type for this adapter."""
        return LLMTransportType.OPENROUTER_API

    @property
    def provider_type(self) -> LLMProviderType:
        """Return the provider type for this adapter."""
        return LLMProviderType.OPENROUTER

    def is_available(self) -> bool:
        """Check if OpenRouter transport is available.

        Returns:
            True if an API key is configured.
        """
        if self._key_manager is not None:
            return self._key_manager.available_count > 0
        return self._api_key is not None and len(self._api_key) > 0

    async def execute(self, request: LLMRequest) -> LLMResponse:
        """Execute an LLM request through OpenRouter API.

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
                "OpenRouter API key not configured",
                provider=LLMProviderType.OPENROUTER,
                transport=LLMTransportType.OPENROUTER_API,
            )

        start_time = time.time()
        model = request.model or self._model

        # Build the request payload in OpenAI-compatible format
        payload = self._build_payload(request, model)

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
                while True:
                    current_api_key = await self._get_available_api_key()
                    response = await client.post(
                        f"{self._base_url}/chat/completions",
                        json=payload,
                        headers=self._build_headers(current_api_key),
                    )

                    duration_ms = int((time.time() - start_time) * 1000)

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
                            "OpenRouter authentication failed: invalid API key",
                            provider=LLMProviderType.OPENROUTER,
                            transport=LLMTransportType.OPENROUTER_API,
                        )

                    if response.status_code == 429:
                        retry_after = self._parse_retry_after(response)
                        rotated = await self._rotate_rate_limited_key(
                            current_api_key,
                            retry_after,
                        )
                        if rotated:
                            continue

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
                            "OpenRouter rate limit exceeded",
                            retry_after_seconds=retry_after,
                            provider=LLMProviderType.OPENROUTER,
                            transport=LLMTransportType.OPENROUTER_API,
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
                            f"OpenRouter API error ({response.status_code}): {error_message}",
                            status_code=response.status_code,
                            provider=LLMProviderType.OPENROUTER,
                            transport=LLMTransportType.OPENROUTER_API,
                        )

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
                f"OpenRouter request timed out after {self._timeout_seconds} seconds",
                timeout_seconds=self._timeout_seconds,
                provider=LLMProviderType.OPENROUTER,
                transport=LLMTransportType.OPENROUTER_API,
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
                f"OpenRouter request failed: {exc}",
                provider=LLMProviderType.OPENROUTER,
                transport=LLMTransportType.OPENROUTER_API,
                original_error=exc,
            ) from exc
        except AllKeysExhaustedError as exc:
            duration_ms = int((time.time() - start_time) * 1000)
            retry_after_seconds = None
            if exc.reset_time is not None:
                retry_after_seconds = max(
                    0,
                    int((exc.reset_time - datetime.utcnow()).total_seconds()),
                )
            self._emit_telemetry(
                "llm_request_failed",
                {
                    "operation": request.metadata.get("operation", "unknown"),
                    "error_type": "rate_limit",
                    "status_code": 429,
                    "latency_ms": duration_ms,
                    "retry_after_seconds": retry_after_seconds,
                },
            )
            raise LLMRateLimitError(
                "OpenRouter rate limit exceeded",
                retry_after_seconds=retry_after_seconds,
                provider=LLMProviderType.OPENROUTER,
                transport=LLMTransportType.OPENROUTER_API,
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

    def _build_headers(self, api_key: str) -> dict[str, str]:
        """Build the API request headers.

        Returns:
            Headers dictionary.
        """
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://github.com/cc-deep-research",
            "X-Title": "CC Deep Research",
        }
        headers.update(self._extra_headers)
        return headers

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

    async def _get_available_api_key(self) -> str:
        """Return the current active API key."""
        if self._key_manager is None:
            if self._api_key is None:
                raise LLMAuthenticationError(
                    "OpenRouter API key not configured",
                    provider=LLMProviderType.OPENROUTER,
                    transport=LLMTransportType.OPENROUTER_API,
                )
            return self._api_key

        async with self._key_rotation_lock:
            return self._key_manager.get_available_key()

    async def _rotate_rate_limited_key(
        self,
        api_key: str,
        retry_after_seconds: int | None,
    ) -> bool:
        """Disable a rate-limited key and report whether another key is available."""
        if self._key_manager is None:
            return False

        async with self._key_rotation_lock:
            self._key_manager.mark_rate_limited(
                api_key,
                retry_after_seconds=retry_after_seconds,
            )
            return self._key_manager.available_count > 0


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
                "Failed to parse OpenRouter response as JSON",
                status_code=response.status_code,
                provider=LLMProviderType.OPENROUTER,
                transport=LLMTransportType.OPENROUTER_API,
                original_error=exc,
            ) from exc

        # Extract content from choices
        choices = data.get("choices", [])
        if not choices:
            raise LLMProviderError(
                "OpenRouter response contains no choices",
                status_code=response.status_code,
                provider=LLMProviderType.OPENROUTER,
                transport=LLMTransportType.OPENROUTER_API,
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
            provider=LLMProviderType.OPENROUTER,
            transport=LLMTransportType.OPENROUTER_API,
            usage=usage,
            latency_ms=duration_ms,
            finish_reason=finish_reason,
            metadata={
                "operation": request.metadata.get("operation", "unknown"),
                "response_id": data.get("id"),
            },
        )


__all__ = ["OpenRouterTransport"]
