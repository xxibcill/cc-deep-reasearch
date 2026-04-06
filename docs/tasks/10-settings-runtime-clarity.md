# Task 10: Clarify Settings And Runtime Override Behavior

## Status

Done

## Goal

Improve the settings experience so operators can quickly understand which values are persisted, which values are overridden at runtime, and which settings will affect future runs.

## Depends On

- Tasks 01 through 09 complete

## Primary Areas

- `dashboard/src/app/settings/page.tsx`
- `dashboard/src/components/config-editor.tsx`
- `dashboard/src/components/config-secrets-panel.tsx`
- `dashboard/src/lib/api.ts`
- `dashboard/src/types/config.ts`
- `docs/DASHBOARD_GUIDE.md` if wording changes materially

## Problem To Solve

The dashboard already exposes persisted and effective config, but the current settings experience is still dense and easy to misread:

- override behavior is technically correct but not obvious
- settings feel like a long form rather than an operator control surface
- secret handling is clear enough for implementation, but not optimized for fast operator understanding

## Required Changes

1. Reorganize settings so related concerns are easier to parse:
   - research defaults
   - execution and output
   - model routing
   - secrets
   - runtime override status
2. Make runtime override impact explicit near the affected fields, not only in a separate summary block.
3. Improve save/reset feedback so operators know whether a change affects:
   - future runs only
   - persisted config only
   - a field that is currently shadowed by an environment variable
4. Make secrets and non-secret settings feel like parts of the same system without weakening secret safety.

## Implementation Guidance

- Preserve the current API contract for config fetch and patch.
- Avoid mixing secret values into normal form state.
- Use clear, concise operator language instead of backend terminology where possible.
- If read-only fields are shown because of overrides, make the reason and the effective value easy to understand.

## Out Of Scope

- changing backend config precedence rules
- adding new config fields
- secret export/import features

## Acceptance Criteria

- Operators can tell which settings are editable, which are overridden, and when changes take effect.
- Save/reset flows remain safe and predictable.
- Settings page styling matches the rest of the dashboard.

## Verification

- Test overridden and non-overridden config states.
- Test save success, validation failure, and reset behavior.
- Confirm secret replace and clear flows still work.
