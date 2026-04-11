"""Research lead agent implementation.

The research lead agent is responsible for:
- Orchestrating overall research strategy
- Decomposing research queries into tasks
- Coordinating task assignment to other agents
- Monitoring research progress
- Aggregating results from all agents
"""

import re
from typing import Any

from cc_deep_research.models import (
    QueryProfile,
    ResearchDepth,
    ResearchSession,
    StrategyPlan,
    StrategyResult,
)


class ResearchLeadAgent:
    """Lead agent that orchestrates research strategy.

    This agent serves as the team coordinator, responsible for:
    - Analyzing the research query
    - Determining research strategy based on depth mode
    - Creating and assigning tasks to appropriate agents
    - Monitoring progress of all tasks
    - Collecting and aggregating results from all agents
    - Ensuring research quality and completeness
    """

    def __init__(self, config: dict[str, Any]) -> None:
        """Initialize the research lead agent.

        Args:
            config: Agent configuration dictionary.
        """
        self._config = config

    def analyze_query(
        self,
        query: str,
        depth: ResearchDepth,
    ) -> StrategyResult:
        """Analyze the research query and determine strategy.

        Args:
            query: The research query string.
            depth: Research depth mode (quick/standard/deep).

        Returns:
            Typed strategy result and task plan.
        """
        # Analyze query complexity and scope
        complexity = self._assess_complexity(query)
        profile = self._build_query_profile(query)

        # Determine strategy based on depth
        strategy = self._create_strategy(depth, complexity, profile)

        return StrategyResult(
            query=query,
            complexity=complexity,
            depth=depth,
            profile=profile,
            strategy=strategy,
            tasks_needed=list(strategy.tasks),
        )

    def _assess_complexity(self, query: str) -> str:
        """Assess the complexity of a research query.

        Args:
            query: The research query.

        Returns:
            Complexity level: "simple", "moderate", or "complex".
        """
        # Simple heuristic assessment
        # In production, this could use AI analysis
        words = len(query.split())
        if words < 5:
            return "simple"
        elif words < 15:
            return "moderate"
        else:
            return "complex"

    def _create_strategy(
        self,
        depth: ResearchDepth,
        complexity: str,
        profile: QueryProfile,
    ) -> StrategyPlan:
        """Create research strategy based on depth and complexity.

        Args:
            depth: Research depth mode.
            complexity: Query complexity level.

        Returns:
            Strategy dictionary with task plan.
        """
        strategies: dict[ResearchDepth, dict[str, Any]] = {
            ResearchDepth.QUICK: {
                "query_variations": 1,
                "max_sources": 3,
                "enable_cross_ref": False,
                "enable_quality_scoring": False,
                "tasks": ["collect", "report"],
            },
            ResearchDepth.STANDARD: {
                "query_variations": 3,
                "max_sources": 10,
                "enable_cross_ref": False,
                "enable_quality_scoring": True,
                "tasks": ["expand", "collect", "analyze", "report"],
            },
            ResearchDepth.DEEP: {
                "query_variations": 5,
                "max_sources": 20,
                "enable_cross_ref": True,
                "enable_quality_scoring": True,
                "tasks": ["expand", "collect", "analyze", "validate", "report"],
            },
        }

        base_strategy = strategies[depth].copy()

        # Adjust based on complexity
        if complexity == "simple":
            base_strategy["query_variations"] = 1
        elif complexity == "complex" and depth == ResearchDepth.DEEP:
            base_strategy["query_variations"] = 7

        if profile.is_time_sensitive:
            base_strategy["query_variations"] += 1

        if profile.intent == "comparative":
            base_strategy["tasks"] = [
                *base_strategy["tasks"],
                "compare",
            ]

        base_strategy["follow_up_bias"] = self._get_follow_up_bias(profile)
        base_strategy["intent"] = profile.intent
        base_strategy["time_sensitive"] = profile.is_time_sensitive
        base_strategy["key_terms"] = profile.key_terms
        base_strategy["target_source_classes"] = profile.target_source_classes

        return StrategyPlan(**base_strategy)

    def _build_query_profile(self, query: str) -> QueryProfile:
        """Build a lightweight profile for planning and expansion."""
        words = self._tokenize(query)
        key_terms = self._extract_key_terms(words)
        intent = self._classify_intent(query, words)
        is_time_sensitive = self._detect_time_sensitivity(query, words)
        target_source_classes = self._infer_source_classes(query, words, intent, is_time_sensitive)

        return QueryProfile(
            intent=intent,
            is_time_sensitive=is_time_sensitive,
            key_terms=key_terms,
            target_source_classes=target_source_classes,
        )

    def _get_follow_up_bias(self, profile: QueryProfile) -> str:
        """Describe the preferred follow-up direction for the query."""
        if profile.intent == "comparative":
            return "comparison_evidence"
        if profile.intent == "evidence-seeking":
            return "primary_evidence"
        if profile.is_time_sensitive:
            return "recent_updates"
        return "coverage"

    @staticmethod
    def _tokenize(query: str) -> list[str]:
        """Tokenize a query into normalized lowercase terms."""
        return re.findall(r"[a-z0-9]+", query.lower())

    @staticmethod
    def _extract_key_terms(words: list[str]) -> list[str]:
        """Return stable keywords with duplicates removed."""
        stop_words = {
            "a",
            "an",
            "and",
            "are",
            "best",
            "can",
            "for",
            "from",
            "how",
            "in",
            "is",
            "of",
            "or",
            "the",
            "to",
            "what",
            "which",
            "who",
            "why",
        }
        key_terms: list[str] = []
        seen: set[str] = set()
        for word in words:
            if len(word) <= 2 or word in stop_words or word in seen:
                continue
            seen.add(word)
            key_terms.append(word)
            if len(key_terms) >= 8:
                break
        return key_terms

    def _classify_intent(self, query: str, words: list[str]) -> str:
        """Classify the primary research intent using deterministic signals."""
        comparative_terms = {
            "better",
            "compare",
            "comparison",
            "versus",
            "vs",
            "difference",
            "differences",
        }
        evidence_terms = {
            "citation",
            "citations",
            "data",
            "dataset",
            "datasets",
            "evidence",
            "evidence-based",
            "proof",
            "prove",
            "research",
            "source",
            "sources",
            "study",
            "studies",
            "supporting",
        }

        if any(term in words for term in comparative_terms):
            return "comparative"
        if any(term in words for term in evidence_terms):
            return "evidence-seeking"
        if self._detect_time_sensitivity(query, words):
            return "time-sensitive"
        return "informational"

    def _detect_time_sensitivity(self, query: str, words: list[str]) -> bool:
        """Detect whether a query depends on recent or dated information."""
        lowered = query.lower()
        time_terms = {
            "breaking",
            "current",
            "currently",
            "forecast",
            "latest",
            "newest",
            "now",
            "recent",
            "recently",
            "today",
            "tonight",
            "trending",
            "update",
            "updates",
            "upcoming",
            "yesterday",
        }
        month_names = {
            "january",
            "february",
            "march",
            "april",
            "may",
            "june",
            "july",
            "august",
            "september",
            "october",
            "november",
            "december",
        }

        if any(term in words for term in time_terms):
            return True
        if "as of" in lowered or "this week" in lowered or "this month" in lowered:
            return True
        if any(month in words for month in month_names):
            return True
        return re.search(r"\b(19|20)\d{2}\b", query) is not None

    def _infer_source_classes(
        self,
        query: str,
        words: list[str],
        intent: str,
        is_time_sensitive: bool,
    ) -> list[str]:
        """Infer likely source classes needed to answer the query well."""
        lowered = query.lower()
        academic_terms = {
            "academic",
            "clinical",
            "journal",
            "meta-analysis",
            "paper",
            "papers",
            "peer",
            "peer-reviewed",
            "research",
            "scholar",
            "science",
            "scientific",
            "study",
            "studies",
            "trial",
        }
        official_terms = {
            "agency",
            "compliance",
            "court",
            "fda",
            "filing",
            "filings",
            "government",
            "guidance",
            "law",
            "legal",
            "official",
            "policy",
            "regulation",
            "regulations",
            "regulator",
            "rule",
            "rules",
            "sec",
            "standard",
            "standards",
        }
        market_terms = {
            "earnings",
            "equity",
            "finance",
            "financial",
            "forecast",
            "industry",
            "investment",
            "investor",
            "market",
            "pricing",
            "revenue",
            "stock",
            "trade",
            "valuation",
        }

        target_source_classes: list[str] = []

        def add_source_class(name: str) -> None:
            if name not in target_source_classes:
                target_source_classes.append(name)

        if is_time_sensitive:
            add_source_class("news")
        if intent == "evidence-seeking" or any(term in lowered for term in academic_terms):
            add_source_class("academic")
        if any(term in lowered for term in official_terms):
            add_source_class("official_docs")
        if any(term in lowered for term in market_terms):
            add_source_class("market_analysis")
        if intent == "comparative":
            add_source_class("official_docs")
            add_source_class("market_analysis")
        if not target_source_classes:
            add_source_class("official_docs" if len(words) <= 4 else "news")

        return target_source_classes

    def coordinate_research(
        self,
        strategy: StrategyResult,
    ) -> ResearchSession:
        """Coordinate the research process using the strategy.

        Args:
            strategy: Research strategy from analyze_query.

        Returns:
            ResearchSession with aggregated results.

        Note: In actual implementation, this would:
        - Create tasks based on strategy
        - Assign tasks to appropriate agents
        - Monitor task progress
        - Collect results from all agents
        - Aggregate and validate results
        """
        # Placeholder - would implement actual coordination
        # using Claude's SendMessage and Task management tools
        session_id = f"session-{hash(strategy)}"

        return ResearchSession(
            session_id=session_id,
            query=strategy.query,
        )

    def validate_completeness(
        self,
        session: ResearchSession,
        min_sources: int | None = None,
    ) -> tuple[bool, list[str]]:
        """Validate that research is complete and sufficient.

        Args:
            session: Research session to validate.
            min_sources: Minimum required sources.

        Returns:
            Tuple of (is_complete, list of issues).
        """
        issues = []

        # Check source count
        if min_sources and session.total_sources < min_sources:
            issues.append(f"Insufficient sources: {session.total_sources} < {min_sources}")

        # Check for gaps (placeholder logic)
        if not session.sources:
            issues.append("No sources collected")

        # Check for diversity (placeholder logic)
        # In production, would analyze domain diversity

        is_complete = len(issues) == 0
        return is_complete, issues


__all__ = ["ResearchLeadAgent"]
