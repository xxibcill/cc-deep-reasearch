"""Session purge service for orchestrating session deletion across storage layers."""

from __future__ import annotations

import shutil
from pathlib import Path

from cc_deep_research.research_runs.models import (
    DeletedLayer,
    SessionDeleteRequest,
    SessionDeleteResponse,
)
from cc_deep_research.session_store import SessionStore
from cc_deep_research.telemetry import (
    delete_session_from_duckdb,
    get_default_dashboard_db_path,
    get_default_telemetry_dir,
    query_live_sessions,
)


class SessionPurgeService:
    """Service that orchestrates session deletion across all storage layers.

    This service coordinates deletion of:
    - Saved session files (JSON)
    - Telemetry session directories
    - DuckDB analytics records

    The service is idempotent and reports partial cleanup results clearly.
    """

    def __init__(
        self,
        session_store: SessionStore | None = None,
        telemetry_dir: Path | None = None,
        db_path: Path | None = None,
    ) -> None:
        """Initialize the session purge service.

        Args:
            session_store: Optional SessionStore instance.
            telemetry_dir: Optional path to telemetry directory.
            db_path: Optional path to DuckDB database.
        """
        self._session_store = session_store or SessionStore()
        self._telemetry_dir = telemetry_dir or get_default_telemetry_dir()
        self._db_path = db_path or get_default_dashboard_db_path()

    def _is_session_active(self, session_id: str) -> bool:
        """Check if a session is currently active.

        Args:
            session_id: The session ID to check.

        Returns:
            True if session is active, False otherwise.
        """
        live_sessions = query_live_sessions(base_dir=self._telemetry_dir)
        return any(
            s.get("session_id") == session_id and s.get("active")
            for s in live_sessions
        )

    def _get_telemetry_session_dir(self, session_id: str) -> Path:
        """Get the telemetry directory path for a session.

        Args:
            session_id: The session ID.

        Returns:
            Path to the telemetry session directory.
        """
        return self._telemetry_dir / session_id

    def delete_session(
        self,
        request: SessionDeleteRequest,
    ) -> SessionDeleteResponse:
        """Delete a session from all storage layers.

        Args:
            request: The deletion request containing session_id and force flag.

        Returns:
            SessionDeleteResponse with results per storage layer.
        """
        session_id = request.session_id
        force = request.force

        session_file_path = self._session_store.get_session_path(session_id)
        telemetry_session_dir = self._get_telemetry_session_dir(session_id)

        deleted_layers: list[DeletedLayer] = []
        any_deleted = False

        is_active = self._is_session_active(session_id)
        active_conflict = is_active and not force

        if active_conflict:
            deleted_layers.extend([
                DeletedLayer(
                    layer="session",
                    deleted=False,
                    missing=not session_file_path.exists(),
                    error="Session is active and force=false",
                ),
                DeletedLayer(
                    layer="telemetry",
                    deleted=False,
                    missing=not telemetry_session_dir.exists(),
                    error="Session is active and force=false",
                ),
                DeletedLayer(
                    layer="duckdb",
                    deleted=False,
                    missing=not self._db_path.exists(),
                ),
            ])

            return SessionDeleteResponse(
                session_id=session_id,
                success=False,
                deleted_layers=deleted_layers,
                active_conflict=True,
            )

        layer_session = self._delete_session_file(session_file_path)
        deleted_layers.append(layer_session)
        if layer_session.deleted:
            any_deleted = True

        layer_telemetry = self._delete_telemetry_dir(telemetry_session_dir)
        deleted_layers.append(layer_telemetry)
        if layer_telemetry.deleted:
            any_deleted = True

        layer_duckdb = self._delete_duckdb_records(session_id)
        deleted_layers.append(layer_duckdb)
        if layer_duckdb.deleted:
            any_deleted = True

        return SessionDeleteResponse(
            session_id=session_id,
            success=any_deleted,
            deleted_layers=deleted_layers,
            active_conflict=False,
        )

    def _delete_session_file(self, session_file_path: Path) -> DeletedLayer:
        """Delete the session file from disk.

        Args:
            session_file_path: Path to the session file.

        Returns:
            DeletedLayer with deletion result.
        """
        layer = DeletedLayer(
            layer="session",
            deleted=False,
            missing=not session_file_path.exists(),
        )

        if session_file_path.exists():
            try:
                session_file_path.unlink()
                layer.deleted = True
                layer.missing = False
            except Exception as e:
                layer.error = str(e)

        return layer

    def _delete_telemetry_dir(self, telemetry_dir: Path) -> DeletedLayer:
        """Delete the telemetry directory for a session.

        Args:
            telemetry_dir: Path to the telemetry session directory.

        Returns:
            DeletedLayer with deletion result.
        """
        layer = DeletedLayer(
            layer="telemetry",
            deleted=False,
            missing=not telemetry_dir.exists(),
        )

        if telemetry_dir.exists():
            try:
                shutil.rmtree(telemetry_dir)
                layer.deleted = True
                layer.missing = False
            except Exception as e:
                layer.error = str(e)

        return layer

    def _delete_duckdb_records(self, session_id: str) -> DeletedLayer:
        """Delete session records from DuckDB.

        Args:
            session_id: The session ID to delete from DuckDB.

        Returns:
            DeletedLayer with deletion result.
        """
        layer = DeletedLayer(
            layer="duckdb",
            deleted=False,
            missing=not self._db_path.exists(),
        )

        if self._db_path.exists():
            try:
                result = delete_session_from_duckdb(session_id, self._db_path)
                layer.deleted = result["deleted"]
                layer.missing = result["missing"]
            except Exception as e:
                layer.error = str(e)

        return layer


def purge_session(request: SessionDeleteRequest) -> SessionDeleteResponse:
    """Convenience function to purge a session.

    Args:
        request: The deletion request.

    Returns:
        SessionDeleteResponse with deletion results.
    """
    service = SessionPurgeService()
    return service.delete_session(request)


__all__ = [
    "SessionPurgeService",
    "purge_session",
]
