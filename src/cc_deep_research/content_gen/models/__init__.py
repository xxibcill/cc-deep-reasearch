"""Data models for the content generation workflow.

This subpackage replaces the former monolithic ``content_gen/models.py``.
All public models are re-exported here for backward compatibility.

Contract Version: 1.8.0
"""

from __future__ import annotations

# Contracts
from .contracts import (
    CONTRACT_VERSION,
    CONTENT_GEN_STAGE_CONTRACTS,
    ContentGenStageContract,
)

# Shared enums and types
from .shared import (
    ClaimStatus,
    ClaimTraceStage,
    ClaimTraceStatus,
    DraftLaneDecision,
    EffortTier,
    EvidenceDirectness,
    FactRiskDecision,
    LearningCategory,
    LearningDurability,
    MissingAssetDecision,
    OperatingPhase,
    PlanningLearningCategory,
    ProductionComplexity,
    ReleaseState,
    ResearchClaimType,
    ResearchConfidence,
    ResearchDepthTier,
    ResearchFindingType,
    ResearchFlagType,
    ResearchSeverity,
    RetrievalMode,
    RevisionMode,
    RewriteActionType,
    RuleChangeOperation,
    RuleLifecycleStatus,
    RuleVersionKind,
    SourceAuthority,
    SourceFreshness,
    StrategyReadiness,
    TriageOperationKind,
    VisualComplexity,
    BriefExecutionPolicyMode,
    BriefLifecycleState,
    BriefProvenance,
)

# Stage-specific models
from .angle import (
    AngleDefinition,
    AngleOption,
    AngleOutput,
    BeatIntent,
    BeatIntentMap,
    CoreInputs,
    CtAVariants,
    DerivativeOpportunity,
    EarlyPackagingSignals,
    HookSet,
    StrategyMemory,
    ThesisArtifact,
)

from .backlog import (
    AudienceProblemFitFields,
    BacklogItem,
    BacklogOutput,
    ContentExecutionFields,
    IdeaCoreFields,
    IdeaScores,
    PrioritizationFields,
    ScoringOutput,
    TriageOperation,
    TriageResponse,
    ValidationLayerFields,
)

from .brief import (
    BriefExecutionGate,
    BriefRevision,
    ManagedBriefOutput,
    ManagedOpportunityBrief,
    OpportunityBrief,
    PipelineBriefReference,
    StrategyReadinessIssue,
    StrategyReadinessResult,
)
from .pipeline import (
    PhaseExitCriteria,
    PhaseKillCondition,
    PhaseReuseOpportunity,
    PhaseSkipCondition,
)

from .learning import (
    ContentGenRunMetrics,
    OperatingFitnessMetrics,
    PerformanceAnalysis,
    PerformanceLearning,
    PerformanceLearningSet,
    PlanningLearning,
    PlanningMetrics,
    RuleVersion,
    RuleVersionHistory,
    StrategyPerformanceGuidance,
)

from .pipeline import (
    DEFAULT_PHASE_POLICIES,
    OPERATING_PHASE_LABELS,
    PHASE_TO_STAGES_MAPPING,
    PIPELINE_STAGE_LABELS,
    PIPELINE_STAGES,
    STAGE_TO_PHASE_MAPPING,
    OperatingPhasePolicy,
    PhaseExitCriteria,
    PhaseKillCondition,
    PhaseReuseOpportunity,
    PhaseSkipCondition,
    PipelineContext,
    PipelineLaneContext,
    PipelineStageTrace,
    StageTraceMetadata,
    get_phase_for_stage,
    get_phase_policy,
    get_stages_for_phase,
)

from .production import (
    AssetFallback,
    BeatRevisionScope,
    BeatVisual,
    HumanQCGate,
    IterationState,
    MissingAssetDecision,
    PlatformPackage,
    ProductionBrief,
    PublishItem,
    QualityEvaluation,
    TargetedRevisionPlan,
    TargetedRewriteAction,
    VisualPlanOutput,
    VisualProductionExecutionBrief,
)

