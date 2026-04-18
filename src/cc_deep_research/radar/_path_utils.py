"""Path safety utilities for Radar storage and telemetry.

Shared path validation to prevent directory traversal attacks.
"""

from __future__ import annotations

import os
import tempfile
from pathlib import Path


def allowed_prefixes() -> tuple[str, ...]:
    """Compute allowed path prefixes at runtime."""
    return (
        str(Path.home() / ".config"),
        "/tmp",
        os.path.realpath(tempfile.gettempdir()),
        str(Path.cwd().resolve()),
    )


def is_safe_path(path: Path) -> bool:
    """Reject paths that escape intended storage directories.

    Args:
        path: The path to validate.

    Returns:
        True if the path is safe (within allowed directories or relative).

    Raises:
        (OSError, ValueError): If path resolution fails.
    """
    try:
        resolved = path.resolve()
        for prefix in allowed_prefixes():
            resolved_prefix = Path(prefix).resolve()
            if str(resolved).startswith(str(resolved_prefix)):
                return True
        # Relative paths are considered safe for explicit overrides only
        if not path.is_absolute():
            return True
        return False
    except (OSError, ValueError):
        return False
