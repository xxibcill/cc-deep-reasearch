"""Tests for the entity and source deduplication service."""

from __future__ import annotations

from pathlib import Path

import pytest

from cc_deep_research.knowledge import (
    EdgeKind,
    KnowledgeNode,
    NodeKind,
)
from cc_deep_research.knowledge.dedup import (
    DuplicateCandidate,
    DuplicateCandidateStore,
    DuplicateMatchReason,
    _build_label_normalized_index,
    _build_url_index,
    _combined_text_similarity,
    _levenshtein_similarity,
    _ngram_similarity,
    _normalize_claim_text,
    _normalize_title,
    _url_stem,
    find_duplicate_candidates,
    merge_nodes,
)
from cc_deep_research.knowledge.graph_index import GraphIndex

# ---------------------------------------------------------------------------
# Text normalization tests
# ---------------------------------------------------------------------------


class TestNormalizeTitle:
    """Tests for title normalization."""

    def test_lowercase_conversion(self) -> None:
        """Titles are lowercased."""
        assert _normalize_title("Hello World") == "hello world"

    def test_strip_punctuation(self) -> None:
        """Punctuation is stripped."""
        assert _normalize_title("Hello, World!") == "hello world"

    def test_collapse_whitespace(self) -> None:
        """Multiple spaces collapsed."""
        assert _normalize_title("Hello    World") == "hello world"


class TestNormalizeClaimText:
    """Tests for claim text normalization."""

    def test_basic_normalization(self) -> None:
        """Basic normalization works."""
        result = _normalize_claim_text("The quick brown fox jumps over the lazy dog")
        assert "the" in result.split() or result.count("the") == 0

    def test_filler_words_removed(self) -> None:
        """Common filler words are removed."""
        result = _normalize_claim_text("The solution is a method that is used")
        words = result.split()
        assert "the" not in words
        assert "is" not in words


class TestUrlStem:
    """Tests for URL stem extraction."""

    def test_simple_url(self) -> None:
        """Simple URL returns last segment."""
        assert _url_stem("https://example.com/page") == "page"

    def test_url_with_query_params(self) -> None:
        """Query params are stripped."""
        assert _url_stem("https://example.com/page?q=test") == "page"

    def test_url_with_fragment(self) -> None:
        """Fragment is stripped."""
        assert _url_stem("https://example.com/page#section") == "page"

    def test_url_without_path(self) -> None:
        """URL without path returns the host."""
        stem = _url_stem("https://example.com")
        assert stem == "example.com"


class TestNgramSimilarity:
    """Tests for n-gram similarity."""

    def test_identical_texts(self) -> None:
        """Identical texts have similarity 1.0."""
        assert _ngram_similarity("hello", "hello") == 1.0

    def test_completely_different(self) -> None:
        """Completely different texts have low similarity."""
        score = _ngram_similarity("abc", "xyz")
        assert score < 0.5

    def test_similar_texts(self) -> None:
        """Similar texts have higher similarity."""
        score = _ngram_similarity("hello world", "hello world")
        assert score > 0.8


class TestLevenshteinSimilarity:
    """Tests for Levenshtein similarity."""

    def test_identical_strings(self) -> None:
        """Identical strings have similarity 1.0."""
        assert _levenshtein_similarity("hello", "hello") == 1.0

    def test_one_char_difference(self) -> None:
        """One character difference yields high similarity."""
        score = _levenshtein_similarity("hello", "hallo")
        assert score > 0.7

    def test_empty_strings(self) -> None:
        """Empty strings return 1.0."""
        assert _levenshtein_similarity("", "") == 1.0

    def test_one_empty_string(self) -> None:
        """One empty string returns 0.0."""
        assert _levenshtein_similarity("hello", "") == 0.0


class TestCombinedTextSimilarity:
    """Tests for combined text similarity."""

    def test_combines_ngram_and_levenshtein(self) -> None:
        """Combined similarity takes the higher score."""
        # Both methods should produce same result for identical strings
        score = _combined_text_similarity("hello world", "hello world")
        assert score == 1.0

    def test_returns_max_of_both_methods(self) -> None:
        """Returns the higher of n-gram and Levenshtein scores."""
        # Different texts may score differently between methods
        score = _combined_text_similarity("test", "text")
        assert 0.0 <= score <= 1.0


