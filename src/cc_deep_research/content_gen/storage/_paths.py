"""Shared path resolution for content-generation storage backends."""

from __future__ import annotations

import os
import tempfile
from pathlib import Path
from typing import TYPE_CHECKING

from cc_deep_research.config import get_default_config_path, load_config

if TYPE_CHECKING:
    from cc_deep_research.config import Config


def default_content_gen_dir() -> Path:
    """Return the default content-generation config directory."""
    return get_default_config_path().parent


def _allowed_prefixes() -> tuple[str, ...]:
    """Compute allowed path prefixes at runtime.

    Includes the system temp directory (resolved to real path to handle
    symlinks like /private/var/folders on macOS).
    """
    return (
        str(Path.home() / ".config"),
        "/tmp",
        os.path.realpath(tempfile.gettempdir()),
        str(Path.cwd().resolve()),
    )


def _is_safe_path(path: Path) -> bool:
    """Reject paths that escape intended storage directories.

    Prevents directory traversal attacks where a malicious config might
    specify a path like ~/.config/../../../etc/something.
    """
    try:
        resolved = path.resolve()
        # Check the resolved path starts with a resolved allowed prefix
        for prefix in _allowed_prefixes():
            resolved_prefix = Path(prefix).resolve()
            if str(resolved).startswith(str(resolved_prefix)):
                return True
        # Also allow paths that are purely relative (safety net)
        if not path.is_absolute():
            return True
        return False
    except (OSError, ValueError):
        return False


def resolve_content_gen_file_path(
    *,
    explicit_path: Path | None,
    config: Config | None,
    config_attr: str,
    default_name: str,
    use_config_parent: bool = False,
) -> Path:
    """Resolve a content-generation file path from explicit, config, or default sources."""
    if explicit_path is not None:
        if not _is_safe_path(explicit_path):
            raise ValueError(f"Explicit path {explicit_path} escapes allowed directories")
        return explicit_path

    resolved_config = config or load_config()
    configured_path = getattr(resolved_config.content_gen, config_attr, None)
    if configured_path:
        path = Path(configured_path).expanduser()
        if not _is_safe_path(path):
            raise ValueError(f"Configured path {path} escapes allowed directories")
        if use_config_parent:
            safe_parent = path.parent.resolve()
            if not _is_safe_path(safe_parent / default_name):
                raise ValueError(f"Resolved parent path {safe_parent} escapes allowed directories")
            return safe_parent / default_name
        return path
    resolved_default = (default_content_gen_dir() / default_name).resolve()
    return resolved_default


__all__ = ["default_content_gen_dir", "resolve_content_gen_file_path"]
