"""Idempotent cleanup for session-owned knowledge projections."""

from __future__ import annotations

import shutil
import sqlite3
from pathlib import Path
from typing import Any

from cc_deep_research.knowledge.vault import (
    graph_sqlite_path,
    raw_session_dir,
    sessions_dir,
)


def session_projection_exists(
    session_id: str,
    *,
    config_path: Path | None = None,
) -> bool:
    """Return whether any session-owned knowledge artifact exists."""
    if raw_session_dir(session_id, config_path).exists():
        return True
    if (sessions_dir(config_path) / f"{session_id}.md").exists():
        return True
    db_path = graph_sqlite_path(config_path)
    if not db_path.exists():
        return False
    try:
        with sqlite3.connect(db_path) as conn:
            row = conn.execute(
                "SELECT 1 FROM nodes WHERE id = ? LIMIT 1",
                (f"session:{session_id}",),
            ).fetchone()
        return row is not None
    except sqlite3.Error:
        return False


def delete_session_projection(
    session_id: str,
    *,
    config_path: Path | None = None,
) -> dict[str, Any]:
    """Remove raw/session-page/graph artifacts owned by one session."""
    existed = session_projection_exists(session_id, config_path=config_path)
    if not existed:
        return {"deleted": False, "missing": True, "error": None}

    try:
        db_path = graph_sqlite_path(config_path)
        if db_path.exists():
            with sqlite3.connect(db_path) as conn:
                conn.execute("PRAGMA foreign_keys=ON")
                node_id = f"session:{session_id}"
                conn.execute(
                    "DELETE FROM edges WHERE source_id = ? OR target_id = ?",
                    (node_id, node_id),
                )
                conn.execute("DELETE FROM node_terms WHERE node_id = ?", (node_id,))
                conn.execute("DELETE FROM nodes WHERE id = ?", (node_id,))
                conn.commit()

        raw_dir = raw_session_dir(session_id, config_path)
        if raw_dir.exists():
            shutil.rmtree(raw_dir)
        (sessions_dir(config_path) / f"{session_id}.md").unlink(missing_ok=True)
        return {"deleted": True, "missing": False, "error": None}
    except (OSError, sqlite3.Error) as exc:
        return {"deleted": False, "missing": False, "error": str(exc)}


__all__ = ["delete_session_projection", "session_projection_exists"]
