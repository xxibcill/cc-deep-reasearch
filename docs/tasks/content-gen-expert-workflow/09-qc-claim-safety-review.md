# Task 09: Strengthen QC Around Unsupported Claims

Goal:
Make the AI-assisted QC gate explicitly check claim safety, unsupported assertions, and legal or trust risks.

Primary files:
- `src/cc_deep_research/content_gen/models.py`
- `src/cc_deep_research/content_gen/prompts/qc.py`
- `src/cc_deep_research/content_gen/agents/qc.py`

Scope:
- Add new QC outputs for unsupported claims, risky claims, and required fact-check items.
- Update the QC prompt to inspect the script against the structured research or argument map summary if available.
- Preserve the rule that AI does not auto-approve publish.

Implementation notes:
- Keep the review operator-friendly.
- Make sure claim-safety findings land in `must_fix_items` when they are severe.
- Avoid duplicating the evaluator's exact scoring shape; QC is a gate, not a scorer.

Acceptance criteria:
- QC output can distinguish clarity problems from claim-safety problems.
- High-risk unsupported claims are surfaced as must-fix items.
- The parser stays aligned with the prompt contract.

Validation:
- Add QC parser tests for claim-safety issue buckets.

Out of scope:
- Publish workflow changes

