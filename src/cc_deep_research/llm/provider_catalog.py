"""Central provider route definitions for registry and planner consumers."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from types import MappingProxyType
from typing import Any, Final

from cc_deep_research.config import LLMConfig
from cc_deep_research.llm.base import (
    LLMProviderType,
    LLMRoute,
    LLMTransportType,
)

ExtraBuilder = Callable[[Any, list[str]], dict[str, Any]]


@dataclass(frozen=True, slots=True)
class ProviderRouteDefinition:
    """Describe how one configured provider becomes a runtime route."""

    provider_type: LLMProviderType
    config_attribute: str
    extra_builder: ExtraBuilder
    requires_api_keys: bool = True
    default_model: str | None = None


def _openrouter_extra(config: Any, api_keys: list[str]) -> dict[str, Any]:
    return {
        "api_key": api_keys[0] if api_keys else None,
        "api_keys": api_keys,
        "base_url": config.base_url,
        "extra_headers": config.extra_headers,
    }


def _standard_api_extra(config: Any, api_keys: list[str]) -> dict[str, Any]:
    return {
        "api_key": api_keys[0] if api_keys else None,
        "api_keys": api_keys,
        "base_url": config.base_url,
    }


def _anthropic_extra(config: Any, api_keys: list[str]) -> dict[str, Any]:
    return {
        **_standard_api_extra(config, api_keys),
        "max_tokens": config.max_tokens,
    }


def _kimi_extra(config: Any, api_keys: list[str]) -> dict[str, Any]:
    return {
        **_standard_api_extra(config, api_keys),
        "reasoning_effort": config.reasoning_effort,
    }


def _codex_extra(config: Any, _api_keys: list[str]) -> dict[str, Any]:
    return {
        "model": config.model,
        "reasoning_effort": config.reasoning_effort,
    }


PROVIDER_ROUTE_DEFINITIONS: Final[Mapping[LLMTransportType, ProviderRouteDefinition]] = (
    MappingProxyType(
        {
            LLMTransportType.OPENROUTER_API: ProviderRouteDefinition(
                provider_type=LLMProviderType.OPENROUTER,
                config_attribute="openrouter",
                extra_builder=_openrouter_extra,
            ),
            LLMTransportType.CEREBRAS_API: ProviderRouteDefinition(
                provider_type=LLMProviderType.CEREBRAS,
                config_attribute="cerebras",
                extra_builder=_standard_api_extra,
            ),
            LLMTransportType.ANTHROPIC_API: ProviderRouteDefinition(
                provider_type=LLMProviderType.ANTHROPIC,
                config_attribute="anthropic",
                extra_builder=_anthropic_extra,
            ),
            LLMTransportType.KIMI_API: ProviderRouteDefinition(
                provider_type=LLMProviderType.KIMI,
                config_attribute="kimi",
                extra_builder=_kimi_extra,
            ),
            LLMTransportType.CODEX_APP_SERVER: ProviderRouteDefinition(
                provider_type=LLMProviderType.CODEX,
                config_attribute="codex",
                extra_builder=_codex_extra,
                requires_api_keys=False,
                default_model="codex-default",
            ),
        }
    )
)


def build_route_for_transport(config: LLMConfig, transport: LLMTransportType) -> LLMRoute:
    """Build a configured runtime route from the provider catalog."""
    if transport == LLMTransportType.HEURISTIC:
        return LLMRoute(
            transport=transport,
            provider=LLMProviderType.HEURISTIC,
            model="heuristic",
            enabled=True,
        )

    definition = PROVIDER_ROUTE_DEFINITIONS[transport]
    provider_config = getattr(config, definition.config_attribute)
    api_keys = provider_config.get_api_keys() if definition.requires_api_keys else []
    model = provider_config.model or definition.default_model or ""
    enabled = provider_config.enabled and (
        bool(api_keys) if definition.requires_api_keys else True
    )
    return LLMRoute(
        transport=transport,
        provider=definition.provider_type,
        model=model,
        enabled=enabled,
        timeout_seconds=provider_config.timeout_seconds,
        extra=definition.extra_builder(provider_config, api_keys),
    )


__all__ = [
    "PROVIDER_ROUTE_DEFINITIONS",
    "ProviderRouteDefinition",
    "build_route_for_transport",
]
