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

    def test_evidence_quality_section_included(self) -> None:
        """Test that evidence quality section is included in reports."""
        config = {"model": "claude-sonnet-4-6"}
        agent = ReporterAgent(config)

        # Create sources with different study types
        sources = [
            SearchResultItem(
                url="https://pubmed.gov/clinical",
                title="Randomized Controlled Trial of Treatment",
                content="This is a double-blind, placebo-controlled clinical trial "
                        "with human subjects demonstrating significant effects.",
                score=0.95
            ),
            SearchResultItem(
                url="https://nature.com/animal",
                title="Animal Study on Treatment Effects",
                content="This study used mice to investigate the effects. "
                        "The in vivo results showed promising outcomes in rodents.",
                score=0.80
            ),
            SearchResultItem(
                url="https://blog.example.com/post",
                title="General Information",
                content="Some general information about the topic.",
                score=0.35
            ),
        ]

        session = ResearchSession(
            session_id="test-session",
            query="test treatment effects",
            depth=ResearchDepth.DEEP,
            sources=sources,
        )

        analysis = {
            "key_findings": [],
            "themes": ["Treatment Effects"],
            "themes_detailed": [
                {
                    "name": "Treatment Effects",
                    "description": "Effects of the treatment",
                    "key_points": ["Point 1"],
                    "supporting_sources": ["https://pubmed.gov/clinical"],
                }
            ],
            "consensus_points": [],
            "contention_points": [],
            "gaps": [],
            "analysis_method": "ai_semantic"
        }

        report = agent.generate_markdown_report(session, analysis)
        assert "## Evidence Quality Analysis" in report
        assert "### Study Types" in report
        assert "### Evidence Summary" in report

    def test_safety_section_included(self) -> None:
        """Test that safety section is included when safety info is found."""
        config = {"model": "claude-sonnet-4-6"}
        agent = ReporterAgent(config)

        # Create source with safety information
        sources = [
            SearchResultItem(
                url="https://health.example.com/guide",
                title="Health Guide",
                content="Common side effects include headache and nausea. "
                        "Contraindicated for pregnant women. "
                        "Consult your doctor before use. "
                        "May interact with blood thinners like warfarin.",
                score=0.80
            ),
        ]

        session = ResearchSession(
            session_id="test-session",
            query="test safety",
            depth=ResearchDepth.STANDARD,
            sources=sources,
        )

        analysis = {
            "key_findings": [],
            "themes": [],
            "themes_detailed": [],
            "consensus_points": [],
            "contention_points": [],
            "gaps": [],
            "analysis_method": "basic_keyword"
        }

        report = agent.generate_markdown_report(session, analysis)
        assert "## Safety and Contraindications" in report

    def test_json_report_includes_evidence_and_safety(self) -> None:
        """Test that JSON report includes evidence quality and safety info."""
        config = {"model": "claude-sonnet-4-6"}
        agent = ReporterAgent(config)

        sources = [
            SearchResultItem(
                url="https://pubmed.gov/study",
                title="Clinical Trial Study",
                content="This randomized controlled trial examined the effects. "
                        "Side effects: mild headache in some patients.",
                score=0.95
            ),
        ]

        session = ResearchSession(
            session_id="test-session",
            query="test query",
            depth=ResearchDepth.DEEP,
            sources=sources,
        )

        analysis = {
            "key_findings": [],
            "themes": ["Clinical Effects"],
            "themes_detailed": [
                {
                    "name": "Clinical Effects",
                    "description": "Description",
                    "key_points": ["Point 1"],
                    "supporting_sources": ["https://pubmed.gov/study"],
                }
            ],
            "consensus_points": [],
            "contention_points": [],
            "gaps": [],
            "analysis_method": "ai_semantic"
        }

        report = agent.generate_json_report(session, analysis)
        report_dict = json.loads(report)

        # Check evidence quality is included
        assert "evidence_quality" in report_dict
        assert "study_types" in report_dict["evidence_quality"]
        assert "confidence_levels" in report_dict["evidence_quality"]

        # Check safety info is included
        assert "safety_info" in report_dict
        assert "has_safety_info" in report_dict["safety_info"]


