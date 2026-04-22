# P1-T5 - Deprecate Legacy Orchestrator Path

## Outcome

Normal content-gen execution no longer depends on `legacy_orchestrator.py`, while compatibility imports continue to work.

## Scope

- Update `content_gen/orchestrator.py` to delegate to the new pipeline boundary.
- Keep existing public names available where downstream code imports them.
- Mark legacy-only helpers for deletion or quarantine.
- Remove normal route usage of `ContentGenOrchestrator` where possible.

## Implementation Notes

- Do not remove compatibility paths until import usage is measured.
- Keep deprecation comments precise and temporary.
- Avoid changing public API routes in this task.

## Acceptance Criteria

- New content-gen pipeline runs do not instantiate the legacy orchestrator.
- Compatibility imports still pass.
- Remaining legacy code has a documented removal path.

## Verification

- Run content-gen tests plus import compatibility tests.
