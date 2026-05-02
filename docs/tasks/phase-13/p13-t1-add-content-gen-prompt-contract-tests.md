# P13-T1 - Add Content-Gen Prompt Contract Tests

## Functional Feature Outcome

Prompt, parser, and model contract drift is caught by tests before it reaches content-gen runs.

## Why This Task Exists

Content-gen stages depend on natural-language prompts producing structured data that parsers can convert into typed models. The contract registry, prompt modules, and parser functions can currently change independently. That creates a fragile boundary where a prompt update can be valid text but invalid product behavior. Contract tests give this boundary a cheap offline safety net.

## Scope

- Map each content-gen stage contract to its prompt module and parser path.
- Add tests for contract version consistency where prompt modules declare versions.
- Add fixture-based parser tests for representative valid and malformed outputs.
- Assert required output fields from the registry are accepted by the parser and represented in typed models.
- Document the prompt, parser, and contract update workflow.

## Current Friction

- `CONTENT_GEN_STAGE_CONTRACTS` declares expected stage contracts separately from prompt modules.
- Prompt modules can declare their own contract versions.
- Parser functions are spread across content-gen agent modules.
- Strict mypy currently excludes some content-gen contract areas because model contracts are not fully aligned.

## Implementation Notes

- Keep tests deterministic and offline.
- Prefer small representative fixtures over large copied LLM transcripts.
- Do not require every prompt module to expose the exact same structure in this task; document intentional exceptions.
- Start with the highest-risk stages, then extend coverage once the pattern is stable.

## Test Plan

- Add a registry iteration test for stage contract metadata.
- Add version consistency tests for prompt modules that expose `CONTRACT_VERSION`.
- Add parser fixture tests for scripting, research pack, argument map, and backlog outputs.
- Add negative fixtures for missing required fields and malformed structured output.

## Acceptance Criteria

- Prompt contract tests run without live LLM credentials.
- At least the high-risk content-gen stages have parser fixtures.
- Tests fail clearly when a required output field is missing or renamed.
- Documentation tells contributors how to update prompt, parser, and contract registry together.

## Verification Commands

```bash
uv run pytest tests/test_content_gen_contracts.py tests/test_content_gen_agents.py -x
uv run mypy src/cc_deep_research/content_gen/models src/cc_deep_research/content_gen/agents
```

## Risks

- Overly strict fixtures can make useful prompt improvements hard. Validate structure and required semantics, not incidental wording.
- Some existing parsers may accept broad fallback formats. Negative fixtures should target product-breaking omissions, not harmless variation.
