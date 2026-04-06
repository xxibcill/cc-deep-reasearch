# Task 07: Improve The Launch Flow With Presets And Better Progressive Disclosure

## Goal

Make it easier to start research runs quickly without exposing raw advanced controls too early.

## Depends On

- Tasks 01 through 06 complete

## Primary Areas

- `dashboard/src/components/start-research-form.tsx`
- `dashboard/src/app/page.tsx`
- `dashboard/src/types/telemetry.ts`
- `dashboard/src/lib/api.ts` only if request-shape helpers are needed

## Problem To Solve

The launch form is functional, but it still feels like a low-level control panel:

- depth and source settings are understandable
- agent prompt overrides are powerful but too exposed
- there is no faster path for common query types

## Required Changes

1. Introduce a clearer default path for starting research:
   - quick factual check
   - standard research pass
   - deep investigation
2. Keep advanced prompt overrides available, but move them further behind progressive disclosure and clearer framing.
3. Improve form guidance so the user understands what each mode does and when to use it.
4. Consider lightweight preset behavior that pre-fills depth and optional source settings without adding backend complexity.

## Implementation Guidance

- Do not remove existing request fields.
- Keep support for prompt overrides, but treat them as advanced operator tooling.
- Prefer a simple preset model over a large form rewrite.
- Preserve current validation and redirect behavior after run creation.

## Out Of Scope

- persistent saved templates stored on the backend
- expanding agent override support beyond the current backend contract
- content-gen launch flow changes

## Acceptance Criteria

- The common path to start a run is faster and easier to understand.
- Advanced settings remain available but are less intimidating.
- Existing run creation behavior still works.

## Verification

- Manually test quick, standard, and deep launches.
- Test invalid empty query and invalid minimum-source input.
- Confirm prompt override payloads still reach the backend when used.
