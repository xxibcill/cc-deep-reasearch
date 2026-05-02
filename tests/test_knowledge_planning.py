"""Tests for knowledge planning integration."""

from __future__ import annotations

from pathlib import Path

from cc_deep_research.knowledge import KnowledgeNode, NodeKind
from cc_deep_research.knowledge.planning_integration import (
    KnowledgePlanningResult,
    KnowledgePlanningService,
    inject_knowledge_influence,
)
from cc_deep_research.knowledge.retrieval import KnowledgeContext, KnowledgeRetrievalService


class TestKnowledgeRetrievalService:
    """Tests for KnowledgeRetrievalService."""

    def test_empty_context_when_no_vault(self, tmp_path: Path) -> None:
        """When vault doesn't exist, retrieval returns empty context."""
        config = tmp_path / "config.yaml"
        config.write_text("")

        service = KnowledgeRetrievalService(config)
        ctx = service.retrieve_context("quantum computing", depth="deep")

        assert ctx.knowledge_used is False
        assert ctx.prior_sessions == []
        assert ctx.prior_claims == []

    def test_suggested_queries_from_gaps(self, tmp_path: Path) -> None:
        """Gaps in knowledge vault generate suggested queries."""
        config = tmp_path / "config.yaml"
        config.write_text("")

        # Even without a vault, the service should return empty context
        service = KnowledgeRetrievalService(config)
        ctx = service.retrieve_context("machine learning")

        assert ctx.suggested_queries() == []


class TestKnowledgePlanningService:
    """Tests for KnowledgePlanningService."""

    def test_disabled_retrieval_returns_empty(self, tmp_path: Path) -> None:
        """When enabled=False, service returns empty result."""
        config = tmp_path / "config.yaml"
        config.write_text("")

        service = KnowledgePlanningService(config)
        result = service.retrieve_for_planning(
            "quantum computing",
            enabled=False,
        )

        assert result.knowledge_retrieved is False
        assert result.suggested_queries == []

    def test_enabled_retrieval_when_no_vault(self, tmp_path: Path) -> None:
        """When enabled but no vault, returns empty context."""
        config = tmp_path / "config.yaml"
        config.write_text("")

        service = KnowledgePlanningService(config)
        result = service.retrieve_for_planning(
            "quantum computing",
            enabled=True,
        )

        # No vault exists, so knowledge is not really retrieved
        assert result.knowledge_retrieved is False
        assert result.prior_sessions == []


class TestInjectKnowledgeInfluence:
    """Tests for inject_knowledge_influence."""

    def test_injects_empty_influence(self) -> None:
        """Empty planning result produces clean influence dict."""
        planning_result = KnowledgePlanningResult(
            knowledge_retrieved=False,
            prior_sessions=[],
            prior_claims=[],
            prior_gaps=[],
            suggested_queries=[],
            fresh_claims=[],
            stale_claims=[],
            unsupported_claims=[],
            influence_summary={},
        )

        metadata = {"strategy": {}, "analysis": {}}
        updated = inject_knowledge_influence(metadata, planning_result)

        assert "knowledge_influence" in updated
        ki = updated["knowledge_influence"]
        assert ki["knowledge_retrieved"] is False
        assert ki["prior_sessions_count"] == 0

    def test_injects_with_prior_knowledge(self) -> None:
        """With prior knowledge, all fields are populated."""
        node1 = KnowledgeNode(id="session:test-1", kind=NodeKind.SESSION, label="Prior session")
        node2 = KnowledgeNode(id="claim:test-1", kind=NodeKind.CLAIM, label="A claim")

        planning_result = KnowledgePlanningResult(
            knowledge_retrieved=True,
            prior_sessions=[node1],
            prior_claims=[node2],
            prior_gaps=[],
            suggested_queries=["query about gaps"],
            fresh_claims=[],
            stale_claims=[],
            unsupported_claims=[],
            influence_summary={"prior_sessions": 1},
        )

        metadata = {"strategy": {}, "analysis": {}}
        updated = inject_knowledge_influence(metadata, planning_result)

        ki = updated["knowledge_influence"]
        assert ki["knowledge_retrieved"] is True
        assert ki["prior_sessions_count"] == 1
        assert ki["prior_claims_count"] == 1
        assert ki["suggested_queries_from_knowledge"] == ["query about gaps"]
        assert "session:test-1" in ki["prior_session_ids"]


class TestKnowledgeContext:
    """Tests for KnowledgeContext."""

    def test_has_prior_knowledge_false_when_empty(self) -> None:
        ctx = KnowledgeContext(
            relevant_nodes=[],
            prior_sessions=[],
            prior_claims=[],
            prior_gaps=[],
            prior_sources=[],
            fresh_claims=[],
            stale_claims=[],
            unsupported_claims=[],
            knowledge_used=False,
        )
        assert ctx.has_prior_knowledge() is False

    def test_has_prior_knowledge_true_when_sessions_exist(self) -> None:
        ctx = KnowledgeContext(
            relevant_nodes=[],
            prior_sessions=[KnowledgeNode(id="s:1", kind=NodeKind.SESSION, label="Test")],
            prior_claims=[],
            prior_gaps=[],
            prior_sources=[],
            fresh_claims=[],
            stale_claims=[],
            unsupported_claims=[],
            knowledge_used=True,
        )
        assert ctx.has_prior_knowledge() is True

    def test_summary_dict(self) -> None:
        ctx = KnowledgeContext(
            relevant_nodes=[],
            prior_sessions=[KnowledgeNode(id="s:1", kind=NodeKind.SESSION, label="Test")],
            prior_claims=[],
            prior_gaps=[],
            prior_sources=[],
            fresh_claims=[],
            stale_claims=[],
            unsupported_claims=[],
            knowledge_used=True,
        )
        summary = ctx.summary_dict()
        assert summary["knowledge_used"] is True
        assert summary["prior_sessions"] == 1
