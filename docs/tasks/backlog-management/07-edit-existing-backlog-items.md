# Task 07: Add Edit Flow For Existing Backlog Items

Status: Planned

Phase:
Phase 2 - Existing Item Management

Goal:
Let operators edit key metadata on an existing backlog item instead of only changing status.

Primary files:
- `dashboard/src/components/content-gen/backlog-panel.tsx`
- new: `dashboard/src/components/content-gen/backlog-item-form.tsx`
- `dashboard/src/app/content-gen/backlog/page.tsx`

Scope:
- Choose the editable fields for v1, such as `idea`, `category`, `audience`, `problem`, `source_theme`, and `selection_reasoning`.
- Add an edit interaction pattern, likely a dialog or side panel.
- Submit edits through the existing patch endpoint.
- Keep the form schema aligned with the current backlog item model and validation rules.

Acceptance criteria:
- Operators can edit the main operator-managed fields for an existing backlog item.
- Invalid edits surface clear feedback without corrupting page state.
- Saved changes persist through reload.

Validation:
- Manual edit flow for several field combinations, including empty optional fields.

Out of scope:
- Create flow
- Bulk editing
- Advanced validation rules beyond v1 field requirements
