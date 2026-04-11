# Task 08: Upgrade Quality Evaluation For Expert Content

Goal:
Change iterative evaluation from generic content scoring to expert-content scoring.

Primary files:
- `src/cc_deep_research/content_gen/models.py`
- `src/cc_deep_research/content_gen/prompts/quality_evaluator.py`
- `src/cc_deep_research/content_gen/agents/quality_evaluator.py`
- `src/cc_deep_research/content_gen/iterative_loop.py`
- `src/cc_deep_research/content_gen/orchestrator.py`

Scope:
- Add metrics such as `evidence_coverage`, `claim_safety`, `originality`, `precision`, and `expertise_density`.
- Update the prompt and parser to emit those metrics.
- Adjust stop conditions or threshold handling if necessary so unsupported claims can block convergence.
- Ensure previous-feedback handling still works with the expanded evaluation shape.

Implementation notes:
- Keep backward compatibility only if it is cheap; otherwise make the contract change explicit.
- The evaluator should distinguish unsupported claims from mere style weaknesses.
- Favor actionable feedback over vague criticism.

Acceptance criteria:
- `QualityEvaluation` carries expert-quality signals, not only generic writing signals.
- The parser fails predictably or defaults safely for malformed numeric fields.
- Iteration feedback clearly tells the producer what evidence or claim issues must change.

Validation:
- Add parser tests and loop-behavior tests for the new metrics.

Out of scope:
- Human QC prompt changes

