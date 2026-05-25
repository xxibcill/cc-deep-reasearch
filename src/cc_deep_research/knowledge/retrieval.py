"""Knowledge retrieval service for research planning assistance."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import UTC, datetime
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


# ---------------------------------------------------------------------------
# Retrieval explanation
# ---------------------------------------------------------------------------


@dataclass
class RetrievalExplanation:
    """Metadata explaining how retrieval was performed and why nodes were selected."""

    query: str
    query_terms: frozenset[str]
    nodes_selected: list[str]
    nodes_excluded: list[str]
    selection_reasons: dict[str, str]
    score_factors: dict[str, float]
    filters_applied: list[str]
    fallback_active: bool
    total_candidates: int
    max_nodes: int
    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))


@dataclass
class RetrievalResult:
    """Result of knowledge retrieval with explanation metadata."""

    context: KnowledgeContext
    explanation: RetrievalExplanation

    def __getattr__(self, name: str) -> object:
        """Delegate legacy KnowledgeContext attribute access to context."""
        return getattr(self.context, name)


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
    ) -> RetrievalResult:
        """Retrieve knowledge relevant to a research query.

        Args:
            query: The research query string.
            depth: Optional depth mode for filtering.
            max_nodes: Maximum number of nodes to return.

        Returns:
            RetrievalResult containing KnowledgeContext and explanation.
        """
        index = self._open_index()

        query_terms = set(re.findall(r"[a-z0-9]+", query.lower()))
        stop_words = {"what", "is", "the", "a", "an", "of", "and", "to", "for", "in", "on"}
        query_terms -= stop_words

        if index is None:
            explanation = RetrievalExplanation(
                query=query,
                query_terms=frozenset(query_terms),
                nodes_selected=[],
                nodes_excluded=[],
                selection_reasons={},
                score_factors={},
                filters_applied=["vault_not_found"],
                fallback_active=True,
                total_candidates=0,
                max_nodes=max_nodes,
            )
            return RetrievalResult(context=_empty_context(), explanation=explanation)

        all_nodes = index.all_nodes()
        total_candidates = len(all_nodes)

        relevant: list[KnowledgeNode] = []
        prior_sessions: list[KnowledgeNode] = []
        prior_claims: list[KnowledgeNode] = []
        prior_gaps: list[KnowledgeNode] = []
        prior_sources: list[KnowledgeNode] = []
        fresh_claims: list[KnowledgeNode] = []
        stale_claims: list[KnowledgeNode] = []
        unsupported_claims: list[KnowledgeNode] = []

        # Track selection details for explanation
        selection_reasons: dict[str, str] = {}
        score_factors: dict[str, float] = {}
        nodes_excluded: list[str] = []

        for node in all_nodes:
            is_relevant, reason, score = self._compute_node_relevance_details(node, query_terms)
            if is_relevant:
                relevant.append(node)
                selection_reasons[node.id] = _truncate(reason, 200)
                score_factors[node.id] = score

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
            elif len(nodes_excluded) < 5 and len(query_terms) > 0:
                # Track some excluded nodes for debugging (only when candidates > 10)
                if total_candidates > 10:
                    nodes_excluded.append(node.id)

        relevant = relevant[:max_nodes]

        # Sanitize: omit nodes_excluded when candidate count is large to bound payload
        if total_candidates > 10:
            nodes_excluded = []

        filters_applied: list[str] = []
        if depth:
            filters_applied.append(f"depth_filter:{depth}")

        explanation = RetrievalExplanation(
            query=query,
            query_terms=frozenset(query_terms),
            nodes_selected=[n.id for n in relevant],
            nodes_excluded=nodes_excluded,
            selection_reasons={k: _truncate(v, 200) for k, v in selection_reasons.items()},
            score_factors=score_factors,
            filters_applied=filters_applied,
            fallback_active=False,
            total_candidates=total_candidates,
            max_nodes=max_nodes,
        )

        context = KnowledgeContext(
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
        return RetrievalResult(context=context, explanation=explanation)

    @staticmethod
    def _compute_node_relevance_details(
        node: KnowledgeNode, query_terms: set[str]
    ) -> tuple[bool, str, float]:
        """Check if a node is relevant and return match details.

        Returns:
            (is_relevant, reason, score)
            reason: human-readable explanation of why node was/wasn't selected
            score: numeric relevance score based on term overlap
        """
        label_terms = set(re.findall(r"[a-z0-9]+", node.label.lower()))
        prop_values = " ".join(str(v) for v in node.properties.values())
        prop_terms = set(re.findall(r"[a-z0-9]+", prop_values.lower()))
        all_terms = label_terms | prop_terms

        if not query_terms:
            return False, "no query terms after stopword removal", 0.0

        matched_label = query_terms & label_terms
        matched_props = query_terms & prop_terms

        if not matched_label and not matched_props:
            matched = sorted(query_terms)
            return False, f"no terms matched (query had: {matched})", 0.0

        reasons = []
        if matched_label:
            reasons.append(f"label matched: {sorted(matched_label)}")
        if matched_props:
            reasons.append(f"properties matched: {sorted(matched_props)}")

        score = len(matched_label) * 2.0 + len(matched_props) * 1.0
        return True, "; ".join(reasons), score

    @staticmethod
    def _node_relevant(node: KnowledgeNode, query_terms: set[str]) -> bool:
        """Check if a node is relevant to the query."""
        is_relevant, _, _ = KnowledgeRetrievalService._compute_node_relevance_details(
            node, query_terms
        )
        return is_relevant

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


def _truncate(text: str, max_len: int) -> str:
    """Truncate text to max_len characters."""
    if len(text) <= max_len:
        return text
    return text[:max_len] + "..."


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


__all__ = [
    "KnowledgeContext",
    "KnowledgeRetrievalService",
    "RetrievalExplanation",
    "RetrievalResult",
]
