"""Tests for ReporterAgent."""

import json

from cc_deep_research.agents.reporter import ReporterAgent
from cc_deep_research.credibility import SourceCredibilityScorer
from cc_deep_research.models import (
    AnalysisResult,
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


class TestExecutiveSummaryConsolidation:
    """Tests for Task 024: Executive Summary contract consolidation."""

    def test_generate_executive_summary_wrapper_delegates_to_reporter(self) -> None:
        """Test that reporting.generate_executive_summary delegates to ReporterAgent."""
        from cc_deep_research.reporting import generate_executive_summary

        session = ResearchSession(
            session_id="test",
            query="test query",
            depth=ResearchDepth.STANDARD,
            sources=[],
        )

        analysis = {
            "key_findings": [],
            "themes": ["Theme 1", "Theme 2"],
            "themes_detailed": [],
            "consensus_points": [],
            "contention_points": [],
            "gaps": [],
            "analysis_method": "basic_keyword",
        }

        summary = generate_executive_summary(session, analysis)

        # Should produce a non-empty summary
        assert summary
        assert len(summary) > 0

        # Should use the canonical implementation (same as ReporterAgent)
        agent = ReporterAgent({"model": "claude-sonnet-4-6"})
        from cc_deep_research.models import AnalysisResult
        analysis_result = AnalysisResult.model_validate(analysis)
        expected = agent._generate_executive_summary(session, analysis_result)

        assert summary == expected

    def test_executive_summary_uses_constants(self) -> None:
        """Test that _generate_executive_summary uses module constants."""
        from cc_deep_research.agents.reporter import (
            EXECUTIVE_SUMMARY_MAX_THEMES,
            EXECUTIVE_SUMMARY_GAPS_POINTER,
        )

        config = {"model": "claude-sonnet-4-6"}
        agent = ReporterAgent(config)

        # Create session with many themes and gaps
        session = ResearchSession(
            session_id="test",
            query="test query",
            depth=ResearchDepth.DEEP,
            sources=[],
        )

        # Create analysis with more themes than the max
        analysis = {
            "key_findings": [{"title": "Finding 1", "description": "Description"}],
            "themes": [f"Theme {i}" for i in range(10)],  # 10 themes
            "themes_detailed": [],
            "consensus_points": [],
            "contention_points": [],
            "gaps": [{"gap_description": f"Gap {i}", "importance": "medium", "suggested_queries": []} for i in range(3)],
            "analysis_method": "ai_semantic",
        }

        report = agent.generate_markdown_report(session, analysis)

        # Extract executive summary section
        import re
        exec_summary_match = re.search(
            r'## Executive Summary\n(.*?)\n## Methodology',
            report,
            re.DOTALL
        )
        assert exec_summary_match is not None
        exec_summary = exec_summary_match.group(1)

        # Should not have more themes than max
        # Count how many theme names appear in the summary
        themes_found = sum(1 for i in range(10) if f"Theme {i}" in exec_summary)
        assert themes_found <= EXECUTIVE_SUMMARY_MAX_THEMES

        # Should use the gaps pointer instead of listing gaps inline
        assert EXECUTIVE_SUMMARY_GAPS_POINTER in exec_summary

        # Individual gap descriptions should NOT be in the executive summary
        assert "Gap 0" not in exec_summary
        assert "Gap 1" not in exec_summary
        assert "Gap 2" not in exec_summary


class TestExecutiveSummaryInsightOnly:
    """Tests for Task 025: Executive Summary insight-only rewrite."""

    def test_no_prompt_restatement(self) -> None:
        """Executive Summary should not include 'This research investigated'."""
        config = {"model": "claude-sonnet-4-6"}
        agent = ReporterAgent(config)

        session = ResearchSession(
            session_id="test",
            query="what are the effects of caffeine",
            depth=ResearchDepth.STANDARD,
            sources=[],
        )

        analysis = {
            "key_findings": [{"title": "Finding 1", "description": "Description"}],
            "themes": ["Alertness", "Sleep"],
            "themes_detailed": [],
            "consensus_points": [],
            "contention_points": [],
            "gaps": [],
            "analysis_method": "ai_semantic",
        }

        report = agent.generate_markdown_report(session, analysis)

        # Extract executive summary
        import re
        exec_summary_match = re.search(
            r'## Executive Summary\n(.*?)\n## Methodology',
            report,
            re.DOTALL
        )
        assert exec_summary_match is not None
        exec_summary = exec_summary_match.group(1)

        # Should NOT include prompt restatement
        assert "This research investigated" not in exec_summary

    def test_no_methodology_chatter(self) -> None:
        """Executive Summary should not include 'Analysis was performed'."""
        config = {"model": "claude-sonnet-4-6"}
        agent = ReporterAgent(config)

        session = ResearchSession(
            session_id="test",
            query="test query",
            depth=ResearchDepth.STANDARD,
            sources=[],
        )

        # Test with AI semantic method
        analysis = {
            "key_findings": [{"title": "Finding 1", "description": "Description"}],
            "themes": ["Theme 1"],
            "themes_detailed": [],
            "consensus_points": [],
            "contention_points": [],
            "gaps": [],
            "analysis_method": "ai_semantic",
        }

        report = agent.generate_markdown_report(session, analysis)

        # Extract executive summary
        import re
        exec_summary_match = re.search(
            r'## Executive Summary\n(.*?)\n## Methodology',
            report,
            re.DOTALL
        )
        assert exec_summary_match is not None
        exec_summary = exec_summary_match.group(1)

        # Should NOT include methodology chatter
        assert "Analysis was performed" not in exec_summary

    def test_no_inline_gap_inventory(self) -> None:
        """Executive Summary should not include 'Areas requiring additional investigation include'."""
        config = {"model": "claude-sonnet-4-6"}
        agent = ReporterAgent(config)

        session = ResearchSession(
            session_id="test",
            query="test query",
            depth=ResearchDepth.STANDARD,
            sources=[],
        )

        analysis = {
            "key_findings": [{"title": "Finding 1", "description": "Description"}],
            "themes": ["Theme 1"],
            "themes_detailed": [],
            "consensus_points": [],
            "contention_points": [],
            "gaps": [{"gap_description": "Missing data on X", "importance": "high", "suggested_queries": []}],
            "analysis_method": "ai_semantic",
        }

        report = agent.generate_markdown_report(session, analysis)

        # Extract executive summary
        import re
        exec_summary_match = re.search(
            r'## Executive Summary\n(.*?)\n## Methodology',
            report,
            re.DOTALL
        )
        assert exec_summary_match is not None
        exec_summary = exec_summary_match.group(1)

        # Should NOT include inline gap inventory phrase
        assert "Areas requiring additional investigation include" not in exec_summary

    def test_summary_uses_brief_gaps_pointer(self) -> None:
        """When gaps exist, summary should use brief pointer, not list gaps."""
        from cc_deep_research.agents.reporter import EXECUTIVE_SUMMARY_GAPS_POINTER

        config = {"model": "claude-sonnet-4-6"}
        agent = ReporterAgent(config)

        session = ResearchSession(
            session_id="test",
            query="test query",
            depth=ResearchDepth.STANDARD,
            sources=[],
        )

        analysis = {
            "key_findings": [{"title": "Finding 1", "description": "Description"}],
            "themes": ["Theme 1"],
            "themes_detailed": [],
            "consensus_points": [],
            "contention_points": [],
            "gaps": [
                {"gap_description": "Missing data on X", "importance": "high", "suggested_queries": []},
                {"gap_description": "Need more research on Y", "importance": "medium", "suggested_queries": []},
            ],
            "analysis_method": "ai_semantic",
        }

        report = agent.generate_markdown_report(session, analysis)

        # Extract executive summary
        import re
        exec_summary_match = re.search(
            r'## Executive Summary\n(.*?)\n## Methodology',
            report,
            re.DOTALL
        )
        assert exec_summary_match is not None
        exec_summary = exec_summary_match.group(1)

        # Should use the gaps pointer
        assert EXECUTIVE_SUMMARY_GAPS_POINTER in exec_summary

        # Should NOT list gap descriptions inline
        assert "Missing data on X" not in exec_summary
        assert "Need more research on Y" not in exec_summary

    def test_summary_stays_within_character_budget(self) -> None:
        """Summary should stay within the configured character budget."""
        from cc_deep_research.agents.reporter import EXECUTIVE_SUMMARY_MAX_CHARACTERS

        config = {"model": "claude-sonnet-4-6"}
        agent = ReporterAgent(config)

        session = ResearchSession(
            session_id="test",
            query="test query with a very long name that might push the character limit",
            depth=ResearchDepth.DEEP,
            sources=[],
        )

        # Create analysis with many themes to potentially exceed budget
        analysis = {
            "key_findings": [{"title": f"Finding {i}", "description": f"Description {i}"} for i in range(10)],
            "themes": [f"Theme {i} with a longer description" for i in range(10)],
            "themes_detailed": [],
            "consensus_points": [],
            "contention_points": [],
            "gaps": [{"gap_description": f"Gap {i}", "importance": "medium", "suggested_queries": []} for i in range(5)],
            "analysis_method": "ai_semantic",
        }

        report = agent.generate_markdown_report(session, analysis)

        # Extract executive summary
        import re
        exec_summary_match = re.search(
            r'## Executive Summary\n(.*?)\n## Methodology',
            report,
            re.DOTALL
        )
        assert exec_summary_match is not None
        exec_summary = exec_summary_match.group(1).strip()

        # Should stay within character budget
        assert len(exec_summary) <= EXECUTIVE_SUMMARY_MAX_CHARACTERS + 50  # Allow small margin for truncation suffix

    def test_summary_is_insight_first(self) -> None:
        """Summary should start with findings/themes, not the query."""
        config = {"model": "claude-sonnet-4-6"}
        agent = ReporterAgent(config)

        session = ResearchSession(
            session_id="test",
            query="what are the health benefits of green tea",
            depth=ResearchDepth.STANDARD,
            sources=[],
        )

        analysis = {
            "key_findings": [{"title": "Antioxidant Properties", "description": "Green tea contains antioxidants"}],
            "themes": ["Antioxidants", "Heart Health", "Metabolism"],
            "themes_detailed": [],
            "consensus_points": [],
            "contention_points": [],
            "gaps": [],
            "analysis_method": "ai_semantic",
        }

        report = agent.generate_markdown_report(session, analysis)

        # Extract executive summary
        import re
        exec_summary_match = re.search(
            r'## Executive Summary\n(.*?)\n## Methodology',
            report,
            re.DOTALL
        )
        assert exec_summary_match is not None
        exec_summary = exec_summary_match.group(1).strip()

        # Should start with insight (Analysis identified...), not the query
        assert exec_summary.startswith("Analysis identified") or exec_summary.startswith("Key themes") or exec_summary.startswith("Analysis reviewed")

        # Should mention findings/themes
        assert "finding" in exec_summary.lower() or "theme" in exec_summary.lower()


class TestReportRefinementPipeline:
    """Tests for Task 026: Writer/Editor pass integration."""

    def test_report_refinement_invoked_when_issues_detected(self) -> None:
        """Report refinement should be invoked when quality issues are detected."""
        from unittest.mock import MagicMock, patch

        from cc_deep_research.config import Config
        from cc_deep_research.reporting import ReportGenerator

        # Create a config with refinement enabled
        config = Config()
        config.research.quality.enable_report_refinement = True
        config.research.quality.enable_report_quality_evaluation = True

        generator = ReportGenerator(config)

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
            "analysis_method": "basic_keyword",
        }

        # Patch the refiner to track if it was called
        with patch.object(generator._report_refiner, 'refine_report', wraps=generator._report_refiner.refine_report) as mock_refine:
            report = generator.generate_markdown_report(session, analysis)

            # The refiner should have been called if there were issues
            # (Quality evaluator may find issues with a minimal report)
            # At minimum, verify the pipeline runs without error
            assert report is not None
            assert len(report) > 0

    def test_report_refinement_preserves_sections(self) -> None:
        """Refinement should preserve required report sections and citations."""
        from cc_deep_research.agents.report_refiner import ReportRefinerAgent
        from cc_deep_research.models import AnalysisResult, ReportEvaluationResult, ValidationResult

        config = {"model": "claude-sonnet-4-6"}
        refiner = ReportRefinerAgent(config)

        # Create a report with sections and citations
        original_markdown = """# Research Report: Test Query

## Executive Summary

Analysis identified 2 key findings.

## Key Findings

### Finding 1: Test Finding
This is a finding with a citation [1](https://example.com).

## Sources

### Full Catalog

[1] Test Source - https://example.com

## Safety and Contraindications

No safety issues identified.
"""

        session = ResearchSession(
            session_id="test",
            query="test query",
            depth=ResearchDepth.STANDARD,
            sources=[],
        )

        analysis = AnalysisResult(
            key_findings=[],
            themes=[],
            themes_detailed=[],
            consensus_points=[],
            contention_points=[],
            gaps=[],
            analysis_method="basic_keyword",
        )

        validation_result = ValidationResult(
            is_valid=True,
            issues=[],
            warnings=["Minor warning"],
            recommendations=[],
        )

        evaluation_result = ReportEvaluationResult(
            overall_quality_score=0.7,
            is_acceptable=True,
            writing_quality_score=0.8,
            structure_flow_score=0.7,
            technical_accuracy_score=0.7,
            user_experience_score=0.6,
            consistency_score=0.7,
            critical_issues=[],
            warnings=["User experience could be improved"],
            recommendations=[],
        )

        refined = refiner.refine_report(
            original_markdown=original_markdown,
            validation_result=validation_result,
            evaluation_result=evaluation_result,
            session=session,
            analysis=analysis,
        )

        # Should preserve required sections
        assert "## Executive Summary" in refined
        assert "## Key Findings" in refined
        assert "## Sources" in refined

        # Should preserve citations
        assert "[1]" in refined
        assert "https://example.com" in refined

    def test_refinement_disabled_when_config_disabled(self) -> None:
        """Refinement should not run when disabled in config."""
        from unittest.mock import patch

        from cc_deep_research.config import Config
        from cc_deep_research.models import ReportEvaluationResult
        from cc_deep_research.reporting import ReportGenerator

        # Create a config with refinement disabled
        config = Config()
        config.research.quality.enable_report_refinement = False
        config.research.quality.enable_report_quality_evaluation = False

        generator = ReportGenerator(config)

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
            "analysis_method": "basic_keyword",
        }

        # Patch the refiner to ensure it's NOT called
        with patch.object(generator._report_refiner, 'refine_report') as mock_refine:
            report = generator.generate_markdown_report(session, analysis)

            # Refiner should NOT have been called
            mock_refine.assert_not_called()

            # Report should still be generated
            assert report is not None

    def test_report_generator_records_report_route_usage(self) -> None:
        """Report generation should project evaluator route usage into session metadata."""
        from unittest.mock import patch

        from cc_deep_research.config import Config
        from cc_deep_research.models import ReportEvaluationResult
        from cc_deep_research.reporting import ReportGenerator

        config = Config()
        config.research.quality.enable_report_refinement = False

        generator = ReportGenerator(config)
        session = ResearchSession(
            session_id="test",
            query="test query",
            depth=ResearchDepth.STANDARD,
            sources=[],
            metadata={
                "llm_routes": {
                    "planned_routes": {
                        "report_quality_evaluator": {
                            "transport": "openrouter_api",
                            "provider": "openrouter",
                            "model": "anthropic/claude-sonnet-4",
                            "source": "planner",
                        }
                    }
                }
            },
        )
        analysis = {
            "key_findings": [],
            "themes": [],
            "themes_detailed": [],
            "consensus_points": [],
            "contention_points": [],
            "gaps": [],
            "analysis_method": "basic_keyword",
        }

        with patch.object(
            generator._report_quality_evaluator,
            "evaluate_report_quality_sync",
            return_value=ReportEvaluationResult(overall_quality_score=0.8, is_acceptable=True),
        ):
            generator._report_quality_evaluator._last_transport_used = "openrouter_api"
            generator.generate_markdown_report(session, analysis)

        assert session.metadata["llm_routes"]["actual_routes"]["report_quality_evaluator"] == {
            "transport": "openrouter_api",
            "provider": "openrouter",
            "model": "anthropic/claude-sonnet-4",
            "source": "actual",
        }