from .research import (
    ClaimTraceEntry,
    ClaimTraceLedger,
    FactRiskGate,
    FactRiskGateOutput,
    FactRiskGateResult,
    ProgressiveQCIssue,
    ProgressiveQCCheckpoint,
    ResearchClaim,
    ResearchCounterpoint,
    ResearchDepthRouting,
    ResearchFinding,
    ResearchPack,
    ResearchSource,
    ResearchUncertaintyFlag,
    RetrievalBudget,
    RetrievalDecision,
    RetrievalPlan,
    ScriptClaimStatement,
)

from .script import (
    ArgumentBeatClaim,
    ArgumentClaim,
    ArgumentCounterargument,
    ArgumentMap,
    ArgumentProofAnchor,
    BeatIntent,
    BeatIntentMap,
    CtaVariants,
    HookSet,
    QCResult,
    QCCheck,
    SavedScriptRun,
    ScriptStructure,
    ScriptVersion,
    ScriptingContext,
    ScriptingIterationSummary,
    ScriptingIterations,
    ScriptingLLMCallTrace,
    ScriptingRunResult,
    ScriptingStepTrace,
    VisualNote,
)

# Backward-compat: re-export ClaimTraceLedger in research.py for
# models that still reference it from there
from .research import ClaimTraceLedger as _ClaimTraceLedger

# Pipeline context and lane context - assembled here to avoid circular imports
from .pipeline import PipelineStageTrace, StageTraceMetadata
from .angle import ThesisArtifact
from .research import ResearchPack
from .script import ScriptingContext
from .production import (
    BeatVisual,
    HumanQCGate,
    ProductionBrief,
    VisualPlanOutput,
    VisualProductionExecutionBrief,
    PackagingOutput,
    PlatformPackage,
    PublishItem,
    IterationState,
    QualityEvaluation,
    TargetedRevisionPlan,
    RunConstraints,
)
from .brief import PipelineBriefReference, BriefExecutionGate
from .backlog import BacklogOutput, ScoringOutput, PipelineCandidate
from .angle import AngleOutput
from .learning import PerformanceAnalysis


# ─────────────────────────────────────────────────────────────────────────────
# Legacy constants and helpers that lived in models.py
# ─────────────────────────────────────────────────────────────────────────────

SCRIPTING_STEPS: list[str] = [
    "define_core_inputs",
    "define_angle",
    "choose_structure",
    "define_beat_intents",
    "generate_hooks",
    "draft_script",
    "add_retention_mechanics",
    "tighten",
    "add_visual_notes",
    "run_qc",
]

SCRIPTING_STEP_LABELS: dict[str, str] = {
    "define_core_inputs": "Defining core inputs",
    "define_angle": "Defining angle",
    "choose_structure": "Choosing structure",
    "define_beat_intents": "Defining beat intents",
    "generate_hooks": "Generating hooks",
    "draft_script": "Drafting script",
    "add_retention_mechanics": "Adding retention mechanics",
    "tighten": "Tightening script",
    "add_visual_notes": "Adding visual notes",
    "run_qc": "Running QC",
}


# Content type profiles
from .production import ContentTypeProfile, CONTENT_TYPE_PROFILES, get_content_type_profile


