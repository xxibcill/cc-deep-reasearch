"""Shared transport mechanics for OpenAI-compatible chat completion APIs."""

from __future__ import annotations

import asyncio
import json
import time
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from typing import Any, cast

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


@dataclass(frozen=True, slots=True)
class OpenAICompatibleProviderSpec:
    """Stable provider identity used by an OpenAI-compatible transport."""

    display_name: str
    provider_type: LLMProviderType
    transport_type: LLMTransportType
    default_base_url: str


class OpenAICompatibleTransport(BaseLLMTransport):
    """Reusable non-streaming transport for OpenAI-compatible chat APIs."""

    provider_spec: OpenAICompatibleProviderSpec

    def __init__(
        self,
        route: LLMRoute,
        *,
        api_key: str | None = None,
        telemetry_callback: Callable[[dict[str, Any]], None] | None = None,
    ) -> None:
        super().__init__(route, telemetry_callback=telemetry_callback)
        self._api_keys = self._collect_api_keys(
            api_key,
            route.extra.get("api_key"),
            route.extra.get("api_keys"),
        )
        self._base_url = self._resolve_base_url(route.extra.get("base_url"))
        self._timeout_seconds = route.timeout_seconds
        self._model = route.model
        self._key_manager = KeyRotationManager(api_keys=self._api_keys) if self._api_keys else None
        self._key_rotation_lock = asyncio.Lock()

    @property
    def transport_type(self) -> LLMTransportType:
        """Return the configured transport identity."""
        return self.provider_spec.transport_type

    @property
    def provider_type(self) -> LLMProviderType:
        """Return the configured provider identity."""
        return self.provider_spec.provider_type

    def is_available(self) -> bool:
        """Return whether at least one API key is currently usable."""
        if self._key_manager is not None:
            return self._key_manager.available_count > 0
        return bool(self._api_keys)

    async def execute(self, request: LLMRequest) -> LLMResponse:
        """Execute one non-streaming chat completion request."""
        if not self._api_keys:
            raise self._authentication_error("API key not configured")

        started_at = time.monotonic()
        model = request.model or self._model
        payload = self._build_payload(request, model)
        self._emit_telemetry(
            "llm_request_started",
            {
                "operation": self._operation_name(request),
                "model": model,
                "timeout_seconds": self._timeout_seconds,
            },
        )

        try:
            async with httpx.AsyncClient(timeout=self._timeout_seconds) as client:
                return await self._execute_with_client(
                    client=client,
                    payload=payload,
                    request=request,
                    model=model,
                    started_at=started_at,
                )
        except httpx.TimeoutException as exc:
            latency_ms = self._latency_ms(started_at)
            self._emit_telemetry(
                "llm_request_timeout",
                {
                    "operation": self._operation_name(request),
                    "timeout_seconds": self._timeout_seconds,
                    "latency_ms": latency_ms,
                },
            )
            raise LLMTimeoutError(
                f"{self.provider_spec.display_name} request timed out after "
                f"{self._timeout_seconds} seconds",
                timeout_seconds=self._timeout_seconds,
                provider=self.provider_type,
                transport=self.transport_type,
                original_error=exc,
            ) from exc
        except httpx.RequestError as exc:
            self._emit_telemetry(
                "llm_request_error",
                {
                    "operation": self._operation_name(request),
                    "error_type": type(exc).__name__,
                    "latency_ms": self._latency_ms(started_at),
                },
            )
            raise LLMError(
                f"{self.provider_spec.display_name} request failed: {exc}",
                provider=self.provider_type,
                transport=self.transport_type,
                original_error=exc,
            ) from exc
        except AllKeysExhaustedError as exc:
            retry_after_seconds = self._retry_after_from_exhaustion(exc)
            self._emit_rate_limit_failure(
                request=request,
                latency_ms=self._latency_ms(started_at),
                retry_after_seconds=retry_after_seconds,
            )
            raise self._rate_limit_error(retry_after_seconds) from exc

    async def _execute_with_client(
        self,
        *,
        client: httpx.AsyncClient,
        payload: dict[str, Any],
        request: LLMRequest,
        model: str,
        started_at: float,
    ) -> LLMResponse:
        """Send the request, rotating away from rate-limited keys when possible."""
        while True:
            api_key = await self._get_available_api_key()
            response = await client.post(
                f"{self._base_url}/chat/completions",
                json=payload,
                headers=self._build_headers(api_key),
            )
            latency_ms = self._latency_ms(started_at)

            if response.status_code in {401, 403}:
                self._emit_failure(request, latency_ms, "authentication", response.status_code)
                raise self._authentication_error("authentication failed: invalid API key")

            if response.status_code == 429:
                retry_after_seconds = self._parse_retry_after(response)
                if await self._rotate_rate_limited_key(api_key, retry_after_seconds):
                    continue
                self._emit_rate_limit_failure(request, latency_ms, retry_after_seconds)
                raise self._rate_limit_error(retry_after_seconds)

            if response.status_code >= 400:
                error_message = self._extract_error_message(response)
                self._emit_failure(
                    request,
                    latency_ms,
                    "provider_error",
                    response.status_code,
                    error_message=error_message,
                )
                raise LLMProviderError(
                    f"{self.provider_spec.display_name} API error "
                    f"({response.status_code}): {error_message}",
                    status_code=response.status_code,
                    provider=self.provider_type,
                    transport=self.transport_type,
                )

            return self._parse_response(response, model, latency_ms, request)

    def _build_payload(self, request: LLMRequest, model: str) -> dict[str, Any]:
        """Build the standard OpenAI-compatible request payload."""
        messages = self._build_messages(request)
        return {
            "model": model,
            "messages": messages,
            "temperature": request.temperature,
            "max_tokens": request.max_tokens,
        }

    @staticmethod
    def _build_messages(request: LLMRequest) -> list[dict[str, str]]:
        """Build system and user messages from a normalized request."""
        messages: list[dict[str, str]] = []
        if request.system_prompt:
            messages.append({"role": "system", "content": request.system_prompt})
        messages.append({"role": "user", "content": request.prompt})
        return messages

    @staticmethod
    def _build_headers(api_key: str) -> dict[str, str]:
        """Build bearer-authenticated JSON request headers."""
        return {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }

    def _parse_response(
        self,
        response: httpx.Response,
        model: str,
        latency_ms: int,
        request: LLMRequest,
    ) -> LLMResponse:
        """Normalize one successful OpenAI-compatible response."""
        try:
            data = response.json()
        except json.JSONDecodeError as exc:
            raise LLMProviderError(
                f"Failed to parse {self.provider_spec.display_name} response as JSON",
                status_code=response.status_code,
                provider=self.provider_type,
                transport=self.transport_type,
                original_error=exc,
            ) from exc

        choices = data.get("choices", [])
        if not isinstance(choices, list) or not choices:
            raise LLMProviderError(
                f"{self.provider_spec.display_name} response contains no choices",
                status_code=response.status_code,
                provider=self.provider_type,
                transport=self.transport_type,
            )

        choice = choices[0] if isinstance(choices[0], dict) else {}
        message = choice.get("message", {})
        content = message.get("content", "") if isinstance(message, dict) else ""
        if not isinstance(content, str):
            content = str(content)

        usage_data = data.get("usage", {})
        usage = self._parse_usage(usage_data if isinstance(usage_data, dict) else {})
        actual_model = data.get("model", model)
        if not isinstance(actual_model, str):
            actual_model = model
        finish_reason = choice.get("finish_reason")
        if finish_reason is not None and not isinstance(finish_reason, str):
            finish_reason = str(finish_reason)

        self._emit_telemetry(
            "llm_request_completed",
            {
                "operation": self._operation_name(request),
                "model": actual_model,
                "latency_ms": latency_ms,
                "prompt_tokens": usage["prompt_tokens"],
                "completion_tokens": usage["completion_tokens"],
                "finish_reason": finish_reason,
            },
        )
        return LLMResponse(
            content=content,
            model=actual_model,
            provider=self.provider_type,
            transport=self.transport_type,
            usage=usage,
            latency_ms=latency_ms,
            finish_reason=finish_reason,
            metadata={
                "operation": self._operation_name(request),
                "response_id": data.get("id"),
            },
        )

    @staticmethod
    def _parse_usage(usage_data: dict[str, Any]) -> dict[str, int]:
        """Normalize token counters while ignoring malformed provider values."""
        keys = ("prompt_tokens", "completion_tokens", "total_tokens", "cached_tokens")
        return {
            key: value if isinstance(value := usage_data.get(key, 0), int) else 0 for key in keys
        }

    async def _get_available_api_key(self) -> str:
        """Return the next usable API key."""
        if self._key_manager is None:
            if not self._api_keys:
                raise self._authentication_error("API key not configured")
            return self._api_keys[0]
        async with self._key_rotation_lock:
            return self._key_manager.get_available_key()

    async def _rotate_rate_limited_key(
        self,
        api_key: str,
        retry_after_seconds: int | None,
    ) -> bool:
        """Disable one rate-limited key and report whether another is usable."""
        if self._key_manager is None:
            return False
        async with self._key_rotation_lock:
            self._key_manager.mark_rate_limited(
                api_key,
                retry_after_seconds=retry_after_seconds,
            )
            return self._key_manager.available_count > 0

    def _resolve_base_url(self, configured_base_url: Any) -> str:
        """Return a normalized base URL without a trailing slash."""
        if isinstance(configured_base_url, str) and configured_base_url.strip():
            return configured_base_url.strip().rstrip("/")
        return self.provider_spec.default_base_url.rstrip("/")

    @staticmethod
    def _collect_api_keys(*values: Any) -> list[str]:
        """Collect unique non-empty keys in first-seen order."""
        api_keys: list[str] = []
        seen: set[str] = set()
        for value in values:
            candidates = value if isinstance(value, list) else [value]
            for candidate in candidates:
                if not isinstance(candidate, str):
                    continue
                key = candidate.strip()
                if key and key not in seen:
                    seen.add(key)
                    api_keys.append(key)
        return api_keys

    @staticmethod
    def _parse_retry_after(response: httpx.Response) -> int | None:
        """Parse a numeric Retry-After header when present."""
        retry_after = response.headers.get("Retry-After")
        if retry_after:
            try:
                return max(0, int(float(retry_after)))
            except ValueError:
                return None
        return None

    @staticmethod
    def _extract_error_message(response: httpx.Response) -> str:
        """Extract a bounded provider error message."""
        try:
            data = response.json()
            error = data.get("error") if isinstance(data, dict) else None
            if isinstance(error, dict):
                return cast(str, error.get("message", str(error)))
            if error is not None:
                return str(error)
        except json.JSONDecodeError:
            pass
        return response.text[:500] or "Unknown error"

    def _authentication_error(self, detail: str) -> LLMAuthenticationError:
        """Build a provider-aware authentication error."""
        return LLMAuthenticationError(
            f"{self.provider_spec.display_name} {detail}",
            provider=self.provider_type,
            transport=self.transport_type,
        )

    def _rate_limit_error(self, retry_after_seconds: int | None) -> LLMRateLimitError:
        """Build a provider-aware rate-limit error."""
        return LLMRateLimitError(
            f"{self.provider_spec.display_name} rate limit exceeded",
            retry_after_seconds=retry_after_seconds,
            provider=self.provider_type,
            transport=self.transport_type,
        )

    def _emit_failure(
        self,
        request: LLMRequest,
        latency_ms: int,
        error_type: str,
        status_code: int,
        *,
        error_message: str | None = None,
    ) -> None:
        """Emit normalized provider failure telemetry."""
        payload: dict[str, Any] = {
            "operation": self._operation_name(request),
            "error_type": error_type,
            "status_code": status_code,
            "latency_ms": latency_ms,
        }
        if error_message:
            payload["error_message"] = error_message[:200]
        self._emit_telemetry("llm_request_failed", payload)

    def _emit_rate_limit_failure(
        self,
        request: LLMRequest,
        latency_ms: int,
        retry_after_seconds: int | None,
    ) -> None:
        """Emit normalized rate-limit telemetry."""
        self._emit_telemetry(
            "llm_request_failed",
            {
                "operation": self._operation_name(request),
                "error_type": "rate_limit",
                "status_code": 429,
                "latency_ms": latency_ms,
                "retry_after_seconds": retry_after_seconds,
            },
        )

    @staticmethod
    def _operation_name(request: LLMRequest) -> str:
        """Return the telemetry operation name for a request."""
        return str(request.metadata.get("operation", "unknown"))

    @staticmethod
    def _latency_ms(started_at: float) -> int:
        """Return elapsed monotonic time in whole milliseconds."""
        return max(0, int((time.monotonic() - started_at) * 1000))

    @staticmethod
    def _retry_after_from_exhaustion(exc: AllKeysExhaustedError) -> int | None:
        """Convert key-manager reset time into a retry delay."""
        if exc.reset_time is None:
            return None
        return max(0, int((exc.reset_time - datetime.utcnow()).total_seconds()))


__all__ = ["OpenAICompatibleProviderSpec", "OpenAICompatibleTransport"]
