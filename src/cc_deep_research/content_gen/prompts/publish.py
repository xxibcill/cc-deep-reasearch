"""Prompt templates for the publish queue stage."""

from __future__ import annotations

GLOBAL_RULES = """\
You are creating a publish queue entry for a short-form video inside a modular workflow.

Important:
- Only do the task for this step
- Focus on the first-30-minute engagement plan
- Treat publishing as queue management, not a one-off action"""


PUBLISH_SYSTEM = f"""\
{GLOBAL_RULES}

You are creating a publish schedule and engagement plan.

Task:
Generate a first-30-minute engagement plan for the video. This plan covers
what to do immediately after publishing to maximize initial traction.

Output format:

publish_datetime: (suggested ISO 8601 datetime or "optimal" for auto)
first_30_minute_engagement_plan: (specific actions to take in the first 30 minutes)"""


def publish_user(
    platform: str,
    caption: str,
    cta: str,
) -> str:
    return f"Platform: {platform}\nCaption: {caption}\nCTA: {cta}"
