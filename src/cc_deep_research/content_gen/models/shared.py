"""Shared enums and types used across multiple stages."""

from __future__ import annotations

from enum import StrEnum

# ---------------------------------------------------------------------------
# Shared enums
# ---------------------------------------------------------------------------


class ClaimTraceStatus(StrEnum):
    """Status of a claim trace entry."""

    PENDING = "pending"
    SUPPORTED = "supported"
    WEAK = "weak"
    UNSUPPORTED = "unsupported"
    REDACTED = "redacted"


class ClaimTraceStage(StrEnum):
    """Pipeline stage where a claim trace entry was created."""

    RESEARCH_PACK = "research_pack"
    ARGUMENT_MAP = "argument_map"
    SCRIPTING = "scripting"
    QC = "qc"


class LearningDurability(StrEnum):
    """How long a learning pattern remains valid."""

    EPHEMERAL = "ephemeral"  # Single run only
    TRANSIENT = "transient"  # Days to weeks
    DURABLE = "durable"  # Months


class LearningCategory(StrEnum):
    """Category of operational learning."""

    HOOK_EFFECTIVENESS = "hook_effectiveness"
    PROOF_REQUIREMENTS = "proof_requirements"
    AUDIENCE_CLARITY = "audience_clarity"
    STRUCTURE_EFFECTIVENESS = "structure_effectiveness"
    RESEARCH_DEPTH = "research_depth"
    RELEASE_STRATEGY = "release_strategy"


class EffortTier(StrEnum):
    """Production effort tier."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    STANDARD = "standard"  # Alias for MEDIUM for backward compatibility


class ProductionComplexity(StrEnum):
    """Production complexity level."""

    TRIVIAL = "trivial"  # Minimal setup, no B-roll needed
    SIMPLE = "simple"  # Basic setup, minimal B-roll
    STANDARD = "standard"  # Normal production with standard B-roll
    COMPLEX = "complex"  # Significant setup, custom B-roll
    CINEMATIC = "cinematic"  # Full production with extensive B-roll


class VisualComplexity(StrEnum):
    """Visual complexity level for scripting."""

    MINIMAL = "minimal"  # Single shot, no cuts
    SIMPLE = "simple"  # 1-3 shots
    STANDARD = "standard"  # 4-6 shots with transitions
    DYNAMIC = "dynamic"  # 7+ shots, complex transitions


class ResearchConfidence(StrEnum):
    """Confidence level for a research finding."""

    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class ResearchFindingType(StrEnum):
    """Type of research finding."""

    FACTUAL = "factual"
    STATISTICAL = "statistical"
    EXPERT_OPINION = "expert_opinion"
    ANECDOTAL = "anecdotal"


class ResearchClaimType(StrEnum):
    """Type of research claim."""

    SAFE = "safe"
    UNSAFE = "unsafe"
    QUALIFIED = "qualified"


class ResearchFlagType(StrEnum):
    """Type of uncertainty flag on a research claim."""

    VERIFICATION_REQUIRED = "verification_required"
    UNSAFE_OR_UNCERTAIN = "unsafe_or_uncertain"
    AREA_OF_IGNORANCE = "area_of_ignorance"


class ResearchSeverity(StrEnum):
    """Severity of a research flag."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class SourceAuthority(StrEnum):
    """Authority level of a research source."""

    HIGH = "high"  # Peer-reviewed, official sources
    MEDIUM = "medium"  # Established publications
    LOW = "low"  # General web sources


class EvidenceDirectness(StrEnum):
    """How directly evidence supports a claim."""

    DIRECT = "direct"  # Explicitly supports claim
    INDIRECT = "indirect"  # Related but not explicit
    TANGENTIAL = "tangential"  # Loosely related


class SourceFreshness(StrEnum):
    """Freshness of a research source."""

    CURRENT = "current"  # < 6 months
    RECENT = "recent"  # 6-18 months
    AGED = "aged"  # 18 months - 3 years
    STALE = "stale"  # > 3 years


class RetrievalMode(StrEnum):
    """Retrieval strategy mode for the planner."""

    BASELINE = "baseline"  # Standard breadth: 6 families, balanced
    DEEP = "deep"  # Widen to cover gaps: additional queries per family
    TARGETED = "targeted"  # Narrow focus: specific evidence gaps
    CONTRARIAN = "contrarian"  # Emphasize counterevidence and pushback


class ResearchDepthTier(StrEnum):
    """Depth tier for research routing."""

    SURFACE = "surface"  # Quick verification
    STANDARD = "standard"  # Normal depth
    DEEP = "deep"  # Comprehensive research


class ClaimStatus(StrEnum):
    """Status of a claim in the ledger."""

    PENDING = "pending"
    SUPPORTED = "supported"
    WEAK = "weak"
    UNSUPPORTED = "unsupported"


class FactRiskDecision(StrEnum):
    """Decision from the fact-risk gate."""

    PASS = "pass"  # All claims verified
    CONDITIONAL_PASS = "conditional_pass"  # Minor risks, proceed with caution
    FLAG = "flag"  # Significant risks, operator review needed
    BLOCK = "block"  # Critical risks, do not proceed


class MissingAssetDecision(StrEnum):
    """How to handle a missing asset or dependency."""

    DOWNGRADE = "downgrade"  # Use simpler fallback option
    DELAY = "delay"  # Wait until asset is available
    ALT_FORMAT = "alt_format"  # Switch to alternate format
    SKIP = "skip"  # Skip this element entirely


