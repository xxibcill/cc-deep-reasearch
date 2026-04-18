"""Prompt templates for the packaging generator stage.

Contract Version: 1.1.0

Parser expectations:
- generate output: Expects repeated `---` blocks with fields:
  platform, primary_hook, alternate_hooks (list), cover_text, caption,
  keywords (list), hashtags (list), pinned_comment, cta, version_notes.
  A block is kept only when `platform`, `primary_hook`, and `caption`
  are present.
- P4-T1: Early packaging signals (target_channel, content_type_hint) added
  to support channel-aware co-design of draft and packaging.

When editing prompts, ensure output format remains compatible with
the parser in agents/packaging.py.
"""

from __future__ import annotations

from cc_deep_research.content_gen.models import (
    AngleOption,
    EarlyPackagingSignals,
    ScriptVersion,
    StrategyMemory,
)

CONTRACT_VERSION = "1.1.0"

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

P4-T1 Channel-Aware Packaging:
- If early packaging signals are provided (Target Channel, Content Type Hint, Format Constraints),
  use those to guide hook selection and caption style
- Match hook energy to the channel (e.g., 'shorts' favors fast hooks, 'feed' allows more nuance)
- Apply content type framing (e.g., 'contrarian' hooks need edge, 'tutorial' hooks need clarity)
- Honor format constraints (e.g., 60s max, vertical only, no product mentions)

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
    early_signals: EarlyPackagingSignals | None = None,
    draft_hooks: list[str] | None = None,
) -> str:
    parts = [
        f"Platforms: {', '.join(platforms)}",
        f"Core Promise: {angle.core_promise}",
        f"Target Audience: {angle.target_audience}",
        f"Tone: {angle.tone}",
    ]

    # P4-T1: Include early packaging signals if available
    if early_signals:
        if early_signals.target_channel:
            parts.append(f"Target Channel: {early_signals.target_channel}")
        if early_signals.content_type:
            parts.append(f"Content Type Hint: {early_signals.content_type}")
        if early_signals.tone_hint:
            parts.append(f"Tone Hint: {early_signals.tone_hint}")
        if early_signals.format_constraints:
            parts.append(f"Format Constraints: {', '.join(early_signals.format_constraints)}")
        if early_signals.cta_hint:
            parts.append(f"CTA Hint: {early_signals.cta_hint}")

    # P4-T1: Include draft hook candidates for packaging selection
    if draft_hooks:
        parts.append("\nDraft Hook Candidates:\n- " + "\n- ".join(draft_hooks))

    parts.append(f"\nScript:\n{script.content}")

    if strategy.platforms:
        parts.append(f"Active platforms: {', '.join(strategy.platforms)}")

    # P3-T1: Platform-specific packaging rules
    if strategy.platform_rules:
        for pr in strategy.platform_rules:
            if pr.guidance:
                parts.append(f"Platform rule [{pr.platform}]: {pr.guidance}")

    # P3-T1: CTA strategy for packaging
    if strategy.cta_strategy:
        if strategy.cta_strategy.allowed_cta_types:
            parts.append(f"Allowed CTA types: {', '.join(strategy.cta_strategy.allowed_cta_types)}")
        if strategy.cta_strategy.default_by_content_goal:
            defaults = [f"{k}: {v}" for k, v in strategy.cta_strategy.default_by_content_goal.items()]
            parts.append(f"CTA defaults by goal: {'; '.join(defaults[:3])}")

    # P3-T1: Performance learnings - hook patterns
    pg = strategy.performance_guidance
    if pg.winning_hooks:
        parts.append(f"\nWinning hook patterns: {'; '.join(pg.winning_hooks[:3])}")
    if pg.failed_hooks:
        parts.append(f"Failed hook patterns to avoid: {'; '.join(pg.failed_hooks[:3])}")
    if pg.platform_guidance:
        for platform_key, hints in list(pg.platform_guidance.items())[:3]:
            parts.append(f"Platform guidance [{platform_key}]: {'; '.join(hints[:2])}")

    return "\n".join(parts)