__all__ = [
    # Shared
    "ClaimStatus",
    "ClaimTraceStage",
    "ClaimTraceStatus",
    "DraftLaneDecision",
    "EffortTier",
    "EvidenceDirectness",
    "FactRiskDecision",
    "LearningCategory",
    "LearningDurability",
    "MissingAssetDecision",
    "OperatingPhase",
    "PlanningLearningCategory",
    "ProductionComplexity",
    "ReleaseState",
    "ResearchClaimType",
    "ResearchConfidence",
    "ResearchDepthTier",
    "ResearchFindingType",
    "ResearchFlagType",
    "ResearchSeverity",
    "RetrievalMode",
    "RevisionMode",
    "RewriteActionType",
    "RuleChangeOperation",
    "RuleLifecycleStatus",
    "RuleVersionKind",
    "SourceAuthority",
    "SourceFreshness",
    "StrategyReadiness",
    "TriageOperationKind",
    "VisualComplexity",
    "BriefExecutionPolicyMode",
    "BriefLifecycleState",
    "BriefProvenance",
    # Contracts
    "CONTRACT_VERSION",
    "CONTENT_GEN_STAGE_CONTRACTS",
    "ContentGenStageContract",
    # Angle
    "AngleDefinition",
    "AngleOption",
    "AngleOutput",
    "BeatIntent",
    "BeatIntentMap",
    "CoreInputs",
    "CtAVariants",
    "DerivativeOpportunity",
    "EarlyPackagingSignals",
    "HookSet",
    "StrategyMemory",
    "ThesisArtifact",
    # Backlog
    "AudienceProblemFitFields",
    "BacklogItem",
    "BacklogOutput",
    "ContentExecutionFields",
    "IdeaCoreFields",
    "IdeaScores",
    "PrioritizationFields",
    "ScoringOutput",
    "TriageOperation",
    "TriageResponse",
    "ValidationLayerFields",
    # Brief
    "BriefExecutionGate",
    "BriefRevision",
    "ManagedBriefOutput",
    "ManagedOpportunityBrief",
    "OpportunityBrief",
    "PhaseExitCriteria",
    "PhaseKillCondition",
    "PhaseReuseOpportunity",
    "PhaseSkipCondition",
    "PipelineBriefReference",
    "StrategyReadinessIssue",
    "StrategyReadinessResult",
    # Learning
    "ContentGenRunMetrics",
    "OperatingFitnessMetrics",
    "PerformanceAnalysis",
    "PerformanceLearning",
    "PerformanceLearningSet",
    "PlanningLearning",
    "PlanningMetrics",
    "StrategyPerformanceGuidance",
    # Pipeline
    "DEFAULT_PHASE_POLICIES",
    "OPERATING_PHASE_LABELS",
    "PHASE_TO_STAGES_MAPPING",
    "PIPELINE_STAGE_LABELS",
    "PIPELINE_STAGES",
    "STAGE_TO_PHASE_MAPPING",
    "OperatingPhasePolicy",
    "PhaseExitCriteria",
    "PhaseKillCondition",
    "PhaseReuseOpportunity",
    "PhaseSkipCondition",
    "PipelineStageTrace",
    "StageTraceMetadata",
    "get_phase_for_stage",
    "get_phase_policy",
    "get_stages_for_phase",
    # Production
    "AssetFallback",
    "BeatRevisionScope",
    "BeatVisual",
    "ContentTypeProfile",
    "CONTENT_TYPE_PROFILES",
    "HumanQCGate",
    "IterationState",
    "MissingAssetDecision",
    "PlatformPackage",
    "ProductionBrief",
    "PublishItem",
    "QualityEvaluation",
    "TargetedRevisionPlan",
    "TargetedRewriteAction",
    "VisualPlanOutput",
    "VisualProductionExecutionBrief",
    # Research
    "ClaimTraceEntry",
    "ClaimTraceLedger",
    "FactRiskGate",
    "FactRiskGateOutput",
    "FactRiskGateResult",
    "ProgressiveQCIssue",
    "ProgressiveQCCheckpoint",
    "ResearchCounterpoint",
    "ResearchDepthRouting",
    "ResearchFinding",
    "ResearchPack",
    "ResearchSource",
    "ResearchUncertaintyFlag",
    "RetrievalBudget",
    "RetrievalDecision",
    "RetrievalPlan",
    "ScriptClaimStatement",
    # Script
    "BeatIntent",
    "BeatIntentMap",
    "CtAVariants",
    "HookSet",
    "QCResult",
    "QCCheck",
    "SavedScriptRun",
    "ScriptStructure",
    "ScriptVersion",
    "ScriptingContext",
    "ScriptingIterationSummary",
    "ScriptingIterations",
    "ScriptingLLMCallTrace",
    "ScriptingRunResult",
    "ScriptingStepTrace",
    "VisualNote",
    # Backward compat
    "get_content_type_profile",
    "SCRIPTING_STEPS",
    "SCRIPTING_STEP_LABELS",
]


# Rebuild PipelineContext to resolve forward references after all models are loaded
from .pipeline import PipelineContext

PipelineContext.model_rebuild()