class ReleaseState(StrEnum):
    """P6-T2: Explicit release states for publish readiness."""

    BLOCKED = "blocked"  # QC found issues that block publication
    APPROVED = "approved"  # QC passed, no known risks
    APPROVED_WITH_KNOWN_RISKS = "approved_with_known_risks"  # Operator accepted known risks


class DraftLaneDecision(StrEnum):
    """P4-T3: Draft lane decision for publish-now vs hold-for-proof path."""

    PUBLISH_NOW = "publish_now"  # Publish with known uncertainty, fast path
    HOLD_FOR_PROOF = "hold_for_proof"  # Hold for stronger proof before publishing
    RECYCLE_FOR_REUSE = "recycle_for_reuse"  # Recycle to backlog for derivative/reuse
    KILL = "kill"  # Abandon this draft


class RevisionMode(StrEnum):
    """Revision strategy for the iterative loop."""

    FULL = "full"  # Re-run all content stages with broad feedback
    TARGETED = "targeted"  # Surgical repair of specific weak beats only
    NONE = "none"  # No revision needed — script is acceptable


class RewriteActionType(StrEnum):
    """The type of repair action for a targeted revision."""

    REWRITE_BEAT = "rewrite_beat"  # Rewrite the beat content (severe issues)
    REFRESH_EVIDENCE = "refresh_evidence"  # Update evidence only, keep structure
    QUALIFY_CLAIM = "qualify_claim"  # Soften a claim instead of proving it
    REMOVE_CLAIM = "remove_claim"  # Drop the claim entirely
    ADD_COUNTERARGUMENT = "add_counterargument"  # Add counterargument coverage


class RuleVersionKind(StrEnum):
    """What kind of rule was changed."""

    HOOK = "hook"
    FRAMING = "framing"
    SCORING_THRESHOLD = "scoring_threshold"
    PACKAGING_HEURISTIC = "packaging_heuristic"
    REUSE_TEMPLATE = "reuse_template"
    TIME_BUDGET = "time_budget"


class RuleChangeOperation(StrEnum):
    """How the rule was changed."""

    ADDED = "added"
    UPDATED = "updated"
    REMOVED = "removed"


class RuleLifecycleStatus(StrEnum):
    """Lifecycle state of a reusable rule."""

    PROMOTED = "promoted"  # Active and in use
    UNDER_REVIEW = "under_review"  # Awaiting operator review
    DEPRECATED = "deprecated"  # No longer recommended
    EXPIRED = "expired"  # Past review date, needs attention


class StrategyReadiness(StrEnum):
    """Readiness level for a strategy memory."""

    INVALID = "invalid"  # Critical required fields missing, blocks pipeline
    INCOMPLETE = "incomplete"  # Has niche/pillars but weak overall, warns
    HEALTHY = "healthy"  # Core strategy is well-populated


class BriefLifecycleState(StrEnum):
    """Lifecycle states for a managed opportunity brief."""

    DRAFT = "draft"  # Initial state; AI-generated or operator-created, not yet approved
    APPROVED = "approved"  # Reviewed and approved; ready to drive backlog generation
    SUPERSEDED = "superseded"  # Replaced by a newer approved brief (rare; for long-running campaigns)
    ARCHIVED = "archived"  # No longer active; retained for audit trail


class BriefProvenance(StrEnum):
    """How a brief entered the managed brief system."""

    GENERATED = "generated"
    IMPORTED = "imported"
    CLONED = "cloned"
    BRANCHED = "branched"
    OPERATOR_CREATED = "operator_created"


class BriefExecutionPolicyMode(StrEnum):
    """Policy modes for brief approval gates."""

    DEFAULT_APPROVED = "default_approved"
    ALLOW_DRAFT = "allow_draft"
    ALLOW_ANY = "allow_any"


class TriageOperationKind(str):
    """Kinds of batch triage proposals."""

    BATCH_ENRICH = "batch_enrich"
    BATCH_REFRAME = "batch_reframe"
    DEDUPE_RECOMMENDATION = "dedupe_recommendation"
    ARCHIVE_RECOMMENDATION = "archive_recommendation"
    PRIORITY_RECOMMENDATION = "priority_recommendation"


class PlanningLearningCategory(StrEnum):
    """Category of opportunity planning learning."""

    BRIEF_SPECIFICITY = "brief_specificity"
    AUDIENCE_DEFINITION = "audience_definition"
    HYPOTHESIS_QUALITY = "hypothesis_quality"
    SUCCESS_CRITERIA = "success_criteria"
    PROOF_REQUIREMENTS = "proof_requirements"
    SUB_ANGLE_DISTINCTION = "sub_angle_distinction"


class OperatingPhase(StrEnum):
    """Canonical seven-phase operating model for content generation."""

    PHASE_01_STRATEGY = "phase_01_strategy"
    PHASE_02_OPPORTUNITY = "phase_02_opportunity"
    PHASE_03_RESEARCH = "phase_03_research"
    PHASE_04_DRAFT = "phase_04_draft"
    PHASE_05_VISUAL = "phase_05_visual"
    PHASE_06_QC = "phase_06_qc"
    PHASE_07_PUBLISH = "phase_07_publish"
