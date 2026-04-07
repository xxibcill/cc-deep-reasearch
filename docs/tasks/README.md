# Dashboard Upgrade Task Set

This directory breaks the dashboard upgrade into small, ordered tasks that a smaller agent can execute one at a time.

## Working Rules

- Complete tasks in numeric order unless a task explicitly says it can run in parallel.
- Treat each task as implementation-ready, not just analysis.
- Do not expand scope beyond the files and acceptance criteria listed in the task.
- Preserve existing functionality unless the task explicitly calls for a behavior change.
- Before editing, check for unrelated local changes and avoid reverting user work.

## Task Order

Tasks `01` through `19` are complete and summarized in [`CHANGELOG.md`](../../CHANGELOG.md).

The next planned dashboard task number is `20`.

## Intended Outcome

After all tasks are complete, the dashboard should:

- feel visually consistent across home, session, report, compare, and settings surfaces
- behave like a unified operator workspace instead of several loosely related pages
- make active runs, failures, and completed artifacts easier to triage
- provide higher-level summaries instead of forcing operators into raw telemetry first
- support repeatable operator workflows through saved views, resilient live monitoring, and better cross-session analysis
- connect research sessions more clearly to downstream publishing and content-generation work
- expose bundles, artifacts, benchmarks, and historical analytics as first-class operator tools
- become easier to learn and faster to operate through keyboard workflows and contextual help
- have updated tests and docs that match the new UI structure
