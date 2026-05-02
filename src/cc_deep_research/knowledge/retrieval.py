"""Knowledge retrieval service for research planning assistance."""

from __future__ import annotations

import re
from pathlib import Path
from typing import TYPE_CHECKING

from cc_deep_research.knowledge import KnowledgeNode, NodeKind
from cc_deep_research.knowledge.graph_index import GraphIndex
from cc_deep_research.knowledge.vault import (
    graph_sqlite_path,
    wiki_index_path,
)

if TYPE_CHECKING:
    pass


class KnowledgeContext:
    """Retrieved context from the knowledge vault for research planning."""

    def __init__(
        self,
        relevant_nodes: list[KnowledgeNode],
        prior_sessions: list[KnowledgeNode],
        prior_claims: list[KnowledgeNode],
        prior_gaps: list[KnowledgeNode],
        prior_sources: list[KnowledgeNode],
        fresh_claims: list[KnowledgeNode],
        stale_claims: list[KnowledgeNode],
        unsupported_claims: list[KnowledgeNode],
        knowledge_used: bool,
    ) -> None:
        self.relevant_nodes = relevant_nodes
        self.prior_sessions = prior_sessions
        self.prior_claims = prior_claims
        self.prior_gaps = prior_gaps
        self.prior_sources = prior_sources
        self.fresh_claims = fresh_claims
        self.stale_claims = stale_claims
        self.unsupported_claims = unsupported_claims
        self.knowledge_used = knowledge_used

    def has_prior_knowledge(self) -> bool:
        return len(self.prior_sessions) > 0 or len(self.prior_claims) > 0

    def suggested_queries(self) -> list[str]:
        """Return gap-driven follow-up queries."""
        queries = []
        for gap in self.prior_gaps:
            title = gap.label
            if len(title) > 10:
                queries.append(title)
        return queries[:5]

    def summary_dict(self) -> dict:
        return {
            "knowledge_used": self.knowledge_used,
            "prior_sessions": len(self.prior_sessions),
            "prior_claims": len(self.prior_claims),
            "prior_gaps": len(self.prior_gaps),
            "prior_sources": len(self.prior_sources),
            "fresh_claims": len(self.fresh_claims),
            "stale_claims": len(self.stale_claims),
            "unsupported_claims": len(self.unsupported_claims),
        }


class KnowledgeRetrievalService:
    """Service for retrieving relevant knowledge from the vault."""

    def __init__(self, config_path: Path | None = None) -> None:
        self._config_path = config_path
        self._index: GraphIndex | None = None

    def _open_index(self) -> GraphIndex | None:
        db_path = graph_sqlite_path(self._config_path)
        if not db_path.exists():
            return None
        if self._index is None:
            self._index = GraphIndex(db_path)
        return self._index

    def retrieve_context(
        self,
        query: str,
        *,
        depth: str | None = None,
        max_nodes: int = 20,
    ) -> KnowledgeContext:
        """Retrieve knowledge relevant to a research query.

        Args:
            query: The research query string.
            depth: Optional depth mode for filtering.
            max_nodes: Maximum number of nodes to return.

        Returns:
            KnowledgeContext with relevant prior knowledge.
        """
        index = self._open_index()
        if index is None:
            return _empty_context()

        query_terms = set(re.findall(r"[a-z0-9]+", query.lower()))
        stop_words = {"what", "is", "the", "a", "an", "of", "and", "to", "for", "in", "on"}
        query_terms -= stop_words

        all_nodes = index.all_nodes()
        relevant: list[KnowledgeNode] = []
        prior_sessions: list[KnowledgeNode] = []
        prior_claims: list[KnowledgeNode] = []
        prior_gaps: list[KnowledgeNode] = []
        prior_sources: list[KnowledgeNode] = []
        fresh_claims: list[KnowledgeNode] = []
        stale_claims: list[KnowledgeNode] = []
        unsupported_claims: list[KnowledgeNode] = []

        for node in all_nodes:
            if self._node_relevant(node, query_terms):
                relevant.append(node)
                if node.kind == NodeKind.SESSION:
                    prior_sessions.append(node)
                elif node.kind == NodeKind.CLAIM:
                    prior_claims.append(node)
                    freshness = node.properties.get("freshness", "")
                    if freshness in ("current", "recent"):
                        fresh_claims.append(node)
                    elif freshness == "dated":
                        stale_claims.append(node)
                    confidence = node.properties.get("confidence", 0.5)
                    if confidence < 0.4:
                        unsupported_claims.append(node)
                elif node.kind == NodeKind.GAP:
                    prior_gaps.append(node)
                elif node.kind == NodeKind.SOURCE:
                    prior_sources.append(node)

        relevant = relevant[:max_nodes]

        return KnowledgeContext(
            relevant_nodes=relevant,
            prior_sessions=prior_sessions[:5],
            prior_claims=prior_claims[:10],
            prior_gaps=prior_gaps[:5],
            prior_sources=prior_sources[:10],
            fresh_claims=fresh_claims,
            stale_claims=stale_claims,
            unsupported_claims=unsupported_claims,
            knowledge_used=True,
        )

    @staticmethod
    def _node_relevant(node: KnowledgeNode, query_terms: set[str]) -> bool:
        """Check if a node is relevant to the query."""
        label_terms = set(re.findall(r"[a-z0-9]+", node.label.lower()))
        prop_values = " ".join(str(v) for v in node.properties.values())
        prop_terms = set(re.findall(r"[a-z0-9]+", prop_values.lower()))
        all_terms = label_terms | prop_terms

        if query_terms & all_terms:
            return True
        return False

    def get_session_influence(self, session_id: str) -> dict:
        """Return which prior knowledge influenced a given session.

        Returns a dict describing prior pages/nodes that influenced this session.
        """
        db_path = graph_sqlite_path(self._config_path)
        if not db_path.exists():
            return {}

        index = GraphIndex(db_path)
        session_node = index.node(f"session:{session_id}")
        if session_node is None:
            return {}

        # Get edges where session is source (session -> sources/claims)
        edges = index.all_edges()
        influenced_nodes: list[str] = []
        for edge in edges:
            if edge.source_id == session_node.id:
                influenced_nodes.append(edge.target_id)

        result: dict = {
            "session_id": session_id,
            "knowledge_nodes_influenced": len(influenced_nodes),
            "influenced_node_ids": influenced_nodes,
        }
        return result

    def read_index_summary(self) -> str:
        """Read and summarize the wiki index content."""
        path = wiki_index_path(self._config_path)
        if not path.exists():
            return ""
        content = path.read_text(encoding="utf-8")
        # Return first 500 chars
        return content[:500]


def _empty_context() -> KnowledgeContext:
    return KnowledgeContext(
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


__all__ = ["KnowledgeContext", "KnowledgeRetrievalService"]