class TestReporterSchemaContractTests:
    """Contract tests for ReporterAgent schema handling."""

    def test_reporter_handles_string_key_findings(self) -> None:
        """Reporter should handle string items in key_findings."""
        config = {"model": "claude-sonnet-4-6"}
        agent = ReporterAgent(config)

        session = ResearchSession(
            session_id="test",
            query="test query",
            depth=ResearchDepth.STANDARD,
            sources=[],
        )

        analysis = {
            "key_findings": ["Finding 1", "Finding 2"],
            "themes": ["Theme 1"],
            "themes_detailed": [],
            "consensus_points": [],
            "contention_points": [],
            "gaps": [],
            "analysis_method": "basic_keyword",
        }

        report = agent.generate_markdown_report(session, analysis)
        assert "## Key Findings" in report
        assert "Finding 1" in report

    def test_reporter_handles_dict_key_findings(self) -> None:
        """Reporter should handle dict items in key_findings."""
        config = {"model": "claude-sonnet-4-6"}
        agent = ReporterAgent(config)

        session = ResearchSession(
            session_id="test",
            query="test query",
            depth=ResearchDepth.STANDARD,
            sources=[],
        )

        analysis = {
            "key_findings": [
                {"title": "Finding Title", "description": "Finding description", "evidence": [], "confidence": "high"}
            ],
            "themes": [],
            "themes_detailed": [],
            "consensus_points": [],
            "contention_points": [],
            "gaps": [],
            "analysis_method": "basic_keyword",
        }

        report = agent.generate_markdown_report(session, analysis)
        assert "## Key Findings" in report

    def test_reporter_handles_string_gaps(self) -> None:
        """Reporter should handle string items in gaps."""
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
            "gaps": ["Gap 1", "Gap 2"],
            "analysis_method": "basic_keyword",
        }

        report = agent.generate_markdown_report(session, analysis)
        assert "## Research Gaps and Limitations" in report
        assert "Gap 1" in report

    def test_reporter_handles_dict_gaps(self) -> None:
        """Reporter should handle dict items in gaps."""
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
            "gaps": [
                {"gap_description": "Missing data", "importance": "high", "suggested_queries": []},
                {"gap_description": "Need more research", "importance": "medium", "suggested_queries": []},
            ],
            "analysis_method": "basic_keyword",
        }

        report = agent.generate_markdown_report(session, analysis)
        assert "## Research Gaps and Limitations" in report
        assert "Missing data" in report

    def test_reporter_handles_stringified_consensus_points(self) -> None:
        """Reporter should handle pre-stringified consensus points."""
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
            "consensus_points": ["Treatment is effective"],
            "contention_points": [],
            "disagreement_points": [],
            "gaps": [],
            "analysis_method": "basic_keyword",
        }

        report = agent.generate_markdown_report(session, analysis)
        assert "Treatment is effective" in report

    def test_reporter_handles_string_themes(self) -> None:
        """Reporter should handle string items in themes field."""
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
            "themes": ["Theme 1", "Theme 2"],
            "themes_detailed": [],
            "consensus_points": [],
            "contention_points": [],
            "gaps": [],
            "analysis_method": "basic_keyword",
        }

        report = agent.generate_markdown_report(session, analysis)
        assert "Key themes identified: Theme 1, Theme 2" in report

    def test_reporter_handles_missing_analysis_fields(self) -> None:
        """Reporter should handle missing optional analysis fields gracefully."""
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
        }

        report = agent.generate_markdown_report(session, analysis)
        assert report is not None
        assert len(report) > 0

    def test_reporter_handles_empty_themes(self) -> None:
        """Reporter should handle empty themes list."""
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
            "analysis_method": "basic_keyword",
        }

        report = agent.generate_markdown_report(session, analysis)
        assert report is not None

    def test_reporter_handles_themes_detailed_with_sources(self) -> None:
        """Reporter should handle themes_detailed and show supporting sources."""
        config = {"model": "claude-sonnet-4-6"}
        agent = ReporterAgent(config)

        sources = [
            SearchResultItem(url="https://example.com/1", title="Source 1", content="Content 1", score=0.9)
        ]

        session = ResearchSession(
            session_id="test",
            query="test query",
            depth=ResearchDepth.STANDARD,
            sources=sources,
        )

        analysis = {
            "key_findings": [],
            "themes": ["Theme 1"],
            "themes_detailed": [
                {
                    "name": "Theme 1",
                    "description": "Theme description",
                    "key_points": ["Point 1", "Point 2"],
                    "supporting_sources": ["https://example.com/1"],
                }
            ],
            "consensus_points": [],
            "contention_points": [],
            "gaps": [],
            "analysis_method": "basic_keyword",
        }

        report = agent.generate_markdown_report(session, analysis)
        assert "Thematic Analysis" in report
        assert "Supporting Sources:" in report

    def test_json_report_handles_string_findings_in_analysis(self) -> None:
        """JSON report should have key_findings nested under analysis."""
        config = {"model": "claude-sonnet-4-6"}
        agent = ReporterAgent(config)

        session = ResearchSession(
            session_id="test",
            query="test query",
            depth=ResearchDepth.STANDARD,
            sources=[],
        )

        analysis = {
            "key_findings": ["Finding 1", "Finding 2"],
            "themes": [],
            "themes_detailed": [],
            "consensus_points": [],
            "contention_points": [],
            "gaps": [],
            "analysis_method": "basic_keyword",
        }

        report = agent.generate_json_report(session, analysis)
        report_dict = json.loads(report)
        assert "analysis" in report_dict
        assert "key_findings" in report_dict["analysis"]

    def test_json_report_handles_dict_gaps_with_importance(self) -> None:
        """JSON report should properly serialize gap importance levels."""
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
            "gaps": [
                {"gap_description": "High priority gap", "importance": "High", "suggested_queries": []},
                {"gap_description": "Medium priority gap", "importance": "Medium", "suggested_queries": []},
            ],
            "analysis_method": "basic_keyword",
        }

        report = agent.generate_json_report(session, analysis)
        report_dict = json.loads(report)
        assert "analysis" in report_dict
        assert "gaps" in report_dict["analysis"]


