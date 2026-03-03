"""Tests for source credibility scoring."""

from cc_deep_research.credibility import (
    CREDIBILITY_DOMAINS,
    DEFAULT_TLD_SCORES,
    SourceCredibilityScorer,
    format_credibility_badge,
)
from cc_deep_research.models import QualityScore, SearchResultItem


class TestSourceCredibilityScorer:
    """Tests for SourceCredibilityScorer class."""

    def test_scorer_initialization(self) -> None:
        """Test scorer initializes correctly."""
        scorer = SourceCredibilityScorer()
        assert scorer is not None

    def test_extract_domain_basic(self) -> None:
        """Test domain extraction from URLs."""
        scorer = SourceCredibilityScorer()

        assert scorer._extract_domain("https://example.com/path") == "example.com"
        assert scorer._extract_domain("https://www.example.com/path") == "example.com"
        assert scorer._extract_domain("http://sub.example.com/page") == "sub.example.com"

    def test_get_domain_credibility_peer_reviewed(self) -> None:
        """Test credibility for peer-reviewed domains."""
        scorer = SourceCredibilityScorer()

        score, source_type = scorer._get_domain_credibility("pubmed.gov")
        assert score >= 0.95
        assert source_type == "Peer-Reviewed"

    def test_get_domain_credibility_government(self) -> None:
        """Test credibility for government domains."""
        scorer = SourceCredibilityScorer()

        score, source_type = scorer._get_domain_credibility("cdc.gov")
        assert score >= 0.90
        assert source_type == "Government"

    def test_get_domain_credibility_news(self) -> None:
        """Test credibility for news domains."""
        scorer = SourceCredibilityScorer()

        score, source_type = scorer._get_domain_credibility("bbc.com")
        assert 0.6 <= score <= 0.8
        assert source_type == "News"

    def test_get_domain_credibility_blog(self) -> None:
        """Test credibility for blog platforms."""
        scorer = SourceCredibilityScorer()

        score, source_type = scorer._get_domain_credibility("medium.com")
        assert score < 0.5
        assert source_type == "Blog Platform"

    def test_get_domain_credibility_unknown(self) -> None:
        """Test credibility for unknown domains with unknown TLD."""
        scorer = SourceCredibilityScorer()

        # Use a domain with an unknown TLD that won't match DEFAULT_TLD_SCORES
        score, source_type = scorer._get_domain_credibility("unknown-random-domain-12345.xyz")
        assert score == 0.40
        assert source_type == "Web Source"

    def test_get_domain_credibility_subdomain(self) -> None:
        """Test credibility matches subdomain to parent domain."""
        scorer = SourceCredibilityScorer()

        # news.harvard.edu should match harvard.edu
        score, source_type = scorer._get_domain_credibility("news.harvard.edu")
        assert score >= 0.80
        assert source_type == "Academic"

    def test_get_domain_credibility_tld_fallback(self) -> None:
        """Test credibility falls back to TLD for unknown domains."""
        scorer = SourceCredibilityScorer()

        score, source_type = scorer._get_domain_credibility("some-school.edu")
        assert score >= 0.80
        assert source_type == "Educational"

    def test_calculate_relevance_score_high(self) -> None:
        """Test relevance score with matching content."""
        scorer = SourceCredibilityScorer()

        item = SearchResultItem(
            url="https://example.com",
            title="Health Benefits of Green Tea",
            snippet="Green tea has many health benefits including antioxidants.",
        )

        score = scorer._calculate_relevance_score(item, "green tea health benefits")
        assert score >= 0.5

    def test_calculate_relevance_score_low(self) -> None:
        """Test relevance score with non-matching content."""
        scorer = SourceCredibilityScorer()

        item = SearchResultItem(
            url="https://example.com",
            title="Cooking Recipes",
            snippet="How to make delicious pasta dishes.",
        )

        score = scorer._calculate_relevance_score(item, "quantum physics")
        assert score < 0.5

    def test_calculate_freshness_score_recent(self) -> None:
        """Test freshness score for recent content."""
        scorer = SourceCredibilityScorer()

        item = SearchResultItem(
            url="https://example.com",
            title="Test",
            snippet="Test",
            source_metadata={"published_date": "2026-02-01"},
        )

        score = scorer._calculate_freshness_score(item)
        assert score >= 0.9

    def test_calculate_freshness_score_old(self) -> None:
        """Test freshness score for old content."""
        scorer = SourceCredibilityScorer()

        item = SearchResultItem(
            url="https://example.com",
            title="Test",
            snippet="Test",
            source_metadata={"published_date": "2020-01-01"},
        )

        score = scorer._calculate_freshness_score(item)
        assert score < 0.6

    def test_calculate_freshness_score_no_date(self) -> None:
        """Test freshness score when no date is available."""
        scorer = SourceCredibilityScorer()

        item = SearchResultItem(
            url="https://example.com",
            title="Test",
            snippet="Test",
        )

        score = scorer._calculate_freshness_score(item)
        assert score == 0.5  # Default when no date

    def test_calculate_diversity_score_first(self) -> None:
        """Test diversity score for first occurrence of domain."""
        scorer = SourceCredibilityScorer()

        score = scorer._calculate_diversity_score("example.com")
        assert score == 1.0

    def test_calculate_diversity_score_repeat(self) -> None:
        """Test diversity score for repeated domain."""
        scorer = SourceCredibilityScorer()

        scorer._calculate_diversity_score("example.com")
        score = scorer._calculate_diversity_score("example.com")
        assert score == 0.4

    def test_score_source(self) -> None:
        """Test comprehensive source scoring."""
        scorer = SourceCredibilityScorer()

        item = SearchResultItem(
            url="https://pubmed.gov/article",
            title="Health Benefits of Tea Study",
            snippet="A comprehensive study on tea health benefits.",
            source_metadata={"published_date": "2025-06-01"},
        )

        score = scorer.score_source(item, "tea health benefits")

        assert isinstance(score, QualityScore)
        assert 0.0 <= score.credibility <= 1.0
        assert 0.0 <= score.relevance <= 1.0
        assert 0.0 <= score.freshness <= 1.0
        assert 0.0 <= score.diversity <= 1.0
        assert 0.0 <= score.overall <= 1.0

        # High credibility domain should have high credibility score
        assert score.credibility >= 0.9

    def test_score_sources(self) -> None:
        """Test scoring multiple sources."""
        scorer = SourceCredibilityScorer()

        sources = [
            SearchResultItem(url="https://blog.com/post", title="Blog Post", snippet="Info"),
            SearchResultItem(url="https://pubmed.gov/study", title="Study", snippet="Research"),
            SearchResultItem(url="https://news.com/article", title="News", snippet="Article"),
        ]

        scored = scorer.score_sources(sources, "test query")

        assert len(scored) == 3
        # Should be sorted by overall score descending
        assert scored[0][1].overall >= scored[1][1].overall
        assert scored[1][1].overall >= scored[2][1].overall

    def test_get_source_type(self) -> None:
        """Test getting source type for URLs."""
        scorer = SourceCredibilityScorer()

        assert scorer.get_source_type("https://pubmed.gov/article") == "Peer-Reviewed"
        assert scorer.get_source_type("https://cdc.gov/info") == "Government"
        assert scorer.get_source_type("https://medium.com/post") == "Blog Platform"

    def test_get_credibility_summary(self) -> None:
        """Test credibility summary generation."""
        scorer = SourceCredibilityScorer()

        sources = [
            SearchResultItem(url="https://pubmed.gov/1", title="A", snippet=""),
            SearchResultItem(url="https://blog.com/2", title="B", snippet=""),
            SearchResultItem(url="https://news.com/3", title="C", snippet=""),
        ]

        summary = scorer.get_credibility_summary(sources)

        assert summary["total_sources"] == 3
        assert "source_types" in summary
        assert "credibility_distribution" in summary
        assert "high" in summary["credibility_distribution"]
        assert "medium" in summary["credibility_distribution"]
        assert "low" in summary["credibility_distribution"]


