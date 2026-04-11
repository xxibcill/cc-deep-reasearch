# Task 10: Clean Up Content Studio Navigation For Backlog Management

Status: Planned

Phase:
Phase 4 - Hardening And Rollout

Goal:
Make backlog management discoverable and coherent within the content studio navigation, reducing the current mix of query-string tabs and redirect-only subpages.

Primary files:
- `dashboard/src/components/content-gen/content-gen-shell.tsx`
- `dashboard/src/app/content-gen/page.tsx`
- `dashboard/src/app/content-gen/strategy/page.tsx`
- `dashboard/src/app/content-gen/scripts/page.tsx`
- `dashboard/src/app/content-gen/publish/page.tsx`
- `dashboard/src/app/content-gen/backlog/page.tsx`

Scope:
- Decide whether backlog remains a tab-backed route, a dedicated route, or both with canonical redirects.
- Add a visible backlog navigation entry in the shell.
- Reduce user confusion caused by placeholder backlog content on the main overview page.
- Keep existing links stable or redirect them cleanly.

Acceptance criteria:
- Operators can discover backlog management from the primary content-studio navigation.
- There is one clear canonical backlog-management route.
- The overview page no longer suggests that backlog management requires pipeline selection.

Validation:
- Manual navigation pass across content-studio routes.

Out of scope:
- Major visual redesign
- Testing implementation details
