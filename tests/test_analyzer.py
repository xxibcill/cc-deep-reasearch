"""Tests for AnalyzerAgent with fixture data.

Task 006: Run realistic fixture data through analyzer code paths to catch
late-stage schema or formatting failures before full orchestration.
"""

import pytest

from cc_deep_research.agents.analyzer import AnalyzerAgent
from cc_deep_research.models import (
    AnalysisResult,
    ResearchSession,
    SearchResultItem,
)


class TestAnalyzerAgentFixtureSmokeTests:
    """Smoke tests for AnalyzerAgent with realistic fixture data."""

    def test_analyzer_with_realistic_sources(self) -> None:
        """Analyzer should process realistic source data without errors."""
        config = {"ai_num_themes": 5}
        agent = AnalyzerAgent(config)

        sources = [
            SearchResultItem(
                url="https://www.nature.com/articles/d41586-023-01444-9",
                title="What is quantum computing?",
                snippet="potentially solving certain problems exponentially faster than classical computers",
                content="""Quantum computing is a type of computation whose operations can exploit
                phenomena of quantum mechanics such as superposition, interference, and entanglement.
                Unlike classical computers that use bits, quantum computers use quantum bits or qubits.
                A qubit can exist in a superposition of both 0 and 1 states simultaneously.
                This allows quantum computers to process multiple possibilities at once.""",
                score=0.95,
            ),
            SearchResultItem(
                url="https://quantumcomputingreport.com/what-is-quantum-computing/",
                title="What is Quantum Computing?",
                snippet="solving certain problems exponentially faster than classical counterparts",
                content="""Quantum computing utilizes quantum mechanical phenomena to perform computation.
                Quantum computers use qubits which can exist in multiple states at once due to
                superposition. This allows them to solve certain problems exponentially faster
                than classical computers. Quantum entanglement is another key property that
                enables quantum computers to perform certain calculations much faster.""",
                score=0.90,
            ),
            SearchResultItem(
                url="https://en.wikipedia.org/wiki/Quantum_computing",
                title="Quantum computing",
                snippet="solve certain problems exponentially faster than classical computers",
                content="""Quantum computing is a multidisciplinary field comprising quantum physics,
                computer science, information theory, and mathematics. Quantum computers provide
                a new way to process information that is fundamentally different from classical
                computers. The power of quantum computers comes from the ability to exist in
                multiple quantum states simultaneously through superposition.""",
                score=0.85,
            ),
            SearchResultItem(
                url="https://www.ibm.com/quantum-computing/learn/what-is-quantum-computing",
                title="What is quantum computing?",
                snippet="error correction for practical applications",
                content="""Current quantum computers are noisy and error-prone. The technology is still
                in its infancy with qubits highly susceptible to environmental noise and decoherence.
                Error rates in current systems range from 0.1% to 1% per gate operation, far above
                the threshold needed for fault-tolerant quantum computing. Error correction requires
                hundreds of physical qubits per logical qubit.""",
                score=0.92,
            ),
            SearchResultItem(
                url="https://news.mit.edu/2023/quantum-computing-explained-0323",
                title="Quantum computing explained",
                snippet="quantum computing explained",
                content="""Quantum computing represents a paradigm shift in computation. The fundamental
                unit of quantum computation is the qubit, which can represent both 0 and 1 at the
                same time through superposition. This property, along with quantum entanglement,
                allows quantum computers to explore multiple solutions simultaneously.""",
                score=0.88,
            ),
        ]

        result = agent.analyze_sources(sources, "What is quantum computing and how does it work?")

        assert result is not None
        assert isinstance(result, AnalysisResult)
        assert result.source_count == 5
        assert result.analysis_method in ("ai_semantic", "basic_keyword")

        assert len(result.key_findings) > 0
        assert len(result.themes) > 0

    def test_analyzer_produces_valid_analysis_result(self) -> None:
        """Analyzer should produce AnalysisResult that passes model validation."""
        config = {"ai_num_themes": 3}
        agent = AnalyzerAgent(config)

        sources = [
            SearchResultItem(
                url="https://example.com/article1",
                title="Article 1",
                snippet="Content about topic A",
                content="Detailed content about topic A with substantial information" * 20,
                score=0.85,
            ),
            SearchResultItem(
                url="https://example.com/article2",
                title="Article 2",
                snippet="Content about topic B",
                content="Detailed content about topic B with substantial information" * 20,
                score=0.80,
            ),
        ]

        result = agent.analyze_sources(sources, "test query")

        validated = AnalysisResult.model_validate(result.model_dump())
        assert validated is not None

    def test_analyzer_empty_sources(self) -> None:
        """Analyzer should handle empty sources list."""
        config = {}
        agent = AnalyzerAgent(config)

        result = agent.analyze_sources([], "test query")

        assert result is not None
        assert isinstance(result, AnalysisResult)
        assert result.source_count == 0

    def test_analyzer_insufficient_content_falls_back(self) -> None:
        """Analyzer should fall back to basic analysis when content is insufficient."""
        config = {"ai_num_themes": 3}
        agent = AnalyzerAgent(config)

        sources = [
            SearchResultItem(
                url="https://example.com/short",
                title="Short Title",
                snippet="Very short snippet",
                score=0.5,
            ),
        ]

        result = agent.analyze_sources(sources, "test query")

        assert result is not None
        assert result.analysis_method == "basic_keyword"

    def test_analyzer_with_degraded_fixture_path(self) -> None:
        """Analyzer should handle degraded path with minimal data gracefully."""
        config = {"ai_num_themes": 2}
        agent = AnalyzerAgent(config)

        sources = [
            SearchResultItem(
                url="https://example.com/1",
                title="Source One",
                snippet="Minimal",
                score=0.3,
            ),
            SearchResultItem(
                url="https://example.com/2",
                title="Source Two",
                snippet="Also minimal",
                score=0.2,
            ),
        ]

        result = agent.analyze_sources(sources, "minimal data query")

        assert result is not None
        assert isinstance(result, AnalysisResult)
        assert result.source_count == 2
        assert len(result.gaps) > 0

    def test_analyzer_output_survives_reporting_path(self) -> None:
        """Analyzer output should be compatible with reporter."""
        from cc_deep_research.agents.reporter import ReporterAgent

        config = {"ai_num_themes": 3}
        agent = AnalyzerAgent(config)

        sources = [
            SearchResultItem(
                url="https://example.com/1",
                title="Test Source",
                snippet="Content here",
                content="More detailed content for analysis" * 30,
                score=0.9,
            ),
        ]

        analysis_result = agent.analyze_sources(sources, "test query")

        reporter = ReporterAgent({"model": "claude-sonnet-4-6"})

        session = ResearchSession(
            session_id="analyzer-to-reporter-test",
            query="test query",
            sources=sources,
        )

        report = reporter.generate_markdown_report(session, analysis_result.model_dump())

        assert report is not None
        assert len(report) > 0
        assert "## Executive Summary" in report


