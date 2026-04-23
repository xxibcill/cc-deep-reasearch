# Scripting Pipeline Input/Output Schemas

The scripting pipeline (pipeline stage 5, `run_scripting`) is a 10-step sub-pipeline. Each step reads required fields from `ScriptingContext`, calls the LLM, and writes its output back into the context. All models are Pydantic classes defined in `src/cc_deep_research/content_gen/models/`.

## Accumulated Context

`ScriptingContext` holds all state and flows through every step:

| Field | Type | Populated by |
|-------|------|-------------|
| `raw_idea` | `str` | Entry point / step 1 |
| `research_context` | `str` | Pipeline stage 4 (research pack) |
| `tone` | `str` | Strategy memory |
| `cta` | `str` | Strategy memory |
| `core_inputs` | `CoreInputs` | Step 1 |
| `angle` | `AngleDefinition` | Step 2 |
| `structure` | `ScriptStructure` | Step 3 |
| `beat_intents` | `BeatIntentMap` | Step 4 |
| `hooks` | `HookSet` | Step 5 |
| `draft` | `ScriptVersion` | Step 6 |
| `retention_revised` | `ScriptVersion` | Step 7 |
| `tightened` | `ScriptVersion` | Step 8 |
| `annotated_script` | `ScriptVersion` | Step 9 |
| `visual_notes` | `list[VisualNote]` | Step 9 |
| `qc` | `QCResult` | Step 10 |

## Step-by-Step Schemas

### Step 1 — `define_core_inputs`

Extracts the fundamental building blocks from the raw idea.

**Input:** `raw_idea: str`

**Output:** `CoreInputs`

| Field | Type | Description |
|-------|------|-------------|
| `topic` | `str` | What the content is about |
| `outcome` | `str` | What the viewer should get |
| `audience` | `str` | Who the content is for |

---

### Step 2 — `define_angle`

Chooses the editorial angle and content type.

**Input:** `core_inputs`

**Output:** `AngleDefinition`

| Field | Type | Description |
|-------|------|-------------|
| `angle` | `str` | The editorial angle |
| `content_type` | `str` | Format (e.g. listicle, story, rant) |
| `core_tension` | `str` | The central conflict or tension |
| `why_it_works` | `str` | Rationale for the angle |

---

### Step 3 — `choose_structure`

Selects a narrative structure and breaks it into beats.

**Input:** `core_inputs`, `angle`

**Output:** `ScriptStructure`

| Field | Type | Description |
|-------|------|-------------|
| `chosen_structure` | `str` | Name of the structure template |
| `why_it_fits` | `str` | Why this structure fits the angle |
| `beat_list` | `list[str]` | Ordered list of beat names |

---

### Step 4 — `define_beat_intents`

Assigns a purpose to each beat from step 3.

**Input:** `core_inputs`, `angle`, `structure`

**Output:** `BeatIntentMap`

| Field | Type | Description |
|-------|------|-------------|
| `beats` | `list[BeatIntent]` | All beats with their intents |

**`BeatIntent`:**

| Field | Type | Description |
|-------|------|-------------|
| `beat_name` | `str` | Name matching a beat from `beat_list` |
| `intent` | `str` | What this beat should accomplish |

---

### Step 5 — `generate_hooks`

Generates hook options and selects the strongest.

**Input:** `core_inputs`, `angle`, `beat_intents`

**Output:** `HookSet`

| Field | Type | Description |
|-------|------|-------------|
| `hooks` | `list[str]` | All generated hook options |
| `best_hook` | `str` | The selected strongest hook |
| `best_hook_reason` | `str` | Why this hook is strongest |

---

### Step 6 — `draft_script`

Writes the full script using all prior context.

**Input:** `core_inputs`, `angle`, `structure`, `beat_intents`, `hooks`

**Output:** `ScriptVersion` (written to `draft`)

| Field | Type | Description |
|-------|------|-------------|
| `content` | `str` | The full script text |
| `word_count` | `int` | Word count (target: 120, hard cap: 144) |

> If the draft exceeds 144 words, the agent re-prompts the LLM to trim it.

---

### Step 7 — `add_retention_mechanics`

Rewrites the script to improve pacing and viewer retention.

**Input:** `draft`

**Output:** `ScriptVersion` (written to `retention_revised`)

| Field | Type | Description |
|-------|------|-------------|
| `content` | `str` | Retention-revised script |
| `word_count` | `int` | Word count of the revision |

---

### Step 8 — `tighten`

Sharpens the script by cutting filler and tightening language.

**Input:** `retention_revised` or `draft` (falls back)

**Output:** `ScriptVersion` (written to `tightened`)

| Field | Type | Description |
|-------|------|-------------|
| `content` | `str` | Tightened script |
| `word_count` | `int` | Word count after tightening |

---

### Step 9 — `add_visual_notes`

Adds production annotations (shot notes, visual cues) inline.

**Input:** `tightened` or `retention_revised` or `draft` (falls back)

**Output:** `ScriptVersion` (written to `annotated_script`) + `list[VisualNote]`

**`VisualNote`:**

| Field | Type | Description |
|-------|------|-------------|
| `beat_name` | `str` | Which beat this note belongs to |
| `line` | `str` | The spoken line |
| `note` | `str \| None` | Visual/production annotation |

---

### Step 10 — `run_qc`

Final quality control pass with checklist and weakest-part analysis.

**Input:** `annotated_script` or `tightened` or `retention_revised` or `draft` (falls back)

**Output:** `QCResult`

| Field | Type | Description |
|-------|------|-------------|
| `checks` | `list[QCCheck]` | Pass/fail checklist items |
| `weakest_parts` | `list[str]` | Identified weak sections |
| `final_script` | `str` | The approved final script text |

**`QCCheck`:**

| Field | Type | Description |
|-------|------|-------------|
| `item` | `str` | Checklist item description |
| `passed` | `bool` | Whether it passed |

## Validation

Each step validates its required inputs at the top of the method. If a required field is `None`, a `ValueError` is raised with a message identifying the step and missing field. The `_require()` helper additionally checks for empty strings.

## Temperature Settings

| Step | Temperature | Rationale |
|------|------------|-----------|
| `define_core_inputs` | 0.3 | Factual extraction |
| `define_angle` | 0.5 | Balanced creativity |
| `choose_structure` | 0.3 | Analytical selection |
| `define_beat_intents` | 0.3 | Analytical mapping |
| `generate_hooks` | 0.7 | High creativity |
| `draft_script` | 0.5 | Balanced writing |
| `add_retention_mechanics` | 0.4 | Moderate creativity |
| `tighten` | 0.3 | Precision editing |
| `add_visual_notes` | 0.3 | Descriptive annotation |
| `run_qc` | 0.2 | Strict evaluation |
