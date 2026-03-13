"""Clock helpers for coordination state."""

from __future__ import annotations

from time import monotonic


def monotonic_time() -> float:
    """Return a monotonic timestamp for duration tracking."""
    return monotonic()