class TestFormatCredibilityBadge:
    """Tests for format_credibility_badge function."""

    def test_high_credibility_badge(self) -> None:
        """Test badge for high credibility."""
        score = QualityScore(credibility=0.9)
        badge = format_credibility_badge(score)
        assert badge == "[High Credibility]"

    def test_medium_credibility_badge(self) -> None:
        """Test badge for medium credibility."""
        score = QualityScore(credibility=0.7)
        badge = format_credibility_badge(score)
        assert badge == "[Medium Credibility]"

    def test_standard_source_badge(self) -> None:
        """Test badge for standard sources."""
        score = QualityScore(credibility=0.5)
        badge = format_credibility_badge(score)
        assert badge == "[Standard Source]"

    def test_low_credibility_badge(self) -> None:
        """Test badge for low credibility."""
        score = QualityScore(credibility=0.3)
        badge = format_credibility_badge(score)
        assert badge == "[Low Credibility]"


class TestCredibilityDomains:
    """Tests for credibility domain configuration."""

    def test_peer_reviewed_domains_exist(self) -> None:
        """Test that key peer-reviewed domains are configured."""
        assert "pubmed.gov" in CREDIBILITY_DOMAINS
        assert "nature.com" in CREDIBILITY_DOMAINS
        assert "science.org" in CREDIBILITY_DOMAINS

    def test_government_domains_exist(self) -> None:
        """Test that key government domains are configured."""
        assert "nih.gov" in CREDIBILITY_DOMAINS
        assert "cdc.gov" in CREDIBILITY_DOMAINS
        assert "who.int" in CREDIBILITY_DOMAINS

    def test_default_tld_scores_exist(self) -> None:
        """Test that default TLD scores are configured."""
        assert ".gov" in DEFAULT_TLD_SCORES
        assert ".edu" in DEFAULT_TLD_SCORES
        assert ".com" in DEFAULT_TLD_SCORES
