"""Knowledge planning integration for research workflow."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from cc_deep_research.knowledge import KnowledgeNode
from cc_deep_research.knowledge.retrieval import KnowledgeRetrievalService


@dataclass
class KnowledgePlanningResult:
    """Result of knowledge-assisted planning inputs."""

    knowledge_retrieved: bool
    prior_sessions: list[KnowledgeNode]
    prior_claims: list[KnowledgeNode]
    prior_gaps: list[KnowledgeNode]
    suggested_queries: list[str]
    fresh_claims: list[KnowledgeNode]
    stale_claims: list[KnowledgeNode]
    unsupported_claims: list[KnowledgeNode]
    influence_summary: dict[str, Any]


class KnowledgePlanningService:
    """Service for integrating knowledge into research planning."""

    def __init__(self, config_path: Any | None = None) -> None:
        self._retrieval = KnowledgeRetrievalService(config_path)

    def retrieve_for_planning(
        self,
        query: str,
        *,
        depth: str | None = None,
        enabled: bool = True,
    ) -> KnowledgePlanningResult:
        """Retrieve knowledge relevant to a query for planning purposes.

        Args:
            query: The research query string.
            depth: Optional depth mode.
            enabled: Whether knowledge retrieval is enabled.

        Returns:
            KnowledgePlanningResult with retrieved context and suggestions.
        """
        if not enabled:
            return KnowledgePlanningResult(
                knowledge_retrieved=False,
                prior_sessions=[],
                prior_claims=[],
                prior_gaps=[],
                suggested_queries=[],
                fresh_claims=[],
                stale_claims=[],
                unsupported_claims=[],
                influence_summary={"enabled": False},
            )

        ctx = self._retrieval.retrieve_context(query, depth=depth)

        suggested = ctx.suggested_queries()

        # Seed from stale claims - these need fresh investigation
        for claim in ctx.stale_claims[:3]:
            if claim.label and len(claim.label) > 10:
                suggested.append(f"(refresh) {claim.label}")

        # Seed from unsupported claims - these need source backing
        for claim in ctx.unsupported_claims[:2]:
            if claim.label and len(claim.label) > 10:
                suggested.append(f"(source needed) {claim.label}")

        return KnowledgePlanningResult(
            knowledge_retrieved=ctx.knowledge_used,
            prior_sessions=ctx.prior_sessions,
            prior_claims=ctx.prior_claims,
            prior_gaps=ctx.prior_gaps,
            suggested_queries=suggested[:8],
            fresh_claims=ctx.fresh_claims,
            stale_claims=ctx.stale_claims,
            unsupported_claims=ctx.unsupported_claims,
            influence_summary=ctx.summary_dict(),
        )

    def summarize_influence(
        self,
        session_id: str,
    ) -> dict[str, Any]:
        """Summarize knowledge influence for a completed session."""
        return self._retrieval.get_session_influence(session_id)


def inject_knowledge_influence(
    metadata: dict[str, Any],
    planning_result: KnowledgePlanningResult,
) -> dict[str, Any]:
    """Inject knowledge influence into session metadata.

    Args:
        metadata: The session metadata dict.
        planning_result: The result of knowledge retrieval.

    Returns:
        Updated metadata dict with knowledge influence.
    """
    metadata = dict(metadata)

    knowledge_influence: dict[str, Any] = {
        "knowledge_retrieved": planning_result.knowledge_retrieved,
        "prior_sessions_count": len(planning_result.prior_sessions),
        "prior_claims_count": len(planning_result.prior_claims),
        "prior_gaps_count": len(planning_result.prior_gaps),
        "suggested_queries_from_knowledge": planning_result.suggested_queries,
        "fresh_claims_count": len(planning_result.fresh_claims),
        "stale_claims_count": len(planning_result.stale_claims),
        "unsupported_claims_count": len(planning_result.unsupported_claims),
        "prior_session_ids": [n.id for n in planning_result.prior_sessions],
        "prior_claim_ids": [n.id for n in planning_result.prior_claims],
        "prior_gap_ids": [n.id for n in planning_result.prior_gaps],
    }

    metadata["knowledge_influence"] = knowledge_influence
    return metadata


__all__ = [
    "inject_knowledge_influence",
    "KnowledgePlanningResult",
    "KnowledgePlanningService",
]
