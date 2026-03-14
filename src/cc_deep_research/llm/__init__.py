"""LLM routing layer for CC Deep Research.

This package provides a unified interface for LLM operations across multiple
transport providers (Claude CLI, OpenRouter, Cerebras) with session-scoped
route management and telemetry.
"""

from cc_deep_research.llm.base import (
    LLMTransportType,
    LLMProviderType,
    LLMRoute,
    LLMRoutePlan,
    LLMRequest,
    LLMResponse,
    LLMError,
    LLMTimeoutError,
    LLMAuthenticationError,
    LLMRateLimitError,
    LLMProviderError,
    BaseLLMTransport,
)
from cc_deep_research.llm.cerebras import CerebrasTransport
from cc_deep_research.llm.claude_cli import ClaudeCLITransport
from cc_deep_research.llm.openrouter import OpenRouterTransport
from cc_deep_research.llm.registry import LLMRouteRegistry
from cc_deep_research.llm.router import LLMRouter

__all__ = [
    "LLMTransportType",
    "LLMProviderType",
    "LLMRoute",
    "LLMRoutePlan",
    "LLMRequest",
    "LLMResponse",
    "LLMError",
    "LLMTimeoutError",
    "LLMAuthenticationError",
    "LLMRateLimitError",
    "LLMProviderError",
    "BaseLLMTransport",
    "LLMRouteRegistry",
    "LLMRouter",
    "ClaudeCLITransport",
    "OpenRouterTransport",
    "CerebrasTransport",
]
