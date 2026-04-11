# Task 09: Add Backlog Item Create UI Flow

Status: Done

Phase:
Phase 3 - Full CRUD Create Flow

Goal:
Expose a clear operator flow for creating new backlog items from the dedicated backlog-management page.

Primary files:
- `dashboard/src/app/content-gen/backlog/page.tsx`
- new: `dashboard/src/components/content-gen/backlog-item-form.tsx`
- `dashboard/src/lib/content-gen-api.ts`
- `dashboard/src/hooks/useContentGen.ts`

Scope:
- Add a `New item` action on the backlog page.
- Reuse the backlog item form pattern for create and edit if practical.
- Validate the minimum required fields before submit.
- Insert the created item into the visible backlog state after success.
- Keep the UX lightweight enough for frequent editorial use.

Acceptance criteria:
- Operators can create a backlog item entirely from the dashboard.
- Successful creation updates the list immediately and persists through reload.
- Validation and API failures surface clear, local feedback.

Validation:
- Manual create flow with both valid and invalid inputs.

Out of scope:
- Bulk create
- CSV import
- AI-assisted item drafting
