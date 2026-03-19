# Task 016: Define Bulk Session Action Contract And Safety Rules

Status: Planned

## Objective

Introduce a typed contract for multi-session destructive actions before adding bulk delete UX, so partial success and safety behavior are explicit.

## Scope

- define bulk request and response models for a bounded set of session ids
- decide how active conflicts, not-found rows, and partial layer failures are reported per session
- define batch-size limits and validation rules to keep accidental large deletes harder
- keep the first bulk action focused on hard delete rather than mixing archive and delete in one endpoint

## Target Files

- `src/cc_deep_research/research_runs/models.py`
- `src/cc_deep_research/web_server.py`
- `dashboard/src/types/telemetry.ts`

## Dependencies

- [010_deletion_safety_and_validation.md](010_deletion_safety_and_validation.md)
- [015_dashboard_active_run_stop_flow.md](015_dashboard_active_run_stop_flow.md)

## Acceptance Criteria

- one response shape exists for bulk delete results with per-session outcomes
- the backend can report partial success without forcing the frontend to infer mixed states from one top-level status code
- safety rules are strict enough to prevent accidental large destructive batches

## Suggested Verification

- add focused model and route serialization coverage in `tests/test_web_server.py`
