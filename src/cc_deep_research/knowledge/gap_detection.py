"""Knowledge gap detection for the knowledge vault.

Scans the knowledge graph to identify weak areas and knowledge gaps,
surfacing them as GapCandidate objects that operators can review,
accept, dismiss, defer, or resolve.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path

from cc_deep_research.knowledge import (
    EdgeKind,
    KnowledgeEdge,
    KnowledgeNode,
    NodeKind,
)
from cc_deep_research.knowledge.graph_index import GraphIndex
from cc_deep_research.knowledge.health import orphaned_nodes
from cc_deep_research.knowledge.vault import graph_dir

# ---------------------------------------------------------------------------
# Types
# ---------------------------------------------------------------------------


class GapReason(StrEnum):
    """Reason why a gap was detected."""

    LOW_SOURCE_COUNT = "low_source_count"
    STALE_COVERAGE = "stale_coverage"
    CONTRADICTORY_CLAIMS = "contradictory_claims"
    MISSING_PROVENANCE = "missing_provenance"
    FAILED_RETRIEVAL = "failed_retrieval"
    SPARSE_ENTITY = "sparse_entity"
    ORPHAN_NODE = "orphan_node"


class GapStatus(StrEnum):
    """Status of a gap candidate."""

    DETECTED = "detected"
    ACCEPTED = "accepted"
    DISMISSED = "dismissed"
    DEFERRED = "deferred"
    RESOLVED = "resolved"


@dataclass
class GapCandidate:
    """A detected gap in the knowledge graph."""

    id: str
    node_id: str | None
    gap_type: GapReason
    description: str
    evidence: dict
    suggested_queries: list[str]
    status: GapStatus
    created_at: datetime
    resolved_at: datetime | None = None

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "node_id": self.node_id,
            "gap_type": self.gap_type.value,
            "description": self.description,
            "evidence": self.evidence,
            "suggested_queries": self.suggested_queries,
            "status": self.status.value,
            "created_at": self.created_at.isoformat(),
            "resolved_at": self.resolved_at.isoformat() if self.resolved_at else None,
        }

    @classmethod
    def from_dict(cls, data: dict) -> GapCandidate:
        status_val = data.get("status", GapStatus.DETECTED.value)
        try:
            status = GapStatus(status_val)
        except ValueError:
            status = GapStatus.DETECTED

        gap_type_val = data.get("gap_type", "")
        try:
            gap_type = GapReason(gap_type_val)
        except ValueError:
            gap_type = GapReason.SPARSE_ENTITY

        resolved_at = None
        if data.get("resolved_at"):
            try:
                resolved_at = datetime.fromisoformat(data["resolved_at"])
            except (ValueError, TypeError):
                resolved_at = None

        return cls(
            id=data["id"],
            node_id=data.get("node_id"),
            gap_type=gap_type,
            description=data.get("description", ""),
            evidence=data.get("evidence", {}),
            suggested_queries=data.get("suggested_queries", []),
            status=status,
            created_at=datetime.fromisoformat(data["created_at"]),
            resolved_at=resolved_at,
        )


# ---------------------------------------------------------------------------
# GapStore
# ---------------------------------------------------------------------------


class GapStore:
    """Persists gap candidates in graph/gap_store.json."""

    def __init__(self, store_path: Path | None = None) -> None:
        if store_path is None:
            store_path = graph_dir() / "gap_store.json"
        self._path = store_path
        self._gaps: list[GapCandidate] = []
        self._load()

    def _load(self) -> None:
        """Load gaps from the JSON file."""
        if not self._path.exists():
            self._gaps = []
            return

        try:
            data = json.loads(self._path.read_text(encoding="utf-8"))
            self._gaps = [GapCandidate.from_dict(g) for g in data.get("gaps", [])]
        except (json.JSONDecodeError, KeyError, ValueError):
            self._gaps = []

    def _save(self) -> None:
        """Persist gaps to the JSON file."""
        self._path.parent.mkdir(parents=True, exist_ok=True)
        data = {"gaps": [g.to_dict() for g in self._gaps]}
        self._path.write_text(json.dumps(data, indent=2), encoding="utf-8")

    def get_gaps(self, status: GapStatus | None = None) -> list[GapCandidate]:
        """Get all gaps, optionally filtered by status."""
        if status is None:
            return list(self._gaps)
        return [g for g in self._gaps if g.status == status]

    def gap(self, gap_id: str) -> GapCandidate | None:
        """Get a specific gap by ID."""
        for g in self._gaps:
            if g.id == gap_id:
                return g
        return None

    def add_gap(self, gap: GapCandidate) -> None:
        """Add a new gap candidate if it doesn't already exist."""
        existing_ids = {g.id for g in self._gaps}
        if gap.id in existing_ids:
            return
        self._gaps.append(gap)
        self._save()

    def update_status(
        self,
        gap_id: str,
        new_status: GapStatus,
    ) -> bool:
        """Update the status of a gap candidate.

        When a gap is resolved, sets resolved_at timestamp.
        Returns True if the gap was found and updated.
        """
        for gap in self._gaps:
            if gap.id == gap_id:
                gap.status = new_status
                if new_status == GapStatus.RESOLVED:
                    gap.resolved_at = datetime.now(UTC)
                elif new_status == GapStatus.ACCEPTED:
                    # Clear any previous resolved_at when re-accepting
                    gap.resolved_at = None
                self._save()
                return True
        return False

    def get_accepted_gaps(self) -> list[GapCandidate]:
        """Get gaps with ACCEPTED status ready for follow-up research."""
        return [g for g in self._gaps if g.status == GapStatus.ACCEPTED]

    def get_detected_gaps(self) -> list[GapCandidate]:
        """Get gaps with DETECTED status not yet reviewed."""
        return [g for g in self._gaps if g.status == GapStatus.DETECTED]


