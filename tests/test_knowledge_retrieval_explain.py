"""Tests for P23-T3 retrieval explainability."""

from __future__ import annotations

from pathlib import Path

from cc_deep_research.knowledge import KnowledgeNode, NodeKind
from cc_deep_research.knowledge.graph_index import GraphIndex
from cc_deep_research.knowledge.retrieval import (
    KnowledgeRetrievalService,
    RetrievalExplanation,
    RetrievalResult,
)


class TestRetrievalExplanation:
    """Tests for retrieval explanation feature."""

    def test_normal_retrieval_returns_explanation(self, tmp_path: Path) -> None:
        """Normal retrieval returns explanation with selection reasons."""
        from cc_deep_research.knowledge.vault import init_vault
        init_vault(tmp_path)

        from cc_deep_research.knowledge.vault import graph_sqlite_path
        db = graph_sqlite_path(tmp_path)
        index = GraphIndex(db)
        index.upsert_node(KnowledgeNode(
            id="claim:1", kind=NodeKind.CLAIM,
            label="Quantum computers solve optimization problems",
            properties={"freshness": "current"}
        ))
        index.upsert_node(KnowledgeNode(
            id="source:1", kind=NodeKind.SOURCE,
            label="IBM Quantum research paper",
            properties={"url": "https://ibm.com/quantum"}
        ))
        index.commit()
        index.close()

        service = KnowledgeRetrievalService(config_path=tmp_path)
        result = service.retrieve_context("quantum computers optimization")

        assert isinstance(result, RetrievalResult)
        assert isinstance(result.explanation, RetrievalExplanation)
        assert result.explanation.query == "quantum computers optimization"
        assert "quantum" in result.explanation.query_terms
        assert "optimization" in result.explanation.query_terms
        assert len(result.explanation.nodes_selected) > 0
        assert len(result.explanation.selection_reasons) > 0

        # Verify context is intact for backward compatibility
        assert hasattr(result, 'context')
        assert result.context.has_prior_knowledge() is not None

    def test_empty_vault_fallback_active(self, tmp_path: Path) -> None:
        """Empty vault triggers fallback_active in explanation."""
        nonexistent = tmp_path / "nonexistent"
        service = KnowledgeRetrievalService(config_path=nonexistent)
        result = service.retrieve_context("any query")

        assert result.explanation.fallback_active is True
        assert result.explanation.nodes_selected == []
        assert result.explanation.total_candidates == 0

    def test_sanitization_truncates_long_values(self, tmp_path: Path) -> None:
        """Selection reasons are truncated to max 200 chars."""
        from cc_deep_research.knowledge.vault import graph_sqlite_path, init_vault
        init_vault(tmp_path)

        db = graph_sqlite_path(tmp_path)
        index = GraphIndex(db)

        long_label = "A" * 500
        index.upsert_node(KnowledgeNode(
            id="claim:long", kind=NodeKind.CLAIM,
            label=long_label,
            properties={"description": "B" * 500}
        ))
        index.commit()
        index.close()

        service = KnowledgeRetrievalService(config_path=tmp_path)
        result = service.retrieve_context("A" * 100)

        for reason in result.explanation.selection_reasons.values():
            assert len(reason) <= 200

    def test_bounded_payload_excludes_excessive_nodes_excluded(self, tmp_path: Path) -> None:
        """When total_candidates > 10, nodes_excluded is excluded."""
        from cc_deep_research.knowledge.vault import graph_sqlite_path, init_vault
        init_vault(tmp_path)

        db = graph_sqlite_path(tmp_path)
        index = GraphIndex(db)

        for i in range(20):
            index.upsert_node(KnowledgeNode(
                id=f"node:{i}", kind=NodeKind.CONCEPT,
                label=f"Unrelated concept {i}",
                properties={}
            ))
        index.upsert_node(KnowledgeNode(
            id="claim:match", kind=NodeKind.CLAIM,
            label="matching quantum claim",
            properties={"freshness": "current"}
        ))
        index.commit()
        index.close()

        service = KnowledgeRetrievalService(config_path=tmp_path)
        result = service.retrieve_context("quantum", max_nodes=1)

        assert result.explanation.total_candidates > 10
        assert len(result.explanation.nodes_excluded) == 0

    def test_backward_compatibility_existing_callers(self, tmp_path: Path) -> None:
        """Existing code using context attributes still works."""
        from cc_deep_research.knowledge.vault import graph_sqlite_path, init_vault
        init_vault(tmp_path)

        db = graph_sqlite_path(tmp_path)
        index = GraphIndex(db)
        index.upsert_node(KnowledgeNode(
            id="session:1", kind=NodeKind.SESSION,
            label="Test research session",
            properties={}
        ))
        index.commit()
        index.close()

        service = KnowledgeRetrievalService(config_path=tmp_path)
        result = service.retrieve_context("research session")

        # Access context the old way
        assert result.context.has_prior_knowledge() is True
        assert result.context.suggested_queries() == []
        assert isinstance(result.context.summary_dict(), dict)

    def test_selection_reasons_contain_matched_terms(self, tmp_path: Path) -> None:
        """Selection reasons show which terms matched."""
        from cc_deep_research.knowledge.vault import graph_sqlite_path, init_vault
        init_vault(tmp_path)

        db = graph_sqlite_path(tmp_path)
        index = GraphIndex(db)
        index.upsert_node(KnowledgeNode(
            id="claim:1", kind=NodeKind.CLAIM,
            label="Machine learning models",
            properties={"domain": "AI"}
        ))
        index.commit()
        index.close()

        service = KnowledgeRetrievalService(config_path=tmp_path)
        result = service.retrieve_context("machine learning")

        reasons = result.explanation.selection_reasons
        assert "claim:1" in reasons
        assert "label matched" in reasons["claim:1"]

    def test_score_factors_reflect_term_overlap(self, tmp_path: Path) -> None:
        """Score factors are higher when more terms match."""
        from cc_deep_research.knowledge.vault import graph_sqlite_path, init_vault
        init_vault(tmp_path)

        db = graph_sqlite_path(tmp_path)
        index = GraphIndex(db)
        index.upsert_node(KnowledgeNode(
            id="claim:1", kind=NodeKind.CLAIM,
            label="Quantum computing research",
            properties={}
        ))
        index.commit()
        index.close()

        service = KnowledgeRetrievalService(config_path=tmp_path)
        result = service.retrieve_context("quantum computing")

        scores = result.explanation.score_factors
        assert "claim:1" in scores
        assert scores["claim:1"] > 0

    def test_fallback_context_has_no_prior_knowledge(self, tmp_path: Path) -> None:
        """Fallback context has knowledge_used=False."""
        nonexistent = tmp_path / "nonexistent"
        service = KnowledgeRetrievalService(config_path=nonexistent)
        result = service.retrieve_context("test query")

        assert result.explanation.fallback_active is True
        assert result.context.knowledge_used is False
        assert result.context.has_prior_knowledge() is False

    def test_nodes_excluded_limited_when_candidates_small(self, tmp_path: Path) -> None:
        """When candidates <= 10, nodes_excluded has up to 5 entries."""
        from cc_deep_research.knowledge.vault import graph_sqlite_path, init_vault
        init_vault(tmp_path)

        db = graph_sqlite_path(tmp_path)
        index = GraphIndex(db)

        # Create 6 nodes, 1 that matches "test" and 5 that don't
        index.upsert_node(KnowledgeNode(
            id="node:match", kind=NodeKind.CONCEPT,
            label="test concept", properties={}
        ))
        for i in range(5):
            index.upsert_node(KnowledgeNode(
                id=f"node:{i}", kind=NodeKind.CONCEPT,
                label=f"Unrelated {i}", properties={}
            ))
        index.commit()
        index.close()

        service = KnowledgeRetrievalService(config_path=tmp_path)
        # Only match the one "test" node, leaving 5 as candidates but not selected
        result = service.retrieve_context("test", max_nodes=1)

        assert result.explanation.total_candidates <= 10
        assert len(result.explanation.nodes_excluded) <= 5
        # The matched node should be in nodes_selected
        assert "node:match" in result.explanation.nodes_selected

    def test_retrieval_explain_api_endpoint(self, tmp_path: Path) -> None:
        """Test the /api/knowledge/retrieval/explain endpoint."""
        from fastapi.testclient import TestClient

        # Create vault and graph data
        from cc_deep_research.knowledge.vault import init_vault
        from cc_deep_research.web_server import create_app
        init_vault(tmp_path)

        from cc_deep_research.knowledge.vault import graph_sqlite_path
        db_path = graph_sqlite_path(tmp_path)
        index = GraphIndex(db_path)
        index.upsert_node(KnowledgeNode(
            id="session:test", kind=NodeKind.SESSION,
            label="Test session",
            properties={}
        ))
        index.commit()
        index.close()

        client = TestClient(create_app())
        response = client.get(
            "/api/knowledge/retrieval/explain",
            params={"query": "test session", "max_nodes": 10}
        )
        assert response.status_code == 200
        data = response.json()
        assert "context" in data
        assert "explanation" in data
        assert "query" in data["explanation"]
        assert "nodes_selected" in data["explanation"]
        assert "selection_reasons" in data["explanation"]
