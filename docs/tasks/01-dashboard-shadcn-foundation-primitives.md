# 01. Dashboard shadcn Foundation Primitives

Status: Planned

## Goal

Upgrade the shared `dashboard/src/components/ui/` layer so later migrations can use real, reusable primitives instead of custom wrappers and repeated raw controls.

## Scope

- Replace or harden the existing `Select`, `Dialog`, `AlertDialog`, and `Tabs`
- Add missing shared primitives needed across the dashboard
- Preserve the current visual language while improving API consistency and accessibility

## Non-Goals

- Refactoring every page in the same task
- Replacing custom graph internals

## Work

- Audit the current `ui/` directory and identify which files should be replaced by shadcn-generated implementations versus locally maintained wrappers
- Add shared primitives for:
  - `input`
  - `textarea`
  - `label`
  - `checkbox`
  - `table`
  - `alert`
  - `accordion` or `collapsible`
  - `separator`
- Decide whether `Tabs` should keep its current custom API or align to the standard shadcn composition model
- Decide whether the current custom `Select` API should remain as a convenience wrapper on top of the real primitive
- Ensure all primitives use `cn()` and dashboard tokens from `globals.css`

## Acceptance Criteria

- `dashboard/src/components/ui/` contains the primitives required by all follow-on tasks
- New primitives can replace repeated raw HTML without additional ad hoc class bundles
- Keyboard and focus behavior for dialogs and selects is better than the current custom implementations
- Existing imports are not broken without an intentional migration step

## Likely Files

- `dashboard/src/components/ui/button.tsx`
- `dashboard/src/components/ui/card.tsx`
- `dashboard/src/components/ui/select.tsx`
- `dashboard/src/components/ui/dialog.tsx`
- `dashboard/src/components/ui/alert-dialog.tsx`
- `dashboard/src/components/ui/tabs.tsx`
- new files under `dashboard/src/components/ui/`
- `dashboard/src/lib/utils.ts`
- `dashboard/src/app/globals.css`

## Depends On

- None