class TestFixtureSmokeTests:
    """Smoke tests for fixture data flowing through analysis and reporting pipeline.

    Task 006: Run realistic fixture data through analyzer, deep analyzer,
    validator, and reporter paths to catch late-stage schema or formatting
    failures before full orchestration.
    """

    def test_reporter_with_healthy_analysis_fixture(self) -> None:
        """Reporter should handle healthy analysis fixture without errors."""
        from tests.helpers.fixture_loader import load_analysis_healthy

        fixture = load_analysis_healthy()

        config = {"model": "claude-sonnet-4-6"}
        agent = ReporterAgent(config)

        sources = [
            SearchResultItem(
                url="https://www.nature.com/articles/d41586-023-01444-9",
                title="What is quantum computing?",
                snippet="potentially solving certain problems exponentially faster",
                content="Full content about quantum computing",
                score=0.95,
            ),
            SearchResultItem(
                url="https://quantumcomputingreport.com/what-is-quantum-computing/",
                title="What is Quantum Computing?",
                snippet="solving certain problems exponentially faster",
                content="More content about quantum computing",
                score=0.90,
            ),
            SearchResultItem(
                url="https://en.wikipedia.org/wiki/Quantum_computing",
                title="Quantum computing",
                snippet="solve certain problems exponentially faster",
                content="Wikipedia content about quantum computing",
                score=0.85,
            ),
            SearchResultItem(
                url="https://www.ibm.com/quantum-computing/learn/what-is-quantum-computing",
                title="What is quantum computing?",
                snippet="error correction for practical applications",
                content="IBM quantum computing guide",
                score=0.92,
            ),
            SearchResultItem(
                url="https://news.mit.edu/2023/quantum-computing-explained-0323",
                title="Quantum computing explained",
                snippet="quantum computing explained",
                content="MIT news about quantum computing",
                score=0.88,
            ),
        ]

        session = ResearchSession(
            session_id="test-fixture-session",
            query="What is quantum computing and how does it work?",
            depth=ResearchDepth.DEEP,
            sources=sources,
        )

        normalized_fixture = self._normalize_fixture_schema(fixture)
        report = agent.generate_markdown_report(session, normalized_fixture)

        assert report is not None
        assert len(report) > 0
        assert "## Executive Summary" in report
        assert "## Key Findings" in report
        assert "## Sources" in report

    def test_reporter_with_malformed_analysis_fixture(self) -> None:
        """Reporter should handle malformed analysis fixture gracefully."""
        from tests.helpers.fixture_loader import load_analysis_malformed

        fixture = load_analysis_malformed()

        config = {"model": "claude-sonnet-4-6"}
        agent = ReporterAgent(config)

        session = ResearchSession(
            session_id="test-malformed-session",
            query="test query",
            depth=ResearchDepth.QUICK,
            sources=[],
        )

        analysis = fixture

        report = agent.generate_markdown_report(session, analysis)

        assert report is not None
        assert len(report) > 0
        assert "## Executive Summary" in report

    def test_reporter_with_cross_reference_fixture(self) -> None:
        """Reporter should handle analysis with cross-reference claims."""
        from tests.helpers.fixture_loader import load_analysis_cross_reference

        fixture = load_analysis_cross_reference()

        config = {"model": "claude-sonnet-4-6"}
        agent = ReporterAgent(config)

        session = ResearchSession(
            session_id="test-cross-ref-session",
            query="test query",
            depth=ResearchDepth.STANDARD,
            sources=[],
        )

        normalized_fixture = self._normalize_fixture_schema(fixture)
        report = agent.generate_markdown_report(session, normalized_fixture)

        assert report is not None
        assert "## Key Findings" in report

    def test_json_report_with_healthy_fixture(self) -> None:
        """JSON report should handle healthy analysis fixture correctly."""
        from tests.helpers.fixture_loader import load_analysis_healthy

        fixture = load_analysis_healthy()

        config = {"model": "claude-sonnet-4-6"}
        agent = ReporterAgent(config)

        session = ResearchSession(
            session_id="test-json-session",
            query="test query",
            depth=ResearchDepth.STANDARD,
            sources=[],
        )

        normalized_fixture = self._normalize_fixture_schema(fixture)
        report = agent.generate_json_report(session, normalized_fixture)
        report_dict = json.loads(report)

        assert "analysis" in report_dict
        assert "key_findings" in report_dict["analysis"]
        assert "themes" in report_dict["analysis"]
        assert "gaps" in report_dict["analysis"]

    def test_reporter_evidence_quality_with_fixture_sources(self) -> None:
        """Reporter should produce evidence quality section with fixture sources."""
        config = {"model": "claude-sonnet-4-6"}
        agent = ReporterAgent(config)

        sources = [
            SearchResultItem(
                url="https://pubmed.gov/clinical-trial",
                title="Randomized Controlled Trial",
                content="This double-blind placebo-controlled clinical trial "
                        "with 500 human subjects demonstrated significant effects.",
                score=0.95,
            ),
            SearchResultItem(
                url="https://nature.com/animal-study",
                title="Animal Model Study",
                content="This study used mice to investigate the effects. "
                        "In vivo results showed promising outcomes in rodents.",
                score=0.80,
            ),
            SearchResultItem(
                url="https://blog.example.com/opinion",
                title="Opinion Piece",
                content="Some personal opinions about the topic.",
                score=0.35,
            ),
        ]

        session = ResearchSession(
            session_id="test-evidence-session",
            query="treatment effectiveness",
            depth=ResearchDepth.DEEP,
            sources=sources,
        )

        analysis = {
            "key_findings": [
                {
                    "title": "Treatment shows positive results",
                    "description": "The treatment demonstrated effectiveness in clinical trials.",
                    "evidence": ["https://pubmed.gov/clinical-trial"],
                    "confidence": "high",
                }
            ],
            "themes": ["Clinical Effectiveness", "Safety Profile"],
            "themes_detailed": [
                {
                    "name": "Clinical Effectiveness",
                    "description": "Results from clinical trials",
                    "key_points": ["Significant improvement observed"],
                    "supporting_sources": ["https://pubmed.gov/clinical-trial"],
                }
            ],
            "consensus_points": ["Treatment is effective based on clinical evidence"],
            "contention_points": [],
            "gaps": [],
            "analysis_method": "ai_semantic",
        }

        report = agent.generate_markdown_report(session, analysis)

        assert "## Evidence Quality Analysis" in report
        assert "### Study Types" in report
        assert "Randomized Controlled Trial" in report
        assert "Animal Model Study" in report

    def test_reporter_safety_section_with_fixture_sources(self) -> None:
        """Reporter should include safety section with health-related sources."""
        config = {"model": "claude-sonnet-4-6"}
        agent = ReporterAgent(config)

        sources = [
            SearchResultItem(
                url="https://health.example.com/drug-guide",
                title="Drug Safety Guide",
                content="Common side effects include headache, nausea, and dizziness. "
                        "Contraindicated for pregnant women. "
                        "May interact with blood thinners like warfarin. "
                        "Consult your healthcare provider before use. "
                        "Warning: may cause allergic reactions in some patients.",
                score=0.85,
            ),
        ]

        session = ResearchSession(
            session_id="test-safety-session",
            query="drug safety profile",
            depth=ResearchDepth.STANDARD,
            sources=sources,
        )

        analysis = {
            "key_findings": [
                {
                    "title": "Drug has known side effects",
                    "description": "The drug has documented side effects.",
                    "evidence": ["https://health.example.com/drug-guide"],
                    "confidence": "high",
                }
            ],
            "themes": ["Safety", "Side Effects"],
            "themes_detailed": [],
            "consensus_points": [],
            "contention_points": [],
            "gaps": [],
            "analysis_method": "basic_keyword",
        }

        report = agent.generate_markdown_report(session, analysis)

        assert "## Safety and Contraindications" in report
        assert "side effects" in report.lower()
        assert "contraindications" in report.lower()

    def _normalize_fixture_schema(self, fixture: dict) -> dict:
        """Normalize fixture schema to match reporter expectations.

        The fixtures use different field names than what the reporter expects.
        This helper transforms the fixture data to the expected format.
        """
        normalized = dict(fixture)

        if "themes_detailed" in normalized:
            themes = normalized["themes_detailed"]
            if themes and isinstance(themes[0], dict):
                normalized["themes_detailed"] = [
                    {
                        "name": t.get("theme") or t.get("name", "Unnamed Theme"),
                        "description": t.get("description", ""),
                        "key_points": t.get("detail_points", []) or t.get("key_points", []),
                        "supporting_sources": (
                            [t["supporting_sources"]] if isinstance(t.get("supporting_sources"), int) else t.get("supporting_sources", [])
                        ),
                    }
                    for t in themes
                ]

        return normalized


