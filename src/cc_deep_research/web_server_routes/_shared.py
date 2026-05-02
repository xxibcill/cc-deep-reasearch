"""Shared utilities for web server route modules."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any


def serialize_timestamp(value: Any) -> str | None:
    """Return a JSON-safe timestamp string."""
    if value is None:
        return None
    if hasattr(value, "isoformat"):
        return value.isoformat()  # type: ignore[no-any-return]
    return str(value)


def parse_timestamp(value: Any) -> datetime | None:
    """Parse ISO-like timestamps used by telemetry files and DuckDB results."""
    if value is None:
        return None
    if isinstance(value, datetime):
        return value if value.tzinfo is not None else value.replace(tzinfo=UTC)
    if not isinstance(value, str) or not value:
        return None

    normalized = value.replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError:
        return None
    return parsed if parsed.tzinfo is not None else parsed.replace(tzinfo=UTC)
