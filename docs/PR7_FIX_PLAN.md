# PR 7 Fix Plan

## Context

PR `#7` (`ab62ed1`, title `feat(dashboard): Session & dashboard infrastructure`) does not currently build against `origin/main`.

I validated that in an isolated worktree with:

```bash
git fetch origin pull/7/head:refs/remotes/origin/pr-7
git worktree add /tmp/ccdr-pr7-review origin/pr-7
cd /tmp/ccdr-pr7-review/dashboard
npm exec tsc --noEmit
```

That typecheck fails immediately with missing-module errors and component/type contract mismatches.

## Short Version

There are two separate problems:

1. The PR imports code from other dashboard branches that are not part of PR 7.
2. The PR also updates local call sites to newer component/type APIs that do not exist on the PR 7 branch.

As written, PR 7 is neither standalone nor correctly stacked.

## What Is Missing

These imports are referenced by PR 7 but are not present in the PR 7 tree:

| Referenced from | Missing module | Present on branch |
| --- | --- | --- |
| `dashboard/src/app/page.tsx` | `@/components/ui/help-callout` | `origin/pr-d1-ui-components` |
| `dashboard/src/app/page.tsx` | `@/components/ui/metric-card` | `origin/pr-d1-ui-components` |
| `dashboard/src/app/page.tsx` | `@/components/research-content-actions` | `origin/pr-d4-content-gen-compare` |
| `dashboard/src/app/page.tsx` | `@/lib/research-content-bridge` | `origin/pr-d4-content-gen-compare` |
| `dashboard/src/components/app-shell.tsx` | `@/components/ui/nav-bar` | `origin/pr-d1-ui-components` |
| `dashboard/src/components/app-shell.tsx` | `@/components/ui/notification-center` | `origin/pr-d1-ui-components` |
| `dashboard/src/components/saved-view-controls.tsx` | `@/components/ui/input` | `origin/pr-d1-ui-components` |
| `dashboard/src/components/trace-bundle-export-dialog.tsx` | `@/components/ui/checkbox` | `origin/pr-d1-ui-components` |
| `dashboard/src/components/trace-bundle-export-dialog.tsx` | `@/components/ui/notification-center` | `origin/pr-d1-ui-components` |
| `dashboard/tests/e2e/app.spec.ts` | `./dashboard-mocks` | `origin/pr-d4-content-gen-compare` |
| `dashboard/tests/e2e/app.spec.ts` | `./scenarios` | `origin/pr-d4-content-gen-compare` |
| `dashboard/tests/e2e/app.spec.ts` | `./test-fixtures` | `origin/pr-d5-session-components` |

There is no single existing remote branch in this repo that contains all of those dependencies together.

## What Is Mismatched

PR 7 also assumes newer local APIs than the branch actually has.

### Type and store mismatches

- `dashboard/src/hooks/useDashboard.ts` imports `LiveStreamStatus`, but PR 7's `dashboard/src/types/telemetry.ts` does not export that type.
- `dashboard/src/hooks/useDashboard.ts` and `dashboard/src/lib/saved-views.ts` use `SessionListQueryState.archivedOnly`, but PR 7's `SessionListQueryState` only has `search`, `status`, and `activeOnly`.

Those newer contracts do exist on `origin/pr-d3-telemetry-enhancements`.

### Session page/component mismatches

- `dashboard/src/app/session/[id]/monitor/page.tsx` passes `runStatus` and `sessionSummary` into `SessionTelemetryWorkspace`, but the PR 7 version of that component only accepts `{ sessionId: string }`.
- `dashboard/src/app/session/[id]/page.tsx` imports `SessionOverview`, but PR 7's `dashboard/src/components/session-static-details.tsx` does not export it.
- `dashboard/src/app/session/[id]/report/page.tsx` passes `sessionSummary` into `SessionReport`, but the PR 7 version does not accept that prop.

Those newer contracts exist on later branches:

- `LiveStreamStatus` and the expanded telemetry workspace contract exist on `origin/pr-d3-telemetry-enhancements`.
- `SessionOverview` and the expanded `SessionReport` contract exist on `origin/pr-d5-session-components`.

### UI primitive mismatches

PR 7 uses richer component APIs than its own branch contains:

- `dashboard/src/app/page.tsx` uses `<Badge variant="info">`, but PR 7's `Badge` only supports `default`, `secondary`, `success`, `warning`, `destructive`, and `outline`.
- `dashboard/src/components/saved-view-controls.tsx` passes `emptyLabel` and `testId` into `Select`, but PR 7's `Select` does not support those props.
- `dashboard/src/components/trace-bundle-export-dialog.tsx` imports `buttonVariants`, but PR 7's `Button` module does not export it.
- `dashboard/src/components/trace-bundle-export-dialog.tsx` imports `DialogBody`, `DialogDescription`, `DialogFooter`, `DialogHeader`, `DialogTitle`, and `DialogContent`, but PR 7's `Dialog` component is a single wrapper with a required `title` prop and none of those subcomponents.
- `dashboard/src/components/trace-bundle-export-dialog.tsx` calls `getSessionBundle(sessionId, options)`, but PR 7's `getSessionBundle` only accepts `sessionId`.

