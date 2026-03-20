"""LLM routing layer for CC Deep Research.

This package provides a unified interface for LLM operations across multiple
transport providers (OpenRouter, Cerebras, Anthropic) with session-scoped
route management and telemetry.
"""

from cc_deep_research.llm.anthropic import AnthropicAPITransport
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
    "OpenRouterTransport",
    "CerebrasTransport",
    "AnthropicAPITransport",
]
