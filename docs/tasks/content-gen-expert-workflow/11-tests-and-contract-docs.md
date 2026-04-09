# Task 11: Finish Contract Docs And Regression Coverage

Status: Done

Goal:
Close the loop on all prompt/parser contract changes and protect the new expert workflow with tests.

Primary files:
- `tests/test_content_gen.py`
- `tests/test_iterative_loop.py`
- `docs/content-generation.md`

Scope:
- Update contract and stage-count tests for the new stage and revised models.
- Add parser coverage for new research, argument-map, evaluator, and QC contracts.
- Update `docs/content-generation.md` so the shipped behavior matches the code.

Implementation notes:
- This task is cleanup after the feature tasks land.
- Do not invent behavior in docs that the code does not implement.
- Prefer focused fixture-style tests over huge end-to-end mocks unless needed.

Acceptance criteria:
- The content-generation doc reflects the new stage flow and new contract shapes.
- Regression tests cover the main failure modes introduced by the expert-workflow changes.
- Stage registry docs and prompt module versions stay consistent.

Validation:
- Run the content-gen test subset after updates.

Out of scope:
- Dashboard UX polish
