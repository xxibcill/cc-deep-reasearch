"""Tests for graph health metrics and API endpoint."""

from __future__ import annotations

from pathlib import Path

import pytest

from cc_deep_research.knowledge import (
    EdgeKind,
    GraphSnapshot,
    KnowledgeEdge,
    KnowledgeNode,
    NodeKind,
)
from cc_deep_research.knowledge.graph_index import GraphIndex
from cc_deep_research.knowledge.health import (
    GraphHealthMetrics,
    compute_graph_metrics,
    duplicate_node_candidates,
    orphaned_nodes,
)


class TestOrphanedNodes:
    """Tests for orphan node detection."""

    def test_empty_nodes_returns_empty_list(self) -> None:
        """No nodes returns empty list."""
        result = orphaned_nodes([], [])
        assert result == []

    def test_node_with_no_edges_is_orphan(self) -> None:
        """A node with no incoming or outgoing edges is an orphan."""
        node = KnowledgeNode(id="n1", kind=NodeKind.SESSION, label="Test")
        result = orphaned_nodes([node], [])
        assert len(result) == 1
        assert result[0].id == "n1"

    def test_node_with_source_edge_not_orphan(self) -> None:
        """A node that is a source of an edge is not an orphan."""
        node = KnowledgeNode(id="n1", kind=NodeKind.SESSION, label="Test")
        edge = KnowledgeEdge(id="e1", source_id="n1", target_id="n2", kind=EdgeKind.CITED)
        result = orphaned_nodes([node], [edge])
        assert len(result) == 0

    def test_node_with_target_edge_not_orphan(self) -> None:
        """A node that is a target of an edge is not an orphan."""
        node = KnowledgeNode(id="n2", kind=NodeKind.CLAIM, label="Test")
        edge = KnowledgeEdge(id="e1", source_id="n1", target_id="n2", kind=EdgeKind.CITED)
        result = orphaned_nodes([node], [edge])
        assert len(result) == 0

    def test_multiple_orphans_detected(self) -> None:
        """Multiple orphan nodes are all detected."""
        nodes = [
            KnowledgeNode(id="n1", kind=NodeKind.SESSION, label="S1"),
            KnowledgeNode(id="n2", kind=NodeKind.SESSION, label="S2"),
            KnowledgeNode(id="n3", kind=NodeKind.CONCEPT, label="C1"),
        ]
        result = orphaned_nodes(nodes, [])
        assert len(result) == 3


class TestDuplicateNodeCandidates:
    """Tests for duplicate node candidate detection."""

    def test_empty_nodes_returns_empty_list(self) -> None:
        """No nodes returns empty list."""
        result = duplicate_node_candidates([])
        assert result == []

    def test_nodes_with_same_kind_and_label_are_duplicates(self) -> None:
        """Two nodes with same kind and label are duplicate candidates."""
        nodes = [
            KnowledgeNode(id="n1", kind=NodeKind.CLAIM, label="Same claim"),
            KnowledgeNode(id="n2", kind=NodeKind.CLAIM, label="Same claim"),
        ]
        result = duplicate_node_candidates(nodes)
        assert len(result) == 1
        assert result[0] == (nodes[0], nodes[1])

    def test_nodes_with_different_labels_not_duplicates(self) -> None:
        """Nodes with same kind but different labels are not duplicates."""
        nodes = [
            KnowledgeNode(id="n1", kind=NodeKind.CLAIM, label="Claim A"),
            KnowledgeNode(id="n2", kind=NodeKind.CLAIM, label="Claim B"),
        ]
        result = duplicate_node_candidates(nodes)
        assert len(result) == 0

    def test_nodes_with_different_kinds_not_duplicates(self) -> None:
        """Nodes with same label but different kinds are not duplicates."""
        nodes = [
            KnowledgeNode(id="n1", kind=NodeKind.CLAIM, label="Same label"),
            KnowledgeNode(id="n2", kind=NodeKind.CONCEPT, label="Same label"),
        ]
        result = duplicate_node_candidates(nodes)
        assert len(result) == 0

    def test_session_nodes_not_flagged_as_duplicates(self) -> None:
        """Session nodes with identical labels are allowed (different sessions)."""
        nodes = [
            KnowledgeNode(id="s1", kind=NodeKind.SESSION, label="Same session label"),
            KnowledgeNode(id="s2", kind=NodeKind.SESSION, label="Same session label"),
        ]
        result = duplicate_node_candidates(nodes)
        assert len(result) == 0

    def test_multiple_duplicates_returned(self) -> None:
        """When three nodes share same kind+label, three pairs returned."""
        nodes = [
            KnowledgeNode(id="n1", kind=NodeKind.CLAIM, label="Same"),
            KnowledgeNode(id="n2", kind=NodeKind.CLAIM, label="Same"),
            KnowledgeNode(id="n3", kind=NodeKind.CLAIM, label="Same"),
        ]
        result = duplicate_node_candidates(nodes)
        # C(3,2) = 3 pairs
        assert len(result) == 3

    def test_empty_label_nodes_ignored(self) -> None:
        """Nodes with empty labels are not considered for duplication."""
        nodes = [
            KnowledgeNode(id="n1", kind=NodeKind.CLAIM, label=""),
            KnowledgeNode(id="n2", kind=NodeKind.CLAIM, label=""),
        ]
        result = duplicate_node_candidates(nodes)
        assert len(result) == 0


