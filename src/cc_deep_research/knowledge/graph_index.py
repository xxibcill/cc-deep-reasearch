"""In-memory and SQLite-backed knowledge graph index."""

from __future__ import annotations

import json
import re
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

    def __init__(
        self,
        db_path: Path | None = None,
        *,
        enforce_foreign_keys: bool = False,
    ) -> None:
        self._db_path = db_path
        self._enforce_foreign_keys = enforce_foreign_keys
        self._conn: sqlite3.Connection | None = None
        if db_path is not None:
            self._init_db()

    def _init_db(self) -> None:
        """Create schema if the database doesn't exist."""
        assert self._db_path is not None
        self._conn = sqlite3.connect(str(self._db_path))
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA synchronous=NORMAL")
        self._conn.execute("PRAGMA busy_timeout=5000")
        self._conn.execute(
            f"PRAGMA foreign_keys={'ON' if self._enforce_foreign_keys else 'OFF'}"
        )
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
        self._conn.execute("""
            CREATE TABLE IF NOT EXISTS node_terms (
                node_id TEXT NOT NULL,
                term TEXT NOT NULL,
                PRIMARY KEY (node_id, term),
                FOREIGN KEY (node_id) REFERENCES nodes(id) ON DELETE CASCADE
            )
        """)
        self._conn.execute("CREATE INDEX IF NOT EXISTS idx_node_terms_term ON node_terms(term)")
        self._conn.commit()

    @property
    def _c(self) -> sqlite3.Connection:
        if self._conn is None:
            raise RuntimeError("GraphIndex not initialized with a db_path")
        return self._conn

    def clear(self) -> None:
        """Remove all nodes and edges."""
        self._c.execute("DELETE FROM edges")
        self._c.execute("DELETE FROM node_terms")
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
        self._replace_node_terms(node)

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

    def node_count(self) -> int:
        """Return the number of nodes in the graph."""
        row = self._c.execute("SELECT COUNT(*) FROM nodes").fetchone()
        return int(row[0]) if row is not None else 0

    def nodes_by_ids(self, node_ids: set[str] | list[str] | tuple[str, ...]) -> list[KnowledgeNode]:
        """Return nodes for a set of IDs in the input order where possible."""
        ordered_ids = list(dict.fromkeys(node_ids))
        if not ordered_ids:
            return []
        placeholders = ",".join("?" for _ in ordered_ids)
        rows = self._c.execute(
            f"SELECT * FROM nodes WHERE id IN ({placeholders})",
            ordered_ids,
        ).fetchall()
        nodes_by_id = {row["id"]: self._row_to_node(row) for row in rows}
        return [nodes_by_id[node_id] for node_id in ordered_ids if node_id in nodes_by_id]

    def nodes_matching_terms(self, terms: set[str], *, limit: int | None = None) -> list[KnowledgeNode]:
        """Return nodes whose indexed label/property terms intersect the query terms."""
        normalized_terms = sorted(_normalize_terms(terms))
        if not normalized_terms:
            return []
        self._rebuild_node_terms_if_empty()
        placeholders = ",".join("?" for _ in normalized_terms)
        limit_sql = " LIMIT ?" if limit is not None else ""
        params: list[object] = [*normalized_terms]
        if limit is not None:
            params.append(limit)
        rows = self._c.execute(
            f"""
            SELECT DISTINCT n.*
            FROM node_terms t
            JOIN nodes n ON n.id = t.node_id
            WHERE t.term IN ({placeholders})
            ORDER BY n.updated_at DESC, n.id ASC
            {limit_sql}
            """,
            params,
        ).fetchall()
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

    def edges_for_node(self, node_id: str) -> list[KnowledgeEdge]:
        """Return edges where the node is either source or target."""
        rows = self._c.execute(
            "SELECT * FROM edges WHERE source_id = ? OR target_id = ?",
            (node_id, node_id),
        ).fetchall()
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

    def rollback(self) -> None:
        """Discard pending graph mutations."""
        if self._conn is not None:
            self._conn.rollback()

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

    def _replace_node_terms(self, node: KnowledgeNode) -> None:
        """Refresh the token index for one node."""
        terms = _terms_for_node(node)
        self._c.execute("DELETE FROM node_terms WHERE node_id = ?", (node.id,))
        if terms:
            self._c.executemany(
                "INSERT OR IGNORE INTO node_terms (node_id, term) VALUES (?, ?)",
                [(node.id, term) for term in terms],
            )

    def _rebuild_node_terms_if_empty(self) -> None:
        """Populate token index for databases created before node_terms existed."""
        row = self._c.execute("SELECT COUNT(*) FROM node_terms").fetchone()
        if row is not None and int(row[0]) > 0:
            return
        for node in self.all_nodes():
            self._replace_node_terms(node)


def _normalize_terms(terms: set[str]) -> set[str]:
    """Normalize query terms to the token shape used by the graph term index."""
    return {term.lower() for term in terms if term}


def _terms_for_node(node: KnowledgeNode) -> set[str]:
    """Extract searchable terms from a node label and properties."""
    prop_values = " ".join(str(value) for value in node.properties.values())
    return set(re.findall(r"[a-z0-9]+", f"{node.label} {prop_values}".lower()))


__all__ = ["GraphIndex"]
