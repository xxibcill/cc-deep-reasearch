"""Tests for telemetry/query.py — query_session_summaries."""

import json
import tempfile
from pathlib import Path

import pytest

from cc_deep_research.telemetry.ingest import ingest_telemetry_to_duckdb
from cc_deep_research.telemetry.query import query_session_summaries


@pytest.fixture
def temp_db():
    """Create a temporary DuckDB database with telemetry_sessions data."""
    import duckdb

    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "dashboard.db"
        conn = duckdb.connect(str(db_path))

        conn.execute("""
            CREATE TABLE telemetry_sessions (
                session_id VARCHAR PRIMARY KEY,
                created_at TIMESTAMP,
                last_event_at TIMESTAMP,
                total_time_ms BIGINT,
                total_sources BIGINT,
                status VARCHAR,
                archived BOOLEAN DEFAULT FALSE,
                query VARCHAR,
                llm_total_tokens BIGINT DEFAULT 0,
                search_queries BIGINT DEFAULT 0,
                phase VARCHAR
            )
        """)

        now = "2026-05-01 12:00:00"
        base_time = "2026-05-01 12:00:00"
        sessions = [
            # Active (non-archived) sessions — use distinct timestamps for cursor pagination
            ("active-1", "2026-05-01 12:00:00", "2026-05-01 12:00:00", 1000, 5, "completed", False, "test query alpha", 1000, 3, "analysis"),
            ("active-2", "2026-05-01 12:01:00", "2026-05-01 12:01:00", 2000, 3, "completed", False, "another query", 2000, 5, "strategy"),
            ("active-3", "2026-05-01 12:02:00", "2026-05-01 12:02:00", 1500, 4, "completed", False, "third query", 1500, 4, "analysis"),
            # Archived sessions
            ("archived-1", "2026-05-01 12:03:00", "2026-05-01 12:03:00", 1500, 2, "failed", True, "failed archived", 500, 1, "collection"),
            # Session with % in query (search wildcard test)
            ("wildcard-pct", "2026-05-01 12:04:00", "2026-05-01 12:04:00", 3000, 1, "completed", False, "100% coverage", 3000, 10, "analysis"),
            # Session with _ in query (search wildcard test)
            ("wildcard-underscore", "2026-05-01 12:05:00", "2026-05-01 12:05:00", 2500, 4, "completed", False, "field_name test", 2500, 8, "strategy"),
        ]
        for s in sessions:
            conn.execute(
                """
                INSERT INTO telemetry_sessions
                (session_id, created_at, last_event_at, total_time_ms, total_sources, status, archived, query, llm_total_tokens, search_queries, phase)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                s,
            )
        conn.close()
        yield db_path


class TestQuerySessionSummaries:
    def test_returns_only_non_archived_by_default(self, temp_db):
        """When archived_only defaults to False, only non-archived sessions are returned."""
        result = query_session_summaries(temp_db, limit=10)
        session_ids = {s["session_id"] for s in result["sessions"]}
        assert "active-1" in session_ids
        assert "active-2" in session_ids
        assert "active-3" in session_ids
        assert "archived-1" not in session_ids  # archived session excluded
        # 3 active + 2 wildcard = 5 non-archived
        assert result["total"] == 5

    def test_respects_limit(self, temp_db):
        result = query_session_summaries(temp_db, limit=2)
        assert len(result["sessions"]) == 2
        assert result["total"] == 5
        assert result["next_cursor"] is not None

    def test_archived_only_true_returns_only_archived(self, temp_db):
        result = query_session_summaries(temp_db, limit=10, archived_only=True)
        session_ids = {s["session_id"] for s in result["sessions"]}
        assert session_ids == {"archived-1"}
        assert result["total"] == 1

    def test_search_exact_match(self, temp_db):
        result = query_session_summaries(temp_db, search="alpha", limit=10)
        assert len(result["sessions"]) == 1
        assert result["sessions"][0]["session_id"] == "active-1"

    def test_search_prefix_match(self, temp_db):
        result = query_session_summaries(temp_db, search="test", limit=10)
        # "test query alpha" matches, "field_name test" matches
        session_ids = {s["session_id"] for s in result["sessions"]}
        assert "active-1" in session_ids
        assert "wildcard-underscore" in session_ids

    def test_search_literal_percent_not_treated_as_wildcard(self, temp_db):
        """A literal % in the search string should be treated as a character, not a SQL wildcard.

        Searching for "100%" should match "100% coverage" but NOT match "test query alpha"
        just because the word "test" appears somewhere.
        """
        result = query_session_summaries(temp_db, search="100%", limit=10)
        session_ids = {s["session_id"] for s in result["sessions"]}
        assert "wildcard-pct" in session_ids
        # Should NOT match active-1 (which has "test" but not "100%")
        assert "active-1" not in session_ids

    def test_search_literal_underscore_not_treated_as_wildcard(self, temp_db):
        """A literal _ in the search string should be treated as a character, not a SQL wildcard."""
        result = query_session_summaries(temp_db, search="field_name", limit=10)
        session_ids = {s["session_id"] for s in result["sessions"]}
        assert "wildcard-underscore" in session_ids

    def test_status_filter(self, temp_db):
        # active-1 and active-2 are 'completed', archived-1 is 'failed'
        # Since default is non-archived, status=failed finds nothing
        result = query_session_summaries(temp_db, status="completed", limit=10)
        assert all(s["status"] == "completed" for s in result["sessions"])
        session_ids = {s["session_id"] for s in result["sessions"]}
        assert "active-1" in session_ids
        assert "active-2" in session_ids

    def test_status_filter_with_archived_only(self, temp_db):
        # archived_only=True includes archived sessions
        result = query_session_summaries(temp_db, status="failed", archived_only=True, limit=10)
        assert all(s["status"] == "failed" for s in result["sessions"])

    def test_empty_db_returns_empty_sessions(self):
        import duckdb

        with tempfile.TemporaryDirectory() as tmpdir:
            empty_db = Path(tmpdir) / "empty.db"
            conn = duckdb.connect(str(empty_db))
            conn.execute("""
                CREATE TABLE telemetry_sessions (
                    session_id VARCHAR PRIMARY KEY, created_at TIMESTAMP,
                    last_event_at TIMESTAMP, total_time_ms BIGINT,
                    total_sources BIGINT, status VARCHAR,
                    archived BOOLEAN DEFAULT FALSE, query VARCHAR
                )
            """)
            conn.close()

            result = query_session_summaries(empty_db, limit=10)
            assert result["sessions"] == []
            assert result["total"] == 0
            assert result["next_cursor"] is None

    def test_nonexistent_db_returns_empty_sessions(self):
        result = query_session_summaries(Path("/nonexistent/path.db"), limit=10)
        assert result["sessions"] == []
        assert result["total"] == 0
        assert result["next_cursor"] is None

    def test_cursor_pagination(self, temp_db):
        """Cursor pagination returns consecutive non-overlapping pages."""
        # First page
        page1 = query_session_summaries(temp_db, limit=2, sort_order="desc")
        assert len(page1["sessions"]) == 2
        cursor = page1["next_cursor"]
        assert cursor is not None

        # Second page
        page2 = query_session_summaries(temp_db, limit=2, cursor=cursor, sort_order="desc")

        # No overlap between pages (key invariant)
        page1_ids = {s["session_id"] for s in page1["sessions"]}
        page2_ids = {s["session_id"] for s in page2["sessions"]}
        assert page1_ids.isdisjoint(page2_ids), f"Overlap: {page1_ids & page2_ids}"

        # Page 2 should have at least 1 item (we have 5 non-archived sessions)
        assert len(page2["sessions"]) >= 1

    def test_cursor_none_when_fewer_than_limit(self, temp_db):
        result = query_session_summaries(temp_db, limit=10)
        assert result["next_cursor"] is None  # 3 sessions, limit=10

    def test_archived_only_combined_with_search(self, temp_db):
        result = query_session_summaries(temp_db, search="failed", archived_only=True, limit=10)
        assert len(result["sessions"]) == 1
        assert result["sessions"][0]["session_id"] == "archived-1"

    def test_archived_only_combined_with_status(self, temp_db):
        result = query_session_summaries(temp_db, status="failed", archived_only=True, limit=10)
        assert len(result["sessions"]) == 1
        assert result["sessions"][0]["session_id"] == "archived-1"

    def test_archived_only_false_different_from_default(self, temp_db):
        """archived_only=False (explicit) should behave the same as the default (None)."""
        result_default = query_session_summaries(temp_db, limit=10)
        result_explicit = query_session_summaries(temp_db, limit=10, archived_only=False)
        assert {s["session_id"] for s in result_default["sessions"]} == {
            s["session_id"] for s in result_explicit["sessions"]
        }

    def test_search_with_percent_in_query_field(self, temp_db):
        """Search for 'coverage' should find the session with '100% coverage' in query."""
        result = query_session_summaries(temp_db, search="coverage", limit=10)
        session_ids = {s["session_id"] for s in result["sessions"]}
        assert "wildcard-pct" in session_ids

    def test_ingested_schema_without_query_or_archived_columns(self, tmp_path):
        """Real ingest schema derives query/archive state from summary_json without crashing."""
        telemetry_dir = tmp_path / "telemetry"
        telemetry_dir.mkdir()

        for session_id, query, archived in [
            ("session-active", "alpha coverage", False),
            ("session-archived", "archived alpha", True),
        ]:
            session_dir = telemetry_dir / session_id
            session_dir.mkdir()
            (session_dir / "summary.json").write_text(
                json.dumps({
                    "session_id": session_id,
                    "status": "completed",
                    "total_sources": 1,
                    "total_time_ms": 100,
                    "created_at": "2026-05-01T12:00:00Z",
                    "query": query,
                    "archived": archived,
                }),
                encoding="utf-8",
            )

        db_path = tmp_path / "telemetry.duckdb"
        ingest_telemetry_to_duckdb(base_dir=telemetry_dir, db_path=db_path)

        default_result = query_session_summaries(db_path, limit=10)
        assert {s["session_id"] for s in default_result["sessions"]} == {"session-active"}

        search_result = query_session_summaries(db_path, search="coverage", limit=10)
        assert [s["session_id"] for s in search_result["sessions"]] == ["session-active"]

        archived_result = query_session_summaries(db_path, archived_only=True, limit=10)
        assert {s["session_id"] for s in archived_result["sessions"]} == {"session-archived"}
