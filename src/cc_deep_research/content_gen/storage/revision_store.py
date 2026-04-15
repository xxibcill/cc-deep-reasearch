"""SQLite-backed BriefRevision persistence for version-aware brief storage.

This module provides a thread-safe SQLite store for persisting individual
BriefRevision objects separately from the ManagedOpportunityBrief resource.
This enables:
- Listing and retrieving specific revisions
- Proper audit trail for revision changes
- Efficient revision history queries

Schema
======
briefs_revisions table:
  - revision_id TEXT PRIMARY KEY
  - brief_id    TEXT NOT NULL (indexed)
  - data        TEXT NOT NULL (JSON-serialized BriefRevision)
  - created_at  TEXT NOT NULL
"""

from __future__ import annotations

import json
import sqlite3
import threading
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING

from cc_deep_research.content_gen.models import BriefRevision

if TYPE_CHECKING:
    from cc_deep_research.config import Config

_json_encoded = json.dumps
_json_decoded = json.loads


def _now_iso() -> str:
    return datetime.now(tz=UTC).isoformat()


class BriefRevisionStore:
    """SQLite-backed store for individual BriefRevision objects.

    Each revision is stored as a separate row, enabling efficient
    listing and querying of revision history.
    """

    def __init__(
        self,
        path: Path | None = None,
        *,
        config: Config | None = None,
    ) -> None:
        from cc_deep_research.content_gen.storage._paths import resolve_content_gen_file_path

        if path is None:
            db_path = resolve_content_gen_file_path(
                explicit_path=None,
                config=config,
                config_attr="brief_path",
                default_name="briefs_revisions.db",
                use_config_parent=True,
            )
        else:
            db_path = path

        self._db_path = db_path
        self._initialized = False
        self._lock = threading.RLock()
        self._conn: sqlite3.Connection | None = None
        self._db_path.parent.mkdir(parents=True, exist_ok=True)

    @property
    def path(self) -> Path:
        return self._db_path

    def _get_conn(self) -> sqlite3.Connection:
        """Return a cached connection (caller must hold lock)."""
        if self._conn is None:
            self._conn = sqlite3.connect(self._db_path, check_same_thread=False)
            self._conn.execute("PRAGMA journal_mode=WAL")
            self._conn.execute("PRAGMA synchronous=NORMAL")
        return self._conn

    def _ensure_initialized(self) -> None:
        """Create schema if it doesn't exist (caller must hold lock)."""
        if self._initialized:
            return
        conn = self._get_conn()
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS briefs_revisions (
                revision_id TEXT PRIMARY KEY,
                brief_id    TEXT NOT NULL,
                data        TEXT NOT NULL,
                created_at  TEXT NOT NULL
            )
            """
        )
        conn.execute("CREATE INDEX IF NOT EXISTS idx_revisions_brief_id ON briefs_revisions(brief_id)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_revisions_created ON briefs_revisions(created_at)")
        conn.commit()
        self._initialized = True

    def save_revision(self, revision: BriefRevision) -> None:
        """Persist a single BriefRevision."""
        with self._lock:
            self._ensure_initialized()
            conn = self._get_conn()
            data = revision.model_dump(exclude_none=True)
            json_data = _json_encoded(data)
            conn.execute(
                """
                INSERT OR REPLACE INTO briefs_revisions (revision_id, brief_id, data, created_at)
                VALUES (?, ?, ?, ?)
                """,
                (revision.revision_id, revision.brief_id, json_data, revision.created_at or _now_iso()),
            )
            conn.commit()

    def get_revision(self, revision_id: str) -> BriefRevision | None:
        """Load a single revision by ID."""
        with self._lock:
            self._ensure_initialized()
            conn = self._get_conn()
            cursor = conn.execute(
                "SELECT data FROM briefs_revisions WHERE revision_id = ?",
                (revision_id,),
            )
            row = cursor.fetchone()
            if row is None:
                return None
            data = _json_decoded(row[0])
            return BriefRevision.model_validate(data)

    def list_revisions(
        self,
        brief_id: str,
        *,
        limit: int = 50,
    ) -> list[BriefRevision]:
        """List all revisions for a brief, most recent first."""
        with self._lock:
            self._ensure_initialized()
            conn = self._get_conn()
            cursor = conn.execute(
                """
                SELECT data FROM briefs_revisions
                WHERE brief_id = ?
                ORDER BY created_at DESC
                LIMIT ?
                """,
                (brief_id, limit),
            )
            rows = cursor.fetchall()
            return [BriefRevision.model_validate(_json_decoded(row[0])) for row in rows]

    def get_latest_revision(self, brief_id: str) -> BriefRevision | None:
        """Get the most recently created revision for a brief."""
        revisions = self.list_revisions(brief_id, limit=1)
        return revisions[0] if revisions else None

    def delete_revisions_for_brief(self, brief_id: str) -> int:
        """Delete all revisions for a brief. Returns count of deleted revisions."""
        with self._lock:
            self._ensure_initialized()
            conn = self._get_conn()
            cursor = conn.execute(
                "SELECT COUNT(*) FROM briefs_revisions WHERE brief_id = ?",
                (brief_id,),
            )
            count = cursor.fetchone()[0]
            conn.execute("DELETE FROM briefs_revisions WHERE brief_id = ?", (brief_id,))
            conn.commit()
            return count
