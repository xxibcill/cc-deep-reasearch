# Task 017: Reduce Public Package Exports

Status: Planned

## Objective

Shrink the package-root API to the small set of names that should remain stable for external consumers.

## Scope

- audit exports in `cc_deep_research.__init__`
- keep only stable, intentional public symbols
- update internal imports to stop relying on package-root re-exports

## Target Files

- `/Users/jjae/Documents/guthib/cc-deep-research/src/cc_deep_research/__init__.py`
- `/Users/jjae/Documents/guthib/cc-deep-research/src/cc_deep_research/`

## Dependencies

- [007_add_models_compatibility_layer.md](/Users/jjae/Documents/guthib/cc-deep-research/docs/refactor/tasks/007_add_models_compatibility_layer.md)
- [013_slim_orchestrator_facade.md](/Users/jjae/Documents/guthib/cc-deep-research/docs/refactor/tasks/013_slim_orchestrator_facade.md)

## Acceptance Criteria

- the package root exposes an intentional public API instead of a convenience grab bag
- internal modules import from direct boundaries
- external-facing names that remain exported are documented and stable

## Suggested Verification

- run `uv run pytest tests/test_coordination_imports.py tests/test_versioning.py`
