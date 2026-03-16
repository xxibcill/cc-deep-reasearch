"""Configuration loading and persistence helpers."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import yaml

from .defaults import get_default_config_path
from .schema import Config, Settings, _normalize_api_key_list


def _parse_api_keys_from_env() -> list[str]:
    """Parse TAVILY_API_KEYS from the environment."""
    env_value = os.environ.get("TAVILY_API_KEYS", "")
    if not env_value:
        return []
    return _normalize_api_key_list(env_value.split(","))


def _parse_provider_api_keys_from_env(
    list_env_var: str,
    single_env_var: str,
) -> list[str]:
    """Parse provider API keys from multi-key or single-key env vars."""
    list_value = os.environ.get(list_env_var, "")
    single_value = os.environ.get(single_env_var, "")

    parsed_list = list_value.split(",") if list_value else []
    return _normalize_api_key_list(parsed_list, single_value)


def load_config(config_path: Path | None = None) -> Config:
    """Load configuration from file and environment variables."""
    settings = Settings()
    resolved_path = config_path or settings.config_path or get_default_config_path()

    config_data: dict[str, Any] = {}
    if resolved_path.exists():
        with resolved_path.open() as handle:
            config_data = yaml.safe_load(handle) or {}

    config = Config(**config_data)

    api_keys = _parse_api_keys_from_env()
    if api_keys:
        config.tavily.api_keys = api_keys

    openrouter_api_keys = _parse_provider_api_keys_from_env(
        "OPENROUTER_API_KEYS",
        "OPENROUTER_API_KEY",
    )
    if openrouter_api_keys:
        config.llm.openrouter.api_keys = openrouter_api_keys
        config.llm.openrouter.api_key = openrouter_api_keys[0]

    cerebras_api_keys = _parse_provider_api_keys_from_env(
        "CEREBRAS_API_KEYS",
        "CEREBRAS_API_KEY",
    )
    if cerebras_api_keys:
        config.llm.cerebras.api_keys = cerebras_api_keys
        config.llm.cerebras.api_key = cerebras_api_keys[0]

    if settings.depth:
        config.search.depth = settings.depth
        config.research.default_depth = settings.depth

    if settings.output_format:
        config.output.format = settings.output_format

    if settings.no_color:
        config.display.color = "never"

    return config


def save_config(config: Config, config_path: Path | None = None) -> None:
    """Save configuration to file."""
    resolved_path = config_path or get_default_config_path()
    resolved_path.parent.mkdir(parents=True, exist_ok=True)

    with resolved_path.open("w") as handle:
        yaml.dump(
            config.model_dump(mode="json"),
            handle,
            default_flow_style=False,
            sort_keys=False,
        )


__all__ = [
    "_parse_api_keys_from_env",
    "_parse_provider_api_keys_from_env",
    "load_config",
    "save_config",
]
