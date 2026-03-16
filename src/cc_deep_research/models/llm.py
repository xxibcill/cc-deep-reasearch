"""Compatibility aliases for LLM routing models."""

from cc_deep_research.llm.base import (
    LLMProviderType,
    LLMTransportType,
)
from cc_deep_research.llm.base import (
    LLMRoute as LLMRouteModel,
)
from cc_deep_research.llm.base import (
    LLMRoutePlan as LLMPlanModel,
)

__all__ = [
    "LLMPlanModel",
    "LLMProviderType",
    "LLMRouteModel",
    "LLMTransportType",
]
