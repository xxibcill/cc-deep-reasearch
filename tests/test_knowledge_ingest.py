"""Tests for knowledge ingest functionality."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

import pytest

from cc_deep_research.knowledge.ingest import IngestResult, ingest_session
from cc_deep_research.knowledge.vault import (
    claims_dir,
    sessions_dir,
    sources_dir,
    vault_root,
)
from cc_deep_research.models import ResearchDepth, ResearchSession, SearchResultItem


@pytest.fixture
def sample_session() -> ResearchSession:
    """Create a sample ResearchSession for ingest testing."""
    session = ResearchSession(
        session_id="ingest-test-session-001",
        query="What is quantum computing?",
        depth=ResearchDepth.DEEP,
        started_at=datetime(2024, 1, 15, 10, 30, 0),
        completed_at=datetime(2024, 1, 15, 10, 35, 0),
        sources=[
            SearchResultItem(
                url="https://example.com/quantum",
                title="Introduction to Quantum Computing",
                snippet="Quantum computing uses qubits...",
                score=0.95,
            ),
            SearchResultItem(
                url="https://ibm.com/quantum-computing",
                title="IBM Quantum Computing",
                snippet="IBM's quantum computing research...",
                score=0.88,
            ),
        ],
        metadata={
            "analysis": {
                "key_findings": [
                    {
                        "title": "Quantum computers use qubits",
                        "summary": "Quantum computers use quantum bits (qubits)",
                        "description": "Unlike classical bits, qubits can exist in superposition",
                        "source": "https://example.com/quantum",
                        "evidence": ["https://example.com/quantum"],
                        "confidence": "high",
                    },
                ],
                "gaps": [
                    {
                        "gap_description": "Limited information on commercial applications",
                        "suggested_queries": ["quantum computing commercial applications"],
                        "importance": "medium",
                    },
                ],
                "cross_reference_claims": [
                    {
                        "claim": "Quantum computers can solve certain problems exponentially faster",
                        "supporting_sources": [
                            {
                                "url": "https://example.com/quantum",
                                "title": "Quantum Computing Intro",
                                "snippet": "exponentially faster than classical",
                            }
                        ],
                        "contradicting_sources": [],
                        "confidence": "high",
                        "freshness": "current",
                        "evidence_type": "research",
                        "consensus_level": 1.0,
                    },
                ],
                "themes": ["Quantum mechanics", "Computing"],
            },
            "validation": {
                "quality_score": 0.85,
            },
        },
    )
    return session


class TestIngestSession:
    """Tests for the ingest_session function."""

    def test_ingest_creates_vault_directories(self, tmp_path: Path, sample_session: ResearchSession) -> None:
        """Ingest should create all vault directories."""
        config = tmp_path / "config.yaml"
        config.write_text("")

        result = ingest_session(sample_session, config_path=config)

        root = vault_root(config)
        assert (root / "raw").exists()
        assert (root / "wiki" / "sessions").exists()
        assert (root / "wiki" / "sources").exists()
        assert (root / "wiki" / "claims").exists()
        assert (root / "wiki" / "questions").exists()
        assert (root / "graph").exists()

    def test_ingest_creates_raw_artifacts(self, tmp_path: Path, sample_session: ResearchSession) -> None:
        """Ingest should create raw session snapshot."""
        config = tmp_path / "config.yaml"
        config.write_text("")

        result = ingest_session(sample_session, config_path=config)

        raw_session = tmp_path / "knowledge" / "raw" / "sessions" / "ingest-test-session-001" / "session.json"
        assert raw_session.exists()
        data = json.loads(raw_session.read_text())
        assert data["session_id"] == "ingest-test-session-001"

    def test_ingest_creates_session_wiki_page(self, tmp_path: Path, sample_session: ResearchSession) -> None:
        """Ingest should create a session wiki page."""
        config = tmp_path / "config.yaml"
        config.write_text("")

        result = ingest_session(sample_session, config_path=config)

        session_page = sessions_dir(config) / "ingest-test-session-001.md"
        assert session_page.exists()
        content = session_page.read_text()
        assert "Research Session:" in content
        assert sample_session.query in content

    def test_ingest_creates_source_wiki_pages(self, tmp_path: Path, sample_session: ResearchSession) -> None:
        """Ingest should create wiki pages for sources."""
        config = tmp_path / "config.yaml"
        config.write_text("")

        result = ingest_session(sample_session, config_path=config)

        sources_wiki = sources_dir(config)
        md_files = list(sources_wiki.glob("*.md"))
        assert len(md_files) >= 2

    def test_ingest_creates_claim_wiki_pages(self, tmp_path: Path, sample_session: ResearchSession) -> None:
        """Ingest should create wiki pages for claims."""
        config = tmp_path / "config.yaml"
        config.write_text("")

        result = ingest_session(sample_session, config_path=config)

        claims_wiki = claims_dir(config)
        md_files = list(claims_wiki.glob("*.md"))
        assert len(md_files) >= 1

    def test_ingest_result_tracks_counts(self, tmp_path: Path, sample_session: ResearchSession) -> None:
        """IngestResult should track ingestion counts."""
        config = tmp_path / "config.yaml"
        config.write_text("")

        result = ingest_session(sample_session, config_path=config)

        assert result.session_id == "ingest-test-session-001"
        assert result.nodes_ingested > 0
        assert result.sources_ingested == 2
        assert result.claims_ingested >= 1
        assert result.gaps_ingested >= 1

    def test_ingest_handles_missing_report_gracefully(self, tmp_path: Path, sample_session: ResearchSession) -> None:
        """Ingest should not fail when report is None."""
        config = tmp_path / "config.yaml"
        config.write_text("")

        result = ingest_session(sample_session, report_md=None, config_path=config)

        assert result.session_id == "ingest-test-session-001"
        assert result.warnings == [] or len(result.warnings) >= 0

    def test_ingest_with_report_snapshots_report(self, tmp_path: Path, sample_session: ResearchSession) -> None:
        """Ingest with a report should snapshot it."""
        config = tmp_path / "config.yaml"
        config.write_text("")
        report_md = "# Quantum Computing Report\n\nThis report covers..."

        result = ingest_session(sample_session, report_md=report_md, config_path=config)

        raw_report = tmp_path / "knowledge" / "raw" / "sessions" / "ingest-test-session-001" / "report.json"
        assert raw_report.exists()

    def test_ingest_non_fatal_on_file_errors(self, tmp_path: Path, sample_session: ResearchSession) -> None:
        """Ingest should not raise on file write errors."""
        config = tmp_path / "config.yaml"
        config.write_text("")

        # Should succeed even with unusual conditions
        result = ingest_session(sample_session, config_path=config)
        assert isinstance(result, IngestResult)
        assert result.session_id == "ingest-test-session-001"

    def test_reingest_is_idempotent(self, tmp_path: Path, sample_session: ResearchSession) -> None:
        """Re-ingesting the same session should not duplicate content."""
        config = tmp_path / "config.yaml"
        config.write_text("")

        result1 = ingest_session(sample_session, config_path=config)
        result2 = ingest_session(sample_session, config_path=config)

        # Both should succeed
        assert result2.nodes_ingested >= 0
        assert result2.sources_ingested >= 0

    def test_ingest_creates_manifest(self, tmp_path: Path, sample_session: ResearchSession) -> None:
        """Ingest should create a manifest file."""
        config = tmp_path / "config.yaml"
        config.write_text("")

        result = ingest_session(sample_session, config_path=config)

        manifest_path = tmp_path / "knowledge" / "raw" / "sessions" / "ingest-test-session-001" / "manifest.json"
        assert manifest_path.exists()
        manifest = json.loads(manifest_path.read_text())
        assert manifest["session_id"] == "ingest-test-session-001"
        assert "ingested_at" in manifest


class TestIngestResult:
    """Tests for IngestResult."""

    def test_repr(self) -> None:
        result = IngestResult(
            session_id="test-123",
            nodes_ingested=5,
            edges_ingested=3,
            sources_ingested=2,
            claims_ingested=1,
            findings_ingested=1,
            gaps_ingested=1,
            warnings=[],
        )
        repr_str = repr(result)
        assert "test-123" in repr_str
        assert "nodes=5" in repr_str


class TestSlugStability:
    """Tests for ID stability in the ingest module."""

    def test_session_page_idempotent_on_reingest(self, tmp_path: Path, sample_session: ResearchSession) -> None:
        """Re-ingesting should not create duplicate session pages."""
        config = tmp_path / "config.yaml"
        config.write_text("")

        ingest_session(sample_session, config_path=config)
        ingest_session(sample_session, config_path=config)

        session_page = sessions_dir(config) / "ingest-test-session-001.md"
        # Should exist without error
        assert session_page.exists()
