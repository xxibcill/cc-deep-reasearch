"""Configuration path resolution without persistence dependencies."""

from __future__ import annotations

import os
from pathlib import Path


def get_default_config_path() -> Path:
    """Get the default configuration file path."""
    xdg_config = os.environ.get("XDG_CONFIG_HOME")
    if xdg_config:
        return Path(xdg_config) / "inqulume-studio" / "config.yaml"
    return Path.home() / ".config" / "inqulume-studio" / "config.yaml"


__all__ = ["get_default_config_path"]
