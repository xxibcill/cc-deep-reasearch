"""Prompt templates for the packaging generator stage.

Contract Version: 1.0.0

Parser expectations:
- generate output: Expects "Platform:" header, then per-platform blocks
  with fields: primary_hook, alternate_hooks (list), cover_text, caption,
  keywords (list), hashtags (list), pinned_comment, cta, version_notes

When editing prompts, ensure output format remains compatible with
the parser in agents/packaging.py.
"""

from __future__ import annotations

from cc_deep_research.content_gen.models import (
    AngleOption,
    ScriptVersion,
    StrategyMemory,
)

CONTRACT_VERSION = "1.0.0"

GLOBAL_RULES = """\
You are generating platform packaging for a short-form video inside a modular workflow.

Important:
- Only do the task for this step
- Generate at least 3 hooks per platform
- Usually the hook is a bigger lever than minor script polishing
- Do not wait to think about packaging — it is part of the process
- Each platform may need different tone, length, and CTA"""


PACKAGING_SYSTEM = f"""\
{GLOBAL_RULES}

You are generating publish-ready packaging variants for each platform.

Task:
For each platform, generate a complete packaging set including hooks,
cover text, caption, keywords, hashtags, and pinned comment.

Output format — repeat for each platform:

---
platform: (platform name)
primary_hook: (strongest hook)
alternate_hooks:
- (hook 2)
- (hook 3)
cover_text: (text for thumbnail/cover)
caption: (full caption with line breaks)
keywords:
- (keyword 1)
hashtags:
- (hashtag 1)
pinned_comment: (comment to pin after publishing)
cta: (call to action for this platform)
version_notes: (any platform-specific notes)
---"""


def packaging_user(
    script: ScriptVersion,
    angle: AngleOption,
    platforms: list[str],
    strategy: StrategyMemory,
) -> str:
    parts = [
        f"Platforms: {', '.join(platforms)}",
        f"Core Promise: {angle.core_promise}",
        f"Target Audience: {angle.target_audience}",
        f"Tone: {angle.tone}",
        f"\nScript:\n{script.content}",
    ]
    if strategy.platforms:
        parts.append(f"Active platforms: {', '.join(strategy.platforms)}")
    return "\n".join(parts)
