"""Trace bundle export for portable session snapshots.

This module provides functionality to export research session traces
as portable, self-contained JSON bundles for replay, analysis, and
debugging purposes.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

BUNDLE_SCHEMA_VERSION = "1.0.0"


def build_trace_bundle(
    session_id: str,
    session_summary: dict[str, Any],
    events: list[dict[str, Any]],
    config_snapshot: dict[str, Any] | None,
    derived_outputs: dict[str, Any],
    artifacts: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Build a portable trace bundle for a research session.

    Args:
        session_id: The session identifier.
        session_summary: Summary metadata about the session.
        events: List of telemetry events from the session.
        config_snapshot: Configuration used during the session (redacted).
        derived_outputs: Derived analysis outputs (narrative, critical_path, etc.).
        artifacts: Optional list of artifact references.

    Returns:
        A dict containing the complete trace bundle ready for serialization.
    """
    return {
        "schema_version": BUNDLE_SCHEMA_VERSION,
        "exported_at": datetime.now(UTC).isoformat(),
        "session_id": session_id,
        "session_summary": session_summary,
        "events": events,
        "config_snapshot": config_snapshot,
        "artifacts": artifacts or [],
        "derived_outputs": {
            "narrative": derived_outputs.get("narrative", []),
            "critical_path": derived_outputs.get("critical_path", {}),
            "state_changes": derived_outputs.get("state_changes", []),
            "decisions": derived_outputs.get("decisions", []),
            "degradations": derived_outputs.get("degradations", []),
            "failures": derived_outputs.get("failures", []),
        },
    }


__all__ = [
    "BUNDLE_SCHEMA_VERSION",
    "build_trace_bundle",
]