Those richer UI and API contracts exist on `origin/pr-d5-session-components`.

## Recommended Fix Strategy

### Preferred: make PR 7 standalone against `main`

If PR 7 is supposed to merge into `main`, this is the cleaner path.

Keep only the changes that can compile on top of `main`, and remove the parts that depend on later dashboard PRs.

### Alternative: intentionally restack PR 7

If the implementation in PR 7 is intentionally written against newer dashboard branches, do not merge it into `main` as PR 7.

Instead:

1. Create a new integration branch.
2. Bring in the exact dependencies from `pr-d1`, `pr-d3`, `pr-d4`, and `pr-d5`.
3. Rebase or cherry-pick `ab62ed1` on top of that integration branch.
4. Open a replacement PR against the correct base.

Because there is no single upstream branch that already contains all required dependencies, this is a multi-branch integration task, not a small fix.

## Detailed Fix Plan If PR 7 Must Stay Based On `main`

### 1. Fix `dashboard/src/app/page.tsx`

Current issue:

- The page imports UI and content-bridge modules that do not exist on PR 7.
- It also uses the `info` badge variant that PR 7's `Badge` does not support.

Fix:

1. Remove `HelpCallout`, `OnboardingCard`, `MetricCard`, `ResearchContentActions`, and `buildResearchContentBridgePayloadFromSession`.
2. Revert the page to a layout that only uses components already present on `main` or add those dependencies in this PR.
3. Replace `variant="info"` with an existing variant if you keep the badge, or expand `Badge` in the same PR.

Recommended scope decision:

- If this PR is about session/dashboard infrastructure, the fastest fix is to keep the home page simple and avoid borrowing future compare/content-gen UI.

### 2. Fix `dashboard/src/components/app-shell.tsx`

Current issue:

- It depends on `NavBar` and `NotificationProvider`, neither of which exists on PR 7.

Fix:

Choose one:

1. Remove `AppShell` entirely from this PR and keep the existing layout behavior.
2. Inline a minimal shell that uses only components already present on `main`.
3. Explicitly copy the needed primitives from `origin/pr-d1-ui-components` into this PR.

If you copy from `pr-d1`, bring in at least:

- `dashboard/src/components/ui/nav-bar.tsx`
- `dashboard/src/components/ui/notification-center.tsx`

### 3. Fix `dashboard/src/hooks/useDashboard.ts`

Current issue:

- It references `LiveStreamStatus`.
- It adds `archivedOnly` to `SessionListQueryState`.
- It adds buffering/status behavior that requires matching type updates elsewhere.

Fix:

Choose one path:

1. Revert the `LiveStreamStatus` and `archivedOnly` changes so the store matches the current `types/telemetry.ts`.
2. Or bring over the matching type and websocket changes from `origin/pr-d3-telemetry-enhancements`.

If you keep the new live-stream model, you must also update:

- `dashboard/src/types/telemetry.ts`
- `dashboard/src/lib/websocket.ts`
- Any telemetry components consuming the new status shape

Do not keep `useDashboard.ts` halfway migrated. That is what causes the current compile break.

### 4. Fix `dashboard/src/lib/saved-views.ts`

Current issue:

- It assumes `archivedOnly` exists in `SessionListQueryState`.
- `areSessionListQueriesEqual` ignores `archivedOnly`, which is a logic bug even after the type issue is fixed.

Fix:

If you keep archived filtering:

```ts
export function areSessionListQueriesEqual(
  left: SessionListQueryState,
  right: SessionListQueryState
): boolean {
  return (
    left.search === right.search &&
    left.status === right.status &&
    left.activeOnly === right.activeOnly &&
    left.archivedOnly === right.archivedOnly
  );
}
```

If you do not keep archived filtering in PR 7:

- Remove `archivedOnly` from the saved-view sanitizer and equality logic.

### 5. Fix the session route pages

Files:

- `dashboard/src/app/session/[id]/monitor/page.tsx`
- `dashboard/src/app/session/[id]/page.tsx`
- `dashboard/src/app/session/[id]/report/page.tsx`

Current issue:

- These pages were updated to call newer component APIs, but the components in PR 7 are still older versions.

Fix:

Use one consistent version of each component.

If staying on `main`, the minimal fix is:

1. `monitor/page.tsx`: pass only `sessionId` into `SessionTelemetryWorkspace`.
2. `page.tsx`: import and render the existing export from `session-static-details.tsx`, not `SessionOverview`.
3. `report/page.tsx`: pass only the props supported by the current `SessionReport` component.

If you want the richer session pages:

- Bring over the matching component implementations from `origin/pr-d3-telemetry-enhancements` and `origin/pr-d5-session-components`.

### 6. Fix `dashboard/src/components/saved-view-controls.tsx`

Current issue:

- It imports `Input`, which is missing.
- It uses a newer `Select` API (`emptyLabel`, `testId`) than PR 7 contains.
- It has implicit `any` event parameters under `strict` mode.

Fix:

Choose one:

1. Replace `Input` with a plain `<input>` and adapt to the current `Select` API.
2. Or copy `Input` from `origin/pr-d1-ui-components` and copy the richer `Select` implementation from `origin/pr-d5-session-components`.

