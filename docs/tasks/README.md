# Dashboard Upgrade Task Set

This directory breaks the dashboard upgrade into small, ordered tasks that a smaller agent can execute one at a time.

## Working Rules

- Complete tasks in numeric order unless a task explicitly says it can run in parallel.
- Treat each task as implementation-ready, not just analysis.
- Do not expand scope beyond the files and acceptance criteria listed in the task.
- Preserve existing functionality unless the task explicitly calls for a behavior change.
- Before editing, check for unrelated local changes and avoid reverting user work.

## Task Order

Tasks `01` through `10` are complete and summarized in [`CHANGELOG.md`](../../CHANGELOG.md).

1. [11-search-cache-operations.md](./11-search-cache-operations.md)
2. [12-saved-filters-and-views.md](./12-saved-filters-and-views.md)
3. [13-live-run-stream-resilience.md](./13-live-run-stream-resilience.md)
4. [14-telemetry-performance-at-scale.md](./14-telemetry-performance-at-scale.md)
5. [15-decision-graph-usability.md](./15-decision-graph-usability.md)
6. [16-cross-session-analysis.md](./16-cross-session-analysis.md)
7. [17-notifications-and-completion-feedback.md](./17-notifications-and-completion-feedback.md)
8. [18-research-to-content-studio-bridge.md](./18-research-to-content-studio-bridge.md)
9. [19-design-system-extraction-and-hardening.md](./19-design-system-extraction-and-hardening.md)

## Intended Outcome

After all tasks are complete, the dashboard should:

- feel visually consistent across home, session, report, compare, and settings surfaces
- behave like a unified operator workspace instead of several loosely related pages
- make active runs, failures, and completed artifacts easier to triage
- provide higher-level summaries instead of forcing operators into raw telemetry first
- support repeatable operator workflows through saved views, resilient live monitoring, and better cross-session analysis
- connect research sessions more clearly to downstream publishing and content-generation work
- have updated tests and docs that match the new UI structure
