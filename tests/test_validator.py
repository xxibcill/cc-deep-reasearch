"""Tests for ValidatorAgent follow-up behavior."""

from cc_deep_research.agents.validator import ValidatorAgent
from cc_deep_research.models import ResearchDepth, ResearchSession, SearchResultItem


class TestValidatorAgent:
    """Tests for validation remediation signals."""

    def test_validate_research_builds_follow_up_queries(self) -> None:
        """Validator should produce follow-up queries for weak runs."""
        agent = ValidatorAgent({"min_sources": 3})
        session = ResearchSession(
            session_id="session-1",
            query="test topic",
            depth=ResearchDepth.STANDARD,
            sources=[
                SearchResultItem(
                    url="https://example.com/article",
                    title="Article",
                    snippet="Short snippet",
                    score=0.4,
                )
            ],
        )
        analysis = {
            "key_findings": [{"title": "Finding", "description": "Desc"}],
            "gaps": [
                {
                    "gap_description": "missing regulatory context",
                    "suggested_queries": ["test topic regulation"],
                }
            ],
        }

        validation = agent.validate_research(
            session,
            analysis,
            query="test topic",
            min_sources_override=4,
        )

        assert validation["needs_follow_up"] is True
        assert "test topic regulation" in validation["follow_up_queries"]
        assert "test topic expert analysis" in validation["follow_up_queries"]
