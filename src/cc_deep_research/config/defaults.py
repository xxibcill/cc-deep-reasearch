"""Configuration defaults and path helpers."""

from __future__ import annotations

import os
from pathlib import Path

from .schema import Config


def get_default_config_path() -> Path:
    """Get the default configuration file path."""
    xdg_config = os.environ.get("XDG_CONFIG_HOME")
    if xdg_config:
        return Path(xdg_config) / "cc-deep-research" / "config.yaml"
    return Path.home() / ".config" / "cc-deep-research" / "config.yaml"


def get_default_config() -> Config:
    """Get the default configuration."""
    return Config()


def create_default_config_file(config_path: Path | None = None) -> Path:
    """Create a default configuration file."""
    from .io import save_config

    resolved_path = config_path or get_default_config_path()
    save_config(get_default_config(), resolved_path)
    return resolved_path


__all__ = [
    "create_default_config_file",
    "get_default_config",
    "get_default_config_path",
]
