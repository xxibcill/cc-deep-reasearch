# Task 020: Update Refactor Docs

Status: Done

## Objective

Document the new module boundaries and migration path once the refactor lands so contributors stop relying on outdated file-level assumptions.

## Scope

- add a short refactor overview document
- update contributor-facing docs that reference the old CLI, models, telemetry, or dashboard layout
- keep the docs aligned with the code that actually ships

## Target Files

- `/Users/jjae/Documents/guthib/cc-deep-research/docs/README.md`
- `/Users/jjae/Documents/guthib/cc-deep-research/docs/RESEARCH_WORKFLOW.md`
- `/Users/jjae/Documents/guthib/cc-deep-research/docs/USAGE.md`
- `/Users/jjae/Documents/guthib/cc-deep-research/docs/refactor/`

## Dependencies

- [012_extract_operations_commands.md](/Users/jjae/Documents/guthib/cc-deep-research/docs/refactor/tasks/012_extract_operations_commands.md)
- [016_split_telemetry_analytics.md](/Users/jjae/Documents/guthib/cc-deep-research/docs/refactor/tasks/016_split_telemetry_analytics.md)
- [017_reduce_public_package_exports.md](/Users/jjae/Documents/guthib/cc-deep-research/docs/refactor/tasks/017_reduce_public_package_exports.md)
- [019_dashboard_state_and_components.md](/Users/jjae/Documents/guthib/cc-deep-research/docs/refactor/tasks/019_dashboard_state_and_components.md)

## Acceptance Criteria

- contributor docs describe the new boundaries accurately
- the refactor task set has a clear landing point in the docs
- no core doc still points readers at superseded module layouts without explanation

## Suggested Verification

- manually review the updated docs against the final code layout