Also fix event typing explicitly:

```ts
onChange={(event: React.ChangeEvent<HTMLInputElement>) => setDraftName(event.target.value)}
```

### 7. Fix `dashboard/src/components/trace-bundle-export-dialog.tsx`

Current issue:

- It is written against future `Button`, `Checkbox`, `Dialog`, `NotificationProvider`, and `getSessionBundle` APIs.
- `buttonVariants` is imported but not used.

Fix:

If staying on `main`, simplify the component to current branch contracts:

1. Remove the `buttonVariants` import.
2. Replace `Checkbox` with a native `<input type="checkbox">` or add the checkbox component from `pr-d1`.
3. Rewrite the dialog markup to use the current `Dialog` wrapper API:
   - Pass `title`
   - Render body content directly inside `Dialog`
   - Do not import subcomponents that do not exist
4. Change `getSessionBundle(sessionId, options)` to match the current API, or upgrade `lib/api.ts` in the same PR.

If you want the richer dialog as written, copy the matching implementations from `origin/pr-d5-session-components`:

- `dashboard/src/components/ui/button.tsx`
- `dashboard/src/components/ui/dialog.tsx`
- `dashboard/src/lib/api.ts`

### 8. Fix `dashboard/src/app/layout.tsx`

Current issue:

- The metadata was changed to "Content Studio", which does not match what this PR actually contains.

Fix:

- Restore dashboard-focused metadata unless this PR is deliberately rebranding the entire dashboard.

This is not a compile blocker, but it is misleading and will confuse smoke tests and document titles.

### 9. Fix the E2E tests

Current issue:

- `dashboard/tests/e2e/app.spec.ts` imports helper modules that are not in PR 7.

Fix:

Choose one:

1. Remove or reduce those new tests so they only use helpers already present on `main`.
2. Or copy the required test helpers:
   - `dashboard/tests/e2e/dashboard-mocks.ts` from `origin/pr-d4-content-gen-compare`
   - `dashboard/tests/e2e/scenarios.ts` from `origin/pr-d4-content-gen-compare`
   - `dashboard/tests/e2e/test-fixtures.ts` from `origin/pr-d5-session-components`

If you keep those tests, verify they still match the final UI after you trim or restack the feature work.

## Detailed Fix Plan If You Want To Keep The Implementation Mostly As Written

This path means PR 7 should stop pretending to be a standalone PR against `main`.

### Dependency map

Bring in these dependency groups first:

| Dependency branch | Needed for |
| --- | --- |
| `origin/pr-d1-ui-components` | `help-callout`, `metric-card`, `nav-bar`, `notification-center`, `input`, `checkbox` |
| `origin/pr-d3-telemetry-enhancements` | `LiveStreamStatus`, `archivedOnly` session query type, telemetry workspace/live stream contracts |
| `origin/pr-d4-content-gen-compare` | `research-content-actions`, `research-content-bridge`, `dashboard-mocks`, `scenarios` |
| `origin/pr-d5-session-components` | `SessionOverview`, richer `SessionReport`, richer `Button`, `Dialog`, `Select`, `test-fixtures`, newer badge variant support |

### Practical sequence

1. Create a temporary integration branch.
2. Copy or cherry-pick the exact dependency files from those branches.
3. Reapply PR 7 on top.
4. Re-run typecheck.
5. Re-run focused tests.

Example starting point:

```bash
git fetch origin
git checkout -b codex/pr7-integration origin/main
```

Then either cherry-pick commits if the branch history is clean enough, or copy file sets directly with non-interactive checkout commands, for example:

```bash
git checkout origin/pr-d1-ui-components -- dashboard/src/components/ui/help-callout.tsx
git checkout origin/pr-d1-ui-components -- dashboard/src/components/ui/metric-card.tsx
git checkout origin/pr-d1-ui-components -- dashboard/src/components/ui/nav-bar.tsx
git checkout origin/pr-d1-ui-components -- dashboard/src/components/ui/notification-center.tsx
```

Do the same for the `pr-d3`, `pr-d4`, and `pr-d5` dependencies listed above, then apply the PR 7 changes and resolve conflicts.

## Validation Checklist

Before reopening or updating the PR, all of these should pass:

```bash
cd dashboard
npm exec tsc --noEmit
npm run lint
npm run test:e2e -- --grep "home page|keyboard shortcuts|session workspace|saved views|trace bundle"
```

If the PR is trimmed back to infrastructure-only scope, also remove tests that cover features intentionally deferred to later PRs.

## Recommended Outcome

The safest outcome is:

1. Keep PR 7 narrowly scoped to infrastructure that can stand on `main`.
2. Remove imports and UI upgrades borrowed from `pr-d1`, `pr-d3`, `pr-d4`, and `pr-d5`.
3. Fix the saved-view equality bug.
4. Reintroduce the richer home page, telemetry UX, compare hooks, and dialog primitives only in the PRs that actually own those dependencies.

If the goal is to ship the richer experience immediately, replace PR 7 with a deliberately stacked integration PR instead of trying to force this branch into `main`.
