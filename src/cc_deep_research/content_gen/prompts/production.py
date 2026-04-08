"""Prompt templates for the production brief stage.

Contract Version: 1.0.0

Parser expectations:
- production output: Expects scalar fields location, setup, wardrobe,
  and backup_plan
- list sections are parsed from "-" or "* " items under:
  props, assets_to_prepare, audio_checks, battery_checks,
  storage_checks, pickup_lines_to_capture
- this parser is intentionally tolerant and returns sparse fields when
  sections are omitted

When editing prompts, ensure output format remains compatible with
the parser in agents/production.py.
"""

from __future__ import annotations

CONTRACT_VERSION = "1.0.0"

PRODUCTION_SYSTEM = """\
You are creating a production brief for a short-form video inside a modular workflow.

Important:
- Only do the task for this step
- Make the brief idiot-proof
- Include every check that prevents production failures
- Be specific about what to prepare

You are creating a production brief so filming is idiot-proof.

Task:
Using the visual plan, generate a complete production brief that prevents
forgotten screenshots, missing close-ups, no screen recordings, lost pickup
lines, or no room tone.

Output format:

location: (where to film)
setup: (camera, lighting, mic setup)
wardrobe: (what to wear)
props:
- (prop 1)
assets_to_prepare:
- (asset 1)
audio_checks:
- (check 1)
battery_checks:
- (check 1)
storage_checks:
- (check 1)
pickup_lines_to_capture:
- (line 1)
backup_plan: (what to do if primary setup fails)"""


def production_user(visual_plan: object) -> str:
    """Build user prompt from a VisualPlanOutput-like object."""
    lines = []
    for bv in getattr(visual_plan, "visual_plan", []):
        lines.append(
            f"- {getattr(bv, 'beat', '')}: {getattr(bv, 'spoken_line', '')} | "
            f"Visual: {getattr(bv, 'visual', '')} | "
            f"Shot: {getattr(bv, 'shot_type', '')} | "
            f"Prop: {getattr(bv, 'prop_or_asset', '')}"
        )
    return "Visual plan:\n" + "\n".join(lines)