class TestAIAgentIntegrationEvidence:
    """Tests for evidence quality analysis in AIAgentIntegration."""

    def test_classify_study_type_clinical(self) -> None:
        """Test classification of clinical trial sources."""
        from cc_deep_research.agents.ai_agent_integration import AIAgentIntegration

        config = {"model": "claude-sonnet-4-6"}
        integration = AIAgentIntegration(config)

        source = SearchResultItem(
            url="https://pubmed.gov/trial",
            title="Randomized Controlled Trial",
            content="This double-blind, placebo-controlled clinical trial "
                    "with human subjects demonstrated significant effects.",
            score=0.95
        )

        study_type = integration._classify_study_type(source)
        assert study_type == "human_clinical"

    def test_classify_study_type_animal(self) -> None:
        """Test classification of animal study sources."""
        from cc_deep_research.agents.ai_agent_integration import AIAgentIntegration

        config = {"model": "claude-sonnet-4-6"}
        integration = AIAgentIntegration(config)

        source = SearchResultItem(
            url="https://nature.com/study",
            title="Animal Model Study",
            content="This study used mice to investigate the effects. "
                    "In vivo results showed promising outcomes in rodents.",
            score=0.80
        )

        study_type = integration._classify_study_type(source)
        assert study_type == "animal"

    def test_classify_study_type_meta_analysis(self) -> None:
        """Test classification of meta-analysis sources."""
        from cc_deep_research.agents.ai_agent_integration import AIAgentIntegration

        config = {"model": "claude-sonnet-4-6"}
        integration = AIAgentIntegration(config)

        source = SearchResultItem(
            url="https://cochrane.org/review",
            title="Systematic Review and Meta-Analysis",
            content="This Cochrane systematic review pooled data from 20 studies.",
            score=0.99
        )

        study_type = integration._classify_study_type(source)
        assert study_type == "review_meta"

    def test_analyze_evidence_quality(self) -> None:
        """Test full evidence quality analysis."""
        from cc_deep_research.agents.ai_agent_integration import AIAgentIntegration

        config = {"model": "claude-sonnet-4-6"}
        integration = AIAgentIntegration(config)

        sources = [
            SearchResultItem(
                url="https://pubmed.gov/clinical",
                title="RCT Study",
                content="Randomized controlled trial with human participants.",
                score=0.95
            ),
            SearchResultItem(
                url="https://nature.com/animal",
                title="Mouse Study",
                content="This animal study used mice for investigation.",
                score=0.80
            ),
        ]

        themes = [
            {
                "name": "Treatment Effects",
                "supporting_sources": ["https://pubmed.gov/clinical"],
            }
        ]

        result = integration.analyze_evidence_quality(sources, themes)

        assert "study_types" in result
        assert "evidence_conflicts" in result
        assert "confidence_levels" in result
        assert "evidence_summary" in result

        # Check that study types were classified
        assert len(result["study_types"]["human_clinical"]) == 1
        assert len(result["study_types"]["animal"]) == 1

    def test_extract_safety_information(self) -> None:
        """Test safety information extraction."""
        from cc_deep_research.agents.ai_agent_integration import AIAgentIntegration

        config = {"model": "claude-sonnet-4-6"}
        integration = AIAgentIntegration(config)

        sources = [
            SearchResultItem(
                url="https://health.example.com/guide",
                title="Health Guide",
                content="Common side effects include headache and nausea. "
                        "Contraindicated for pregnant women. "
                        "May interact with blood thinners. "
                        "Caution: consult your doctor before use. "
                        "Warning: may cause allergic reactions.",
                score=0.80
            ),
        ]

        result = integration.extract_safety_information(sources)

        assert result["has_safety_info"] is True
        assert len(result["side_effects"]) > 0
        assert len(result["contraindications"]) > 0
        assert len(result["drug_interactions"]) > 0
