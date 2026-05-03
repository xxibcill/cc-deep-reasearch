"""Tests for knowledge vault contracts."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

import pytest

from cc_deep_research.knowledge import (
    EdgeKind,
    GraphSnapshot,
    KnowledgeEdge,
    KnowledgeNode,
    LintFinding,
    LintSeverity,
    NodeKind,
    PageFrontmatter,
    PageStatus,
)
from cc_deep_research.knowledge.vault import (
    agents_md_path,
    graph_export_path,
    graph_sqlite_path,
    init_vault,
    raw_session_dir,
    raw_source_file,
    vault_root,
    wiki_index_path,
    wiki_log_path,
)


class TestNodeKind:
    """Tests for NodeKind enum."""

    def test_all_kinds_present(self) -> None:
        assert NodeKind.SESSION == "session"
        assert NodeKind.SOURCE == "source"
        assert NodeKind.QUERY == "query"
        assert NodeKind.CONCEPT == "concept"
        assert NodeKind.ENTITY == "entity"
        assert NodeKind.CLAIM == "claim"
        assert NodeKind.FINDING == "finding"
        assert NodeKind.GAP == "gap"
        assert NodeKind.QUESTION == "question"
        assert NodeKind.WIKI_PAGE == "wiki_page"


class TestEdgeKind:
    """Tests for EdgeKind enum."""

    def test_all_kinds_present(self) -> None:
        assert EdgeKind.CITED == "cited"
        assert EdgeKind.MENTIONS == "mentions"
        assert EdgeKind.SUPPORTS == "supports"
        assert EdgeKind.CONTRADICTS == "contradicts"
        assert EdgeKind.DERIVED_FROM == "derived_from"
        assert EdgeKind.USED_QUERY == "used_query"
        assert EdgeKind.SUGGESTS_QUERY == "suggests_query"
        assert EdgeKind.SUPERSEDES == "supersedes"
        assert EdgeKind.EVOLVES == "evolves"
        assert EdgeKind.LINKS_TO == "links_to"


class TestPageStatus:
    """Tests for PageStatus enum."""

    def test_all_statuses_present(self) -> None:
        assert PageStatus.DRAFT == "draft"
        assert PageStatus.STABLE == "stable"
        assert PageStatus.DEPRECATED == "deprecated"
        assert PageStatus.NEEDS_REVIEW == "needs_review"


class TestKnowledgeNode:
    """Tests for KnowledgeNode model."""

    def test_create_node(self) -> None:
        node = KnowledgeNode(
            id="node-1",
            kind=NodeKind.CLAIM,
            label="Quantum computers use qubits",
        )
        assert node.id == "node-1"
        assert node.kind == NodeKind.CLAIM
        assert node.label == "Quantum computers use qubits"
        assert node.properties == {}
        assert isinstance(node.created_at, datetime)

    def test_node_accepts_extra_properties(self) -> None:
        node = KnowledgeNode(
            id="node-2",
            kind=NodeKind.SOURCE,
            label="IBM Quantum",
            properties={"url": "https://ibm.com/quantum", "domain": "ibm.com"},
        )
        assert node.properties["url"] == "https://ibm.com/quantum"
        assert node.properties["domain"] == "ibm.com"

    def test_node_serialization_round_trip(self) -> None:
        node = KnowledgeNode(
            id="node-3",
            kind=NodeKind.CONCEPT,
            label="Superposition",
            properties={"aliases": ["quantum superposition"]},
        )
        data = node.model_dump(mode="json")
        restored = KnowledgeNode.model_validate(data)
        assert restored.id == node.id
        assert restored.kind == node.kind
        assert restored.properties == node.properties


class TestKnowledgeEdge:
    """Tests for KnowledgeEdge model."""

    def test_create_edge(self) -> None:
        edge = KnowledgeEdge(
            id="edge-1",
            source_id="source-node-1",
            target_id="claim-node-1",
            kind=EdgeKind.CITED,
        )
        assert edge.id == "edge-1"
        assert edge.source_id == "source-node-1"
        assert edge.target_id == "claim-node-1"
        assert edge.kind == EdgeKind.CITED
        assert edge.properties == {}

    def test_edge_with_properties(self) -> None:
        edge = KnowledgeEdge(
            id="edge-2",
            source_id="finding-1",
            target_id="claim-1",
            kind=EdgeKind.SUPPORTS,
            properties={"confidence": 0.9},
        )
        assert edge.properties["confidence"] == 0.9


class TestPageFrontmatter:
    """Tests for PageFrontmatter model."""

    def test_create_frontmatter(self) -> None:
        fm = PageFrontmatter(
            id="claim-quantum-advantage",
            kind=NodeKind.CLAIM,
            title="Quantum computers solve certain problems exponentially faster",
            status=PageStatus.STABLE,
            tags=["quantum", "computing", "advantage"],
            source_ids=["src-1", "src-2"],
            session_ids=["sess-1"],
            confidence=0.95,
        )
        assert fm.id == "claim-quantum-advantage"
        assert fm.kind == NodeKind.CLAIM
        assert fm.title == "Quantum computers solve certain problems exponentially faster"
        assert fm.status == PageStatus.STABLE
        assert fm.confidence == 0.95

    def test_frontmatter_default_status(self) -> None:
        fm = PageFrontmatter(
            id="test-page",
            kind=NodeKind.CONCEPT,
            title="Test Concept",
        )
        assert fm.status == PageStatus.DRAFT

    def test_frontmatter_accepts_extra(self) -> None:
        fm = PageFrontmatter(
            id="test-extra",
            kind=NodeKind.ENTITY,
            title="Test Entity",
            extra_field="should_pass_through",
            another_field=42,
        )
        assert fm.extra_field == "should_pass_through"
        assert fm.another_field == 42

    def test_frontmatter_invalid_kind_rejected(self) -> None:
        with pytest.raises(ValueError):
            PageFrontmatter(
                id="bad-kind",
                kind="not_a_kind",  # type: ignore[arg-type]
                title="Bad",
            )


class TestGraphSnapshot:
    """Tests for GraphSnapshot model."""

    def test_empty_snapshot(self) -> None:
        snap = GraphSnapshot()
        assert snap.nodes == []
        assert snap.edges == []
        assert isinstance(snap.exported_at, datetime)

    def test_snapshot_with_nodes_and_edges(self) -> None:
        nodes = [
            KnowledgeNode(id="n1", kind=NodeKind.SESSION, label="Session 1"),
            KnowledgeNode(id="n2", kind=NodeKind.SOURCE, label="Source 1"),
        ]
        edges = [
            KnowledgeEdge(
                id="e1",
                source_id="n1",
                target_id="n2",
                kind=EdgeKind.CITED,
            ),
        ]
        snap = GraphSnapshot(nodes=nodes, edges=edges)
        assert len(snap.nodes) == 2
        assert len(snap.edges) == 1

    def test_snapshot_json_round_trip(self) -> None:
        snap = GraphSnapshot(
            nodes=[
                KnowledgeNode(
                    id="test-node",
                    kind=NodeKind.CLAIM,
                    label="Test claim",
                    properties={"confidence": 0.8},
                )
            ],
            edges=[
                KnowledgeEdge(
                    id="test-edge",
                    source_id="src-1",
                    target_id="test-node",
                    kind=EdgeKind.SUPPORTS,
                )
            ],
        )
        data = snap.model_dump(mode="json")
        restored = GraphSnapshot.model_validate(data)
        assert len(restored.nodes) == 1
        assert restored.nodes[0].id == "test-node"
        assert len(restored.edges) == 1


class TestLintFinding:
    """Tests for LintFinding model."""

    def test_lint_finding_error(self) -> None:
        finding = LintFinding(
            severity=LintSeverity.ERROR,
            category="broken_wikilink",
            message="Wiki link [[missing-page]] does not exist",
            page_path="wiki/claims/test.md",
        )
        assert finding.severity == LintSeverity.ERROR
        assert finding.category == "broken_wikilink"

    def test_lint_finding_with_node_id(self) -> None:
        finding = LintFinding(
            severity=LintSeverity.WARNING,
            category="unsupported_claim",
            message="Claim has no backing source",
            node_id="claim-123",
        )
        assert finding.node_id == "claim-123"


# ---------------------------------------------------------------------------
# Path resolution tests
# ---------------------------------------------------------------------------

class TestVaultPaths:
    """Tests for knowledge vault path resolution."""

    def test_vault_root_default(self) -> None:
        root = vault_root()
        assert isinstance(root, Path)
        assert root.name == "knowledge"

    def test_vault_root_with_config_dir(self, tmp_path: Path) -> None:
        """When config_path is a directory, vault goes under it."""
        root = vault_root(tmp_path)
        assert root.name == "knowledge"
        assert root.parent == tmp_path

    def test_all_subdirs_resolve(self, tmp_path: Path) -> None:
        config = tmp_path / "config.yaml"
        config.write_text("")
        root = vault_root(config)

        assert (root / "raw").name == "raw"
        assert (root / "wiki").name == "wiki"
        assert (root / "graph").name == "graph"
        assert (root / "schema").name == "schema"
        assert (root / "wiki" / "concepts").name == "concepts"
        assert (root / "wiki" / "entities").name == "entities"
        assert (root / "wiki" / "claims").name == "claims"
        assert (root / "wiki" / "questions").name == "questions"
        assert (root / "wiki" / "sessions").name == "sessions"
        assert (root / "wiki" / "sources").name == "sources"

    def test_raw_session_dir(self) -> None:
        path = raw_session_dir("session-abc-123")
        assert "sessions" in str(path)
        assert "session-abc-123" in str(path)

    def test_raw_source_file_kinds(self) -> None:
        path = raw_source_file("sess-1", "src-1", "session")
        assert path.name == "session.json"
        assert "sessions" in str(path)

        path = raw_source_file("sess-1", "src-1", "report")
        assert path.name == "report.json"

        path = raw_source_file("sess-1", "src-1", "sources")
        assert path.name == "sources.json"

        path = raw_source_file("sess-1", "src-1", "manifest")
        assert path.name == "manifest.json"

    def test_graph_sqlite_path(self) -> None:
        path = graph_sqlite_path()
        assert path.name == "graph.sqlite"
        assert "graph" in str(path)

    def test_graph_export_path(self) -> None:
        path = graph_export_path()
        assert path.name == "graph.json"
        assert "graph" in str(path)

    def test_agents_md_path(self) -> None:
        path = agents_md_path()
        assert path.name == "AGENTS.md"


# ---------------------------------------------------------------------------
# Vault initialization tests
# ---------------------------------------------------------------------------

class TestVaultInit:
    """Tests for vault initialization."""

    def test_init_vault_creates_directories(self, tmp_path: Path) -> None:
        config = tmp_path / "config.yaml"
        config.write_text("")
        result = init_vault(config)

        for key, path in result.items():
            if key.startswith("dir:"):
                assert path.exists(), f"{key} should exist"
                assert path.is_dir(), f"{key} should be a directory"

    def test_init_vault_creates_seed_files(self, tmp_path: Path) -> None:
        config = tmp_path / "config.yaml"
        config.write_text("")
        result = init_vault(config)

        for key, path in result.items():
            if key.startswith("file:"):
                assert path.exists(), f"{key} should exist"
                assert path.is_file(), f"{key} should be a file"

    def test_init_vault_idempotent(self, tmp_path: Path) -> None:
        config = tmp_path / "config.yaml"
        config.write_text("")

        result1 = init_vault(config)
        result2 = init_vault(config)

        # Both should return the same set of paths
        assert set(result1.keys()) == set(result2.keys())

    def test_init_vault_dry_run(self, tmp_path: Path) -> None:
        config = tmp_path / "config.yaml"
        config.write_text("")
        result = init_vault(config, dry_run=True)

        for key, path in result.items():
            assert not path.exists(), f"{key} should NOT exist in dry run"

    def test_wiki_index_has_frontmatter(self, tmp_path: Path) -> None:
        config = tmp_path / "config.yaml"
        config.write_text("")
        init_vault(config)

        index = wiki_index_path(config)
        content = index.read_text()
        assert "---" in content
        assert "id: vault-index" in content

    def test_log_file_exists(self, tmp_path: Path) -> None:
        config = tmp_path / "config.yaml"
        config.write_text("")
        init_vault(config)

        log = wiki_log_path(config)
        assert log.exists()
        content = log.read_text()
        assert "# Vault Activity Log" in content

    def test_agents_md_exists(self, tmp_path: Path) -> None:
        config = tmp_path / "config.yaml"
        config.write_text("")
        init_vault(config)

        md = agents_md_path(config)
        assert md.exists()
        content = md.read_text()
        assert "Agent Editing Rules" in content


class TestIdStability:
    """Tests for ID stability in knowledge models."""

    def test_node_id_required(self) -> None:
        with pytest.raises(ValueError):
            KnowledgeNode(id="", kind=NodeKind.SESSION)

    def test_edge_id_required(self) -> None:
        with pytest.raises(ValueError):
            KnowledgeEdge(id="", source_id="s", target_id="t", kind=EdgeKind.CITED)

    def test_page_frontmatter_id_required(self) -> None:
        with pytest.raises(ValueError):
            PageFrontmatter(id="", kind=NodeKind.CONCEPT, title="Test")

    def test_stable_node_id_across_serializations(self) -> None:
        node = KnowledgeNode(
            id="stable-id-test",
            kind=NodeKind.CLAIM,
            label="Test label",
        )
        for _ in range(3):
            data = node.model_dump(mode="json")
            node = KnowledgeNode.model_validate(data)
            assert node.id == "stable-id-test"
