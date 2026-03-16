"""Compatibility aliases for LLM routing models."""

from cc_deep_research.llm.base import (
    LLMProviderType,
    LLMRoute as LLMRouteModel,
    LLMRoutePlan as LLMPlanModel,
    LLMTransportType,
)

__all__ = [
    "LLMPlanModel",
    "LLMProviderType",
    "LLMRouteModel",
    "LLMTransportType",
]