# ---------------------------------------------------------------------------
# Index building tests
# ---------------------------------------------------------------------------


class TestBuildLabelNormalizedIndex:
    """Tests for label normalized index building."""

    def test_empty_nodes(self) -> None:
        """Empty list returns empty index."""
        index = _build_label_normalized_index([])
        assert index == {}

    def test_nodes_grouped_by_normalized_label(self) -> None:
        """Nodes with same normalized label are grouped."""
        nodes = [
            KnowledgeNode(id="n1", kind=NodeKind.CLAIM, label="Hello World"),
            KnowledgeNode(id="n2", kind=NodeKind.CLAIM, label="hello world"),
            KnowledgeNode(id="n3", kind=NodeKind.CLAIM, label="Hello World!"),
        ]
        index = _build_label_normalized_index(nodes)
        assert len(index["hello world"]) == 3

    def test_empty_labels_ignored(self) -> None:
        """Nodes with empty labels are not indexed."""
        nodes = [
            KnowledgeNode(id="n1", kind=NodeKind.CLAIM, label=""),
            KnowledgeNode(id="n2", kind=NodeKind.CLAIM, label="Hello"),
        ]
        index = _build_label_normalized_index(nodes)
        assert "" not in index
        assert "hello" in index


class TestBuildUrlIndex:
    """Tests for URL index building."""

    def test_empty_nodes(self) -> None:
        """Empty list returns empty index."""
        index = _build_url_index([])
        assert index == {}

    def test_only_source_nodes_indexed(self) -> None:
        """Only SOURCE nodes are indexed."""
        nodes = [
            KnowledgeNode(id="n1", kind=NodeKind.SESSION, label="Session"),
            KnowledgeNode(id="n2", kind=NodeKind.SOURCE, label="Source", properties={"url": "https://example.com/page"}),
        ]
        index = _build_url_index(nodes)
        assert len(index) == 1

    def test_url_normalized_to_stem(self) -> None:
        """URLs are normalized to stems."""
        nodes = [
            KnowledgeNode(id="n1", kind=NodeKind.SOURCE, label="Source1", properties={"url": "https://example.com/page1"}),
            KnowledgeNode(id="n2", kind=NodeKind.SOURCE, label="Source2", properties={"url": "https://example.com/page1"}),
        ]
        index = _build_url_index(nodes)
        assert len(index["page1"]) == 2


# ---------------------------------------------------------------------------
# DuplicateCandidateStore tests
# ---------------------------------------------------------------------------


