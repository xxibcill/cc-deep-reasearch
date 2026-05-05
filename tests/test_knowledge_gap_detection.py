"""Tests for knowledge gap detection."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest

from cc_deep_research.knowledge import (
    EdgeKind,
    KnowledgeEdge,
    KnowledgeNode,
    NodeKind,
)
from cc_deep_research.knowledge.gap_detection import (
    GapCandidate,
    GapReason,
    GapStatus,
    GapStore,
    _build_cited_target_set,
    _build_edge_count_map,
    _detect_contradictory_claims_gaps,
    _detect_low_source_count_gaps,
    _detect_missing_provenance_gaps,
    _detect_orphan_node_gaps,
    _detect_sparse_entity_gaps,
    _detect_stale_coverage_gaps,
    detect_gaps,
)
from cc_deep_research.knowledge.graph_index import GraphIndex


# ---------------------------------------------------------------------------
# Helper data classes
# ---------------------------------------------------------------------------


def _make_node(
    node_id: str,
    kind: NodeKind,
    label: str = "",
    properties: dict | None = None,
) -> KnowledgeNode:
    return KnowledgeNode(
        id=node_id,
        kind=kind,
        label=label,
        properties=properties or {},
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )


def _make_edge(
    edge_id: str,
    source_id: str,
    target_id: str,
    kind: EdgeKind,
) -> KnowledgeEdge:
    return KnowledgeEdge(
        id=edge_id,
        source_id=source_id,
        target_id=target_id,
        kind=kind,
    )


# ---------------------------------------------------------------------------
# Edge map building tests
# ---------------------------------------------------------------------------


class TestEdgeMapBuilding:
    """Tests for edge map helper functions."""

    def test_build_cited_target_set(self) -> None:
        """CITED edges populate the cited target set."""
        edges = [
            _make_edge("e1", "src:1", "claim:1", EdgeKind.CITED),
            _make_edge("e2", "src:2", "claim:1", EdgeKind.CITED),
            _make_edge("e3", "src:3", "claim:2", EdgeKind.MENTIONS),
        ]
        targets = _build_cited_target_set(edges)
        assert targets == {"claim:1"}  # claim:2 is MENTIONS, not CITED

    def test_build_edge_count_map(self) -> None:
        """Edge count map counts both incoming and outgoing."""
        edges = [
            _make_edge("e1", "node:A", "node:B", EdgeKind.CITED),
            _make_edge("e2", "node:A", "node:C", EdgeKind.MENTIONS),
            _make_edge("e3", "node:D", "node:A", EdgeKind.SUPPORTS),
        ]
        counts = _build_edge_count_map(edges)
        assert counts["node:A"] == 3  # e1(out), e2(out), e3(in)
        assert counts["node:B"] == 1  # e1(in)
        assert counts["node:C"] == 1  # e2(in)
        assert counts["node:D"] == 1  # e3(out)


# ---------------------------------------------------------------------------
# LOW_SOURCE_COUNT gap detection
# ---------------------------------------------------------------------------


class TestLowSourceCountGaps:
    """Tests for low-source claim detection."""

    def test_claim_without_cited_source_is_gap(self) -> None:
        """Claim without incoming CITED edge and low confidence is a gap."""
        nodes = [
            _make_node("claim:1", NodeKind.CLAIM, "Global temps rising", {"confidence": 0.3}),
        ]
        cited_targets: set[str] = set()
        gaps = _detect_low_source_count_gaps(nodes, cited_targets)
        assert len(gaps) == 1
        assert gaps[0].gap_type == GapReason.LOW_SOURCE_COUNT
        assert gaps[0].node_id == "claim:1"

    def test_claim_with_cited_source_not_gap(self) -> None:
        """Claim that is a CITED target is not flagged."""
        nodes = [
            _make_node("claim:1", NodeKind.CLAIM, "Global temps rising", {"confidence": 0.3}),
        ]
        cited_targets = {"claim:1"}
        gaps = _detect_low_source_count_gaps(nodes, cited_targets)
        assert len(gaps) == 0

    def test_claim_with_high_confidence_not_gap(self) -> None:
        """Claim with confidence >= 0.5 is not flagged even if unsourced."""
        nodes = [
            _make_node("claim:1", NodeKind.CLAIM, "Global temps rising", {"confidence": 0.7}),
        ]
        cited_targets: set[str] = set()
        gaps = _detect_low_source_count_gaps(nodes, cited_targets)
        assert len(gaps) == 0

    def test_non_claim_nodes_ignored(self) -> None:
        """Non-claim nodes are not evaluated for low source count."""
        nodes = [
            _make_node("entity:1", NodeKind.ENTITY, "Earth"),
        ]
        cited_targets: set[str] = set()
        gaps = _detect_low_source_count_gaps(nodes, cited_targets)
        assert len(gaps) == 0


# ---------------------------------------------------------------------------
# STALE_COVERAGE gap detection
# ---------------------------------------------------------------------------


class TestStaleCoverageGaps:
    """Tests for stale coverage detection."""

    def test_dated_claim_is_gap(self) -> None:
        """Claim with freshness='dated' is a stale coverage gap."""
        nodes = [
            _make_node("claim:1", NodeKind.CLAIM, "Mars had water 2018", {"freshness": "dated"}),
        ]
        gaps = _detect_stale_coverage_gaps(nodes)
        assert len(gaps) == 1
        assert gaps[0].gap_type == GapReason.STALE_COVERAGE
        assert gaps[0].node_id == "claim:1"

    def test_current_claim_not_gap(self) -> None:
        """Claim with freshness='current' is not a gap."""
        nodes = [
            _make_node("claim:1", NodeKind.CLAIM, "Mars has water", {"freshness": "current"}),
        ]
        gaps = _detect_stale_coverage_gaps(nodes)
        assert len(gaps) == 0

    def test_claim_without_freshness_not_gap(self) -> None:
        """Claim without freshness property is not flagged."""
        nodes = [
            _make_node("claim:1", NodeKind.CLAIM, "Mars is red"),
        ]
        gaps = _detect_stale_coverage_gaps(nodes)
        assert len(gaps) == 0


# ---------------------------------------------------------------------------
# CONTRADICTORY_CLAIMS gap detection
# ---------------------------------------------------------------------------


class TestContradictoryClaimsGaps:
    """Tests for contradictory claims detection."""

    def test_contradicts_edge_creates_gap(self) -> None:
        """Two claims connected by CONTRADICTS edge are flagged as gap."""
        nodes = [
            _make_node("claim:1", NodeKind.CLAIM, "Climate change is real"),
            _make_node("claim:2", NodeKind.CLAIM, "Climate change is hoax"),
        ]
        edges = [
            _make_edge("e1", "claim:1", "claim:2", EdgeKind.CONTRADICTS),
        ]
        gaps = _detect_contradictory_claims_gaps(nodes, edges)
        assert len(gaps) >= 1
        gap = next(g for g in gaps if g.gap_type == GapReason.CONTRADICTORY_CLAIMS)
        assert "Climate change is real" in gap.description
        assert "Climate change is hoax" in gap.description

    def test_contradicts_edge_idempotent(self) -> None:
        """Duplicate CONTRADICTS edges between same pair produce one gap."""
        nodes = [
            _make_node("claim:1", NodeKind.CLAIM, "A"),
            _make_node("claim:2", NodeKind.CLAIM, "B"),
        ]
        edges = [
            _make_edge("e1", "claim:1", "claim:2", EdgeKind.CONTRADICTS),
            _make_edge("e2", "claim:2", "claim:1", EdgeKind.CONTRADICTS),
        ]
        gaps = _detect_contradictory_claims_gaps(nodes, edges)
        contradictory = [g for g in gaps if g.gap_type == GapReason.CONTRADICTORY_CLAIMS]
        # Should be exactly one gap (pair deduplicated)
        assert len(contradictory) == 1


# ---------------------------------------------------------------------------
# MISSING_PROVENANCE gap detection
# ---------------------------------------------------------------------------


class TestMissingProvenanceGaps:
    """Tests for missing provenance detection."""

    def test_claim_without_session_or_source_ids(self) -> None:
        """Claim with no session_ids and no source_ids is flagged."""
        nodes = [
            _make_node("claim:1", NodeKind.CLAIM, "Test claim"),
        ]
        gaps = _detect_missing_provenance_gaps(nodes)
        assert len(gaps) == 1
        assert gaps[0].gap_type == GapReason.MISSING_PROVENANCE

    def test_claim_with_session_ids_not_gap(self) -> None:
        """Claim with session_ids is not flagged."""
        nodes = [
            _make_node("claim:1", NodeKind.CLAIM, "Test claim", {"session_ids": ["sess:1"]}),
        ]
        gaps = _detect_missing_provenance_gaps(nodes)
        assert len(gaps) == 0

    def test_claim_with_source_ids_not_gap(self) -> None:
        """Claim with source_ids is not flagged."""
        nodes = [
            _make_node("claim:1", NodeKind.CLAIM, "Test claim", {"source_ids": ["src:1"]}),
        ]
        gaps = _detect_missing_provenance_gaps(nodes)
        assert len(gaps) == 0

    def test_entity_without_provenance(self) -> None:
        """Entity without session_ids is flagged."""
        nodes = [
            _make_node("entity:1", NodeKind.ENTITY, "Test Entity"),
        ]
        gaps = _detect_missing_provenance_gaps(nodes)
        assert len(gaps) == 1

    def test_source_node_not_checked(self) -> None:
        """SOURCE nodes are not checked for provenance."""
        nodes = [
            _make_node("src:1", NodeKind.SOURCE, "Test Source", {"url": "https://example.com"}),
        ]
        gaps = _detect_missing_provenance_gaps(nodes)
        assert len(gaps) == 0


# ---------------------------------------------------------------------------
# SPARSE_ENTITY gap detection
# ---------------------------------------------------------------------------


class TestSparseEntityGaps:
    """Tests for sparse entity detection."""

    def test_entity_with_one_edge_is_gap(self) -> None:
        """Entity with fewer than 2 edges is a gap."""
        nodes = [
            _make_node("entity:1", NodeKind.ENTITY, "Sparse Entity"),
        ]
        edge_counts = {"entity:1": 1}
        gaps = _detect_sparse_entity_gaps(nodes, edge_counts)
        assert len(gaps) == 1
        assert gaps[0].gap_type == GapReason.SPARSE_ENTITY
        assert gaps[0].evidence["edge_count"] == 1

    def test_entity_with_two_edges_not_gap(self) -> None:
        """Entity with 2+ edges is not flagged."""
        nodes = [
            _make_node("entity:1", NodeKind.ENTITY, "Connected Entity"),
        ]
        edge_counts = {"entity:1": 3}
        gaps = _detect_sparse_entity_gaps(nodes, edge_counts)
        assert len(gaps) == 0

    def test_claim_node_not_checked(self) -> None:
        """CLAIM nodes are not checked for sparsity."""
        nodes = [
            _make_node("claim:1", NodeKind.CLAIM, "Test claim"),
        ]
        edge_counts: dict[str, int] = {}
        gaps = _detect_sparse_entity_gaps(nodes, edge_counts)
        assert len(gaps) == 0


# ---------------------------------------------------------------------------
# ORPHAN_NODE gap detection
# ---------------------------------------------------------------------------


class TestOrphanNodeGaps:
    """Tests for orphan node detection."""

    def test_node_with_no_edges_is_orphan(self) -> None:
        """Node with zero edges is flagged."""
        nodes = [
            _make_node("orphan:1", NodeKind.CLAIM, "Orphaned claim"),
            _make_node("connected:1", NodeKind.SOURCE, "Connected source"),
        ]
        edges = [
            _make_edge("e1", "connected:1", "claim:ref", EdgeKind.CITED),
        ]
        gaps = _detect_orphan_node_gaps(nodes, edges)
        assert len(gaps) == 1
        assert gaps[0].node_id == "orphan:1"

    def test_connected_node_not_gap(self) -> None:
        """Node that participates in edges is not flagged."""
        nodes = [
            _make_node("node:1", NodeKind.SOURCE, "Source"),
            _make_node("node:2", NodeKind.CLAIM, "Claim"),
        ]
        edges = [
            _make_edge("e1", "node:1", "node:2", EdgeKind.CITED),
        ]
        gaps = _detect_orphan_node_gaps(nodes, edges)
        assert len(gaps) == 0


# ---------------------------------------------------------------------------
# GapStore tests
# ---------------------------------------------------------------------------


class TestGapStore:
    """Tests for GapStore."""

    def test_empty_store(self, tmp_path: Path) -> None:
        """Empty store initializes correctly."""
        store_path = tmp_path / "gaps.json"
        store = GapStore(store_path)
        assert store.get_gaps() == []

    def test_add_and_retrieve_gap(self, tmp_path: Path) -> None:
        """Adding a gap makes it retrievable."""
        store_path = tmp_path / "gaps.json"
        store = GapStore(store_path)

        gap = GapCandidate(
            id="gap:test:1",
            node_id="node:1",
            gap_type=GapReason.ORPHAN_NODE,
            description="Test gap",
            evidence={"node_id": "node:1"},
            suggested_queries=["Test query"],
            status=GapStatus.DETECTED,
            created_at=datetime.now(UTC),
        )

        store.add_gap(gap)
        retrieved = store.get_gaps()

        assert len(retrieved) == 1
        assert retrieved[0].id == "gap:test:1"

    def test_update_status(self, tmp_path: Path) -> None:
        """Updating status works correctly."""
        store_path = tmp_path / "gaps.json"
        store = GapStore(store_path)

        gap = GapCandidate(
            id="gap:test:2",
            node_id="node:1",
            gap_type=GapReason.ORPHAN_NODE,
            description="Test gap",
            evidence={},
            suggested_queries=[],
            status=GapStatus.DETECTED,
            created_at=datetime.now(UTC),
        )

        store.add_gap(gap)

        # Accept the gap
        result = store.update_status("gap:test:2", GapStatus.ACCEPTED)
        assert result is True
        assert store.gap("gap:test:2") is not None and store.gap("gap:test:2").status == GapStatus.ACCEPTED

        # Resolve the gap
        result = store.update_status("gap:test:2", GapStatus.RESOLVED)
        assert result is True
        resolved_gap = store.gap("gap:test:2")
        assert resolved_gap is not None and resolved_gap.status == GapStatus.RESOLVED
        assert resolved_gap is not None and resolved_gap.resolved_at is not None

    def test_get_accepted_gaps(self, tmp_path: Path) -> None:
        """get_accepted_gaps returns only accepted gaps."""
        store_path = tmp_path / "gaps.json"
        store = GapStore(store_path)

        for i in range(3):
            gap = GapCandidate(
                id=f"gap:accept:{i}",
                node_id=f"node:{i}",
                gap_type=GapReason.ORPHAN_NODE,
                description=f"Gap {i}",
                evidence={},
                suggested_queries=[],
                status=GapStatus.ACCEPTED if i < 2 else GapStatus.DETECTED,
                created_at=datetime.now(UTC),
            )
            store.add_gap(gap)

        accepted = store.get_accepted_gaps()
        assert len(accepted) == 2

    def test_dismissed_gaps_not_resurfaced(self, tmp_path: Path) -> None:
        """Dismissed gaps remain with dismissed status."""
        store_path = tmp_path / "gaps.json"
        store = GapStore(store_path)

        gap = GapCandidate(
            id="gap:dismiss:1",
            node_id="node:1",
            gap_type=GapReason.ORPHAN_NODE,
            description="Test gap",
            evidence={},
            suggested_queries=[],
            status=GapStatus.DETECTED,
            created_at=datetime.now(UTC),
        )
        store.add_gap(gap)

        store.update_status("gap:dismiss:1", GapStatus.DISMISSED)
        dismissed = store.get_gaps(GapStatus.DISMISSED)
        assert len(dismissed) == 1
        assert dismissed[0].status == GapStatus.DISMISSED

    def test_deferred_gaps_can_be_reactivated(self, tmp_path: Path) -> None:
        """Deferred gaps can be accepted or resolved later."""
        store_path = tmp_path / "gaps.json"
        store = GapStore(store_path)

        gap = GapCandidate(
            id="gap:defer:1",
            node_id="node:1",
            gap_type=GapReason.STALE_COVERAGE,
            description="Test gap",
            evidence={},
            suggested_queries=[],
            status=GapStatus.DETECTED,
            created_at=datetime.now(UTC),
        )
        store.add_gap(gap)

        store.update_status("gap:defer:1", GapStatus.DEFERRED)
        assert store.gap("gap:defer:1") is not None and store.gap("gap:defer:1").status == GapStatus.DEFERRED

        # Re-accept
        store.update_status("gap:defer:1", GapStatus.ACCEPTED)
        assert store.gap("gap:defer:1") is not None and store.gap("gap:defer:1").status == GapStatus.ACCEPTED

        # Then resolve
        store.update_status("gap:defer:1", GapStatus.RESOLVED)
        resolved = store.gap("gap:defer:1")
        assert resolved is not None and resolved.status == GapStatus.RESOLVED
        assert resolved is not None and resolved.resolved_at is not None

    def test_resolve_sets_resolved_at(self, tmp_path: Path) -> None:
        """Resolving a gap sets the resolved_at timestamp."""
        store_path = tmp_path / "gaps.json"
        store = GapStore(store_path)

        gap = GapCandidate(
            id="gap:resolve:1",
            node_id="node:1",
            gap_type=GapReason.LOW_SOURCE_COUNT,
            description="Test gap",
            evidence={},
            suggested_queries=[],
            status=GapStatus.ACCEPTED,
            created_at=datetime.now(UTC),
        )
        store.add_gap(gap)

        store.update_status("gap:resolve:1", GapStatus.RESOLVED)
        resolved_gap = store.gap("gap:resolve:1")
        assert resolved_gap is not None
        assert resolved_gap.resolved_at is not None


# ---------------------------------------------------------------------------
# detect_gaps integration tests
# ---------------------------------------------------------------------------


class TestDetectGaps:
    """Tests for the detect_gaps function."""

    def test_empty_graph_returns_empty(self, tmp_path: Path) -> None:
        """Empty graph produces no gaps."""
        db = tmp_path / "test.sqlite"
        index = GraphIndex(db)
        index.commit()

        gaps = detect_gaps(index)
        assert gaps == []

        index.close()

    def test_all_gap_types_detected(self, tmp_path: Path) -> None:
        """Mixed graph with multiple gap types produces corresponding gaps."""
        db = tmp_path / "test.sqlite"
        index = GraphIndex(db)

        # Orphan claim (no edges)
        index.upsert_node(_make_node("orphan:1", NodeKind.CLAIM, "Orphan claim"))

        # Low-source claim (no cited edge, low confidence)
        index.upsert_node(_make_node(
            "unsourced:1", NodeKind.CLAIM, "Unsourced claim",
            {"confidence": 0.3}
        ))

        # Stale claim
        index.upsert_node(_make_node(
            "stale:1", NodeKind.CLAIM, "Dated claim",
            {"freshness": "dated", "confidence": 0.6}
        ))

        # Sparse entity (only 1 edge)
        index.upsert_node(_make_node("sparse:1", NodeKind.ENTITY, "Sparse entity"))
        index.upsert_edge(_make_edge("sparse:e1", "sparse:1", "some:node", EdgeKind.MENTIONS))

        # Missing provenance entity (no session_ids)
        index.upsert_node(_make_node("noproven:1", NodeKind.CONCEPT, "No provenance concept"))

        # Contradictory pair
        index.upsert_node(_make_node("contra:a", NodeKind.CLAIM, "Claim A"))
        index.upsert_node(_make_node("contra:b", NodeKind.CLAIM, "Claim B"))
        index.upsert_edge(_make_edge("contra:e1", "contra:a", "contra:b", EdgeKind.CONTRADICTS))

        index.commit()

        gaps = detect_gaps(index)
        gap_types = {g.gap_type for g in gaps}

        assert GapReason.ORPHAN_NODE in gap_types
        assert GapReason.LOW_SOURCE_COUNT in gap_types
        assert GapReason.STALE_COVERAGE in gap_types
        assert GapReason.SPARSE_ENTITY in gap_types
        assert GapReason.CONTRADICTORY_CLAIMS in gap_types

        index.close()

    def test_gap_idempotency(self, tmp_path: Path) -> None:
        """Running detect_gaps twice returns same gaps (no duplicates)."""
        db = tmp_path / "test.sqlite"
        index = GraphIndex(db)

        index.upsert_node(_make_node(
            "unsourced:1", NodeKind.CLAIM, "Unsourced claim",
            {"confidence": 0.3}
        ))
        index.commit()

        first = detect_gaps(index)
        second = detect_gaps(index)

        # Same gap IDs returned
        first_ids = {g.id for g in first}
        second_ids = {g.id for g in second}
        assert first_ids == second_ids

        index.close()


# ---------------------------------------------------------------------------
# GapCandidate serialization tests
# ---------------------------------------------------------------------------


class TestGapCandidateSerialization:
    """Tests for GapCandidate to_dict/from_dict round-trip."""

    def test_round_trip(self) -> None:
        """GapCandidate survives to_dict -> from_dict round-trip."""
        original = GapCandidate(
            id="gap:round:1",
            node_id="node:1",
            gap_type=GapReason.STALE_COVERAGE,
            description="Test gap with special chars: '\"'",
            evidence={"key": "value", "count": 42},
            suggested_queries=["query 1", "query 2"],
            status=GapStatus.ACCEPTED,
            created_at=datetime.now(UTC),
            resolved_at=None,
        )

        data = original.to_dict()
        restored = GapCandidate.from_dict(data)

        assert restored.id == original.id
        assert restored.node_id == original.node_id
        assert restored.gap_type == original.gap_type
        assert restored.description == original.description
        assert restored.evidence == original.evidence
        assert restored.suggested_queries == original.suggested_queries
        assert restored.status == original.status
        assert restored.resolved_at is None

    def test_resolved_at_round_trip(self) -> None:
        """resolved_at is preserved through round-trip."""
        resolved_time = datetime.now(UTC)
        original = GapCandidate(
            id="gap:resolved:1",
            node_id=None,
            gap_type=GapReason.SPARSE_ENTITY,
            description="Test",
            evidence={},
            suggested_queries=[],
            status=GapStatus.RESOLVED,
            created_at=datetime.now(UTC),
            resolved_at=resolved_time,
        )

        data = original.to_dict()
        restored = GapCandidate.from_dict(data)

        assert restored.resolved_at is not None
        assert abs((restored.resolved_at - resolved_time).total_seconds()) < 1

    def test_unknown_status_defaults_to_detected(self) -> None:
        """Unknown status values default to DETECTED."""
        data = {
            "id": "gap:unknown:1",
            "node_id": None,
            "gap_type": "unknown_reason",
            "description": "Test",
            "evidence": {},
            "suggested_queries": [],
            "status": "unknown_status",
            "created_at": datetime.now(UTC).isoformat(),
        }
        gap = GapCandidate.from_dict(data)
        assert gap.status == GapStatus.DETECTED
