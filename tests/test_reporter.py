"""Tests for ReporterAgent."""

import json

from cc_deep_research.agents.reporter import ReporterAgent
from cc_deep_research.credibility import SourceCredibilityScorer
from cc_deep_research.models import (
    ClaimEvidence,
    CrossReferenceClaim,
    ResearchDepth,
    ResearchSession,
    SearchResultItem,
    ValidationResult,
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
        assert "### Evidence Strength" in report
        assert "### Freshness Notes" in report
        assert "### Primary-Source Coverage" in report
        assert "### Contradiction Notes" in report
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

    def test_markdown_report_includes_claim_annotations_and_iteration_summary(self) -> None:
        """Test markdown report exposes evidence annotations and follow-up impact."""
        config = {"model": "claude-sonnet-4-6"}
        agent = ReporterAgent(config)

        session = ResearchSession(
            session_id="test-session",
            query="latest chip demand outlook",
            depth=ResearchDepth.DEEP,
            sources=[
                SearchResultItem(
                    url="https://sec.gov/filing",
                    title="SEC Filing",
                    snippet="Primary filing",
                    source_metadata={"published_date": "2026-02-20"},
                ),
                SearchResultItem(
                    url="https://reuters.com/story",
                    title="Reuters Story",
                    snippet="Independent confirmation",
                    source_metadata={"published_date": "2026-02-25"},
                ),
                SearchResultItem(
                    url="https://blog.example.com/opinion",
                    title="Opinion Post",
                    snippet="Counterpoint",
                    source_metadata={"published_date": "2025-01-05"},
                ),
            ],
            metadata={
                "validation": ValidationResult(
                    is_valid=False,
                    issues=["Evidence contains substantial contradiction pressure across core claims"],
                    warnings=["Evidence freshness does not match the query's time sensitivity"],
                    recommendations=["Refresh the evidence base with recent reporting or current source documents"],
                    failure_modes=["high_contradiction_pressure", "stale_evidence_for_time_sensitive_query"],
                    evidence_diagnosis="needs_better_sources",
                    quality_score=0.58,
                ).model_dump(mode="python"),
                "iteration_history": [
                    {
                        "iteration": 1,
                        "source_count": 3,
                        "quality_score": 0.42,
                        "gap_count": 3,
                    },
                    {
                        "iteration": 2,
                        "source_count": 6,
                        "quality_score": 0.58,
                        "gap_count": 1,
                    },
                ],
            },
        )
        analysis = {
            "key_findings": [
                {
                    "title": "Demand remains elevated",
                    "description": "Demand signals remain positive across supplier and market commentary.",
                    "claims": [
                        CrossReferenceClaim(
                            claim="Demand remains elevated",
                            supporting_sources=[
                                ClaimEvidence(
                                    url="https://sec.gov/filing",
                                    title="SEC Filing",
                                    published_date="2026-02-20",
                                ),
                                ClaimEvidence(
                                    url="https://reuters.com/story",
                                    title="Reuters Story",
                                    published_date="2026-02-25",
                                ),
                            ],
                            contradicting_sources=[
                                ClaimEvidence(
                                    url="https://blog.example.com/opinion",
                                    title="Opinion Post",
                                    published_date="2025-01-05",
                                )
                            ],
                            consensus_level=0.67,
                        )
                    ],
                }
            ],
            "themes": ["Demand"],
            "themes_detailed": [],
            "consensus_points": [],
            "contention_points": ["Some analysts expect a correction"],
            "gaps": ["Need direct supplier shipment data"],
            "analysis_method": "ai_semantic",
        }

        report = agent.generate_markdown_report(session, analysis)

        assert "**Evidence Strength:**" in report
        assert "**Freshness:**" in report
        assert "**Primary-Source Coverage:**" in report
        assert "**Contradiction Note:**" in report
        assert "### Iteration Summary" in report
        assert "Follow-up search materially changed the final report." in report

    def test_json_report_exposes_evidence_annotations(self) -> None:
        """Test JSON report exposes claim evidence fields for downstream tooling."""
        config = {"model": "claude-sonnet-4-6"}
        agent = ReporterAgent(config)

        session = ResearchSession(
            session_id="test-session",
            query="merger approval status",
            depth=ResearchDepth.DEEP,
            sources=[
                SearchResultItem(
                    url="https://sec.gov/filing",
                    title="SEC Filing",
                    source_metadata={"published_date": "2026-03-01"},
                ),
                SearchResultItem(
                    url="https://reuters.com/update",
                    title="Reuters Update",
                    source_metadata={"published_date": "2026-03-02"},
                ),
            ],
            metadata={
                "validation": ValidationResult(
                    is_valid=True,
                    evidence_diagnosis="sufficient",
                    quality_score=0.86,
                    recommendations=["Maintain citation links for each claim"],
                ).model_dump(mode="python"),
            },
        )
        analysis = {
            "key_findings": [],
            "themes": ["Regulatory status"],
            "themes_detailed": [],
            "consensus_points": ["Approval is still pending"],
            "contention_points": [],
            "cross_reference_claims": [
                CrossReferenceClaim(
                    claim="Approval is still pending",
                    supporting_sources=[
                        ClaimEvidence(
                            url="https://sec.gov/filing",
                            title="SEC Filing",
                            published_date="2026-03-01",
                        ),
                        ClaimEvidence(
                            url="https://reuters.com/update",
                            title="Reuters Update",
                            published_date="2026-03-02",
                        ),
                    ],
                    consensus_level=0.75,
                )
            ],
            "gaps": [],
            "analysis_method": "ai_semantic",
        }

        report = json.loads(agent.generate_json_report(session, analysis))

        assert "claims" in report
        assert report["claims"][0]["claim"] == "Approval is still pending"
        assert "evidence_strength" in report["claims"][0]
        assert "freshness_note" in report["claims"][0]
        assert "primary_source_note" in report["claims"][0]
        assert "validation_rationale" in report["claims"][0]
        assert "evidence_strength" in report
        assert "unresolved_gaps" in report
        assert "validation_rationale" in report
        assert report["validation_rationale"]["status"] == "sufficient"


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


class TestReadabilityRegression:
    """Tests for readability improvements to prevent regressions."""

    def test_executive_summary_compact_with_many_gaps(self) -> None:
        """Test that executive summary doesn't inline full gap inventory."""
        config = {"model": "claude-sonnet-4-6"}
        agent = ReporterAgent(config)

        session = ResearchSession(
            session_id="test",
            query="test query",
            depth=ResearchDepth.DEEP,
            sources=[],
        )

        analysis = {
            "key_findings": [],
            "themes": [],
            "themes_detailed": [],
            "consensus_points": [],
            "contention_points": [],
            "gaps": [
                {"gap_description": "Gap 1", "importance": "high", "suggested_queries": []},
                {"gap_description": "Gap 2", "importance": "medium", "suggested_queries": []},
                {"gap_description": "Gap 3", "importance": "low", "suggested_queries": []},
            ],
            "analysis_method": "ai_semantic"
        }

        report = agent.generate_markdown_report(session, analysis)

        # Find the end of the executive summary section
        # Executive summary ends at the end of the paragraph that follows it
        # or at the next level-2 heading
        import re
        # Match from "## Executive Summary" to before "## Methodology"
        exec_summary_match = re.search(
            r'## Executive Summary\n(.*?)\n## Methodology',
            report,
            re.DOTALL
        )
        assert exec_summary_match is not None

        exec_summary = exec_summary_match.group(1)

        # Should NOT list gap descriptions inline
        assert "Gap 1" not in exec_summary
        assert "Gap 2" not in exec_summary
        assert "Gap 3" not in exec_summary

        # Should have pointer to gaps section
        assert "Research Gaps and Limitations" in exec_summary

        # Full gaps section should still exist with details
        assert "## Research Gaps and Limitations" in report
        assert "Gap 1" in report
        assert "Gap 2" in report
        assert "Gap 3" in report

    def test_sources_section_has_summary_and_catalog(self) -> None:
        """Test that sources section is split into summary and catalog."""
        config = {"model": "claude-sonnet-4-6"}
        agent = ReporterAgent(config)

        sources = [
            SearchResultItem(url="https://pubmed.gov/1", title="Study 1", score=0.95),
            SearchResultItem(url="https://gov.example.com/2", title="Doc 2", score=0.90),
            SearchResultItem(url="https://blog.com/3", title="Blog 3", score=0.40),
        ]

        session = ResearchSession(
            session_id="test",
            query="test query",
            depth=ResearchDepth.DEEP,
            sources=sources,
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

        # Extract sources section (stop at next ## heading, not ###)
        import re
        sources_match = re.search(
            r'## Sources\n(.*?)(?=\n##[A-Z]|\Z)',
            report,
            re.DOTALL
        )
        assert sources_match is not None

        sources_section = sources_match.group(1)

        # Should have summary subsection
        assert "### Sources Summary" in sources_section
        assert "Total Sources:" in sources_section
        assert "Top Source Types:" in sources_section

        # Should have full catalog subsection
        assert "### Full Catalog" in sources_section

        # All sources should still be in catalog
        assert "Study 1" in sources_section
        assert "Doc 2" in sources_section
        assert "Blog 3" in sources_section

    def test_report_generation_without_gaps(self) -> None:
        """Test that reports without gaps still generate correctly."""
        config = {"model": "claude-sonnet-4-6"}
        agent = ReporterAgent(config)

        session = ResearchSession(
            session_id="test",
            query="test query",
            depth=ResearchDepth.STANDARD,
            sources=[],
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

        # Executive summary should exist and not have gaps pointer
        assert "## Executive Summary" in report
        assert "## Research Gaps and Limitations" not in report

        # Sources section should still have summary
        assert "### Sources Summary" in report
        assert "### Full Catalog" in report
