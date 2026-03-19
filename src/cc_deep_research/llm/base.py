"""Base models and contracts for the LLM routing layer.

This module defines the core types for agent-level LLM routing:
- Transport types (CLI vs API)
- Provider types (Claude, OpenRouter, Cerebras)
- Route configuration and plans
- Request/response models
- Exception taxonomy
"""

from abc import ABC, abstractmethod
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field


class LLMTransportType(StrEnum):
    """Transport mechanism for LLM operations."""

    CLAUDE_CLI = "claude_cli"
    OPENROUTER_API = "openrouter_api"
    CEREBRAS_API = "cerebras_api"
    ANTHROPIC_API = "anthropic_api"
    HEURISTIC = "heuristic"


class LLMProviderType(StrEnum):
    """LLM provider identifier."""

    CLAUDE = "claude"
    OPENROUTER = "openrouter"
    CEREBRAS = "cerebras"
    ANTHROPIC = "anthropic"
    HEURISTIC = "heuristic"


class LLMRoute(BaseModel):
    """Configuration for a single LLM route.

    A route specifies how to reach an LLM provider, including transport
    method, model selection, and provider-specific settings.
    """

    transport: LLMTransportType = Field(
        default=LLMTransportType.CLAUDE_CLI,
        description="Transport mechanism for this route",
    )
    provider: LLMProviderType = Field(
        default=LLMProviderType.CLAUDE,
        description="LLM provider for this route",
    )
    model: str = Field(
        default="claude-sonnet-4-6",
        description="Model identifier for the provider",
    )
    enabled: bool = Field(
        default=True,
        description="Whether this route is available for use",
    )
    timeout_seconds: int = Field(
        default=180,
        ge=30,
        le=900,
        description="Request timeout in seconds",
    )
    extra: dict[str, Any] = Field(
        default_factory=dict,
        description="Provider-specific configuration",
    )

    def is_available(self, *, check_nested_session: bool = False) -> bool:
        """Check if this route is available for use.

        Args:
            check_nested_session: If True, check for CLAUDECODE environment
                variable that would indicate a nested Claude CLI session.

        Returns:
            True if the route can be used.
        """
        import os

        if not self.enabled:
            return False

        if check_nested_session and self.transport == LLMTransportType.CLAUDE_CLI:
            if os.environ.get("CLAUDECODE"):
                return False

        return True


class LLMRoutePlan(BaseModel):
    """Per-agent LLM route plan for a research session.

    The route plan defines which LLM route each agent should use,
    with fallback options if the primary route fails.
    """

    agent_routes: dict[str, LLMRoute] = Field(
        default_factory=dict,
        description="Mapping from agent ID to its assigned route",
    )
    fallback_order: list[LLMTransportType] = Field(
        default_factory=lambda: [
            LLMTransportType.CLAUDE_CLI,
            LLMTransportType.OPENROUTER_API,
            LLMTransportType.CEREBRAS_API,
            LLMTransportType.HEURISTIC,
        ],
        description="Ordered list of fallback transports",
    )
    default_route: LLMRoute = Field(
        default_factory=LLMRoute,
        description="Default route for agents without explicit assignment",
    )

    def get_route_for_agent(self, agent_id: str) -> LLMRoute:
        """Get the route for a specific agent.

        Args:
            agent_id: The agent identifier.

        Returns:
            The assigned route or the default route if not explicitly assigned.
        """
        return self.agent_routes.get(agent_id, self.default_route)

    def set_route_for_agent(self, agent_id: str, route: LLMRoute) -> None:
        """Set the route for a specific agent.

        Args:
            agent_id: The agent identifier.
            route: The route to assign.
        """
        self.agent_routes[agent_id] = route


class LLMRequest(BaseModel):
    """Normalized LLM request model.

    This model represents a prompt-based LLM request that can be
    executed through any transport adapter.
    """

    prompt: str = Field(
        ...,
        min_length=1,
        description="The prompt to send to the LLM",
    )
    system_prompt: str | None = Field(
        default=None,
        description="Optional system prompt for context",
    )
    model: str | None = Field(
        default=None,
        description="Model override (uses route default if not specified)",
    )
    temperature: float = Field(
        default=0.3,
        ge=0.0,
        le=1.0,
        description="Sampling temperature",
    )
    max_tokens: int = Field(
        default=4096,
        ge=1,
        le=128000,
        description="Maximum tokens in response",
    )
    metadata: dict[str, Any] = Field(
        default_factory=dict,
        description="Request metadata for telemetry",
    )

    model_config = {"extra": "allow"}


