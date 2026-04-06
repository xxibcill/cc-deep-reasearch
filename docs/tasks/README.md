# Dashboard Upgrade Task Set

This directory breaks the dashboard upgrade into small, ordered tasks that a smaller agent can execute one at a time.

## Working Rules

- Complete tasks in numeric order unless a task explicitly says it can run in parallel.
- Treat each task as implementation-ready, not just analysis.
- Do not expand scope beyond the files and acceptance criteria listed in the task.
- Preserve existing functionality unless the task explicitly calls for a behavior change.
- Before editing, check for unrelated local changes and avoid reverting user work.

## Task Order

1. [01-dashboard-visual-foundation.md](./01-dashboard-visual-foundation.md)
2. [02-home-control-room.md](./02-home-control-room.md)
3. [03-session-workspace-shell.md](./03-session-workspace-shell.md)
4. [04-session-overview-panel.md](./04-session-overview-panel.md)
5. [05-session-monitor-and-report-panels.md](./05-session-monitor-and-report-panels.md)
6. [06-operator-insights-and-guidance.md](./06-operator-insights-and-guidance.md)
7. [07-launch-flow-presets-and-templates.md](./07-launch-flow-presets-and-templates.md)
8. [08-session-history-triage-and-compare.md](./08-session-history-triage-and-compare.md)
9. [09-regression-tests-and-doc-refresh.md](./09-regression-tests-and-doc-refresh.md)

## Intended Outcome

After all tasks are complete, the dashboard should:

- feel visually consistent across home, session, report, compare, and settings surfaces
- behave like a unified operator workspace instead of several loosely related pages
- make active runs, failures, and completed artifacts easier to triage
- provide higher-level summaries instead of forcing operators into raw telemetry first
- have updated tests and docs that match the new UI structure
