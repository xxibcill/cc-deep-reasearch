"""Graph health metrics computation for the knowledge vault."""

from __future__ import annotations

from dataclasses import dataclass, field

from cc_deep_research.knowledge import (
    EdgeKind,
    KnowledgeEdge,
    KnowledgeNode,
    NodeKind,
)


@dataclass
class GraphHealthMetrics:
    """Health metrics for a knowledge graph."""

    total_nodes: int = 0
    total_edges: int = 0
    orphan_count: int = 0
    stale_claim_count: int = 0
    duplicate_candidate_count: int = 0
    source_backed_claim_ratio: float = 1.0
    claims_without_sources: int = 0
    nodes_by_kind: dict[str, int] = field(default_factory=dict)
    edges_by_kind: dict[str, int] = field(default_factory=dict)


def orphaned_nodes(
    nodes: list[KnowledgeNode],
    edges: list[KnowledgeEdge],
) -> list[KnowledgeNode]:
    """Return nodes with no incoming or outgoing edges.

    A node is orphaned if it appears in neither the source nor target
    of any edge.
    """
    if not nodes:
        return []

    connected_ids: set[str] = set()
    for edge in edges:
        connected_ids.add(edge.source_id)
        connected_ids.add(edge.target_id)

    return [n for n in nodes if n.id not in connected_ids]


def duplicate_node_candidates(
    nodes: list[KnowledgeNode],
) -> list[tuple[KnowledgeNode, KnowledgeNode]]:
    """Return pairs of nodes with the same label and kind, excluding different sessions.

    Two nodes are considered duplicate candidates if they share the same kind
    and label, but are not both session nodes (sessions are allowed to have
    identical labels since they represent different research sessions).
    """
    if not nodes:
        return []

    # Group nodes by (kind, label)
    groups: dict[tuple[str, str], list[KnowledgeNode]] = {}
    for node in nodes:
        key = (node.kind.value, node.label)
        if node.label:  # Only consider nodes with non-empty labels
            groups.setdefault(key, []).append(node)

    candidates: list[tuple[KnowledgeNode, KnowledgeNode]] = []
    for (kind, label), group in groups.items():
        if len(group) > 1:
            # Skip session nodes - different sessions can have identical labels
            if kind == NodeKind.SESSION.value:
                continue
            # Return all pairs (for clarity in diagnostics)
            for i in range(len(group)):
                for j in range(i + 1, len(group)):
                    candidates.append((group[i], group[j]))

    return candidates


def compute_graph_metrics(index: GraphIndex) -> GraphHealthMetrics:
    """Compute health metrics from a GraphIndex.

    Uses efficient SQLite queries where possible to avoid full in-memory scans
    for large graphs.
    """
    # Handle uninitialized index
    if index._conn is None:
        return GraphHealthMetrics()

    # Total counts via efficient queries
    total_nodes = index._c.execute("SELECT COUNT(*) FROM nodes").fetchone()[0]
    total_edges = index._c.execute("SELECT COUNT(*) FROM edges").fetchone()[0]

    # Nodes by kind - efficient GROUP BY query
    nodes_by_kind: dict[str, int] = {}
    for row in index._c.execute("SELECT kind, COUNT(*) as cnt FROM nodes GROUP BY kind"):
        nodes_by_kind[row["kind"]] = row["cnt"]

    # Edges by kind - efficient GROUP BY query
    edges_by_kind: dict[str, int] = {}
    for row in index._c.execute("SELECT kind, COUNT(*) as cnt FROM edges GROUP BY kind"):
        edges_by_kind[row["kind"]] = row["cnt"]

    # Orphan count: nodes not in any edge source_id or target_id
    # Efficient: LEFT JOIN to find nodes with no edges
    orphan_count = index._c.execute("""
        SELECT COUNT(*) FROM nodes n
        WHERE NOT EXISTS (SELECT 1 FROM edges e WHERE e.source_id = n.id)
        AND NOT EXISTS (SELECT 1 FROM edges e WHERE e.target_id = n.id)
    """).fetchone()[0]

    # Stale claim count: claims where freshness = 'dated'
    stale_claim_count = index._c.execute("""
        SELECT COUNT(*) FROM nodes
        WHERE kind = ? AND properties LIKE '%"freshness"%'
    """, (NodeKind.CLAIM.value,)).fetchone()[0]

    # Filter for stale claims by parsing properties
    stale_claim_count = 0
    claim_rows = index._c.execute(
        "SELECT id, properties FROM nodes WHERE kind = ?",
        (NodeKind.CLAIM.value,)
    ).fetchall()
    for row in claim_rows:
        import json as _json
        try:
            props = _json.loads(row["properties"])
            if props.get("freshness") == "dated":
                stale_claim_count += 1
        except Exception:
            pass

    # Duplicate candidate count: same kind + same label (excluding sessions)
    label_kind_seen: dict[tuple[str, str], int] = {}
    for row in index._c.execute("SELECT kind, label FROM nodes WHERE label != ''"):
        key = (row["kind"], row["label"])
        label_kind_seen[key] = label_kind_seen.get(key, 0) + 1

    duplicate_candidate_count = sum(
        1 for (kind, _), count in label_kind_seen.items()
        if count > 1 and kind != NodeKind.SESSION.value
    )

    # Source-backed claim ratio
    # Count claims that are targets of CITED edges
    cited_claim_ids = {
        row["target_id"]
        for row in index._c.execute(
            "SELECT DISTINCT target_id FROM edges WHERE kind = ?",
            (EdgeKind.CITED.value,)
        ).fetchall()
    }

    claim_ids = {
        row["id"]
        for row in index._c.execute(
            "SELECT id FROM nodes WHERE kind = ?",
            (NodeKind.CLAIM.value,)
        ).fetchall()
    }

    claims_with_sources = len(cited_claim_ids & claim_ids)
    total_claims = len(claim_ids)

    if total_claims > 0:
        source_backed_claim_ratio = round(claims_with_sources / total_claims, 3)
        claims_without_sources = total_claims - claims_with_sources
    else:
        source_backed_claim_ratio = 1.0
        claims_without_sources = 0

    return GraphHealthMetrics(
        total_nodes=total_nodes,
        total_edges=total_edges,
        orphan_count=orphan_count,
        stale_claim_count=stale_claim_count,
        duplicate_candidate_count=duplicate_candidate_count,
        source_backed_claim_ratio=source_backed_claim_ratio,
        claims_without_sources=claims_without_sources,
        nodes_by_kind=nodes_by_kind,
        edges_by_kind=edges_by_kind,
    )


# Import GraphIndex lazily to avoid circular imports
from cc_deep_research.knowledge.graph_index import GraphIndex

__all__ = [
    "GraphHealthMetrics",
    "compute_graph_metrics",
    "duplicate_node_candidates",
    "orphaned_nodes",
]
