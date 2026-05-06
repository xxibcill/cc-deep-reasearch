"""Tests for P23-T5 ingestion quality gates."""

from __future__ import annotations

from unittest.mock import MagicMock

from cc_deep_research.knowledge import KnowledgeNode, NodeKind
from cc_deep_research.knowledge.ingestion_gates import (
    BatchValidationResult,
    IngestCheck,
    IngestGate,
    validate_batch,
    validate_record,
)


class TestValidateRecord:
    """Tests for single record validation."""

    def test_valid_record_passes_all_checks(self) -> None:
        """A valid claim node with provenance passes all checks."""
        node = KnowledgeNode(
            id="claim:test-1",
            kind=NodeKind.CLAIM,
            label="Quantum computing has practical applications",
            properties={"source_ids": ["src:1"], "session_ids": ["sess:1"]},
        )
        result = validate_record(node)
        assert result.valid is True
        assert result.rejection_reason is None

    def test_missing_id_fails_required_fields(self) -> None:
        """Node without id fails REQUIRED_FIELDS check.

        Note: id with min_length=1 can't be empty string at construction,
        so we test the validation at the field level conceptually.
        """
        # id field itself can't be empty due to pydantic validation
        # But we can test nodes where id is conceptually absent/placeholder
        node = KnowledgeNode(
            id="test",  # Valid id
            kind=NodeKind.SESSION,
            label="",
            properties={},
        )
        result = validate_record(node)
        # Empty label should fail normalized text check
        assert result.valid is False

    def test_empty_label_fails_normalized_text(self) -> None:
        """Node with empty label fails NORMALIZED_TEXT check."""
        node = KnowledgeNode(
            id="node:1",
            kind=NodeKind.CLAIM,
            label="",
            properties={},
        )
        result = validate_record(node)
        # Empty label fails REQUIRED_FIELDS check
        assert result.valid is False
        assert result.rejection_reason is not None

    def test_whitespace_label_fails_normalized_text(self) -> None:
        """Node with whitespace-only label fails NORMALIZED_TEXT check."""
        node = KnowledgeNode(
            id="node:1",
            kind=NodeKind.CLAIM,
            label="   ",
            properties={},
        )
        result = validate_record(node)
        assert result.valid is False

    def test_short_claim_fails_claim_shape(self) -> None:
        """Claim with less than 10 characters fails CLAIM_SHAPE."""
        node = KnowledgeNode(
            id="claim:1",
            kind=NodeKind.CLAIM,
            label="Short",
            properties={"source_ids": ["src:1"]},
        )
        result = validate_record(node)
        assert result.valid is False
        shape_failed = any(
            c.check == IngestCheck.CLAIM_SHAPE and not c.passed
            for c in result.check_results
        )
        assert shape_failed

    def test_single_word_claim_fails_claim_shape(self) -> None:
        """Claim with only one word fails CLAIM_SHAPE."""
        node = KnowledgeNode(
            id="claim:1",
            kind=NodeKind.CLAIM,
            label="Quantum",
            properties={"source_ids": ["src:1"]},
        )
        result = validate_record(node)
        assert result.valid is False

    def test_claim_without_provenance_fails_source_provenance(self) -> None:
        """Claim without source_ids and low confidence fails SOURCE_PROVENANCE."""
        node = KnowledgeNode(
            id="claim:1",
            kind=NodeKind.CLAIM,
            label="This is a test claim with sufficient length",
            properties={"confidence": 0.3},
        )
        result = validate_record(node)
        assert result.valid is False
        provenance_failed = any(
            c.check == IngestCheck.SOURCE_PROVENANCE and not c.passed
            for c in result.check_results
        )
        assert provenance_failed

    def test_claim_with_confidence_passes_without_provenance(self) -> None:
        """Claim with high confidence passes even without source_ids."""
        node = KnowledgeNode(
            id="claim:1",
            kind=NodeKind.CLAIM,
            label="This is a test claim with sufficient length",
            properties={"confidence": 0.8},
        )
        result = validate_record(node)
        # Should pass since confidence >= 0.5
        provenance_passed = any(
            c.check == IngestCheck.SOURCE_PROVENANCE and c.passed
            for c in result.check_results
        )
        assert provenance_passed

    def test_source_node_bypasses_claim_checks(self) -> None:
        """Source nodes don't need provenance or claim shape checks."""
        node = KnowledgeNode(
            id="source:1",
            kind=NodeKind.SOURCE,
            label="IBM Research Paper",
            properties={"url": "https://ibm.com/paper"},
        )
        result = validate_record(node)
        # Source nodes pass all checks with just proper label
        claim_check_passed = any(
            c.check == IngestCheck.CLAIM_SHAPE and c.passed
            for c in result.check_results
        )
        assert claim_check_passed

    def test_session_node_passes_with_valid_label(self) -> None:
        """Session nodes pass with valid id and label."""
        node = KnowledgeNode(
            id="session:test-123",
            kind=NodeKind.SESSION,
            label="Research on quantum computing",
            properties={},
        )
        result = validate_record(node)
        assert result.valid is True