class TestDeepAnalyzerAgentFixtureSmokeTests:
    """Smoke tests for DeepAnalyzerAgent with realistic fixture data."""

    def test_deep_analyzer_with_realistic_sources(self) -> None:
        """DeepAnalyzer should process realistic source data without errors."""
        from cc_deep_research.agents.deep_analyzer import DeepAnalyzerAgent

        config = {"deep_analysis_passes": 3, "ai_deep_num_themes": 8}
        agent = DeepAnalyzerAgent(config)

        sources = [
            SearchResultItem(
                url="https://www.nature.com/articles/d41586-023-01444-9",
                title="What is quantum computing?",
                snippet="potentially solving certain problems exponentially faster",
                content="""Quantum computing is a type of computation whose operations can exploit
                phenomena of quantum mechanics such as superposition, interference, and entanglement.
                Quantum computers use qubits that can exist in superposition states.""",
                score=0.95,
            ),
            SearchResultItem(
                url="https://quantumcomputingreport.com/what-is-quantum-computing/",
                title="What is Quantum Computing?",
                snippet="solving certain problems exponentially faster",
                content="""Quantum computing utilizes quantum mechanical phenomena to perform computation.
                Quantum computers can solve certain problems exponentially faster.""",
                score=0.90,
            ),
            SearchResultItem(
                url="https://en.wikipedia.org/wiki/Quantum_computing",
                title="Quantum computing",
                snippet="solve certain problems exponentially faster",
                content="""Quantum computing is a multidisciplinary field. The power comes from
                the ability to exist in multiple quantum states simultaneously.""",
                score=0.85,
            ),
        ]

        result = agent.deep_analyze(sources, "What is quantum computing?")

        assert result is not None
        assert isinstance(result, dict)
        assert "deep_analysis_complete" in result
        assert "themes" in result
        assert "source_count" in result

    def test_deep_analyzer_output_merge_compatibility(self) -> None:
        """Deep analyzer output should be compatible with merging into AnalysisResult."""
        from cc_deep_research.agents.deep_analyzer import DeepAnalyzerAgent

        config = {"deep_analysis_passes": 3}
        agent = DeepAnalyzerAgent(config)

        sources = [
            SearchResultItem(
                url="https://example.com/1",
                title="Source 1",
                snippet="Content",
                content="Detailed content for deep analysis" * 30,
                score=0.9,
            ),
            SearchResultItem(
                url="https://example.com/2",
                title="Source 2",
                snippet="Content",
                content="More detailed content" * 30,
                score=0.85,
            ),
        ]

        deep_result = agent.deep_analyze(sources, "test query")

        analysis_dict = {
            "key_findings": [],
            "themes": deep_result.get("themes", []),
            "themes_detailed": deep_result.get("themes_detailed", []),
            "consensus_points": deep_result.get("consensus_points", []),
            "contention_points": deep_result.get("disagreement_points", []),
            "cross_reference_claims": deep_result.get("cross_reference_claims", []),
            "gaps": [],
            "source_count": deep_result.get("source_count", 0),
            "analysis_method": deep_result.get("analysis_method", "deep_analysis"),
        }

        analysis_result = AnalysisResult.model_validate(analysis_dict)

        assert analysis_result is not None
        assert len(analysis_result.themes) > 0

    def test_deep_analyzer_empty_sources(self) -> None:
        """DeepAnalyzer should handle empty sources list."""
        from cc_deep_research.agents.deep_analyzer import DeepAnalyzerAgent

        config = {}
        agent = DeepAnalyzerAgent(config)

        result = agent.deep_analyze([], "test query")

        assert result is not None
        assert result["deep_analysis_complete"] is False
        assert result["source_count"] == 0

    def test_deep_analyzer_insufficient_content_falls_back(self) -> None:
        """DeepAnalyzer should fall back to shallow analysis when content is insufficient."""
        from cc_deep_research.agents.deep_analyzer import DeepAnalyzerAgent

        config = {"deep_analysis_passes": 3}
        agent = DeepAnalyzerAgent(config)

        sources = [
            SearchResultItem(
                url="https://example.com/short",
                title="Short",
                snippet="Short",
                score=0.5,
            ),
        ]

        result = agent.deep_analyze(sources, "test query")

        assert result is not None
        assert result["analysis_method"] in ("shallow_keyword", "ai_multi_pass")

    def test_deep_analyzer_degraded_path_falls_back_cleanly(self) -> None:
        """DeepAnalyzer should fall back cleanly in degraded path."""
        from cc_deep_research.agents.deep_analyzer import DeepAnalyzerAgent

        config = {"deep_analysis_passes": 3}
        agent = DeepAnalyzerAgent(config)

        sources = [
            SearchResultItem(
                url="https://example.com/1",
                title="Minimal Source",
                snippet="Very minimal",
                score=0.3,
            ),
            SearchResultItem(
                url="https://example.com/2",
                title="Another Minimal",
                snippet="Very minimal",
                score=0.2,
            ),
        ]

        result = agent.deep_analyze(sources, "minimal data query")

        assert result is not None
        assert "deep_analysis_complete" in result
        assert "themes" in result
        assert result["analysis_method"] == "shallow_keyword"

    def test_deep_analyzer_output_survives_validation_path(self) -> None:
        """Deep analyzer output should survive validation."""
        from cc_deep_research.agents.deep_analyzer import DeepAnalyzerAgent
        from cc_deep_research.agents.validator import ValidatorAgent

        config = {"deep_analysis_passes": 3}
        deep_agent = DeepAnalyzerAgent(config)

        sources = [
            SearchResultItem(
                url="https://example.com/1",
                title="Test Source",
                snippet="Content",
                content="Detailed content for deep analysis" * 40,
                score=0.9,
            ),
            SearchResultItem(
                url="https://example.com/2",
                title="Test Source 2",
                snippet="Content",
                content="More detailed content" * 40,
                score=0.85,
            ),
        ]

        deep_result = deep_agent.deep_analyze(sources, "test query")

        analysis_dict = {
            "key_findings": [],
            "themes": deep_result.get("themes", []),
            "themes_detailed": deep_result.get("themes_detailed", []),
            "consensus_points": deep_result.get("consensus_points", []),
            "contention_points": deep_result.get("disagreement_points", []),
            "cross_reference_claims": deep_result.get("cross_reference_claims", []),
            "gaps": [],
            "source_count": deep_result.get("source_count", 0),
            "analysis_method": deep_result.get("analysis_method", "deep"),
        }

        analysis_result = AnalysisResult.model_validate(analysis_dict)

        session = ResearchSession(
            session_id="deep-to-validator-test",
            query="test query",
            sources=sources,
        )

        validator = ValidatorAgent({"min_sources": 2})
        validation = validator.validate_research(session, analysis_result, query="test query")

        assert validation is not None
        assert hasattr(validation, "is_valid")