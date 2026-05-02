# Phase 13 - Content-Gen Prompt Contract Hardening

## Functional Feature Outcome

Content-gen prompt modules, contract registry entries, parsers, and typed output models stay in sync through executable contract tests.

## Why This Phase Exists

Content-gen agents depend on a chain of prompt text, declared contract versions, parser behavior, and typed models. Those pieces are spread across prompt modules, model contracts, and agent parsers, and the strict mypy configuration already calls out content-gen contracts as an area with known friction. This phase makes prompt and parser contracts explicit enough that a prompt change cannot silently drift away from parser or model expectations.

## Scope

- Inventory content-gen stage contracts, prompt contract versions, parsers, and output models.
- Add registry-driven tests that validate prompt versions and required output fields.
- Add parser fixtures for representative valid and invalid outputs.
- Document how prompt, parser, and contract changes should be made together.

## Tasks

| Task | Summary |
| --- | --- |
| [P13-T1](../tasks/phase-13/p13-t1-add-content-gen-prompt-contract-tests.md) | Add executable contract tests that keep content-gen prompts, parsers, and output models aligned. |

## Dependencies

- Existing content-gen contracts should remain the source of truth for stage output expectations.
- LLM calls must not be required for contract tests.
- Prompt changes should remain compatible with current agent behavior unless intentionally migrated.

## Exit Criteria

- Contract tests fail when a stage prompt version, registry contract, parser, or required output field drifts.
- Representative parser fixtures exist for high-risk content-gen stages.
- Contract documentation explains the expected update path for prompt and parser changes.
- The offline test suite can validate contract compatibility without provider credentials.
