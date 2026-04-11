# Phase 2: Existing Item Management

Status: Planned

Functional feature:
Operators can manage existing backlog entries from the dedicated backlog page using update, select, archive, and delete actions.

Why this phase exists:
- The backend already exposes most non-create mutation endpoints.
- The dashboard component already has action affordances, but they are not wired to real state or API calls.
- Shipping management of existing items first delivers immediate operational value without waiting for create support.

Tasks in this phase:
1. `06-wire-existing-item-actions.md`
2. `07-edit-existing-backlog-items.md`

Exit criteria:
- Row actions call real APIs and update page state correctly.
- Operators can change status, mark an item selected, archive it, and delete it.
- Operators can edit important item metadata without opening raw YAML.
