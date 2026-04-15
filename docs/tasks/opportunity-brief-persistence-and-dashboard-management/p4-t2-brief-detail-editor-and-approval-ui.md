# Task P4-T2: Brief Detail Editor And Approval UI

## Objective

Provide a dashboard detail surface where operators can review, revise, compare, and approve a brief intentionally.

## Scope

- Add a detail page showing current brief content, provenance, and revision status.
- Add an editor flow for operator-managed fields and revision notes.
- Add approval, archive, clone, and compare actions where appropriate.
- Make generated versus edited content easy to distinguish.

## Acceptance Criteria

- Operators can revise a generated brief without treating the original output as disposable.
- Approval status and revision history are visible at the point of editing.
- The UI makes it hard to confuse a draft revision with the approved head.

## Advice For The Smaller Coding Agent

- Keep the first editor narrow and auditable. Rich editing can come later.
- Preserve comparison context instead of showing only the latest mutable form.
