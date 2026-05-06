"""Tests for performance feedback loop (P22-T2)."""

from __future__ import annotations

from cc_deep_research.content_gen.models import (
    LearningCategory,
    LearningDurability,
    PerformanceAnalysis,
    PerformanceLearning,
    PerformanceLearningSet,
    StrategyPerformanceGuidance,
)


class TestPerformanceFeedbackModel:
    def test_feedback_can_attach_to_brief(self) -> None:
        learning = PerformanceLearning(
            category=LearningCategory.HOOK_EFFECTIVENESS,
            durability=LearningDurability.TRANSIENT,
            observation="Strong hook opening improves retention",
            implication="Hook strength correlates with watch time",
            guidance="Continue using contrarian claim as opener",
            source_video_ids=["vid-001"],
            source_metrics={
                "views": 5000,
                "engagement_rate": 0.08,
                "retention_rate": 0.65,
            },
            evidence_count=1,
            confidence=0.5,
        )
        assert learning.category == LearningCategory.HOOK_EFFECTIVENESS
        assert "vid-001" in learning.source_video_ids
        assert learning.is_active is True

    def test_feedback_with_idea_and_brief_association(self) -> None:
        learning = PerformanceLearning(
            category=LearningCategory.AUDIENCE_CLARITY,
            observation="Audience resonated with founder-focused framing",
            implication="Founders are the primary audience",
            guidance="Double down on founder pain points",
            source_video_ids=["vid-002"],
            platform="youtube",
            content_type="short_form_video",
            audience_context="founders",
        )
        assert learning.platform == "youtube"
        assert learning.audience_context == "founders"

    def test_feedback_attaches_to_hook(self) -> None:
        learning = PerformanceLearning(
            category=LearningCategory.HOOK_EFFECTIVENESS,
            observation="Question-based hook outperformed statement hook",
            implication="Questions engage curiosity better",
            guidance="Use question format for future hooks",
            exact_pattern="What if I told you?",
        )
        assert "question" in learning.observation.lower()
        assert "?" in learning.exact_pattern

    def test_feedback_attaches_to_packaging(self) -> None:
        learning = PerformanceLearning(
            category=LearningCategory.HOOK_EFFECTIVENESS,
            observation="Caption with numbers in first line outperformed",
            implication="Numbers catch scrollers",
            guidance="Start captions with key number or stat",
        )
        assert "numbers" in learning.observation.lower()

    def test_non_blocking_context_for_future_workflows(self) -> None:
        learning = PerformanceLearning(
            category=LearningCategory.PROOF_REQUIREMENTS,
            durability=LearningDurability.EPHEMERAL,
            observation="Single source insufficient for health claims",
            implication="Need multiple sources for health topics",
            guidance="Require 3+ sources for health-adjacent topics",
            confidence=0.3,
        )
        # Confidence is low — advisory only, not blocking
        assert learning.confidence < 0.5
        assert learning.durability == LearningDurability.EPHEMERAL


class TestPerformanceAnalysisModel:
    def test_analysis_with_metrics(self) -> None:
        analysis = PerformanceAnalysis(
            video_id="vid-001",
            metrics={
                "views": 10000,
                "likes": 450,
                "comments": 85,
                "shares": 120,
                "avg_watch_percentage": 0.58,
                "engagement_rate": 0.065,
            },
            what_worked=["Strong hook opening", "Specific numbers in caption"],
            what_failed=["Pacing was too slow in middle", "CTA was unclear"],
            audience_signals=["Founders liked the pricing angle", "Engineers shared for accuracy"],
            dropoff_hypotheses=["Retention dropped at 45s mark — beat 3 pacing"],
            hook_diagnosis="Question-based hook drove curiosity through first 20s",
            lesson="Always lead with contrarian claim in question form",
            next_test="Test same hook with different B-roll",
        )
        assert analysis.video_id == "vid-001"
        assert len(analysis.what_worked) == 2
        assert len(analysis.what_failed) == 2
        assert "45s" in analysis.dropoff_hypotheses[0]

    def test_analysis_with_brief_comparison(self) -> None:
        analysis = PerformanceAnalysis(
            video_id="vid-002",
            metrics={"views": 8000, "engagement_rate": 0.07},
            opportunity_brief_comparison="Content delivered on 'founder pricing pain' promise",
            brief_success_criteria_results=["criterion_met: credibility via expert quote"],
            brief_hypothesis_results=["hypothesis_validated: founders care about unit economics"],
        )
        assert "founder" in analysis.opportunity_brief_comparison
        assert len(analysis.brief_success_criteria_results) == 1


class TestStrategyPerformanceGuidance:
    def test_guidance_from_learnings(self) -> None:
        guidance = StrategyPerformanceGuidance(
            winning_hooks=["Contrarian claim in question form", "Bold number opening"],
            failed_hooks=["Vague statement opening", "Personal story lead"],
            winning_framings=["Founder-centric pain points", "Unit economics breakdown"],
            failed_framings=["Generic industry overview"],
            audience_resonance_notes=["Founders engage with pricing/unit economics"],
            proof_expectations=["Health claims need 3+ independent sources"],
            pending_tests=["Test question vs statement hook with same content"],
        )
        assert len(guidance.winning_hooks) == 2
        assert len(guidance.failed_hooks) == 2
        assert "pending_tests" in guidance.model_dump()


class TestPerformanceLearningSet:
    def test_learning_set_from_analysis(self) -> None:
        analysis = PerformanceAnalysis(
            video_id="vid-003",
            metrics={"views": 5000, "engagement_rate": 0.05},
            what_worked=["Clear thesis in first 10s"],
            hook_diagnosis="Specific number opening grabbed attention",
        )
        learning_set = PerformanceLearningSet(
            video_id="vid-003",
            learnings=[
                PerformanceLearning(
                    category=LearningCategory.HOOK_EFFECTIVENESS,
                    durability=LearningDurability.TRANSIENT,
                    observation="Specific number opening",
                    implication="Numbers are attention-grabbing",
                    guidance="Start with a number",
                    source_video_ids=["vid-003"],
                    confidence=0.4,
                ),
            ],
            source_analysis=analysis,
        )
        assert learning_set.video_id == "vid-003"
        assert len(learning_set.learnings) == 1
        assert learning_set.source_analysis.video_id == "vid-003"


class TestPerformanceLearningStore:
    def test_learning_serialization_roundtrip(self) -> None:
        learning = PerformanceLearning(
            category=LearningCategory.HOOK_EFFECTIVENESS,
            durability=LearningDurability.TRANSIENT,
            observation="Hook observation",
            implication="Hook implication",
            guidance="Hook guidance",
            exact_pattern="exact hook pattern",
            source_video_ids=["vid-x"],
            source_metrics={"views": 1000},
            evidence_count=1,
            confidence=0.5,
            platform="youtube",
            content_type="short_form_video",
            created_at="2026-05-01T00:00:00Z",
            updated_at="2026-05-01T00:00:00Z",
        )
        data = learning.model_dump(mode="json")
        restored = PerformanceLearning.model_validate(data)
        assert restored.learning_id == learning.learning_id
        assert restored.category == learning.category
        assert restored.platform == "youtube"
