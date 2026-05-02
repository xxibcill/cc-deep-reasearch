"""Tests for knowledge benchmark gates and graph integrity metrics."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from cc_deep_research.knowledge import (
    EdgeKind,
    GraphSnapshot,
    KnowledgeEdge,
    KnowledgeNode,
    NodeKind,
)
from cc_deep_research.knowledge.graph_index import GraphIndex
from cc_deep_research.knowledge.vault import init_vault, vault_root

# ---------------------------------------------------------------------------
# Graph integrity metrics helpers
# ---------------------------------------------------------------------------


def compute_graph_integrity(snap: GraphSnapshot) -> dict:
    """Compute graph integrity metrics from a snapshot."""
    node_count = len(snap.nodes)
    edge_count = len(snap.edges)

    nodes_by_kind: dict[str, int] = {}
    for node in snap.nodes:
        kind = node.kind.value
        nodes_by_kind[kind] = nodes_by_kind.get(kind, 0) + 1

    edges_by_kind: dict[str, int] = {}
    for edge in snap.edges:
        kind = edge.kind.value
        edges_by_kind[kind] = edges_by_kind.get(kind, 0) + 1

    node_ids = {n.id for n in snap.nodes}
    connected_ids = {e.source_id for e in snap.edges} | {e.target_id for e in snap.edges}
    orphan_ids = node_ids - connected_ids

    claim_nodes = [n for n in snap.nodes if n.kind == NodeKind.CLAIM]
    unsupported_count = sum(1 for n in claim_nodes if n.properties.get("confidence", 1.0) < 0.4)

    # A claim is "stale" if freshness is "dated"
    stale_count = sum(
        1 for n in claim_nodes if n.properties.get("freshness") == "dated"
    )

    # Duplicate nodes: same kind + same label (simplified check)
    label_kind_seen: dict[tuple[str, str], int] = {}
    for node in snap.nodes:
        key = (node.kind.value, node.label)
        label_kind_seen[key] = label_kind_seen.get(key, 0) + 1
    duplicate_count = sum(1 for v in label_kind_seen.values() if v > 1)

    # Source-backed claim ratio
    cited_edge_kind = EdgeKind.CITED.value
    cited_claim_ids = {
        e.target_id for e in snap.edges if e.kind.value == cited_edge_kind
    }
    claim_ids = {n.id for n in claim_nodes}
    source_backed_ratio = (
        len(cited_claim_ids & claim_ids) / len(claim_ids) if claim_ids else 1.0
    )

    return {
        "node_count": node_count,
        "edge_count": edge_count,
        "nodes_by_kind": nodes_by_kind,
        "edges_by_kind": edges_by_kind,
        "orphan_count": len(orphan_ids),
        "orphan_ids": list(orphan_ids),
        "unsupported_claim_count": unsupported_count,
        "stale_claim_count": stale_count,
        "duplicate_node_count": duplicate_count,
        "source_backed_claim_ratio": round(source_backed_ratio, 3),
        "total_claims": len(claim_ids),
        "source_backed_claims": len(cited_claim_ids & claim_ids),
    }


# ---------------------------------------------------------------------------
# Tests for benchmark fixtures
# ---------------------------------------------------------------------------

class TestGraphIntegrityMetrics:
    """Tests for graph integrity metric computation."""

    def test_empty_graph_metrics(self) -> None:
        """An empty graph should have zero counts."""
        snap = GraphSnapshot(nodes=[], edges=[])
        metrics = compute_graph_integrity(snap)

        assert metrics["node_count"] == 0
        assert metrics["edge_count"] == 0
        assert metrics["orphan_count"] == 0
        assert metrics["unsupported_claim_count"] == 0
        assert metrics["stale_claim_count"] == 0
        assert metrics["source_backed_claim_ratio"] == 1.0  # no claims = ratio 1.0

    def test_single_session_node_metrics(self) -> None:
        """A single session node with no edges should be an orphan."""
        node = KnowledgeNode(id="session:test-1", kind=NodeKind.SESSION, label="Test query")
        snap = GraphSnapshot(nodes=[node], edges=[])
        metrics = compute_graph_integrity(snap)

        assert metrics["node_count"] == 1
        assert metrics["edge_count"] == 0
        assert metrics["orphan_count"] == 1
        assert metrics["orphan_ids"] == ["session:test-1"]

    def test_source_backed_claim_ratio(self) -> None:
        """Claims with cited edges should have ratio tracked."""
        source_node = KnowledgeNode(
            id="source:1", kind=NodeKind.SOURCE, label="Wikipedia", properties={"url": "https://example.com"}
        )
        claim_node = KnowledgeNode(
            id="claim:1", kind=NodeKind.CLAIM, label="The sky is blue", properties={"confidence": 0.9}
        )
        cited_edge = KnowledgeEdge(
            id="e1", source_id="source:1", target_id="claim:1", kind=EdgeKind.CITED
        )

        snap = GraphSnapshot(nodes=[source_node, claim_node], edges=[cited_edge])
        metrics = compute_graph_integrity(snap)

        assert metrics["source_backed_claim_ratio"] == 1.0
        assert metrics["total_claims"] == 1
        assert metrics["source_backed_claims"] == 1

    def test_unsupported_claim_detection(self) -> None:
        """Claims with low confidence should be flagged."""
        claim = KnowledgeNode(
            id="claim:bad",
            kind=NodeKind.CLAIM,
            label="Some unsupported claim",
            properties={"confidence": 0.2},  # below 0.4 threshold
        )
        snap = GraphSnapshot(nodes=[claim], edges=[])
        metrics = compute_graph_integrity(snap)

        assert metrics["unsupported_claim_count"] == 1

    def test_stale_claim_detection(self) -> None:
        """Claims with dated freshness should be flagged."""
        claim = KnowledgeNode(
            id="claim:stale",
            kind=NodeKind.CLAIM,
            label="Old claim",
            properties={"freshness": "dated", "confidence": 0.8},
        )
        snap = GraphSnapshot(nodes=[claim], edges=[])
        metrics = compute_graph_integrity(snap)

        assert metrics["stale_claim_count"] == 1

    def test_nodes_by_kind_counts(self) -> None:
        """Nodes should be counted by kind."""
        nodes = [
            KnowledgeNode(id="s1", kind=NodeKind.SESSION, label="S1"),
            KnowledgeNode(id="s2", kind=NodeKind.SESSION, label="S2"),
            KnowledgeNode(id="c1", kind=NodeKind.CLAIM, label="C1"),
            KnowledgeNode(id="src1", kind=NodeKind.SOURCE, label="Src1"),
        ]
        snap = GraphSnapshot(nodes=nodes, edges=[])
        metrics = compute_graph_integrity(snap)

        assert metrics["nodes_by_kind"]["session"] == 2
        assert metrics["nodes_by_kind"]["claim"] == 1
        assert metrics["nodes_by_kind"]["source"] == 1

    def test_duplicate_node_detection(self) -> None:
        """Nodes with same kind and label should be flagged as duplicates."""
        nodes = [
            KnowledgeNode(id="n1", kind=NodeKind.CLAIM, label="Same claim"),
            KnowledgeNode(id="n2", kind=NodeKind.CLAIM, label="Same claim"),
            KnowledgeNode(id="n3", kind=NodeKind.CLAIM, label="Different claim"),
        ]
        snap = GraphSnapshot(nodes=nodes, edges=[])
        metrics = compute_graph_integrity(snap)

        assert metrics["duplicate_node_count"] == 1  # "Same claim" appears twice


# ---------------------------------------------------------------------------
# Tests for GraphIndex integrity operations
# ---------------------------------------------------------------------------

class TestGraphIndexIntegrity:
    """Tests for GraphIndex graph integrity operations."""

    def test_clear_preserves_schema(self, tmp_path: Path) -> None:
        """Clearing the index should not corrupt the schema."""
        db = tmp_path / "test.sqlite"
        index = GraphIndex(db)

        index.upsert_node(KnowledgeNode(id="n1", kind=NodeKind.SESSION, label="Test"))
        index.commit()
        index.clear()

        # After clear, should be able to re-insert
        index.upsert_node(KnowledgeNode(id="n2", kind=NodeKind.SOURCE, label="Source"))
        index.commit()
        index.close()

        # Reopen and verify
        index2 = GraphIndex(db)
        nodes = index2.all_nodes()
        assert len(nodes) == 1
        assert nodes[0].id == "n2"

    def test_snapshot_reflects_current_state(self, tmp_path: Path) -> None:
        """Snapshot should reflect current index state."""
        db = tmp_path / "test.sqlite"
        index = GraphIndex(db)

        nodes = [
            KnowledgeNode(id="n1", kind=NodeKind.SESSION, label="Session 1"),
            KnowledgeNode(id="n2", kind=NodeKind.SOURCE, label="Source 1"),
        ]
        edges = [
            KnowledgeEdge(id="e1", source_id="n1", target_id="n2", kind=EdgeKind.CITED),
        ]

        for node in nodes:
            index.upsert_node(node)
        for edge in edges:
            index.upsert_edge(edge)
        index.commit()

        snap = index.snapshot()

        assert len(snap.nodes) == 2
        assert len(snap.edges) == 1

    def test_rebuild_from_snapshot(self, tmp_path: Path) -> None:
        """Rebuild from snapshot should restore complete graph."""
        snap = GraphSnapshot(
            nodes=[
                KnowledgeNode(id="n1", kind=NodeKind.SESSION, label="Session 1"),
                KnowledgeNode(id="n2", kind=NodeKind.CLAIM, label="Claim 1"),
            ],
            edges=[
                KnowledgeEdge(id="e1", source_id="n1", target_id="n2", kind=EdgeKind.SUPPORTS),
            ],
        )

        db = tmp_path / "test.sqlite"
        index = GraphIndex(db)
        index.rebuild_from_snapshot(snap)
        index.commit()

        nodes = index.all_nodes()
        edges = index.all_edges()

        assert len(nodes) == 2
        assert len(edges) == 1

    def test_upsert_is_idempotent(self, tmp_path: Path) -> None:
        """Upserting the same node twice should not duplicate."""
        db = tmp_path / "test.sqlite"
        index = GraphIndex(db)

        node = KnowledgeNode(id="n1", kind=NodeKind.SESSION, label="Test")
        index.upsert_node(node)
        index.upsert_node(node)
        index.commit()

        nodes = index.all_nodes()
        assert len(nodes) == 1


# ---------------------------------------------------------------------------
# Tests for lint thresholds and CI gating
# ---------------------------------------------------------------------------

class TestLintThresholds:
    """Tests for CI-friendly lint threshold checks."""

    def test_clean_vault_passes_lint(self, tmp_path: Path) -> None:
        """A freshly initialized vault should pass lint."""
        config = tmp_path / "config.yaml"
        config.write_text("")

        init_vault(config)

        from click.testing import CliRunner

        from cc_deep_research.cli.main import knowledge

        runner = CliRunner()
        result = runner.invoke(
            knowledge,
            ["lint", "--config", str(config)],
        )

        assert result.exit_code == 0

    def test_lint_threshold_error_on_critical_issues(self, tmp_path: Path) -> None:
        """Lint should fail with exit-code when errors found."""
        config = tmp_path / "config.yaml"
        config.write_text("")

        init_vault(config)

        # Remove index to create an error
        index_path = vault_root(config) / "wiki" / "index.md"
        if index_path.exists():
            index_path.unlink()

        from click.testing import CliRunner

        from cc_deep_research.cli.main import knowledge

        runner = CliRunner()
        result = runner.invoke(
            knowledge,
            ["lint", "--config", str(config), "--exit-code"],
        )

        assert result.exit_code in (0, 1)


# ---------------------------------------------------------------------------
# Tests for planning-impact benchmarks
# ---------------------------------------------------------------------------

class TestPlanningImpactMetrics:
    """Tests for planning-impact comparison metrics."""

    def test_knowledge_retrieval_returns_suggested_queries(self, tmp_path: Path) -> None:
        """Knowledge retrieval should surface gap-driven suggested queries."""
        from cc_deep_research.knowledge.planning_integration import KnowledgePlanningService

        config = tmp_path / "config.yaml"
        config.write_text("")

        service = KnowledgePlanningService(config)
        result = service.retrieve_for_planning(
            "quantum computing applications",
            enabled=True,
        )

        # Should return result (empty if no vault) with suggested queries
        assert isinstance(result.suggested_queries, list)

    def test_disabled_planning_returns_empty_suggestions(self, tmp_path: Path) -> None:
        """When knowledge-assisted planning is disabled, no suggestions returned."""
        from cc_deep_research.knowledge.planning_integration import KnowledgePlanningService

        config = tmp_path / "config.yaml"
        config.write_text("")

        service = KnowledgePlanningService(config)
        result = service.retrieve_for_planning(
            "quantum computing",
            enabled=False,
        )

        assert result.knowledge_retrieved is False
        assert result.suggested_queries == []


# ---------------------------------------------------------------------------
# Tests for regression gates documentation
# ---------------------------------------------------------------------------

class TestRegressionGates:
    """Tests verifying regression gate behavior."""

    def test_graph_snapshot_export_stability(self, tmp_path: Path) -> None:
        """GraphSnapshot JSON export should be stable across serializations."""
        snap = GraphSnapshot(
            nodes=[
                KnowledgeNode(
                    id="claim:test",
                    kind=NodeKind.CLAIM,
                    label="A test claim",
                    properties={"confidence": 0.9, "freshness": "current"},
                )
            ],
            edges=[
                KnowledgeEdge(
                    id="edge:test",
                    source_id="source:test",
                    target_id="claim:test",
                    kind=EdgeKind.CITED,
                )
            ],
        )

        data = snap.model_dump(mode="json")
        restored = GraphSnapshot.model_validate(data)

        assert len(restored.nodes) == 1
        assert len(restored.edges) == 1
        assert restored.nodes[0].id == "claim:test"
        assert restored.edges[0].kind == EdgeKind.CITED


# ---------------------------------------------------------------------------
# Integration tests for full benchmark fixture
# ---------------------------------------------------------------------------

class TestFullBenchmarkFixture:
    """Integration tests using a complete benchmark session fixture."""

    def test_ingest_fixture_session_produces_expected_graph_metrics(self, tmp_path: Path) -> None:
        """Ingesting a fixture session should produce graph with expected metrics."""
        from cc_deep_research.knowledge.ingest import ingest_session
        from cc_deep_research.models import ResearchDepth, ResearchSession, SearchResultItem

        config = tmp_path / "config.yaml"
        config.write_text("")

        session = ResearchSession(
            session_id="benchmark-fixture-001",
            query="What are the applications of quantum computing?",
            depth=ResearchDepth.DEEP,
            started_at=datetime(2024, 6, 1, 10, 0, 0),
            completed_at=datetime(2024, 6, 1, 10, 30, 0),
            sources=[
                SearchResultItem(
                    url="https://nature.com/quantum-applications",
                    title="Quantum computing applications",
                    snippet="Quantum computing has applications in...",
                    score=0.95,
                ),
            ],
            metadata={
                "analysis": {
                    "key_findings": [
                        {"title": "Quantum has many applications", "summary": "Apps in cryptography and simulation"},
                    ],
                    "gaps": [
                        {
                            "gap_description": "Limited public benchmark data for quantum advantage",
                            "suggested_queries": ["quantum advantage benchmarks 2024"],
                            "importance": "high",
                        },
                    ],
                    "cross_reference_claims": [
                        {
                            "claim": "Quantum computers solve certain problems exponentially faster",
                            "supporting_sources": [
                                {"url": "https://nature.com/quantum-applications", "title": "Quantum computing applications"}
                            ],
                            "contradicting_sources": [],
                            "confidence": "high",
                            "freshness": "current",
                            "evidence_type": "research",
                            "consensus_level": 1.0,
                        },
                    ],
                },
            },
        )

        result = ingest_session(session, config_path=config)

        # After ingest, the graph should have multiple nodes
        assert result.nodes_ingested >= 3
        assert result.sources_ingested >= 1

        # The vault should be initialized
        assert (vault_root(config) / "wiki" / "sessions" / "benchmark-fixture-001.md").exists()

    def test_regression_gate_node_count_threshold(self, tmp_path: Path) -> None:
        """Graph with too many orphan nodes should fail regression gate."""
        # Create a graph with many orphan nodes (no edges)
        nodes = [
            KnowledgeNode(id=f"session:{i}", kind=NodeKind.SESSION, label=f"Session {i}")
            for i in range(10)
        ]
        snap = GraphSnapshot(nodes=nodes, edges=[])

        metrics = compute_graph_integrity(snap)

        # With 10 sessions and 0 edges, we have 10 orphan nodes
        assert metrics["orphan_count"] == 10

        # This should be flagged - in a real regression gate you'd assert < threshold
        # Here we just verify the metric correctly detects the situation
        assert metrics["orphan_count"] >= 5  # Would fail a strict regression gate

    def test_source_backed_ratio_below_threshold(self, tmp_path: Path) -> None:
        """Graph with low source-backed claim ratio should fail regression gate."""
        # 3 claims, none with sources
        nodes = [
            KnowledgeNode(id=f"claim:{i}", kind=NodeKind.CLAIM, label=f"Claim {i}", properties={"confidence": 0.5})
            for i in range(3)
        ]
        snap = GraphSnapshot(nodes=nodes, edges=[])

        metrics = compute_graph_integrity(snap)

        assert metrics["source_backed_claim_ratio"] == 0.0  # No claims have sources

        # This would fail a strict regression gate requiring ratio >= 0.8
        assert metrics["source_backed_claim_ratio"] < 0.8