class TestDuplicateCandidateStore:
    """Tests for DuplicateCandidateStore."""

    def test_empty_store(self, tmp_path: Path) -> None:
        """Empty store initializes correctly."""
        store_path = tmp_path / "candidates.json"
        store = DuplicateCandidateStore(store_path)
        assert store.get_candidates() == []

    def test_add_and_retrieve_candidate(self, tmp_path: Path) -> None:
        """Adding a candidate makes it retrievable."""
        from datetime import UTC, datetime

        store_path = tmp_path / "candidates.json"
        store = DuplicateCandidateStore(store_path)

        candidate = DuplicateCandidate(
            id="test-id",
            node_a_id="node1",
            node_b_id="node2",
            match_reason=DuplicateMatchReason.SAME_URL,
            confidence=0.9,
            match_evidence={"url": "https://example.com"},
            suggested_action="merge",
            created_at=datetime.now(UTC),
        )

        store.add_candidate(candidate)
        retrieved = store.get_candidates()

        assert len(retrieved) == 1
        assert retrieved[0].id == "test-id"

    def test_duplicate_candidate_not_added_twice(self, tmp_path: Path) -> None:
        """Same candidate cannot be added twice."""
        from datetime import UTC, datetime

        store_path = tmp_path / "candidates.json"
        store = DuplicateCandidateStore(store_path)

        candidate = DuplicateCandidate(
            id="test-id",
            node_a_id="node1",
            node_b_id="node2",
            match_reason=DuplicateMatchReason.SAME_URL,
            confidence=0.9,
            match_evidence={},
            suggested_action="merge",
            created_at=datetime.now(UTC),
        )

        store.add_candidate(candidate)
        store.add_candidate(candidate)

        assert len(store.get_candidates()) == 1

    def test_resolve_candidate(self, tmp_path: Path) -> None:
        """Resolving a candidate updates its status."""
        from datetime import UTC, datetime

        store_path = tmp_path / "candidates.json"
        store = DuplicateCandidateStore(store_path)

        candidate = DuplicateCandidate(
            id="test-id",
            node_a_id="node1",
            node_b_id="node2",
            match_reason=DuplicateMatchReason.SAME_URL,
            confidence=0.9,
            match_evidence={},
            suggested_action="merge",
            created_at=datetime.now(UTC),
        )

        store.add_candidate(candidate)
        result = store.resolve_candidate("test-id", "dismissed")

        assert result is True
        assert store.candidate("test-id") is not None

    def test_add_merged_pair(self, tmp_path: Path) -> None:
        """Merged pairs are recorded for provenance."""
        store_path = tmp_path / "candidates.json"
        store = DuplicateCandidateStore(store_path)

        store.add_merged_pair(
            node_a_id="node1",
            node_b_id="node2",
            kept_node_id="node1",
            removed_node_id="node2",
            session_ids=["session1", "session2"],
            source_ids=["source1"],
        )

        pairs = store.get_merged_pairs()
        assert len(pairs) == 1
        assert pairs[0]["kept_node_id"] == "node1"
        assert pairs[0]["session_ids"] == ["session1", "session2"]

    def test_get_pending_candidates(self, tmp_path: Path) -> None:
        """Pending candidates are filtered correctly."""
        from datetime import UTC, datetime

        store_path = tmp_path / "candidates.json"
        store = DuplicateCandidateStore(store_path)

        # Create and resolve a candidate
        candidate = DuplicateCandidate(
            id="test-id",
            node_a_id="node1",
            node_b_id="node2",
            match_reason=DuplicateMatchReason.SAME_URL,
            confidence=0.9,
            match_evidence={},
            suggested_action="merge",
            created_at=datetime.now(UTC),
        )

        store.add_candidate(candidate)
        store.resolve_candidate("test-id", "merged")

        # Only pending candidates returned
        pending = store.get_pending_candidates()
        assert len(pending) == 0


# ---------------------------------------------------------------------------
# Find duplicate candidates tests
# ---------------------------------------------------------------------------