# ---------------------------------------------------------------------------
# Gap detection logic
# ---------------------------------------------------------------------------


def _build_edge_count_map(edges: list[KnowledgeEdge]) -> dict[str, int]:
    """Build a map of node_id -> edge count (incoming + outgoing)."""
    counts: dict[str, int] = {}
    for edge in edges:
        counts[edge.source_id] = counts.get(edge.source_id, 0) + 1
        counts[edge.target_id] = counts.get(edge.target_id, 0) + 1
    return counts


def _build_cited_target_set(edges: list[KnowledgeEdge]) -> set[str]:
    """Build set of node IDs that are targets of CITED edges."""
    return {e.target_id for e in edges if e.kind == EdgeKind.CITED}


def _detect_low_source_count_gaps(
    nodes: list[KnowledgeNode],
    cited_targets: set[str],
) -> list[GapCandidate]:
    """Detect claims with no sources backing them.

    A claim is considered unsourced if it is not a target of any CITED edge
    and has confidence < 0.5.
    """
    gaps: list[GapCandidate] = []

    for node in nodes:
        if node.kind != NodeKind.CLAIM:
            continue

        # Skip if it has source backing
        if node.id in cited_targets:
            continue

        confidence = node.properties.get("confidence", 0.5)
        if confidence >= 0.5:
            # Has reasonable confidence, not a gap
            continue

        label = node.label or "unknown claim"
        gap = GapCandidate(
            id=f"gap:low_source:{node.id}",
            node_id=node.id,
            gap_type=GapReason.LOW_SOURCE_COUNT,
            description=f"Claim '{label[:80]}' has no supporting sources and low confidence ({confidence:.2f})",
            evidence={
                "node_id": node.id,
                "confidence": confidence,
                "has_cited_source": False,
            },
            suggested_queries=[f"Find sources for: {label[:100]}"],
            status=GapStatus.DETECTED,
            created_at=datetime.now(UTC),
        )
        gaps.append(gap)

    return gaps


def _detect_stale_coverage_gaps(
    nodes: list[KnowledgeNode],
) -> list[GapCandidate]:
    """Detect claims marked as 'dated' (stale time sensitivity)."""
    gaps: list[GapCandidate] = []

    for node in nodes:
        if node.kind != NodeKind.CLAIM:
            continue

        freshness = node.properties.get("freshness", "")
        if freshness != "dated":
            continue

        label = node.label or "unknown claim"
        gap = GapCandidate(
            id=f"gap:stale:{node.id}",
            node_id=node.id,
            gap_type=GapReason.STALE_COVERAGE,
            description=f"Claim '{label[:80]}' is marked as dated/stale and may be outdated",
            evidence={
                "node_id": node.id,
                "freshness": freshness,
                "confidence": node.properties.get("confidence", 0.5),
            },
            suggested_queries=[f"Investigate current status of: {label[:100]}"],
            status=GapStatus.DETECTED,
            created_at=datetime.now(UTC),
        )
        gaps.append(gap)

    return gaps


