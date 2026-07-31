"""Path helpers shared by session persistence and telemetry readers."""

from __future__ import annotations

from pathlib import Path

from cc_deep_research.config import get_default_config_path


def get_default_session_dir() -> Path:
    """Get the default directory for session storage."""
    return get_default_config_path().parent / "sessions"


__all__ = ["get_default_session_dir"]
