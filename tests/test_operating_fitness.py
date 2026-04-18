"""Tests for OperatingFitnessMetrics computed fields."""

from __future__ import annotations

from cc_deep_research.content_gen.models import OperatingFitnessMetrics


class TestRuleDiversityRatio:
    def test_zero_hook_rules_with_non_hook_rules_returns_2(self) -> None:
        m = OperatingFitnessMetrics(
            hook_rule_count=0,
            framing_rule_count=2,
            scoring_rule_count=1,
            packaging_rule_count=1,
            other_rule_count=0,
        )
        assert m.rule_diversity_ratio == 2.0

    def test_zero_hook_rules_with_no_other_rules_returns_0(self) -> None:
        m = OperatingFitnessMetrics(
            hook_rule_count=0,
            framing_rule_count=0,
            scoring_rule_count=0,
            packaging_rule_count=0,
            other_rule_count=0,
        )
        assert m.rule_diversity_ratio == 0.0

    def test_balanced_rules_returns_1(self) -> None:
        m = OperatingFitnessMetrics(
            hook_rule_count=2,
            framing_rule_count=1,
            scoring_rule_count=0,
            packaging_rule_count=0,
            other_rule_count=1,
        )
        assert m.rule_diversity_ratio == 1.0

    def test_heavily_hook_skewed_returns_low_ratio(self) -> None:
        m = OperatingFitnessMetrics(
            hook_rule_count=10,
            framing_rule_count=1,
            scoring_rule_count=1,
            packaging_rule_count=1,
            other_rule_count=1,
        )
        assert m.rule_diversity_ratio == 0.4


class TestLearningBiasScore:
    def test_no_rules_returns_zero(self) -> None:
        m = OperatingFitnessMetrics(
            hook_rule_count=0,
            framing_rule_count=0,
            scoring_rule_count=0,
            packaging_rule_count=0,
            other_rule_count=0,
        )
        assert m.learning_bias_score == 0.0

    def test_hook_at_expected_share_returns_near_zero(self) -> None:
        # 17 hooks out of 100 total = exactly 17% expected share -> bias = 0
        m = OperatingFitnessMetrics(
            hook_rule_count=17,
            framing_rule_count=20,
            scoring_rule_count=20,
            packaging_rule_count=20,
            other_rule_count=23,
        )
        # hook_share = 17/100 = 0.17, bias = 0, max(0, 0) = 0
        assert m.learning_bias_score == 0.0

    def test_hook_heavily_overrepresented_returns_positive_bias(self) -> None:
        m = OperatingFitnessMetrics(
            hook_rule_count=80,
            framing_rule_count=10,
            scoring_rule_count=5,
            packaging_rule_count=3,
            other_rule_count=2,
        )
        total = 100
        hook_share = 80 / 100
        expected = 0.17
        bias = hook_share - expected
        assert m.learning_bias_score == round(max(0.0, bias), 3)
        assert m.learning_bias_score > 0.5  # should be ~0.63

    def test_hook_underrepresented_returns_zero(self) -> None:
        # Hook is only 5% -> negative bias but clipped to 0
        m = OperatingFitnessMetrics(
            hook_rule_count=5,
            framing_rule_count=30,
            scoring_rule_count=30,
            packaging_rule_count=30,
            other_rule_count=5,
        )
        assert m.learning_bias_score == 0.0


class TestDriftSummary:
    def test_all_zeros_returns_stable(self) -> None:
        m = OperatingFitnessMetrics()
        assert m.drift_summary == "Strategy stable"

    def test_high_churn_includes_churn_message(self) -> None:
        m = OperatingFitnessMetrics(rule_churn_rate=0.8)
        assert "High rule churn" in m.drift_summary

    def test_deprecated_rules_includes_count(self) -> None:
        m = OperatingFitnessMetrics(deprecated_rules_count=3)
        assert "3 rules deprecated" in m.drift_summary

    def test_rules_needing_review_includes_count(self) -> None:
        m = OperatingFitnessMetrics(rules_needing_review_count=2)
        assert "2 rules need review" in m.drift_summary

    def test_high_hook_bias_includes_overrepresentation(self) -> None:
        m = OperatingFitnessMetrics(
            hook_rule_count=80,
            framing_rule_count=5,
            scoring_rule_count=5,
            packaging_rule_count=5,
            other_rule_count=5,
        )
        assert "Hook overrepresentation detected" in m.drift_summary

    def test_moderate_hook_bias_includes_slight_bias(self) -> None:
        m = OperatingFitnessMetrics(
            hook_rule_count=40,
            framing_rule_count=20,
            scoring_rule_count=20,
            packaging_rule_count=10,
            other_rule_count=10,
        )
        bias = (40 / 100) - 0.17
        if bias > 0.3:
            assert "Hook overrepresentation detected" in m.drift_summary
        elif bias > 0.1:
            assert "Slight hook bias" in m.drift_summary

    def test_combined_signals_includes_all_parts(self) -> None:
        m = OperatingFitnessMetrics(
            rule_churn_rate=0.9,
            deprecated_rules_count=2,
            rules_needing_review_count=1,
            hook_rule_count=50,
            framing_rule_count=20,
            scoring_rule_count=20,
            packaging_rule_count=5,
            other_rule_count=5,
        )
        summary = m.drift_summary
        assert "High rule churn" in summary
        assert "2 rules deprecated" in summary
        assert "1 rules need review" in summary
