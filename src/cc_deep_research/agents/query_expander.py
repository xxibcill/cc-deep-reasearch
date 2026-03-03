"""Query expander agent implementation.

The query expander agent is responsible for:
- Generating semantic variations of the research query
- Adding related concepts and terms
- Ensuring comprehensive coverage without diluting relevance
"""

from typing import Any

from cc_deep_research.models import ResearchDepth


class QueryExpanderAgent:
    """Agent that expands queries for comprehensive coverage.

    This agent:
    - Generates semantic variations of the original query
    - Adds related concepts when appropriate
    - Ensures variations remain relevant to original intent
    - Limits number of variations based on research depth
    """

    def __init__(self, config: dict[str, Any]) -> None:
        """Initialize the query expander agent.

        Args:
            config: Agent configuration dictionary.
        """
        self._config = config

    def expand_query(
        self,
        query: str,
        depth: ResearchDepth,
        max_variations: int | None = None,
    ) -> list[str]:
        """Expand a query into multiple variations.

        Args:
            query: Original research query.
            depth: Research depth mode.
            max_variations: Maximum variations to generate (optional).

        Returns:
            List of query variations including original.
        """
        # Determine number of variations based on depth
        if max_variations is None:
            max_variations = self._get_max_variations(depth)

        # Generate variations
        variations = self._generate_variations(query, max_variations)

        # Ensure original query is included
        if query not in variations:
            variations.insert(0, query)

        # Limit to max_variations
        return variations[:max_variations]

    def _get_max_variations(self, depth: ResearchDepth) -> int:
        """Get maximum variations for a depth mode.

        Args:
            depth: Research depth mode.

        Returns:
            Maximum number of variations.
        """
        variations_map = {
            ResearchDepth.QUICK: 1,
            ResearchDepth.STANDARD: 3,
            ResearchDepth.DEEP: 5,
        }
        return variations_map.get(depth, 3)

    def _generate_variations(
        self,
        query: str,
        max_count: int,
    ) -> list[str]:
        """Generate query variations.

        Args:
            query: Original query.
            max_count: Maximum number of variations.

        Returns:
            List of query variations.

        Note: This is a placeholder implementation.
        In production, this would use AI to generate
        semantic variations that preserve intent.
        """
        variations = []

        # Simple heuristics for variation generation
        # In production, would use Claude API or similar
        words = query.split()

        # Variation 1: Rephrase (simple)
        if len(words) > 0:
            variations.append(f"{words[-1]} information" if len(words) < 3 else query)

        # Variation 2: Add context
        variations.append(f"comprehensive guide to {query}")

        # Variation 3: Alternative phrasing
        if "how" not in query.lower():
            variations.append(f"how to {query}")

        # Variation 4: Add related terms
        variations.append(f"{query} overview and analysis")

        # Variation 5: Focus on explanation
        variations.append(f"explain {query} in detail")

        return variations[:max_count]

    def validate_relevance(
        self,
        original: str,
        variations: list[str],
    ) -> list[str]:
        """Validate that variations are relevant to original query.

        Args:
            original: Original query string.
            variations: List of query variations.

        Returns:
            List of relevant variations only.

        Note: This is a placeholder implementation.
        In production, would use semantic similarity or AI analysis.
        """
        relevant = []

        for variation in variations:
            # Simple check: ensure original keywords are present
            original_words = set(original.lower().split())
            variation_words = set(variation.lower().split())

            # At least 50% of original words should be present
            overlap = len(original_words & variation_words)
            if overlap >= len(original_words) * 0.5:
                relevant.append(variation)

        return relevant


__all__ = ["QueryExpanderAgent"]
