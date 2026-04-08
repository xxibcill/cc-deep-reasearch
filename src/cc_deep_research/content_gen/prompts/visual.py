"""Prompt templates for the visual translation stage.

Contract Version: 1.0.0

Parser expectations:
- translate output: Uses `---` as block delimiter for each beat,
  expects fields: beat, spoken_line, visual, shot_type, a_roll, b_roll,
  on_screen_text, overlay_or_graphic, prop_or_asset, transition,
  retention_function
  The parser keeps a block only when it includes both `beat` and `visual`,
  and it also requires a trailing "visual_refresh_check:" field.

When editing prompts, ensure output format remains compatible with
the parser in agents/visual.py.
"""

from __future__ import annotations

from cc_deep_research.content_gen.models import ScriptStructure, ScriptVersion

CONTRACT_VERSION = "1.0.0"

GLOBAL_RULES = """\
You are creating a visual plan for a short-form video inside a modular workflow.

Important:
- Only do the task for this step
- Every 1-3 beats must include a meaningful visual change
- Use A-roll, B-roll, text, overlays, graphics, props, or screen recordings intentionally
- No random visual noise — useful motion only
- Visual changes should serve retention, not decoration"""


VISUAL_SYSTEM = f"""\
{GLOBAL_RULES}

You are translating a short-form video script into a full visual plan.

Task:
For each beat in the script, define the visual treatment. Every 1-3 beats
must include at least one meaningful visual change: punch-in, angle change,
cutaway, screen recording, text emphasis, graphic, or result shot.

Output format — repeat for each beat:

---
beat: (beat name)
spoken_line: (the exact line spoken)
visual: (what the viewer sees)
shot_type: (wide | medium | close-up | punch-in | screen-recording | cutaway)
a_roll: (what the presenter does)
b_roll: (supplementary footage)
on_screen_text: (text overlay if any)
overlay_or_graphic: (graphic element if any)
prop_or_asset: (physical prop or digital asset needed)
transition: (how this beat transitions to the next)
retention_function: (what this visual change does for viewer retention)
---

End with:
visual_refresh_check: pass | fail
(Explain if fail)"""


def visual_user(
    script: ScriptVersion,
    structure: ScriptStructure,
) -> str:
    beats = "\n".join(f"- {b}" for b in structure.beat_list)
    return f"Script:\n{script.content}\n\nBeat List:\n{beats}"
