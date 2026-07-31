"""Codex app-server transport adapter for the shared LLM routing layer."""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from contextlib import suppress
from typing import Any

from openai_codex import (
    JsonRpcError,
    RetryLimitExceededError,
    ServerBusyError,
    TransportClosedError,
)

from cc_deep_research.llm.base import (
    BaseLLMTransport,
    LLMAuthenticationError,
    LLMProviderError,
    LLMProviderType,
    LLMRateLimitError,
    LLMRequest,
    LLMResponse,
    LLMRoute,
    LLMTimeoutError,
    LLMTransportType,
)
from cc_deep_research.llm.codex_runtime import (
    CodexNotAuthenticatedError,
    CodexRuntime,
    CodexRuntimeError,
    CodexRuntimeUnavailableError,
    get_shared_codex_runtime,
)
from cc_deep_research.llm.usage_tracker import TokenUsageEntry, append_usage_entry

_DEFAULT_MODEL_LABELS = {"", "default", "codex-default"}


class CodexTransport(BaseLLMTransport):
    """Execute normalized LLM requests through a managed Codex app-server."""

    def __init__(
        self,
        route: LLMRoute,
        *,
        runtime: CodexRuntime | None = None,
        telemetry_callback: Callable[[dict[str, Any]], None] | None = None,
    ) -> None:
        super().__init__(route, telemetry_callback=telemetry_callback)
        self._runtime = runtime or get_shared_codex_runtime()
        configured_model = route.extra.get("model", route.model)
        self._model = self._normalize_model(configured_model)
        self._reasoning_effort = route.extra.get("reasoning_effort")
        self._timeout_seconds = route.timeout_seconds

    @property
    def transport_type(self) -> LLMTransportType:
        return LLMTransportType.CODEX_APP_SERVER

    @property
    def provider_type(self) -> LLMProviderType:
        return LLMProviderType.CODEX

    def is_available(self) -> bool:
        """Return whether an authenticated or not-yet-preflighted route can run."""
        if not self.route.enabled:
            return False
        if self._runtime.is_authenticated:
            return True
        return self._runtime.can_attempt_start

    async def execute(self, request: LLMRequest) -> LLMResponse:
        """Execute one isolated, ephemeral Codex turn."""
        model = self._normalize_model(request.model) or self._model
        operation = str(request.metadata.get("operation", "unknown"))
        self._emit_telemetry(
            "llm_request_started",
            {
                "operation": operation,
                "model": model or "codex-default",
                "timeout_seconds": self._timeout_seconds,
            },
        )

        try:
            result = await self._runtime.run_turn(
                prompt=request.prompt,
                model=model,
                developer_instructions=request.system_prompt,
                reasoning_effort=str(self._reasoning_effort)
                if self._reasoning_effort
                else None,
                timeout_seconds=self._timeout_seconds,
            )
        except asyncio.CancelledError:
            raise
        except TimeoutError as exc:
            self._emit_failure(request, "timeout")
            raise LLMTimeoutError(
                f"Codex request timed out after {self._timeout_seconds} seconds",
                timeout_seconds=self._timeout_seconds,
                provider=LLMProviderType.CODEX,
                transport=LLMTransportType.CODEX_APP_SERVER,
                original_error=exc,
            ) from exc
        except CodexNotAuthenticatedError as exc:
            self._emit_failure(request, "authentication")
            raise LLMAuthenticationError(
                "Codex is not authenticated. Connect a ChatGPT account first.",
                provider=LLMProviderType.CODEX,
                transport=LLMTransportType.CODEX_APP_SERVER,
                original_error=exc,
            ) from exc
        except (ServerBusyError, RetryLimitExceededError) as exc:
            self._emit_failure(request, "rate_limit")
            raise LLMRateLimitError(
                "Codex is temporarily unavailable.",
                provider=LLMProviderType.CODEX,
                transport=LLMTransportType.CODEX_APP_SERVER,
                original_error=exc,
            ) from exc
        except JsonRpcError as exc:
            if self._looks_rate_limited(exc):
                self._emit_failure(request, "rate_limit")
                raise LLMRateLimitError(
                    "Codex rate limit exceeded.",
                    provider=LLMProviderType.CODEX,
                    transport=LLMTransportType.CODEX_APP_SERVER,
                    original_error=exc,
                ) from exc
            self._emit_failure(request, "provider_error")
            raise LLMProviderError(
                "Codex app-server request failed.",
                status_code=exc.code,
                provider=LLMProviderType.CODEX,
                transport=LLMTransportType.CODEX_APP_SERVER,
                original_error=exc,
            ) from exc
        except (CodexRuntimeUnavailableError, TransportClosedError) as exc:
            self._emit_failure(request, "runtime_unavailable")
            raise LLMProviderError(
                "Codex runtime is unavailable.",
                provider=LLMProviderType.CODEX,
                transport=LLMTransportType.CODEX_APP_SERVER,
                original_error=exc,
            ) from exc
        except CodexRuntimeError as exc:
            self._emit_failure(request, "provider_error")
            raise LLMProviderError(
                "Codex request failed.",
                provider=LLMProviderType.CODEX,
                transport=LLMTransportType.CODEX_APP_SERVER,
                original_error=exc,
            ) from exc
        except Exception as exc:
            error_type = "rate_limit" if self._looks_rate_limited(exc) else "provider_error"
            self._emit_failure(request, error_type)
            if error_type == "rate_limit":
                raise LLMRateLimitError(
                    "Codex rate limit exceeded.",
                    provider=LLMProviderType.CODEX,
                    transport=LLMTransportType.CODEX_APP_SERVER,
                    original_error=exc,
                ) from exc
            raise LLMProviderError(
                "Codex request failed.",
                provider=LLMProviderType.CODEX,
                transport=LLMTransportType.CODEX_APP_SERVER,
                original_error=exc,
            ) from exc

        usage = {
            "prompt_tokens": result.input_tokens,
            "completion_tokens": result.output_tokens,
            "total_tokens": result.total_tokens,
        }
        with suppress(Exception):
            append_usage_entry(
                TokenUsageEntry(
                    model=result.model,
                    base_url="codex-app-server://stdio",
                    request_id=result.turn_id,
                    input_tokens=result.input_tokens,
                    output_tokens=result.output_tokens,
                    total_tokens=result.total_tokens,
                    cache_read_input_tokens=result.cached_input_tokens,
                    max_tokens=request.max_tokens,
                    latency_ms=result.duration_ms,
                    provider=LLMProviderType.CODEX.value,
                    transport=LLMTransportType.CODEX_APP_SERVER.value,
                    operation=operation,
                    session_id=request.metadata.get("session_id"),
                    agent_id=request.metadata.get("agent_id"),
                )
            )

        self._emit_telemetry(
            "llm_request_completed",
            {
                "operation": operation,
                "model": result.model,
                "latency_ms": result.duration_ms,
                "prompt_tokens": result.input_tokens,
                "completion_tokens": result.output_tokens,
                "finish_reason": result.finish_reason,
            },
        )
        return LLMResponse(
            content=result.content,
            model=result.model,
            provider=LLMProviderType.CODEX,
            transport=LLMTransportType.CODEX_APP_SERVER,
            usage=usage,
            latency_ms=result.duration_ms,
            finish_reason="stop" if result.finish_reason == "completed" else result.finish_reason,
            metadata={
                "operation": operation,
                "turn_id": result.turn_id,
                "cached_input_tokens": result.cached_input_tokens,
                "reasoning_output_tokens": result.reasoning_output_tokens,
                "codex_turn_status": result.finish_reason,
                "unsupported_parameters": ["temperature", "max_tokens"],
            },
        )

    def _emit_failure(self, request: LLMRequest, error_type: str) -> None:
        self._emit_telemetry(
            "llm_request_failed",
            {
                "operation": request.metadata.get("operation", "unknown"),
                "error_type": error_type,
            },
        )

    @staticmethod
    def _normalize_model(value: Any) -> str | None:
        if not isinstance(value, str):
            return None
        normalized = value.strip()
        if normalized.lower() in _DEFAULT_MODEL_LABELS:
            return None
        return normalized

    @staticmethod
    def _looks_rate_limited(exc: BaseException) -> bool:
        message = str(exc).lower()
        return any(
            marker in message
            for marker in (
                "rate limit",
                "rate_limit",
                "usage limit",
                "usage_limit",
                "too many requests",
                "server overloaded",
            )
        )


__all__ = ["CodexTransport"]
