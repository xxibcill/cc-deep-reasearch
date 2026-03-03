"""Tests for ReporterAgent."""

import json

from cc_deep_research.agents.reporter import ReporterAgent
from cc_deep_research.credibility import SourceCredibilityScorer
from cc_deep_research.models import (
    ResearchDepth,
    ResearchSession,
    SearchResultItem,
)


class TestReporterAgent:
    """Tests for ReporterAgent class."""

    def test_initialization(self) -> None:
        """Test agent initializes correctly."""
        config = {"model": "claude-sonnet-4-6"}
        agent = ReporterAgent(config)
        assert agent._config == config
        assert agent._credibility_scorer is not None
        assert isinstance(agent._credibility_scorer, SourceCredibilityScorer)

        assert isinstance(agent._config["model"], str)
        assert agent._config["model"] == "claude-sonnet-4-6"

    def test_generate_markdown_report_basic(self) -> None:
        """Test basic markdown report generation."""
        config = {"model": "claude-sonnet-4-6"}
        agent = ReporterAgent(config)

        # Create mock sources using SearchResultItem
        sources = [
            SearchResultItem(
                url="https://pubmed.gov/article1",
                title="Peer-Reviewed Study",
                snippet="Scientific study",
                score=0.95
            ),
            SearchResultItem(
                url="https://blog.example.com/post",
                title="Blog Post",
                snippet="Personal experience",
                score=0.35
            ),
        ]

        # Create a simple session
        session = ResearchSession(
            session_id="test-session",
            query="test query",
            depth=ResearchDepth.QUICK,
            sources=sources,
        )

        analysis = {
            "key_findings": [
                {"title": "Finding 1", "description": "Description 1", "evidence": [], "confidence": "high"}
            ],
            "themes": ["Theme 1", "Theme 2"],
            "themes_detailed": [
                {
                    "name": "Theme 1",
                    "description": "Description for theme 1",
                    "key_points": ["Point 1", "Point 2"],
                    "supporting_sources": [],
                }
            ],
            "consensus_points": ["Consensus 1"],
            "contention_points": [],
            "gaps": [],
            "analysis_method": "basic_keyword"
        }
        report = agent.generate_markdown_report(session, analysis)
        assert "## Sources" in report
        # Check that sources are grouped by type
        assert "### Peer-Reviewed" in report
        assert "[High Credibility]" in report
        assert "[Standard Source]" in report
        assert "[Standard Source]" in report

    def test_methodology_section(self) -> None:
        """Test that methodology section is included in reports."""
        config = {"model": "claude-sonnet-4-6"}
        agent = ReporterAgent(config)

        session = ResearchSession(
            session_id="test-session",
            query="test query",
            depth=ResearchDepth.STANDARD,
        )
        analysis = {
            "key_findings": [],
            "themes": [],
            "themes_detailed": [],
            "consensus_points": [],
            "contention_points": [],
            "gaps": [],
            "analysis_method": "ai_semantic"
        }
        report = agent.generate_markdown_report(session, analysis)
        assert "## Methodology" in report
        assert "### Research Approach" in report
        assert "### Search Strategy" in report
        assert "### Analysis Method" in report
        assert "### Credibility Assessment" in report
        assert "### Limitations" in report

    def test_generate_json_report(self) -> None:
        """Test JSON report generation."""
        config = {"model": "claude-sonnet-4-6"}
        agent = ReporterAgent(config)

        session = ResearchSession(
            session_id="test-session",
            query="test query",
            depth=ResearchDepth.QUICK,
        )
        analysis = {
            "key_findings": [],
            "themes": [],
            "themes_detailed": [],
            "consensus_points": [],
            "contention_points": [],
            "gaps": [],
            "safety_info": {
                "warnings": ["May cause drowsiness"],
                "side_effects": ["Headache", "Nausea", "Dizziness"],
                "contraindications": ["Pregnancy", "Breastfeeding", "Heart conditions"],
                "general_precautions": ["Consult healthcare provider before use"]
            },
        }
        report = agent.generate_json_report(session, analysis)
        report_dict = json.loads(report)
        assert report_dict["query"] == "test query"
        assert report_dict["session_id"] == "test-session"
        assert report_dict["depth"] == "quick"