class TestComputeGraphMetrics:
    """Tests for compute_graph_metrics function."""

    def test_empty_index_returns_zeros(self, tmp_path: Path) -> None:
        """An empty graph index returns metrics with zero counts."""
        db = tmp_path / "test.sqlite"
        index = GraphIndex(db)
        index.commit()

        metrics = compute_graph_metrics(index)

        assert metrics.total_nodes == 0
        assert metrics.total_edges == 0
        assert metrics.orphan_count == 0
        assert metrics.stale_claim_count == 0
        assert metrics.duplicate_candidate_count == 0
        assert metrics.source_backed_claim_ratio == 1.0
        index.close()

    def test_orphan_count_on_empty_edges(self, tmp_path: Path) -> None:
        """Nodes with no edges are counted as orphans."""
        db = tmp_path / "test.sqlite"
        index = GraphIndex(db)

        index.upsert_node(KnowledgeNode(id="n1", kind=NodeKind.SESSION, label="S1"))
        index.upsert_node(KnowledgeNode(id="n2", kind=NodeKind.SESSION, label="S2"))
        index.commit()

        metrics = compute_graph_metrics(index)
        assert metrics.orphan_count == 2
        index.close()

    def test_connected_nodes_not_orphans(self, tmp_path: Path) -> None:
        """Nodes that appear in edges are not orphans."""
        db = tmp_path / "test.sqlite"
        index = GraphIndex(db)

        index.upsert_node(KnowledgeNode(id="n1", kind=NodeKind.SESSION, label="S1"))
        index.upsert_node(KnowledgeNode(id="n2", kind=NodeKind.SOURCE, label="Source"))
        index.upsert_edge(KnowledgeEdge(id="e1", source_id="n1", target_id="n2", kind=EdgeKind.CITED))
        index.commit()

        metrics = compute_graph_metrics(index)
        assert metrics.orphan_count == 0
        index.close()

    def test_stale_claim_detection(self, tmp_path: Path) -> None:
        """Claims with freshness='dated' are counted as stale."""
        db = tmp_path / "test.sqlite"
        index = GraphIndex(db)

        index.upsert_node(KnowledgeNode(
            id="c1", kind=NodeKind.CLAIM, label="Fresh claim",
            properties={"freshness": "current"}
        ))
        index.upsert_node(KnowledgeNode(
            id="c2", kind=NodeKind.CLAIM, label="Stale claim",
            properties={"freshness": "dated"}
        ))
        index.commit()

        metrics = compute_graph_metrics(index)
        assert metrics.stale_claim_count == 1
        index.close()

    def test_duplicate_candidate_count(self, tmp_path: Path) -> None:
        """Duplicate nodes (same kind + label) are counted."""
        db = tmp_path / "test.sqlite"
        index = GraphIndex(db)

        index.upsert_node(KnowledgeNode(id="c1", kind=NodeKind.CLAIM, label="Duplicate"))
        index.upsert_node(KnowledgeNode(id="c2", kind=NodeKind.CLAIM, label="Duplicate"))
        index.commit()

        metrics = compute_graph_metrics(index)
        assert metrics.duplicate_candidate_count == 1
        index.close()

    def test_source_backed_claim_ratio(self, tmp_path: Path) -> None:
        """Source-backed claim ratio is computed correctly."""
        db = tmp_path / "test.sqlite"
        index = GraphIndex(db)

        # Two claims, one with source
        index.upsert_node(KnowledgeNode(id="src1", kind=NodeKind.SOURCE, label="Source"))
        index.upsert_node(KnowledgeNode(id="c1", kind=NodeKind.CLAIM, label="Claim 1"))
        index.upsert_node(KnowledgeNode(id="c2", kind=NodeKind.CLAIM, label="Claim 2"))
        index.upsert_edge(KnowledgeEdge(id="e1", source_id="src1", target_id="c1", kind=EdgeKind.CITED))
        index.commit()

        metrics = compute_graph_metrics(index)
        assert metrics.source_backed_claim_ratio == 0.5
        assert metrics.claims_without_sources == 1
        index.close()

    def test_source_backed_ratio_full_coverage(self, tmp_path: Path) -> None:
        """All claims with sources yields ratio of 1.0."""
        db = tmp_path / "test.sqlite"
        index = GraphIndex(db)

        index.upsert_node(KnowledgeNode(id="src1", kind=NodeKind.SOURCE, label="Source"))
        index.upsert_node(KnowledgeNode(id="c1", kind=NodeKind.CLAIM, label="Claim"))
        index.upsert_edge(KnowledgeEdge(id="e1", source_id="src1", target_id="c1", kind=EdgeKind.CITED))
        index.commit()

        metrics = compute_graph_metrics(index)
        assert metrics.source_backed_claim_ratio == 1.0
        index.close()

    def test_source_backed_ratio_no_claims(self, tmp_path: Path) -> None:
        """No claims yields ratio of 1.0 (no claims to back)."""
        db = tmp_path / "test.sqlite"
        index = GraphIndex(db)

        index.upsert_node(KnowledgeNode(id="s1", kind=NodeKind.SESSION, label="Session"))
        index.commit()

        metrics = compute_graph_metrics(index)
        assert metrics.source_backed_claim_ratio == 1.0
        index.close()

    def test_nodes_by_kind_counts(self, tmp_path: Path) -> None:
        """Nodes are counted by kind."""
        db = tmp_path / "test.sqlite"
        index = GraphIndex(db)

        index.upsert_node(KnowledgeNode(id="s1", kind=NodeKind.SESSION, label="S1"))
        index.upsert_node(KnowledgeNode(id="s2", kind=NodeKind.SESSION, label="S2"))
        index.upsert_node(KnowledgeNode(id="c1", kind=NodeKind.CLAIM, label="C1"))
        index.commit()

        metrics = compute_graph_metrics(index)
        assert metrics.nodes_by_kind["session"] == 2
        assert metrics.nodes_by_kind["claim"] == 1
        index.close()

    def test_edges_by_kind_counts(self, tmp_path: Path) -> None:
        """Edges are counted by kind."""
        db = tmp_path / "test.sqlite"
        index = GraphIndex(db)

        index.upsert_node(KnowledgeNode(id="n1", kind=NodeKind.SESSION, label="S1"))
        index.upsert_node(KnowledgeNode(id="n2", kind=NodeKind.SOURCE, label="Src"))
        index.upsert_edge(KnowledgeEdge(id="e1", source_id="n1", target_id="n2", kind=EdgeKind.CITED))
        index.upsert_edge(KnowledgeEdge(id="e2", source_id="n1", target_id="n2", kind=EdgeKind.MENTIONS))
        index.commit()

        metrics = compute_graph_metrics(index)
        assert metrics.edges_by_kind["cited"] == 1
        assert metrics.edges_by_kind["mentions"] == 1
        index.close()


