# Task Set Index

This directory holds small, ordered task sets that a smaller agent can execute one at a time.

## Working Rules

- Complete tasks in numeric order unless a task explicitly says it can run in parallel.
- Treat each task as implementation-ready, not just analysis.
- Do not expand scope beyond the files and acceptance criteria listed in the task.
- Preserve existing functionality unless the task explicitly calls for a behavior change.
- Before editing, check for unrelated local changes and avoid reverting user work.

## Task Order

Tasks `01` through `29` are complete and summarized in [`CHANGELOG.md`](../../CHANGELOG.md).

Current pending task set:

- [`80_20_necessary_work_task_set.md`](80_20_necessary_work_task_set.md): ordered maintenance and hardening tasks for the "necessary 80%" side of the project

## Intended Outcome

Each task set should:

- break work into implementation-ready units with clear scope
- make acceptance criteria and validation commands explicit
- let a smaller agent complete one task at a time without broad repo context
