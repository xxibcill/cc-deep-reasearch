"""Shared path resolution for content-generation storage backends."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from cc_deep_research.config import get_default_config_path, load_config

if TYPE_CHECKING:
    from cc_deep_research.config import Config


def default_content_gen_dir() -> Path:
    """Return the default content-generation config directory."""
    return get_default_config_path().parent


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
        return explicit_path

    resolved_config = config or load_config()
    configured_path = getattr(resolved_config.content_gen, config_attr, None)
    if configured_path:
        path = Path(configured_path).expanduser()
        if use_config_parent:
            return path.parent / default_name
        return path
    return default_content_gen_dir() / default_name


__all__ = ["default_content_gen_dir", "resolve_content_gen_file_path"]
