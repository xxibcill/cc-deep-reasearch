"""Source credibility scoring for CC Deep Research CLI.

This module provides credibility scoring for sources based on:
- Domain reputation (peer-reviewed, government, educational, news, blog, etc.)
- Content relevance to the query
- Publication freshness
- Source diversity

The scoring helps readers distinguish reliable from unreliable sources.
"""

from datetime import datetime
from typing import Any
from urllib.parse import urlparse

from cc_deep_research.models import QualityScore, SearchResultItem

# Domain credibility categories with base scores
CREDIBILITY_DOMAINS: dict[str, tuple[float, str]] = {
    # Tier 1: Peer-reviewed / Academic / Government (0.9-1.0)
    "pubmed.gov": (0.98, "Peer-Reviewed"),
    "ncbi.nlm.nih.gov": (0.98, "Peer-Reviewed"),
    "nih.gov": (0.95, "Government"),
    "who.int": (0.95, "Government"),
    "cdc.gov": (0.95, "Government"),
    "fda.gov": (0.95, "Government"),
    "nature.com": (0.95, "Peer-Reviewed"),
    "science.org": (0.95, "Peer-Reviewed"),
    "sciencedirect.com": (0.93, "Peer-Reviewed"),
    "springer.com": (0.93, "Peer-Reviewed"),
    "wiley.com": (0.93, "Peer-Reviewed"),
    "arxiv.org": (0.90, "Preprint"),
    "biorxiv.org": (0.90, "Preprint"),
    "medrxiv.org": (0.90, "Preprint"),
    "jstor.org": (0.92, "Academic"),
    "scholar.google.com": (0.90, "Academic"),

    # Tier 2: Educational / Research Institutions (0.8-0.9)
    "harvard.edu": (0.88, "Academic"),
    "stanford.edu": (0.88, "Academic"),
    "mit.edu": (0.88, "Academic"),
    "berkeley.edu": (0.88, "Academic"),
    "ox.ac.uk": (0.88, "Academic"),
    "cam.ac.uk": (0.88, "Academic"),
    "mayoclinic.org": (0.85, "Medical Institution"),
    "clevelandclinic.org": (0.85, "Medical Institution"),
    "webmd.com": (0.75, "Medical Reference"),
    "healthline.com": (0.72, "Medical Reference"),
    "medicalnewstoday.com": (0.70, "Medical News"),

    # Tier 3: Reputable News & Media (0.6-0.8)
    "reuters.com": (0.78, "News Agency"),
    "apnews.com": (0.78, "News Agency"),
    "bbc.com": (0.75, "News"),
    "nytimes.com": (0.72, "News"),
    "washingtonpost.com": (0.72, "News"),
    "theguardian.com": (0.72, "News"),
    "economist.com": (0.75, "News"),
    "wsj.com": (0.72, "News"),
    "cnn.com": (0.68, "News"),
    "npr.org": (0.75, "News"),
    "forbes.com": (0.65, "Business News"),
    "bloomberg.com": (0.68, "Business News"),

    # Tier 4: Reference & General (0.5-0.7)
    "wikipedia.org": (0.65, "Encyclopedia"),
    "britannica.com": (0.70, "Encyclopedia"),
    "investopedia.com": (0.65, "Reference"),

    # Tier 5: Blogs & Commercial (0.3-0.5)
    "medium.com": (0.45, "Blog Platform"),
    "substack.com": (0.45, "Blog Platform"),
    "reddit.com": (0.35, "Social Media"),
    "quora.com": (0.35, "Social Media"),
    "pinterest.com": (0.30, "Social Media"),
    "youtube.com": (0.40, "Video Platform"),
}

# Default scores for unknown domains by TLD
DEFAULT_TLD_SCORES: dict[str, tuple[float, str]] = {
    ".gov": (0.90, "Government"),
    ".edu": (0.80, "Educational"),
    ".org": (0.55, "Organization"),
    ".com": (0.45, "Commercial"),
    ".net": (0.40, "Network"),
    ".io": (0.40, "Tech Startup"),
    ".co": (0.40, "Commercial"),
    ".info": (0.35, "Information"),
    ".blog": (0.35, "Blog"),
}