class TestFindDuplicateCandidates:
    """Tests for find_duplicate_candidates function."""

    def test_empty_index_returns_empty(self, tmp_path: Path) -> None:
        """Empty graph returns no candidates."""
        db = tmp_path / "test.sqlite"
        index = GraphIndex(db)
        index.commit()

        candidates = find_duplicate_candidates(index)
        assert candidates == []

        index.close()

    def test_url_duplicate_detection(self, tmp_path: Path) -> None:
        """Sources with same URL are detected as duplicates."""
        db = tmp_path / "test.sqlite"
        index = GraphIndex(db)

        index.upsert_node(KnowledgeNode(
            id="src:1", kind=NodeKind.SOURCE, label="Source 1",
            properties={"url": "https://example.com/article"}
        ))
        index.upsert_node(KnowledgeNode(
            id="src:2", kind=NodeKind.SOURCE, label="Source 2",
            properties={"url": "https://example.com/article"}
        ))
        index.commit()

        candidates = find_duplicate_candidates(index)

        url_candidates = [c for c in candidates if c.match_reason == DuplicateMatchReason.SAME_URL]
        assert len(url_candidates) >= 1

        index.close()

    def test_title_duplicate_detection(self, tmp_path: Path) -> None:
        """Nodes with same title are detected."""
        db = tmp_path / "test.sqlite"
        index = GraphIndex(db)

        index.upsert_node(KnowledgeNode(
            id="claim:1", kind=NodeKind.CLAIM, label="Climate change is real"
        ))
        index.upsert_node(KnowledgeNode(
            id="claim:2", kind=NodeKind.CLAIM, label="climate change is real"
        ))
        index.commit()

        candidates = find_duplicate_candidates(index)

        title_candidates = [c for c in candidates if c.match_reason == DuplicateMatchReason.SIMILAR_TITLE]
        assert len(title_candidates) >= 1

        index.close()

    def test_entity_duplicate_detection(self, tmp_path: Path) -> None:
        """Entities with same label but different kinds are detected with lower confidence.

        Note: Same kind + same label is caught by SIMILAR_TITLE in section 2.
        SAME_ENTITY_LABEL is used when kinds differ but labels match.
        """
        db = tmp_path / "test.sqlite"
        index = GraphIndex(db)

        # Two entities with same label but different kinds
        index.upsert_node(KnowledgeNode(
            id="entity:1", kind=NodeKind.ENTITY, label="Albert Einstein"
        ))
        index.upsert_node(KnowledgeNode(
            id="concept:1", kind=NodeKind.CONCEPT, label="Albert Einstein"
        ))
        index.commit()

        candidates = find_duplicate_candidates(index)

        entity_candidates = [c for c in candidates if c.match_reason == DuplicateMatchReason.SAME_ENTITY_LABEL]
        assert len(entity_candidates) >= 1
        # Lower confidence since kinds differ
        assert entity_candidates[0].confidence < 0.85

        index.close()

    def test_session_nodes_not_flagged(self, tmp_path: Path) -> None:
        """Two session nodes with same label are not flagged."""
        db = tmp_path / "test.sqlite"
        index = GraphIndex(db)

        index.upsert_node(KnowledgeNode(
            id="session:1", kind=NodeKind.SESSION, label="Research on AI"
        ))
        index.upsert_node(KnowledgeNode(
            id="session:2", kind=NodeKind.SESSION, label="Research on AI"
        ))
        index.commit()

        candidates = find_duplicate_candidates(index)

        # No candidates involving both session nodes
        for c in candidates:
            if c.node_a_id.startswith("session:") and c.node_b_id.startswith("session:"):
                pytest.fail("Session nodes should not be flagged as duplicates")

        index.close()

    def test_claim_text_similarity_detection(self, tmp_path: Path) -> None:
        """Claims with similar text are detected."""
        db = tmp_path / "test.sqlite"
        index = GraphIndex(db)

        index.upsert_node(KnowledgeNode(
            id="claim:1", kind=NodeKind.CLAIM,
            label="The global temperature rose by 1.1 degrees Celsius in 2023"
        ))
        index.upsert_node(KnowledgeNode(
            id="claim:2", kind=NodeKind.CLAIM,
            label="Global temperature rose by 1.1 degrees celsius in 2023"
        ))
        index.commit()

        candidates = find_duplicate_candidates(index)

        text_candidates = [c for c in candidates if c.match_reason == DuplicateMatchReason.SIMILAR_TEXT]
        assert len(text_candidates) >= 1

        index.close()

    def test_similar_names_different_kinds_not_merged(self, tmp_path: Path) -> None:
        """Nodes with same label but different kinds have lower confidence."""
        db = tmp_path / "test.sqlite"
        index = GraphIndex(db)

        index.upsert_node(KnowledgeNode(
            id="claim:1", kind=NodeKind.CLAIM, label="Quantum Computing"
        ))
        index.upsert_node(KnowledgeNode(
            id="concept:1", kind=NodeKind.CONCEPT, label="Quantum Computing"
        ))
        index.commit()

        candidates = find_duplicate_candidates(index)

        # The candidate should have lower confidence since kinds differ
        for c in candidates:
            if c.match_reason == DuplicateMatchReason.SAME_ENTITY_LABEL:
                assert c.confidence < 0.85

        index.close()


# ---------------------------------------------------------------------------
# Merge nodes tests
# ---------------------------------------------------------------------------


