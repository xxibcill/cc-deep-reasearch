"""Data models for the content generation workflow."""

from __future__ import annotations

from pydantic import BaseModel


class CoreInputs(BaseModel):
    """Step 1 output: topic, outcome, audience."""

    topic: str
    outcome: str
    audience: str


class AngleDefinition(BaseModel):
    """Step 2 output: angle, content type, core tension."""

    angle: str
    content_type: str
    core_tension: str
    why_it_works: str = ""


class ScriptStructure(BaseModel):
    """Step 3 output: chosen structure and beat list."""

    chosen_structure: str
    why_it_fits: str = ""
    beat_list: list[str]


class BeatIntent(BaseModel):
    """Single beat with name and intent."""

    beat_name: str
    intent: str


class BeatIntentMap(BaseModel):
    """Step 4 output: all beat intents."""

    beats: list[BeatIntent]


class HookSet(BaseModel):
    """Step 5 output: generated hooks with best selection."""

    hooks: list[str]
    best_hook: str
    best_hook_reason: str


class ScriptVersion(BaseModel):
    """Script text with metadata (used for draft, retention, tightened)."""

    content: str
    word_count: int


class VisualNote(BaseModel):
    """Step 9 output: visual annotation for a beat."""

    beat_name: str
    line: str
    note: str | None = None


class QCCheck(BaseModel):
    """Single QC checklist item."""

    item: str
    passed: bool


class QCResult(BaseModel):
    """Step 10 output: QC review."""

    checks: list[QCCheck]
    weakest_parts: list[str]
    final_script: str


class ScriptingContext(BaseModel):
    """Accumulated state passed through the scripting pipeline.

    Each step enriches the context with its output. Steps can be
    run independently by loading a previously saved context.
    """

    raw_idea: str = ""
    core_inputs: CoreInputs | None = None
    angle: AngleDefinition | None = None
    structure: ScriptStructure | None = None
    beat_intents: BeatIntentMap | None = None
    hooks: HookSet | None = None
    draft: ScriptVersion | None = None
    retention_revised: ScriptVersion | None = None
    tightened: ScriptVersion | None = None
    annotated_script: ScriptVersion | None = None
    visual_notes: list[VisualNote] | None = None
    qc: QCResult | None = None


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