class LLMResponse(BaseModel):
    """Normalized LLM response model.

    This model represents the response from an LLM request, normalized
    across different transport providers.
    """

    content: str = Field(
        default="",
        description="The generated content",
    )
    model: str = Field(
        default="",
        description="The model that generated this response",
    )
    provider: LLMProviderType = Field(
        default=LLMProviderType.CLAUDE,
        description="The provider that handled this request",
    )
    transport: LLMTransportType = Field(
        default=LLMTransportType.CLAUDE_CLI,
        description="The transport used for this request",
    )
    usage: dict[str, int] = Field(
        default_factory=dict,
        description="Token usage statistics (prompt_tokens, completion_tokens, total_tokens)",
    )
    latency_ms: int = Field(
        default=0,
        ge=0,
        description="Request latency in milliseconds",
    )
    finish_reason: str | None = Field(
        default=None,
        description="Reason for completion (stop, length, error, etc.)",
    )
    metadata: dict[str, Any] = Field(
        default_factory=dict,
        description="Response metadata for telemetry",
    )

    model_config = {"extra": "allow"}


# Exception Taxonomy


class LLMError(Exception):
    """Base exception for LLM operations."""

    def __init__(
        self,
        message: str,
        *,
        provider: LLMProviderType | None = None,
        transport: LLMTransportType | None = None,
        original_error: Exception | None = None,
    ) -> None:
        super().__init__(message)
        self.provider = provider
        self.transport = transport
        self.original_error = original_error


class LLMTimeoutError(LLMError):
    """Raised when an LLM request times out."""

    def __init__(
        self,
        message: str = "LLM request timed out",
        *,
        timeout_seconds: int | None = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(message, **kwargs)
        self.timeout_seconds = timeout_seconds


class LLMAuthenticationError(LLMError):
    """Raised when LLM authentication fails."""

    def __init__(
        self,
        message: str = "LLM authentication failed",
        **kwargs: Any,
    ) -> None:
        super().__init__(message, **kwargs)


class LLMRateLimitError(LLMError):
    """Raised when LLM rate limit is exceeded."""

    def __init__(
        self,
        message: str = "LLM rate limit exceeded",
        *,
        retry_after_seconds: int | None = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(message, **kwargs)
        self.retry_after_seconds = retry_after_seconds


class LLMProviderError(LLMError):
    """Raised when the LLM provider returns an error."""

    def __init__(
        self,
        message: str = "LLM provider error",
        *,
        status_code: int | None = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(message, **kwargs)
        self.status_code = status_code


# Transport Contract


class BaseLLMTransport(ABC):
    """Abstract base class for LLM transport adapters.

    Transport adapters implement the low-level communication with
    specific LLM providers (Claude CLI, OpenRouter, Cerebras).
    """

    def __init__(
        self,
        route: LLMRoute,
        *,
        telemetry_callback: Any = None,
    ) -> None:
        """Initialize the transport adapter.

        Args:
            route: The route configuration for this transport.
            telemetry_callback: Optional callback for emitting telemetry events.
        """
        self.route = route
        self.telemetry_callback = telemetry_callback

    @property
    @abstractmethod
    def transport_type(self) -> LLMTransportType:
        """Return the transport type for this adapter."""
        pass

    @property
    @abstractmethod
    def provider_type(self) -> LLMProviderType:
        """Return the provider type for this adapter."""
        pass

    @abstractmethod
    async def execute(self, request: LLMRequest) -> LLMResponse:
        """Execute an LLM request.

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
        pass

    @abstractmethod
    def is_available(self) -> bool:
        """Check if this transport is available for use.

        Returns:
            True if the transport can be used.
        """
        pass

    def _emit_telemetry(self, event_type: str, data: dict[str, Any]) -> None:
        """Emit a telemetry event if a callback is configured.

        Args:
            event_type: The type of telemetry event.
            data: The event data.
        """
        if self.telemetry_callback:
            try:
                self.telemetry_callback(
                    {
                        "event_type": event_type,
                        "transport": self.transport_type.value,
                        "provider": self.provider_type.value,
                        **data,
                    }
                )
            except Exception:
                pass  # Don't fail requests due to telemetry errors
