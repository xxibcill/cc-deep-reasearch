"""Environment loading utilities for LLM configuration.

This module provides utilities for loading environment variables from
project root .env files and extracting Anthropic-specific configuration.
"""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv


def load_env_from_project_root() -> None:
    """Load .env from project root (does not override existing env vars).

    This function looks for a .env file in the project root and loads it.
    It uses dotenv's default behavior which does not override existing
    environment variables.
    """
    # Find project root by looking for pyproject.toml
    current_path = Path.cwd()
    for parent in [current_path] + list(current_path.parents):
        if (parent / "pyproject.toml").exists():
            env_path = parent / ".env"
            if env_path.exists():
                load_dotenv(env_path, override=False)
            return

    # Also try current directory
    env_path = Path.cwd() / ".env"
    if env_path.exists():
        load_dotenv(env_path, override=False)


def get_anthropic_api_key() -> str | None:
    """Get Anthropic API key from environment.

    Priority:
    1. ANTHROPIC_AUTH_TOKEN
    2. ANTHROPIC_API_KEY

    Returns:
        API key if found, None otherwise.
    """
    return os.environ.get("ANTHROPIC_AUTH_TOKEN") or os.environ.get("ANTHROPIC_API_KEY")


def get_anthropic_base_url() -> str | None:
    """Get Anthropic base URL from environment.

    Returns:
        Base URL if set, None otherwise.
    """
    return os.environ.get("ANTHROPIC_BASE_URL")


def get_anthropic_model() -> str | None:
    """Get Anthropic model from environment.

    Returns:
        Model name if set, None otherwise.
    """
    return os.environ.get("ANTHROPIC_MODEL")


def get_api_timeout_ms() -> int | None:
    """Get API timeout in milliseconds from environment, convert to seconds.

    Returns:
        Timeout in seconds if set, None otherwise.
    """
    timeout_ms = os.environ.get("API_TIMEOUT_MS")
    if timeout_ms:
        try:
            return int(timeout_ms) // 1000
        except ValueError:
            return None
    return None


def get_anthropic_max_tokens() -> int:
    """Get Anthropic max tokens from environment.

    Returns:
        Max tokens value, defaults to 512.
    """
    max_tokens = os.environ.get("ANTHROPIC_MAX_TOKENS")
    if max_tokens:
        try:
            return int(max_tokens)
        except ValueError:
            pass
    return 512


__all__ = [
    "load_env_from_project_root",
    "get_anthropic_api_key",
    "get_anthropic_base_url",
    "get_anthropic_model",
    "get_api_timeout_ms",
    "get_anthropic_max_tokens",
]