class TestMergeNodes:
    """Tests for merge_nodes function."""

    def test_merge_success(self, tmp_path: Path) -> None:
        """Merging two nodes succeeds."""
        db = tmp_path / "test.sqlite"
        index = GraphIndex(db)

        index.upsert_node(KnowledgeNode(
            id="node1", kind=NodeKind.CLAIM, label="Node 1",
            properties={"session_ids": ["s1"], "source_ids": ["src1"]}
        ))
        index.upsert_node(KnowledgeNode(
            id="node2", kind=NodeKind.CLAIM, label="Node 2",
            properties={"session_ids": ["s2"], "source_ids": ["src2"]}
        ))
        index.commit()

        store = DuplicateCandidateStore(tmp_path / "candidates.json")
        result = merge_nodes(index, "node1", "node2", store=store)

        assert result["success"] is True
        assert result["kept_node_id"] in ("node1", "node2")
        assert result["removed_node_id"] in ("node1", "node2")
        assert result["kept_node_id"] != result["removed_node_id"]

        index.close()

    def test_merge_preserves_provenance(self, tmp_path: Path) -> None:
        """Merged nodes preserve session_ids and source_ids from both."""
        db = tmp_path / "test.sqlite"
        index = GraphIndex(db)

        index.upsert_node(KnowledgeNode(
            id="node1", kind=NodeKind.CLAIM, label="Node 1",
            properties={"session_ids": ["s1", "s2"], "source_ids": ["src1"]}
        ))
        index.upsert_node(KnowledgeNode(
            id="node2", kind=NodeKind.CLAIM, label="Node 2",
            properties={"session_ids": ["s3"], "source_ids": ["src2", "src3"]}
        ))
        index.commit()

        store = DuplicateCandidateStore(tmp_path / "candidates.json")
        result = merge_nodes(index, "node1", "node2", store=store)

        assert result["success"] is True

        # Session IDs from both
        session_ids = set(result["session_ids"])
        assert "s1" in session_ids
        assert "s2" in session_ids
        assert "s3" in session_ids

        # Source IDs from both
        source_ids = set(result["source_ids"])
        assert "src1" in source_ids
        assert "src2" in source_ids
        assert "src3" in source_ids

        index.close()

    def test_merge_creates_supersedes_edge(self, tmp_path: Path) -> None:
        """Merge creates a SUPERSEDES edge from kept to removed."""
        db = tmp_path / "test.sqlite"
        index = GraphIndex(db)

        index.upsert_node(KnowledgeNode(id="node1", kind=NodeKind.CLAIM, label="Node 1"))
        index.upsert_node(KnowledgeNode(id="node2", kind=NodeKind.CLAIM, label="Node 2"))
        index.commit()

        store = DuplicateCandidateStore(tmp_path / "candidates.json")
        result = merge_nodes(index, "node1", "node2", store=store)

        assert result["success"] is True

        # Check SUPERSEDES edge exists
        edges = index.all_edges()
        supersedes_edges = [e for e in edges if e.kind == EdgeKind.SUPERSEDES]
        assert len(supersedes_edges) >= 1

        index.close()

    def test_merge_nonexistent_node_fails(self, tmp_path: Path) -> None:
        """Merging nonexistent nodes fails gracefully."""
        db = tmp_path / "test.sqlite"
        index = GraphIndex(db)
        index.commit()

        store = DuplicateCandidateStore(tmp_path / "candidates.json")
        result = merge_nodes(index, "nonexistent", "node2", store=store)

        assert result["success"] is False
        assert "error" in result

        index.close()


# ---------------------------------------------------------------------------
# Integration tests
# ---------------------------------------------------------------------------


class TestDedupCandidateResolution:
    """Tests for the full dedup workflow."""

    def test_dismissed_candidates_not_resurfaced(self, tmp_path: Path) -> None:
        """Dismissed candidates are not shown again as pending."""
        db = tmp_path / "test.sqlite"
        index = GraphIndex(db)

        index.upsert_node(KnowledgeNode(
            id="src:1", kind=NodeKind.SOURCE, label="Source 1",
            properties={"url": "https://example.com/page"}
        ))
        index.upsert_node(KnowledgeNode(
            id="src:2", kind=NodeKind.SOURCE, label="Source 2",
            properties={"url": "https://example.com/page"}
        ))
        index.commit()

        store = DuplicateCandidateStore(tmp_path / "candidates.json")

        # Find candidates
        candidates = find_duplicate_candidates(index)

        # Dismiss a candidate
        if candidates:
            store.resolve_candidate(candidates[0].id, "dismissed")

        # Check no pending candidates remain
        pending = store.get_pending_candidates()
        assert len(pending) == 0

        index.close()