def _detect_contradictory_claims_gaps(
    nodes: list[KnowledgeNode],
    edges: list[KnowledgeEdge],
) -> list[GapCandidate]:
    """Detect pairs of claims that contradict each other via CONTRADICTS edges."""
    gaps: list[GapCandidate] = []

    # Build CONTRADICTS edge map: source_id -> list of target_ids it contradicts
    contradicts_map: dict[str, list[str]] = {}
    for edge in edges:
        if edge.kind == EdgeKind.CONTRADICTS:
            contradicts_map.setdefault(edge.source_id, []).append(edge.target_id)
            contradicts_map.setdefault(edge.target_id, []).append(edge.source_id)

    # Build node_id -> label map
    node_labels: dict[str, str] = {n.id: n.label or "unknown" for n in nodes}

    seen_pairs: set[tuple[str, ...]] = set()
    for source_id, target_ids in contradicts_map.items():
        for target_id in target_ids:
            pair = tuple(sorted([source_id, target_id]))
            if pair in seen_pairs:
                continue
            seen_pairs.add(pair)

            label_a = node_labels.get(source_id, "unknown")
            label_b = node_labels.get(target_id, "unknown")

            gap = GapCandidate(
                id=f"gap:contradicts:{source_id}:{target_id}",
                node_id=source_id,
                gap_type=GapReason.CONTRADICTORY_CLAIMS,
                description=f"Contradictory claims detected: '{label_a[:60]}' vs '{label_b[:60]}'",
                evidence={
                    "conflicting_node_ids": [source_id, target_id],
                    "claim_a_label": label_a[:200],
                    "claim_b_label": label_b[:200],
                },
                suggested_queries=[
                    f"Resolve contradiction between: {label_a[:80]}",
                    f"Find authoritative source for: {label_a[:60]} vs {label_b[:60]}",
                ],
                status=GapStatus.DETECTED,
                created_at=datetime.now(UTC),
            )
            gaps.append(gap)

    return gaps


def _detect_missing_provenance_gaps(
    nodes: list[KnowledgeNode],
) -> list[GapCandidate]:
    """Detect nodes missing session_ids or source_ids provenance metadata.

    Considers session, claim, finding, entity, and concept nodes that should
    have at least one session_id or source_id.
    """
    gaps: list[GapCandidate] = []

    provenance_kinds = {
        NodeKind.SESSION,
        NodeKind.CLAIM,
        NodeKind.FINDING,
        NodeKind.ENTITY,
        NodeKind.CONCEPT,
    }

    for node in nodes:
        if node.kind not in provenance_kinds:
            continue

        session_ids = node.properties.get("session_ids", [])
        source_ids = node.properties.get("source_ids", [])

        # Check if provenance is missing
        has_session = bool(session_ids) and session_ids != []
        has_source = bool(source_ids) and source_ids != []

        if has_session or has_source:
            continue

        label = node.label or "unknown node"
        kind_label = node.kind.value

        gap = GapCandidate(
            id=f"gap:provenance:{node.id}",
            node_id=node.id,
            gap_type=GapReason.MISSING_PROVENANCE,
            description=f"{kind_label.title()} '{label[:80]}' has no session_ids or source_ids recorded",
            evidence={
                "node_id": node.id,
                "kind": node.kind.value,
                "has_session_ids": has_session,
                "has_source_ids": has_source,
            },
            suggested_queries=[f"Add provenance tracking for: {label[:100]}"],
            status=GapStatus.DETECTED,
            created_at=datetime.now(UTC),
        )
        gaps.append(gap)

    return gaps


