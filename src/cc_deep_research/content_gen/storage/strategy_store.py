"""YAML persistence for strategy memory."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

import yaml

from cc_deep_research.content_gen.models import (
    RuleChangeOperation,
    RuleLifecycleStatus,
    RuleVersion,
    RuleVersionKind,
    StrategyMemory,
    StrategyReadiness,
    StrategyReadinessIssue,
    StrategyReadinessResult,
)
from cc_deep_research.content_gen.storage._paths import resolve_content_gen_file_path

if TYPE_CHECKING:
    from cc_deep_research.config import Config


def _now_iso() -> str:
    return datetime.now(tz=UTC).isoformat()


def _deep_merge(base: dict[str, Any], patch: dict[str, Any]) -> dict[str, Any]:
    """Recursively merge patch into base, merging nested dicts rather than replacing them."""
    result: dict[str, Any] = dict(base)
    for key, value in patch.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = value
    return result


def _model_to_dict(model: Any) -> dict[str, Any]:
    """Serialize a Pydantic model to a plain dict, converting enums to string values."""
    from enum import Enum

    def _convert_value(value: Any) -> Any:
        if isinstance(value, Enum):
            return value.value
        if isinstance(value, dict):
            return {k: _convert_value(v) for k, v in value.items()}
        if isinstance(value, list):
            return [_convert_value(item) for item in value]
        return value

    data = model.model_dump(exclude_none=True)
    return _convert_value(data)


class StrategyStore:
    """Load and save :class:`StrategyMemory` to a YAML file."""

    def __init__(self, path: Path | None = None, *, config: Config | None = None) -> None:
        self._path = resolve_content_gen_file_path(
            explicit_path=path,
            config=config,
            config_attr="strategy_path",
            default_name="strategy.yaml",
        )

    @property
    def path(self) -> Path:
        return self._path

    def load(self) -> StrategyMemory:
        """Load strategy from disk, returning a blank model when missing."""
        if not self._path.exists():
            return StrategyMemory()
        data = yaml.safe_load(self._path.read_text()) or {}
        return StrategyMemory.model_validate(data)

    def save(self, memory: StrategyMemory) -> None:
        """Persist strategy memory to disk."""
        self._path.parent.mkdir(parents=True, exist_ok=True)
        data = _model_to_dict(memory)
        self._path.write_text(yaml.dump(data, default_flow_style=False, sort_keys=False))

    def update(self, patch: dict[str, Any]) -> StrategyMemory:
        """Load, apply a deep-merged partial update, save, and return the result."""
        memory = self.load()
        merged = _deep_merge(memory.model_dump(), patch)
        updated = StrategyMemory.model_validate(merged)
        self.save(updated)
        return updated

    # ---------------------------------------------------------------------------
    # P7-T2: Rule Version History
    # ---------------------------------------------------------------------------

    def record_rule_version(
        self,
        kind: RuleVersionKind | str,
        operation: RuleChangeOperation | str,
        change_summary: str,
        *,
        previous_value: str = "",
        new_value: str = "",
        source_learning_ids: list[str] | None = None,
        source_content_ids: list[str] | None = None,
        approved_by: str = "",
    ) -> RuleVersion:
        """Record a new rule version in the strategy memory.

        P7-T2: Records versioned rule changes so operators can see when
        guidance changed. Each version records what changed, when, and why.

        Args:
            kind: What kind of rule was changed (hook, framing, scoring, etc.)
            operation: How the rule was changed (added, updated, removed)
            change_summary: Human-readable description of the change
            previous_value: The rule content before change (empty for ADDED)
            new_value: The rule content after change (empty for REMOVED)
            source_learning_ids: Learning IDs that prompted this change
            source_content_ids: Content IDs that provided evidence
            approved_by: Operator who approved (empty if auto-approved)

        Returns:
            The created RuleVersion
        """
        # Normalize string inputs to enums
        if isinstance(kind, str):
            kind = RuleVersionKind(kind)
        if isinstance(operation, str):
            operation = RuleChangeOperation(operation)

        version = RuleVersion(
            kind=kind,
            operation=operation,
            change_summary=change_summary,
            previous_value=previous_value,
            new_value=new_value,
            source_learning_ids=source_learning_ids or [],
            source_content_ids=source_content_ids or [],
            approved_by=approved_by,
            created_at=_now_iso(),
        )

        memory = self.load()
        memory.rule_version_history.versions.append(version)
        self.save(memory)
        return version

    def get_rule_versions(
        self,
        kind: RuleVersionKind | None = None,
    ) -> list[RuleVersion]:
        """Get rule version history, optionally filtered by kind."""
        memory = self.load()
        versions = memory.rule_version_history.versions
        if kind is not None:
            versions = [v for v in versions if v.kind == kind]
        return sorted(versions, key=lambda v: v.created_at)

    # ---------------------------------------------------------------------------
    # P4-T1: Strategy Readiness Validation
    # ---------------------------------------------------------------------------

    def check_readiness(self) -> StrategyReadinessResult:
        """Validate strategy completeness and quality.

        P4-T1: Runs blocking and warning checks to determine whether
        the strategy is invalid, incomplete, or healthy.

        Returns:
            StrategyReadinessResult with readiness level, issues, and summary
        """
        memory = self.load()
        issues: list[StrategyReadinessIssue] = []
        score_components: list[float] = []

        # BLOCKING: Missing niche
        if not memory.niche or not memory.niche.strip():
            issues.append(
                StrategyReadinessIssue(
                    code="MISSING_NICHE",
                    label="Missing niche",
                    severity="blocking",
                    field_path="niche",
                    detail="Strategy has no niche defined",
                    suggestion="Define your content niche (e.g., B2B SaaS, personal finance for developers)",
                )
            )
        else:
            score_components.append(1.0)

        # BLOCKING: Missing content pillars
        if not memory.content_pillars:
            issues.append(
                StrategyReadinessIssue(
                    code="MISSING_PILLARS",
                    label="Missing content pillars",
                    severity="blocking",
                    field_path="content_pillars",
                    detail="Strategy has no content pillars defined",
                    suggestion="Define at least 2-3 content pillars that represent your content categories",
                )
            )
        else:
            score_components.append(min(1.0, len(memory.content_pillars) / 3))

        # WARNING: Missing expertise edge
        if not memory.expertise_edge or not memory.expertise_edge.strip():
            issues.append(
                StrategyReadinessIssue(
                    code="MISSING_EXPERTISE_EDGE",
                    label="Missing expertise edge",
                    severity="warning",
                    field_path="expertise_edge",
                    detail="Strategy has no expertise edge defined",
                    suggestion="Define what makes your content perspective unique",
                )
            )
        else:
            score_components.append(1.0)

        # WARNING: Missing proof standards
        if not memory.proof_standards:
            issues.append(
                StrategyReadinessIssue(
                    code="MISSING_PROOF_STANDARDS",
                    label="Missing proof standards",
                    severity="warning",
                    field_path="proof_standards",
                    detail="Strategy has no proof standards defined",
                    suggestion="Define what evidence and proof standards are required for claims",
                )
            )
        else:
            score_components.append(min(1.0, len(memory.proof_standards) / 3))

        # WARNING: Missing forbidden claims
        if not memory.forbidden_claims:
            issues.append(
                StrategyReadinessIssue(
                    code="MISSING_FORBIDDEN_CLAIMS",
                    label="Missing forbidden claims",
                    severity="warning",
                    field_path="forbidden_claims",
                    detail="Strategy has no forbidden claims defined",
                    suggestion="Define claims you will never make (e.g., guarantees, unsubstantiated stats)",
                )
            )
        else:
            score_components.append(min(1.0, len(memory.forbidden_claims) / 3))

        # WARNING: Missing platforms
        if not memory.platforms:
            issues.append(
                StrategyReadinessIssue(
                    code="MISSING_PLATFORMS",
                    label="Missing platforms",
                    severity="warning",
                    field_path="platforms",
                    detail="Strategy has no platforms defined",
                    suggestion="Define which platforms you publish to (e.g., YouTube, LinkedIn, Newsletter)",
                )
            )
        else:
            score_components.append(1.0)

        # WARNING: No audience segments
        if not memory.audience_segments:
            issues.append(
                StrategyReadinessIssue(
                    code="MISSING_AUDIENCE_SEGMENTS",
                    label="Missing audience segments",
                    severity="warning",
                    field_path="audience_segments",
                    detail="Strategy has no audience segments defined",
                    suggestion="Define 2-3 audience segments with their characteristics and needs",
                )
            )
        else:
            score_components.append(min(1.0, len(memory.audience_segments) / 3))

        # WARNING: No tone rules
        if not memory.tone_rules:
            issues.append(
                StrategyReadinessIssue(
                    code="MISSING_TONE_RULES",
                    label="Missing tone rules",
                    severity="warning",
                    field_path="tone_rules",
                    detail="Strategy has no tone rules defined",
                    suggestion="Define your content tone guidelines (e.g., direct, data-driven, conversational)",
                )
            )
        else:
            score_components.append(min(1.0, len(memory.tone_rules) / 3))

        # WARNING: No past winners
        if not memory.past_winners:
            issues.append(
                StrategyReadinessIssue(
                    code="MISSING_PAST_WINNERS",
                    label="Missing past winners",
                    severity="warning",
                    field_path="past_winners",
                    detail="Strategy has no past winners recorded",
                    suggestion="Record your best-performing content to help the system learn",
                )
            )
        else:
            score_components.append(min(1.0, len(memory.past_winners) / 5))

        # Calculate overall score
        overall_score = sum(score_components) / len(score_components) if score_components else 0.0

        # Determine readiness level
        blocking_issues = [i for i in issues if i.severity == "blocking"]
        if blocking_issues:
            readiness = StrategyReadiness.INVALID
        elif len(issues) > 4 or overall_score < 0.7:
            readiness = StrategyReadiness.INCOMPLETE
        else:
            readiness = StrategyReadiness.HEALTHY

        # Build summary
        if readiness == StrategyReadiness.INVALID:
            summary = f"Strategy is invalid: {len(blocking_issues)} blocking issue(s) must be resolved"
        elif readiness == StrategyReadiness.INCOMPLETE:
            summary = f"Strategy is incomplete: {len(issues)} recommendation(s) to improve quality"
        else:
            summary = f"Strategy is healthy: {overall_score:.0%} completeness"

        return StrategyReadinessResult(
            readiness=readiness,
            overall_score=overall_score,
            issues=issues,
            summary=summary,
        )

    # ---------------------------------------------------------------------------
    # P4-T2: Rule Governance Lifecycle
    # ---------------------------------------------------------------------------

    def update_rule_lifecycle(
        self,
        version_id: str,
        *,
        status: RuleLifecycleStatus | None = None,
        confidence: float | None = None,
        evidence_count: int | None = None,
        review_after: str | None = None,
        review_notes: str | None = None,
    ) -> RuleVersion | None:
        """Update lifecycle metadata for a rule version.

        P4-T2: Allows operators to mark rules as under_review, deprecated,
        or expired and record review notes.

        Args:
            version_id: ID of the rule version to update
            status: New lifecycle status
            confidence: Updated confidence score
            evidence_count: Updated evidence count
            review_after: ISO date string for next review date
            review_notes: Operator review notes

        Returns:
            Updated RuleVersion or None if not found
        """
        memory = self.load()
        for version in memory.rule_version_history.versions:
            if version.version_id == version_id:
                if status is not None:
                    version.lifecycle_status = status
                if confidence is not None:
                    version.confidence = confidence
                if evidence_count is not None:
                    version.evidence_count = evidence_count
                if review_after is not None:
                    version.review_after = review_after
                if review_notes is not None:
                    version.review_notes = review_notes
                self.save(memory)
                return version
        return None

    def deprecate_rule(self, version_id: str, reason: str = "") -> RuleVersion | None:
        """Mark a rule as deprecated.

        P4-T2: Retires a rule with a reason for deprecation.

        Args:
            version_id: ID of the rule version to deprecate
            reason: Reason for deprecation

        Returns:
            Updated RuleVersion or None if not found
        """
        return self.update_rule_lifecycle(
            version_id,
            status=RuleLifecycleStatus.DEPRECATED,
            review_notes=reason,
        )

    def mark_rule_under_review(self, version_id: str, review_after: str) -> RuleVersion | None:
        """Mark a rule as under review with a review date.

        P4-T2: Places a rule in review state pending operator decision.

        Args:
            version_id: ID of the rule version
            review_after: ISO date when review decision is expected

        Returns:
            Updated RuleVersion or None if not found
        """
        return self.update_rule_lifecycle(
            version_id,
            status=RuleLifecycleStatus.UNDER_REVIEW,
            review_after=review_after,
        )

    def get_rules_for_review(self) -> list[RuleVersion]:
        """Get all rules that need operator review.

        P4-T2: Returns rules that are under_review, expired, or past their
        review date.

        Returns:
            List of RuleVersion objects needing review
        """
        memory = self.load()
        return memory.rule_version_history.get_rules_needing_review()