class SourceCredibilityScorer:
    """Scores sources based on credibility factors.

    This class provides:
    - Domain-based credibility scoring
    - Relevance scoring based on content
    - Freshness scoring based on publication date
    - Diversity scoring to promote varied sources
    """

    def __init__(self) -> None:
        """Initialize the credibility scorer."""
        self._seen_domains: set[str] = set()

    def _extract_domain(self, url: str) -> str:
        """Extract the main domain from a URL.

        Args:
            url: URL to extract domain from.

        Returns:
            Lowercase domain string.
        """
        try:
            parsed = urlparse(url.lower())
            domain = parsed.netloc

            # Remove www prefix
            if domain.startswith("www."):
                domain = domain[4:]

            return domain
        except Exception:
            return ""

    def _get_domain_credibility(self, domain: str) -> tuple[float, str]:
        """Get credibility score and type for a domain.

        Args:
            domain: Domain to score.

        Returns:
            Tuple of (credibility_score, source_type).
        """
        # Check exact match
        if domain in CREDIBILITY_DOMAINS:
            return CREDIBILITY_DOMAINS[domain]

        # Check for subdomain matches (e.g., news.harvard.edu -> harvard.edu)
        parts = domain.split(".")
        for i in range(len(parts) - 1):
            partial = ".".join(parts[i:])
            if partial in CREDIBILITY_DOMAINS:
                return CREDIBILITY_DOMAINS[partial]

        # Check TLD defaults
        for tld, (score, source_type) in DEFAULT_TLD_SCORES.items():
            if domain.endswith(tld):
                return (score, source_type)

        # Unknown domain - low default
        return (0.40, "Web Source")

    def _calculate_relevance_score(
        self,
        item: SearchResultItem,
        query: str,
    ) -> float:
        """Calculate relevance score based on query matching.

        Args:
            item: Search result item.
            query: Original search query.

        Returns:
            Relevance score (0.0-1.0).
        """
        if not query:
            return 0.5

        query_words = set(query.lower().split())
        if not query_words:
            return 0.5

        # Combine title, snippet, and content for matching
        text = f"{item.title} {item.snippet}".lower()
        if item.content:
            # Use first 500 chars of content
            text += f" {item.content[:500]}".lower()

        text_words = set(text.split())

        # Calculate word overlap
        if not text_words:
            return 0.3

        overlap = len(query_words & text_words)
        score = overlap / len(query_words)

        # Boost if query words appear in title
        title_words = set(item.title.lower().split())
        title_overlap = len(query_words & title_words)
        if title_overlap > 0:
            score = min(1.0, score + 0.2)

        return max(0.1, min(1.0, score))

    def _calculate_freshness_score(
        self,
        item: SearchResultItem,
    ) -> float:
        """Calculate freshness score based on publication date.

        Args:
            item: Search result item.

        Returns:
            Freshness score (0.0-1.0).
        """
        # Check for publication date in metadata
        published_date = item.source_metadata.get("published_date")

        if not published_date:
            # Check alternative metadata fields
            published_date = item.source_metadata.get("published")

        if not published_date:
            # No date available - assume moderate freshness
            return 0.5

        try:
            # Parse date (handle various formats)
            if isinstance(published_date, str):
                # Try ISO format first
                try:
                    pub_dt = datetime.fromisoformat(published_date.replace("Z", "+00:00"))
                except ValueError:
                    # Try common formats
                    for fmt in ["%Y-%m-%d", "%Y/%m/%d", "%d/%m/%Y", "%B %d, %Y"]:
                        try:
                            pub_dt = datetime.strptime(published_date, fmt)
                            break
                        except ValueError:
                            continue
                    else:
                        return 0.5
            elif isinstance(published_date, datetime):
                pub_dt = published_date
            else:
                return 0.5

            # Calculate age in days
            age_days = (datetime.utcnow() - pub_dt.replace(tzinfo=None)).days

            # Score based on age
            if age_days < 30:  # Less than 1 month
                return 1.0
            elif age_days < 90:  # 1-3 months
                return 0.9
            elif age_days < 180:  # 3-6 months
                return 0.8
            elif age_days < 365:  # 6-12 months
                return 0.7
            elif age_days < 730:  # 1-2 years
                return 0.6
            elif age_days < 1825:  # 2-5 years
                return 0.5
            else:  # 5+ years
                return 0.4

        except Exception:
            return 0.5

    def _calculate_diversity_score(
        self,
        domain: str,
    ) -> float:
        """Calculate diversity score based on domain uniqueness.

        Args:
            domain: Domain to check.

        Returns:
            Diversity score (0.0-1.0).
        """
        if domain in self._seen_domains:
            # Already seen this domain - lower diversity
            return 0.4

        # New domain - high diversity
        self._seen_domains.add(domain)
        return 1.0

    def score_source(
        self,
        item: SearchResultItem,
        query: str,
    ) -> QualityScore:
        """Calculate comprehensive quality score for a source.

        Args:
            item: Search result item to score.
            query: Original search query.

        Returns:
            QualityScore with individual factor scores.
        """
        domain = self._extract_domain(item.url)
        credibility, _ = self._get_domain_credibility(domain)
        relevance = self._calculate_relevance_score(item, query)
        freshness = self._calculate_freshness_score(item)
        diversity = self._calculate_diversity_score(domain)

        # Calculate overall score with weights
        # Credibility is most important, then relevance
        overall = (
            credibility * 0.40 +
            relevance * 0.30 +
            freshness * 0.15 +
            diversity * 0.15
        )

        return QualityScore(
            credibility=credibility,
            relevance=relevance,
            freshness=freshness,
            diversity=diversity,
            overall=overall,
        )

    def get_source_type(self, url: str) -> str:
        """Get the source type label for a URL.

        Args:
            url: URL to classify.

        Returns:
            Source type string (e.g., "Peer-Reviewed", "News", "Blog").
        """
        domain = self._extract_domain(url)
        _, source_type = self._get_domain_credibility(domain)
        return source_type

    def score_sources(
        self,
        sources: list[SearchResultItem],
        query: str,
    ) -> list[tuple[SearchResultItem, QualityScore]]:
        """Score multiple sources.

        Args:
            sources: List of search result items.
            query: Original search query.

        Returns:
            List of (source, score) tuples sorted by overall score descending.
        """
        # Reset diversity tracking for new scoring session
        self._seen_domains.clear()

        scored = []
        for source in sources:
            score = self.score_source(source, query)
            scored.append((source, score))

        # Sort by overall score descending
        scored.sort(key=lambda x: x[1].overall, reverse=True)

        return scored

    def get_credibility_summary(
        self,
        sources: list[SearchResultItem],
    ) -> dict[str, Any]:
        """Generate a summary of source credibility distribution.

        Args:
            sources: List of search result items.

        Returns:
            Dictionary with credibility statistics.
        """
        type_counts: dict[str, int] = {}
        credibility_tiers = {"high": 0, "medium": 0, "low": 0}

        for source in sources:
            source_type = self.get_source_type(source.url)
            type_counts[source_type] = type_counts.get(source_type, 0) + 1

            domain = self._extract_domain(source.url)
            cred, _ = self._get_domain_credibility(domain)

            if cred >= 0.8:
                credibility_tiers["high"] += 1
            elif cred >= 0.5:
                credibility_tiers["medium"] += 1
            else:
                credibility_tiers["low"] += 1

        return {
            "total_sources": len(sources),
            "source_types": type_counts,
            "credibility_distribution": credibility_tiers,
        }


def format_credibility_badge(score: QualityScore) -> str:
    """Format a credibility badge for display.

    Args:
        score: Quality score to format.

    Returns:
        Formatted badge string.
    """
    if score.credibility >= 0.8:
        return "[High Credibility]"
    elif score.credibility >= 0.6:
        return "[Medium Credibility]"
    elif score.credibility >= 0.4:
        return "[Standard Source]"
    else:
        return "[Low Credibility]"


__all__ = [
    "SourceCredibilityScorer",
    "QualityScore",
    "format_credibility_badge",
    "CREDIBILITY_DOMAINS",
    "DEFAULT_TLD_SCORES",
]