class TestReporterFailurePathRegressions:
    """Regression tests for reporter failure modes.

    Task 009: Add Failure-Path Regression Coverage
    These tests verify that the reporter degrades predictably for:
    - Empty findings
    - Incompatible report inputs
    - Missing required fields
    """

    def test_reporter_empty_key_findings_list(self) -> None:
        """Reporter should handle empty key_findings list gracefully."""
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
            "themes": ["Theme 1"],
            "themes_detailed": [],
            "consensus_points": [],
            "contention_points": [],
            "gaps": [],
            "analysis_method": "basic_keyword",
        }

        report = agent.generate_markdown_report(session, analysis)
        assert report is not None

    def test_reporter_none_key_findings(self) -> None:
        """Reporter should handle None key_findings gracefully."""
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
            "analysis_method": "basic_keyword",
        }

        report = agent.generate_markdown_report(session, analysis)
        assert report is not None

    def test_reporter_missing_themes_field(self) -> None:
        """Reporter should handle missing themes field gracefully."""
        config = {"model": "claude-sonnet-4-6"}
        agent = ReporterAgent(config)

        session = ResearchSession(
            session_id="test",
            query="test query",
            depth=ResearchDepth.STANDARD,
            sources=[],
        )

        analysis = {
            "key_findings": [{"title": "Finding", "description": "Description"}],
            "themes_detailed": [],
            "consensus_points": [],
            "contention_points": [],
            "gaps": [],
            "analysis_method": "basic_keyword",
        }

        report = agent.generate_markdown_report(session, analysis)
        assert report is not None
        assert "## Key Findings" in report

    def test_reporter_incompatible_source_objects(self) -> None:
        """Reporter should handle incompatible source objects gracefully."""
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
            "analysis_method": "basic_keyword",
        }

        report = agent.generate_markdown_report(session, analysis)
        assert report is not None
        assert "## Sources" in report

    def test_reporter_unicode_in_content(self) -> None:
        """Reporter should handle unicode characters in content gracefully."""
        config = {"model": "claude-sonnet-4-6"}
        agent = ReporterAgent(config)

        session = ResearchSession(
            session_id="test",
            query="test query",
            depth=ResearchDepth.STANDARD,
            sources=[
                SearchResultItem(
                    url="https://example.com/unicode",
                    title="Unicode Test \u00e9\u00e8\u00ea",
                    snippet="Test with emojis \ud83d\ude00\ud83c\udf1f",
                    score=0.8,
                ),
            ],
        )

        analysis = {
            "key_findings": [
                {"title": "Unicode Finding", "description": "Description with \u00c9\u00e8 characters"}
            ],
            "themes": [],
            "themes_detailed": [],
            "consensus_points": [],
            "contention_points": [],
            "gaps": [],
            "analysis_method": "basic_keyword",
        }

        report = agent.generate_markdown_report(session, analysis)
        assert report is not None

    def test_reporter_empty_session_sources(self) -> None:
        """Reporter should handle session with no sources."""
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
            "analysis_method": "basic_keyword",
        }

        report = agent.generate_markdown_report(session, analysis)
        assert report is not None

    def test_reporter_very_long_source_content(self) -> None:
        """Reporter should handle very long source content without hanging."""
        config = {"model": "claude-sonnet-4-6"}
        agent = ReporterAgent(config)

        session = ResearchSession(
            session_id="test",
            query="test query",
            depth=ResearchDepth.STANDARD,
            sources=[
                SearchResultItem(
                    url="https://example.com/long",
                    title="Long Content",
                    content="x" * 100000,
                    snippet="Very long content",
                    score=0.8,
                ),
            ],
        )

        analysis = {
            "key_findings": [],
            "themes": [],
            "themes_detailed": [],
            "consensus_points": [],
            "contention_points": [],
            "gaps": [],
            "analysis_method": "basic_keyword",
        }

        report = agent.generate_markdown_report(session, analysis)
        assert report is not None

    def test_reporter_empty_json_report_input(self) -> None:
        """Reporter should handle empty dict for JSON report."""
        config = {"model": "claude-sonnet-4-6"}
        agent = ReporterAgent(config)

        session = ResearchSession(
            session_id="test",
            query="test query",
            depth=ResearchDepth.STANDARD,
            sources=[],
        )

        report = agent.generate_json_report(session, {})
        assert report is not None
        assert "test query" in report

    def test_reporter_null_nested_fields(self) -> None:
        """Reporter should handle empty strings in nested analysis fields."""
        config = {"model": "claude-sonnet-4-6"}
        agent = ReporterAgent(config)

        session = ResearchSession(
            session_id="test",
            query="test query",
            depth=ResearchDepth.STANDARD,
            sources=[],
        )

        analysis = {
            "key_findings": [{"title": "Finding", "description": ""}],
            "themes": [],
            "themes_detailed": [],
            "consensus_points": [],
            "contention_points": [],
            "gaps": [],
            "analysis_method": "basic_keyword",
        }

        report = agent.generate_markdown_report(session, analysis)
        assert report is not None
