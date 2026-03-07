"""Query expander agent implementation.

The query expander agent is responsible for:
- Generating purpose-built query families
- Tagging each variation with explicit retrieval intent
- Keeping expansions relevant while reducing repetition
"""

import re
from typing import Any

from cc_deep_research.models import QueryFamily, ResearchDepth


class QueryExpanderAgent:
    """Agent that expands queries into labeled retrieval families."""

    def __init__(self, config: dict[str, Any]) -> None:
        """Initialize the query expander agent."""
        self._config = config

    def expand_query(
        self,
        query: str,
        depth: ResearchDepth,
        max_variations: int | None = None,
        strategy: dict[str, Any] | None = None,
    ) -> list[QueryFamily]:
        """Expand a query into labeled families including the original query."""
        if max_variations is None:
            max_variations = self._get_max_variations(depth)

        strategy_data = strategy or {}
        families = self._generate_query_families(query, strategy_data)
        relevant_families = self.validate_relevance(query, families)
        deduplicated_families = self._deduplicate_families(relevant_families)

        if not any(family.query == query for family in deduplicated_families):
            deduplicated_families.insert(
                0,
                QueryFamily(
                    query=query,
                    family="baseline",
                    intent_tags=self._build_tags("baseline", strategy_data),
                ),
            )

        return deduplicated_families[:max_variations]

    def _get_max_variations(self, depth: ResearchDepth) -> int:
        """Get maximum variations for a depth mode."""
        variations_map = {
            ResearchDepth.QUICK: 1,
            ResearchDepth.STANDARD: 3,
            ResearchDepth.DEEP: 5,
        }
        return variations_map.get(depth, 3)

    def _generate_query_families(
        self,
        query: str,
        strategy_data: dict[str, Any],
    ) -> list[QueryFamily]:
        """Generate family-based expansions with explicit purpose."""
        intent = str(strategy_data.get("intent", "informational"))
        is_time_sensitive = bool(strategy_data.get("time_sensitive", False))
        key_terms = [str(term) for term in strategy_data.get("key_terms", [])]
        source_classes = [str(name) for name in strategy_data.get("target_source_classes", [])]

        candidates = [
            self._create_family(query, "baseline", strategy_data),
        ]

        if self._needs_primary_source_family(intent, source_classes):
            primary_source_query = self._build_primary_source_query(query, source_classes)
            candidates.append(
                self._create_family(primary_source_query, "primary-source", strategy_data)
            )

        candidates.append(
            self._create_family(
                self._build_expert_analysis_query(query, source_classes, key_terms),
                "expert-analysis",
                strategy_data,
            )
        )

        if is_time_sensitive:
            candidates.append(
                self._create_family(
                    self._build_current_updates_query(query),
                    "current-updates",
                    strategy_data,
                )
            )

        candidates.append(
            self._create_family(
                self._build_risk_or_contrast_query(query, intent),
                "opposing-view" if intent == "comparative" else "risk",
                strategy_data,
            )
        )

        return candidates

    def _create_family(
        self,
        query: str,
        family: str,
        strategy_data: dict[str, Any],
    ) -> QueryFamily:
        """Create a typed query family with intent tags."""
        return QueryFamily(
            query=query.strip(),
            family=family,
            intent_tags=self._build_tags(family, strategy_data),
        )

    def _build_tags(self, family: str, strategy_data: dict[str, Any]) -> list[str]:
        """Build deterministic tags for a query family."""
        tags = [family]
        intent = str(strategy_data.get("intent", "informational"))
        tags.append(intent)

        if family == "primary-source":
            tags.append("evidence")
        if family == "expert-analysis":
            tags.append("analysis")
        if family == "current-updates":
            tags.append("freshness")
        if family in {"opposing-view", "risk"}:
            tags.append("contrast" if intent == "comparative" else "risk-review")

        return tags

    @staticmethod
    def _needs_primary_source_family(intent: str, source_classes: list[str]) -> bool:
        """Return whether the strategy should request primary-source coverage."""
        return (
            intent in {"comparative", "evidence-seeking"}
            or "academic" in source_classes
            or "official_docs" in source_classes
        )

    @staticmethod
    def _build_primary_source_query(query: str, source_classes: list[str]) -> str:
        """Build a primary-source oriented query."""
        if "academic" in source_classes and "official_docs" in source_classes:
            return f"{query} primary sources official guidance studies"
        if "academic" in source_classes:
            return f"{query} peer reviewed studies primary sources"
        if "official_docs" in source_classes:
            return f"{query} official guidance filings primary sources"
        return f"{query} primary sources evidence"

    @staticmethod
    def _build_expert_analysis_query(
        query: str,
        source_classes: list[str],
        key_terms: list[str],
    ) -> str:
        """Build an expert-analysis oriented query."""
        focus = "analyst report" if "market_analysis" in source_classes else "expert analysis"
        if key_terms:
            return f"{query} {' '.join(key_terms[:3])} {focus}"
        return f"{query} {focus}"

    @staticmethod
    def _build_current_updates_query(query: str) -> str:
        """Build a freshness-aware query."""
        return f"{query} latest updates current developments news timeline"

    @staticmethod
    def _build_risk_or_contrast_query(query: str, intent: str) -> str:
        """Build an opposing-view or risk-oriented query."""
        if intent == "comparative":
            return f"{query} differences tradeoffs evidence"
        return f"{query} risks criticism opposing view"

    def validate_relevance(
        self,
        original: str,
        families: list[QueryFamily],
    ) -> list[QueryFamily]:
        """Validate that expanded families remain relevant to the original query."""
        original_terms = self._significant_terms(original)
        relevant_families: list[QueryFamily] = []

        for family in families:
            if family.family == "baseline":
                relevant_families.append(family)
                continue

            candidate_terms = self._significant_terms(family.query)
            overlap = len(original_terms & candidate_terms)
            required_overlap = max(1, len(original_terms) // 2)
            if overlap >= required_overlap:
                relevant_families.append(family)

        return relevant_families

    def _deduplicate_families(self, families: list[QueryFamily]) -> list[QueryFamily]:
        """Deduplicate semantically repetitive families while preserving family coverage."""
        deduplicated: list[QueryFamily] = []
        seen_signatures: set[tuple[str, ...]] = set()

        for family in families:
            if family.family == "baseline":
                deduplicated.append(family)
                continue

            signature = self._semantic_signature(family.query)
            if signature in seen_signatures:
                continue
            seen_signatures.add(signature)
            deduplicated.append(family)

        return deduplicated

    @staticmethod
    def _significant_terms(query: str) -> set[str]:
        """Extract significant terms for relevance and deduplication."""
        stop_words = {
            "and",
            "how",
            "information",
            "the",
            "to",
        }
        normalization_map = {
            "analyst": "analysis",
            "experts": "analysis",
            "expert": "analysis",
            "report": "analysis",
            "official": "primary",
            "guidance": "primary",
            "filings": "primary",
            "sources": "primary",
            "studies": "primary",
            "latest": "freshness",
            "current": "freshness",
            "updates": "freshness",
            "developments": "freshness",
            "risks": "risk",
            "criticism": "risk",
        }
        terms = set()
        for term in re.findall(r"[a-z0-9]+", query.lower()):
            if len(term) <= 2 or term in stop_words:
                continue
            terms.add(normalization_map.get(term, term))
        return terms

    def _semantic_signature(self, query: str) -> tuple[str, ...]:
        """Build a stable signature for semantic deduplication."""
        terms = sorted(self._significant_terms(query))
        return tuple(terms[:8])


__all__ = ["QueryExpanderAgent"]
