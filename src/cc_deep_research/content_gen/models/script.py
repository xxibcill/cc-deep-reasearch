"""Script and scripting stage models."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field, model_validator


class ScriptStructure(BaseModel):
    """Per-beat script structure for a single beat in the video."""

    beat_id: str = ""
    beat_type: str = ""
    talking_points: list[str] = Field(default_factory=list)
    evidence_citations: list[str] = Field(default_factory=list)
    hook: str = ""
    cta: str = ""
    duration_seconds: int = 0


class BeatIntent(BaseModel):
    """Beat-level intent for scripting."""

    beat_id: str = ""
    beat_type: str = ""
    intent: str = ""
    key_points: list[str] = Field(default_factory=list)
    evidence_needs: list[str] = Field(default_factory=list)
    talking_duration_seconds: int = 0


class BeatIntentMap(BaseModel):
    """Map of all beats with their intent and evidence needs."""

    beats: list[BeatIntent] = Field(default_factory=list)


class HookSet(BaseModel):
    """Set of hook variants."""

    primary_hook: str = ""
    hook_variants: list[str] = Field(default_factory=list)


class CtaVariants(BaseModel):
    """Step 5b output: generated CTA options with best selection."""

    ctas: list[str]
    best_cta: str
    best_cta_reason: str


# Alias for backward compatibility
CtAVariants = CtaVariants


class ScriptVersion(BaseModel):
    """Single version of a script."""

    version_id: str = ""
    hook: str = ""
    beats: list[ScriptStructure] = Field(default_factory=list)
    cta: str = ""
    word_count: int = 0
    estimated_duration_seconds: int = 0


class VisualNote(BaseModel):
    """Visual note for a beat."""

    beat_id: str = ""
    shot_type: str = ""
    b_roll: str = ""
    on_screen_text: str = ""
    transition: str = ""


class QCCheck(BaseModel):
    """Single QC check for the script."""

    check_id: str = ""
    check_type: str = ""
    passed: bool = True
    issue: str = ""


class QCResult(BaseModel):
    """QC result for the script."""

    passed: bool = True
    issues: list[QCCheck] = Field(default_factory=list)
    # Legacy field from old QCResult
    final_script: str = ""


class ScriptingLLMCallTrace(BaseModel):
    """Trace of a single LLM call within scripting."""

    call_id: str = ""
    prompt_tokens: int = 0
    completion_tokens: int = 0
    model: str = ""
    beat_id: str = ""


class ScriptingStepTrace(BaseModel):
    """Trace of a single scripting step."""

    step_id: str = ""
    step_type: str = ""
    beat_id: str = ""
    llm_calls: list[ScriptingLLMCallTrace] = Field(default_factory=list)
    duration_ms: int = 0
    parse_success: bool = True


class ScriptingContext(BaseModel):
    """Output of the scripting stage."""

    # Legacy fields (for backward compat with stored data and router.py)
    raw_idea: str = ""
    research_context: str = ""
    tone: str = ""
    # Current stage output
    idea_id: str = ""
    hook: str = ""
    thesis: str = ""
    beats: list[ScriptStructure] = Field(default_factory=list)
    cta: str = ""
    word_count: int = 0
    estimated_duration_seconds: int = 0
    version_id: str = ""
    parse_mode: str = "json"
    # Claim ledger for evidence tracking
    claim_ledger: "ClaimTraceLedger | None" = None
    # QC result (named qc for backward compat with old ScriptingContext)
    qc: QCResult | None = None
    # Traces
    llm_traces: list[ScriptingLLMCallTrace] = Field(default_factory=list)
    step_traces: list[ScriptingStepTrace] = Field(default_factory=list)
    # Iteration metadata
    iteration_number: int = 1
    is_revised: bool = False
    # P3-T3: Per-beat evidence citations
    beat_evidence_map: dict[str, list[str]] = Field(default_factory=dict)
    # Warnings
    warnings: list[str] = Field(default_factory=list)

    @property
    def qc_result(self) -> QCResult | None:
        """Backward compat alias for qc."""
        return self.qc


class SavedScriptRun(BaseModel):
    """Saved standalone scripting run for analysis."""

    run_id: str | None = None
    saved_at: str = ""
    raw_idea: str = ""
    word_count: int = 0
    script_path: str = ""
    context_path: str = ""
    result_path: str | None = None
    context: ScriptingContext | None = None
    execution_mode: Literal["single_pass", "iterative"] = "single_pass"


class ScriptingIterationSummary(BaseModel):
    """Compact quality summary for one scripting iteration."""

    iteration: int = Field(default=1, ge=1)
    score: float = Field(default=0.0, ge=0.0, le=1.0)
    passes: bool = False


class ScriptingIterations(BaseModel):
    """Saved iteration summary for iterative scripting runs."""

    count: int = Field(default=1, ge=1)
    max_iterations: int = Field(default=1, ge=1)
    converged: bool = False
    quality_history: list[ScriptingIterationSummary] = Field(default_factory=list)


class ScriptingRunResult(BaseModel):
    """Full saved response for a standalone scripting run."""

    run_id: str | None = None
    raw_idea: str = ""
    script: str = ""
    word_count: int = 0
    context: ScriptingContext
    execution_mode: Literal["single_pass", "iterative"] = "single_pass"
    iterations: ScriptingIterations | None = None


class ArgumentProofAnchor(BaseModel):
    """A piece of evidence or mechanism support that later beats can cite."""

    proof_id: str = Field(default_factory=lambda: f"proof_{uuid4().hex[:8]}")
    summary: str = ""
    source_ids: list[str] = Field(default_factory=list)
    usage_note: str = ""


class ArgumentCounterargument(BaseModel):
    """Credible pushback and the response the script should hold ready."""

    counterargument_id: str = Field(default_factory=lambda: f"counter_{uuid4().hex[:8]}")
    counterargument: str = ""
    response: str = ""
    response_proof_ids: list[str] = Field(default_factory=list)


class ArgumentClaim(BaseModel):
    """A claim candidate that can be safe to state or marked off-limits."""

    claim_id: str = Field(default_factory=lambda: f"claim_{uuid4().hex[:8]}")
    claim: str = ""
    supporting_proof_ids: list[str] = Field(default_factory=list)
    note: str = ""


class ArgumentBeatClaim(BaseModel):
    """Beat-level plan that ties the narrative to validated proof and claims."""

    beat_id: str = Field(default_factory=lambda: f"beat_{uuid4().hex[:8]}")
    beat_name: str = ""
    goal: str = ""
    claim_ids: list[str] = Field(default_factory=list)
    proof_anchor_ids: list[str] = Field(default_factory=list)
    counterargument_ids: list[str] = Field(default_factory=list)
    transition_note: str = ""


class ArgumentMap(BaseModel):
    """Bridge artifact between research synthesis and script drafting."""

    idea_id: str = ""
    angle_id: str = ""
    thesis: str = ""
    audience_belief_to_challenge: str = ""
    core_mechanism: str = ""
    proof_anchors: list[ArgumentProofAnchor] = Field(default_factory=list)
    counterarguments: list[ArgumentCounterargument] = Field(default_factory=list)
    safe_claims: list[ArgumentClaim] = Field(default_factory=list)
    unsafe_claims: list[ArgumentClaim] = Field(default_factory=list)
    beat_claim_plan: list[ArgumentBeatClaim] = Field(default_factory=list)
    what_this_contributes: str = Field(
        default="",
        description="What the selected angle contributes beyond consensus or standard advice",
    )
    genericity_flags: list[str] = Field(
        default_factory=list,
        description="Specific generic or clichéd framings this script must avoid",
    )
    differentiation_stategy: str = Field(
        default="",
        description="The editorial strategy for standing out from market-standard content on this topic",
    )

    @model_validator(mode="after")
    def _validate_references(self) -> ArgumentMap:
        from .research import _ensure_unique_ids

        proof_ids = _ensure_unique_ids(
            self.proof_anchors,
            id_attr="proof_id",
            label="proof_anchors",
        )
        counterargument_ids = _ensure_unique_ids(
            self.counterarguments,
            id_attr="counterargument_id",
            label="counterarguments",
        )
        claim_ids = _ensure_unique_ids(
            [*self.safe_claims, *self.unsafe_claims],
            id_attr="claim_id",
            label="claims",
        )
        return self


# Import uuid at runtime to avoid top-level import issues in this module
from uuid import uuid4  # noqa: E402
