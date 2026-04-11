# Task 12: Fix Pipeline Resume And Direct-Idea Workflow

Status: Done

Goal:
Clean up the workflow mechanics that currently make the full pipeline awkward to operate.

Primary files:
- `src/cc_deep_research/content_gen/cli.py`
- `src/cc_deep_research/content_gen/orchestrator.py`

Scope:
- Make `pipeline --from-file` actually load a saved `PipelineContext`.
- Make `pipeline --idea` skip backlog generation and seed the downstream stages directly.
- Ensure later-stage resume uses prior context instead of constructing a blank context.

Implementation notes:
- Keep CLI behavior explicit and unsurprising.
- Avoid large refactors if a small load-and-resume path solves it.
- Preserve existing progress output where possible.

Acceptance criteria:
- Resume from saved pipeline context works for later stages.
- Direct-idea mode behaves like a true bypass, not just an alternate theme string.
- Error messages are clear when required prior context is missing.

Validation:
- Add CLI tests that cover `--from-file` and `--idea`.

Out of scope:
- Multi-lane fanout
- Dashboard changes