def _detect_sparse_entity_gaps(
    nodes: list[KnowledgeNode],
    edge_counts: dict[str, int],
) -> list[GapCandidate]:
    """Detect entities/concepts with fewer than 2 edges (sparse connections)."""
    gaps: list[GapCandidate] = []

    sparse_kinds = {NodeKind.ENTITY, NodeKind.CONCEPT}

    for node in nodes:
        if node.kind not in sparse_kinds:
            continue

        edge_count = edge_counts.get(node.id, 0)
        if edge_count >= 2:
            continue

        label = node.label or "unknown entity"
        kind_label = node.kind.value

        gap = GapCandidate(
            id=f"gap:sparse:{node.id}",
            node_id=node.id,
            gap_type=GapReason.SPARSE_ENTITY,
            description=f"{kind_label.title()} '{label[:80]}' has only {edge_count} connection(s) — may be under-explored",
            evidence={
                "node_id": node.id,
                "kind": node.kind.value,
                "edge_count": edge_count,
            },
            suggested_queries=[f"Investigate {kind_label} coverage: {label[:100]}"],
            status=GapStatus.DETECTED,
            created_at=datetime.now(UTC),
        )
        gaps.append(gap)

    return gaps


def _detect_orphan_node_gaps(
    nodes: list[KnowledgeNode],
    edges: list[KnowledgeEdge],
) -> list[GapCandidate]:
    """Detect nodes with no edges at all (orphaned nodes)."""
    gaps: list[GapCandidate] = []

    orphans = orphaned_nodes(nodes, edges)

    for node in orphans:
        label = node.label or node.id
        kind_label = node.kind.value

        gap = GapCandidate(
            id=f"gap:orphan:{node.id}",
            node_id=node.id,
            gap_type=GapReason.ORPHAN_NODE,
            description=f"{kind_label.title()} '{label[:80]}' has no connections in the graph",
            evidence={
                "node_id": node.id,
                "kind": node.kind.value,
                "edge_count": 0,
            },
            suggested_queries=[f"Connect orphaned node: {label[:100]}"],
            status=GapStatus.DETECTED,
            created_at=datetime.now(UTC),
        )
        gaps.append(gap)

    return gaps


def detect_gaps(index: GraphIndex) -> list[GapCandidate]:
    """Scan the graph index for knowledge gaps.

    Runs all gap detectors and returns a combined list of GapCandidate objects.
    This is a non-blocking scan — it does not modify the graph.

    Gap types detected:
    - LOW_SOURCE_COUNT: claims with no CITED incoming edges and confidence < 0.5
    - STALE_COVERAGE: claims with freshness = 'dated'
    - CONTRADICTORY_CLAIMS: pairs of claims connected by CONTRADICTS edges
    - MISSING_PROVENANCE: nodes (session/claim/finding/entity/concept) missing session_ids and source_ids
    - SPARSE_ENTITY: entity/concept nodes with fewer than 2 edges
    - ORPHAN_NODE: nodes with zero edges (using orphaned_nodes from health.py)

    Returns:
        List of GapCandidate objects, one per detected gap.
    """
    if index._conn is None:
        return []

    all_nodes = index.all_nodes()
    all_edges = index.all_edges()

    if not all_nodes:
        return []

    cited_targets = _build_cited_target_set(all_edges)
    edge_counts = _build_edge_count_map(all_edges)

    all_gaps: list[GapCandidate] = []

    all_gaps.extend(_detect_low_source_count_gaps(all_nodes, cited_targets))
    all_gaps.extend(_detect_stale_coverage_gaps(all_nodes))
    all_gaps.extend(_detect_contradictory_claims_gaps(all_nodes, all_edges))
    all_gaps.extend(_detect_missing_provenance_gaps(all_nodes))
    all_gaps.extend(_detect_sparse_entity_gaps(all_nodes, edge_counts))
    all_gaps.extend(_detect_orphan_node_gaps(all_nodes, all_edges))

    # Deduplicate by gap ID
    seen_ids: set[str] = set()
    unique_gaps: list[GapCandidate] = []
    for gap in all_gaps:
        if gap.id not in seen_ids:
            seen_ids.add(gap.id)
            unique_gaps.append(gap)

    return unique_gaps


__all__ = [
    "GapCandidate",
    "GapReason",
    "GapStatus",
    "GapStore",
    "detect_gaps",
]