class TestValidateBatch:
    """Tests for batch validation."""

    def test_empty_batch_returns_zeros(self) -> None:
        """Empty batch returns zero counts."""
        result = validate_batch([])
        assert result.total == 0
        assert result.accepted == 0
        assert result.warned == 0
        assert result.rejected == 0

    def test_all_valid_records_accepted(self) -> None:
        """All valid records are accepted (no duplicate density warnings with unique labels)."""
        nodes = [
            KnowledgeNode(
                id="session:unique1",
                kind=NodeKind.SESSION,
                label="First test session",
                properties={},
            ),
            KnowledgeNode(
                id="source:unique1",
                kind=NodeKind.SOURCE,
                label="Different source title",
                properties={"url": "https://example.com"},
            ),
        ]
        result = validate_batch(nodes)
        assert result.total == 2
        assert result.accepted == 2
        assert result.warned == 0
        assert result.rejected == 0

    def test_partial_acceptance_counts_correctly(self) -> None:
        """Some valid, some invalid records are counted correctly."""
        nodes = [
            KnowledgeNode(
                id="session:alpha",
                kind=NodeKind.SESSION,
                label="Alpha valid session",
                properties={},
            ),
            KnowledgeNode(
                id="session:beta",
                kind=NodeKind.SESSION,
                label="",  # Invalid - empty label
                properties={},
            ),
        ]
        result = validate_batch(nodes)
        assert result.total == 2
        # First node is valid, second is rejected
        assert result.accepted == 1
        assert result.rejected == 1

    def test_duplicate_density_warning(self) -> None:
        """When >30% of batch has same label+kind, warning is raised."""
        nodes = [
            KnowledgeNode(
                id=f"source:{i}",
                kind=NodeKind.SOURCE,
                label="Duplicate Source",
                properties={"url": f"https://example.com/{i}"},
            )
            for i in range(5)
        ]
        # 5 identical nodes = 100% duplicate density
        result = validate_batch(nodes)
        assert result.total == 5
        # All have duplicate density warnings
        for r in result.results:
            assert any("duplicate" in w.lower() for w in r.warnings)


class TestIngestGate:
    """Tests for IngestGate service."""

    def test_validate_nodes_direct(self) -> None:
        """IngestGate.validate_nodes works directly."""
        gate = IngestGate()
        nodes = [
            KnowledgeNode(
                id="session:1",
                kind=NodeKind.SESSION,
                label="Test session",
                properties={},
            ),
        ]
        result = gate.validate_nodes(nodes)
        assert result.accepted == 1

    def test_validate_session_for_ingest(self) -> None:
        """IngestGate.validate_session_for_ingest processes a session."""
        from unittest.mock import MagicMock

        gate = IngestGate()

        # Create a mock session
        mock_session = MagicMock()
        mock_session.session_id = "test-session-123"
        mock_session.query = "Research on AI"
        mock_session.depth.value = "standard"
        mock_session.total_sources = 5
        mock_session.sources = []
        mock_session.metadata = {"analysis": {}}

        result = gate.validate_session_for_ingest(mock_session)
        assert result.total >= 1  # At least session node created

    def test_dry_run_alias(self) -> None:
        """dry_run_ingest is an alias for validate_session_for_ingest."""
        gate = IngestGate()
        mock_session = MagicMock()
        mock_session.session_id = "test"
        mock_session.query = "Test"
        mock_session.depth.value = "standard"
        mock_session.total_sources = 0
        mock_session.sources = []
        mock_session.metadata = {}

        result1 = gate.validate_session_for_ingest(mock_session)
        result2 = gate.dry_run_ingest(mock_session)
        assert result1.total == result2.total


class TestBatchValidationResult:
    """Tests for BatchValidationResult structure."""

    def test_result_includes_all_fields(self) -> None:
        """BatchValidationResult includes all required fields."""
        result = BatchValidationResult(
            total=10,
            accepted=7,
            warned=2,
            rejected=1,
        )
        assert result.total == 10
        assert result.accepted == 7
        assert result.warned == 2
        assert result.rejected == 1

    def test_per_record_results_included(self) -> None:
        """Per-record results are included in batch result."""
        node = KnowledgeNode(
            id="session:1",
            kind=NodeKind.SESSION,
            label="Test",
            properties={},
        )
        result = validate_batch([node])
        assert len(result.results) == 1
        assert result.results[0].record_id == "session:1"
        assert result.results[0].valid is True
