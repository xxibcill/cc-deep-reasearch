"""In-memory and SQLite-backed knowledge graph index."""

from __future__ import annotations

import json
import sqlite3
from datetime import UTC, datetime
from pathlib import Path

from cc_deep_research.knowledge import (
    EdgeKind,
    GraphSnapshot,
    KnowledgeEdge,
    KnowledgeNode,
    NodeKind,
)


class GraphIndex:
    """A graph index backed by SQLite, optionally persisted to disk."""

    def __init__(self, db_path: Path | None = None) -> None:
        self._db_path = db_path
        self._conn: sqlite3.Connection | None = None
        if db_path is not None:
            self._init_db()

    def _init_db(self) -> None:
        """Create schema if the database doesn't exist."""
        assert self._db_path is not None
        self._conn = sqlite3.connect(str(self._db_path))
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("""
            CREATE TABLE IF NOT EXISTS nodes (
                id TEXT PRIMARY KEY,
                kind TEXT NOT NULL,
                label TEXT NOT NULL DEFAULT '',
                properties TEXT NOT NULL DEFAULT '{}',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
        """)
        self._conn.execute("""
            CREATE TABLE IF NOT EXISTS edges (
                id TEXT PRIMARY KEY,
                source_id TEXT NOT NULL,
                target_id TEXT NOT NULL,
                kind TEXT NOT NULL,
                properties TEXT NOT NULL DEFAULT '{}',
                FOREIGN KEY (source_id) REFERENCES nodes(id),
                FOREIGN KEY (target_id) REFERENCES nodes(id)
            )
        """)
        self._conn.execute("CREATE INDEX IF NOT EXISTS idx_nodes_kind ON nodes(kind)")
        self._conn.execute("CREATE INDEX IF NOT EXISTS idx_edges_kind ON edges(kind)")
        self._conn.execute("CREATE INDEX IF NOT EXISTS idx_edges_source ON edges(source_id)")
        self._conn.execute("CREATE INDEX IF NOT EXISTS idx_edges_target ON edges(target_id)")

    @property
    def _c(self) -> sqlite3.Connection:
        if self._conn is None:
            raise RuntimeError("GraphIndex not initialized with a db_path")
        return self._conn

    def clear(self) -> None:
        """Remove all nodes and edges."""
        self._c.execute("DELETE FROM edges")
        self._c.execute("DELETE FROM nodes")

    # -------------------------------------------------------------------------
    # Node operations
    # -------------------------------------------------------------------------

    def upsert_node(self, node: KnowledgeNode) -> None:
        """Insert or update a node."""
        now = datetime.now(UTC).isoformat()
        self._c.execute(
            """
            INSERT INTO nodes (id, kind, label, properties, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                kind = excluded.kind,
                label = excluded.label,
                properties = excluded.properties,
                updated_at = excluded.updated_at
            """,
            (
                node.id,
                node.kind.value,
                node.label,
                json.dumps(node.properties),
                now,
                now,
            ),
        )

    def node(self, node_id: str) -> KnowledgeNode | None:
        """Retrieve a node by ID."""
        row = self._c.execute(
            "SELECT * FROM nodes WHERE id = ?", (node_id,)
        ).fetchone()
        if row is None:
            return None
        return self._row_to_node(row)

    def nodes_by_kind(self, kind: NodeKind) -> list[KnowledgeNode]:
        """Return all nodes of a given kind."""
        rows = self._c.execute(
            "SELECT * FROM nodes WHERE kind = ?", (kind.value,)
        ).fetchall()
        return [self._row_to_node(r) for r in rows]

    def all_nodes(self) -> list[KnowledgeNode]:
        """Return all nodes."""
        rows = self._c.execute("SELECT * FROM nodes").fetchall()
        return [self._row_to_node(r) for r in rows]

    # -------------------------------------------------------------------------
    # Edge operations
    # -------------------------------------------------------------------------

    def upsert_edge(self, edge: KnowledgeEdge) -> None:
        """Insert or update an edge (upsert by ID)."""
        self._c.execute(
            """
            INSERT INTO edges (id, source_id, target_id, kind, properties)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                source_id = excluded.source_id,
                target_id = excluded.target_id,
                kind = excluded.kind,
                properties = excluded.properties
            """,
            (
                edge.id,
                edge.source_id,
                edge.target_id,
                edge.kind.value,
                json.dumps(edge.properties),
            ),
        )

    def edge(self, edge_id: str) -> KnowledgeEdge | None:
        """Retrieve an edge by ID."""
        row = self._c.execute(
            "SELECT * FROM edges WHERE id = ?", (edge_id,)
        ).fetchone()
        if row is None:
            return None
        return self._row_to_edge(row)

    def edges_between(self, source_id: str, target_id: str) -> list[KnowledgeEdge]:
        """Return all edges between two nodes."""
        rows = self._c.execute(
            "SELECT * FROM edges WHERE source_id = ? AND target_id = ?",
            (source_id, target_id),
        ).fetchall()
        return [self._row_to_edge(r) for r in rows]

    def edges_by_kind(self, kind: EdgeKind) -> list[KnowledgeEdge]:
        """Return all edges of a given kind."""
        rows = self._c.execute(
            "SELECT * FROM edges WHERE kind = ?", (kind.value,)
        ).fetchall()
        return [self._row_to_edge(r) for r in rows]

    def all_edges(self) -> list[KnowledgeEdge]:
        """Return all edges."""
        rows = self._c.execute("SELECT * FROM edges").fetchall()
        return [self._row_to_edge(r) for r in rows]

    # -------------------------------------------------------------------------
    # Snapshot and rebuild
    # -------------------------------------------------------------------------

    def snapshot(self) -> GraphSnapshot:
        """Return a snapshot of the current graph state."""
        return GraphSnapshot(
            nodes=self.all_nodes(),
            edges=self.all_edges(),
            exported_at=datetime.now(UTC),
        )

    def rebuild_from_snapshot(self, snap: GraphSnapshot) -> None:
        """Clear and repopulate from a snapshot."""
        self.clear()
        for node in snap.nodes:
            self.upsert_node(node)
        for edge in snap.edges:
            self.upsert_edge(edge)

    def commit(self) -> None:
        """Persist any pending changes to disk."""
        if self._conn is not None:
            self._conn.commit()

    def close(self) -> None:
        """Close the database connection."""
        if self._conn is not None:
            self._conn.close()
            self._conn = None

    # -------------------------------------------------------------------------
    # Row helpers
    # -------------------------------------------------------------------------

    @staticmethod
    def _row_to_node(row: sqlite3.Row) -> KnowledgeNode:
        return KnowledgeNode(
            id=row["id"],
            kind=NodeKind(row["kind"]),
            label=row["label"],
            properties=json.loads(row["properties"]),
            created_at=datetime.fromisoformat(row["created_at"]),
            updated_at=datetime.fromisoformat(row["updated_at"]),
        )

    @staticmethod
    def _row_to_edge(row: sqlite3.Row) -> KnowledgeEdge:
        return KnowledgeEdge(
            id=row["id"],
            source_id=row["source_id"],
            target_id=row["target_id"],
            kind=EdgeKind(row["kind"]),
            properties=json.loads(row["properties"]),
        )


__all__ = ["GraphIndex"]
