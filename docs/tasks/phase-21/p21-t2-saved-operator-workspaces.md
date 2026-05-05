# P21-T2: Saved Operator Workspaces

## Summary

Let operators save and restore useful dashboard workspace state across session list, monitor, and compare workflows.

## Details

1. Define workspace state for each supported view:
   - session list filters and saved views
   - monitor filters, selected view mode, detail tab, and graph filters
   - compare run selections and comparison settings
2. Reuse existing saved-view helpers where they fit.
3. Persist workspace state in local storage first unless server-side sharing is explicitly required.
4. Add import/export behavior for workspace definitions if useful for debug handoff.
5. Guard against stale session IDs and incompatible saved state versions.
6. Add tests for save, restore, delete, stale-state cleanup, and version migration.

## Acceptance Criteria

- Operators can save and restore named workspaces for high-value views.
- Stale sessions or invalid filters do not break workspace restore.
- Saved workspace schemas are versioned.
- Existing saved session-list views continue to work.
- Tests cover persistence, restore, delete, and migration behavior.