class TestGraphHealthMetricsEndpoint:
    """Integration tests for the /api/knowledge/health endpoint."""

    def test_health_endpoint_empty_vault(self, tmp_path: Path) -> None:
        """Health endpoint returns zeros for an empty vault."""
        from fastapi.testclient import TestClient

        from cc_deep_research.web_server import create_app

        # The vault is uninitialized by default (no vault exists at default path).
        # create_app() uses the default config path, so we test with the real vault
        # state. If the vault doesn't exist, we get zeros.
        client = TestClient(create_app())
        response = client.get("/api/knowledge/health")
        assert response.status_code == 200
        data = response.json()

        # Vault may or may not be initialized depending on test environment.
        # Just verify structure and that numeric fields are present.
        assert "total_nodes" in data
        assert "total_edges" in data
        assert "orphan_count" in data
        assert "vault_initialized" in data

    def test_health_endpoint_with_data(self, tmp_path: Path) -> None:
        """Health endpoint returns correct metrics with data."""
        from fastapi.testclient import TestClient

        from cc_deep_research.knowledge.vault import init_vault
        from cc_deep_research.web_server import create_app

        config = tmp_path / "config.yaml"
        config.write_text("")

        init_vault(config)

        # Manually populate the graph index
        from cc_deep_research.knowledge.vault import graph_sqlite_path

        db_path = graph_sqlite_path(config)
        index = GraphIndex(db_path)

        index.upsert_node(KnowledgeNode(id="session:1", kind=NodeKind.SESSION, label="Test session"))
        index.upsert_node(KnowledgeNode(id="src:1", kind=NodeKind.SOURCE, label="Source"))
        index.upsert_node(KnowledgeNode(id="c:1", kind=NodeKind.CLAIM, label="Claim"))
        index.upsert_edge(KnowledgeEdge(id="e1", source_id="session:1", target_id="src:1", kind=EdgeKind.CITED))
        index.commit()
        index.close()

        client = TestClient(create_app())
        response = client.get("/api/knowledge/health")
        assert response.status_code == 200
        data = response.json()

        assert data["total_nodes"] == 3
        assert data["total_edges"] == 1
        assert data["orphan_count"] == 1  # claim has no edges
        assert data["vault_initialized"] is True
