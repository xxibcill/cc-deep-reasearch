"""Shared provider construction helpers."""

from __future__ import annotations

from pathlib import Path

from cc_deep_research.config import Config
from cc_deep_research.config.io import resolve_config_path
from cc_deep_research.key_rotation import KeyRotationManager
from cc_deep_research.models import SearchOptions
from cc_deep_research.providers import ProviderSpec, SearchProvider
from cc_deep_research.providers.cached import CachedSearchProvider
from cc_deep_research.providers.tavily import TavilySearchProvider
from cc_deep_research.search_cache import InFlightSearchRegistry, SearchCacheStore

_CACHE_STORES: dict[Path, SearchCacheStore] = {}
_IN_FLIGHT_REGISTRIES: dict[Path, InFlightSearchRegistry] = {}


def build_search_provider(
    config: Config,
    provider_spec: ProviderSpec,
    *,
    max_results_override: int | None = None,
    config_path: Path | None = None,
) -> SearchProvider | None:
    """Build one configured provider and wrap it with cache support when enabled."""
    if provider_spec.provider_type == "tavily":
        return _build_tavily_provider(
            config,
            provider_spec,
            max_results_override=max_results_override,
            config_path=config_path,
        )

    return None


def build_search_providers(
    config: Config,
    provider_specs: list[ProviderSpec],
    *,
    config_path: Path | None = None,
) -> tuple[list[SearchProvider], list[str]]:
    """Build all configured providers and collect any resolution warnings."""
    providers: list[SearchProvider] = []
    warnings: list[str] = []

    for provider_spec in provider_specs:
        provider = build_search_provider(
            config,
            provider_spec,
            config_path=config_path,
        )
        if provider is not None:
            providers.append(provider)
            continue

        warnings.append(_build_provider_warning(provider_spec))

    return providers, warnings


def _build_tavily_provider(
    config: Config,
    provider_spec: ProviderSpec,
    *,
    max_results_override: int | None,
    config_path: Path | None,
) -> SearchProvider | None:
    """Build one Tavily provider if credentials are available."""
    if not config.tavily.api_keys:
        return None

    key_manager = KeyRotationManager(config.tavily.api_keys)
    max_results = max_results_override or config.tavily.max_results
    provider: SearchProvider = TavilySearchProvider(
        max_results=max_results,
        provider_name=provider_spec.provider_name,
        strategy=provider_spec.strategy or "auto",
        key_manager=key_manager,
    )

    cache_components = _resolve_cache_components(config, config_path=config_path)
    if cache_components is None:
        return provider

    store, in_flight_registry = cache_components
    default_options = SearchOptions(
        max_results=max_results,
        search_depth=config.search.depth,
        include_raw_content=True,
    )
    return CachedSearchProvider(
        provider,
        store=store,
        ttl_seconds=config.search_cache.ttl_seconds,
        in_flight_registry=in_flight_registry,
        default_options=default_options,
    )


def _resolve_cache_components(
    config: Config,
    *,
    config_path: Path | None,
) -> tuple[SearchCacheStore, InFlightSearchRegistry] | None:
    """Return shared cache primitives when cache is enabled."""
    if not config.search_cache.enabled:
        return None

    resolved_config_path = resolve_config_path(config_path)
    db_path = config.search_cache.resolve_db_path(resolved_config_path)
    store = _CACHE_STORES.get(db_path)
    if store is None:
        store = SearchCacheStore(db_path, max_entries=config.search_cache.max_entries)
        _CACHE_STORES[db_path] = store

    in_flight_registry = _IN_FLIGHT_REGISTRIES.get(db_path)
    if in_flight_registry is None:
        in_flight_registry = InFlightSearchRegistry()
        _IN_FLIGHT_REGISTRIES[db_path] = in_flight_registry

    return store, in_flight_registry


def _build_provider_warning(provider_spec: ProviderSpec) -> str:
    """Return the appropriate warning for an unavailable provider spec."""
    if provider_spec.provider_type == "tavily":
        return (
            f"Provider '{provider_spec.provider_name}' is selected but no Tavily API keys are configured."
        )
    if provider_spec.provider_type == "claude":
        return "Provider 'claude' is selected but no Claude search provider is implemented yet."
    return f"Provider '{provider_spec.configured_name}' is not supported."


__all__ = ["build_search_provider", "build_search_providers"]
