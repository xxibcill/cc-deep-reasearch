# Task 06: Tests And Ship Checklist

## Objective

Verify that the `/content-gen/chat` upgrade is stable, scoped correctly, and does not regress existing backlog workflows.

## Test Areas

### Route rendering

- `/content-gen/chat` renders the new workspace layout
- the page remains usable with an empty backlog
- mobile/stacked behavior does not hide the composer or apply area

### Conversation flow

- sending a message appends transcript entries correctly
- assistant markdown renders as expected
- starter prompts seed the conversation correctly

### Proposal review

- proposed operations render with enriched review details
- single-operation dismissal works if implemented
- full proposal dismissal still works

### Apply flow

- successful apply clears or updates pending review state
- partial apply failures remain visible
- backlog refresh happens after successful apply

### Session recovery

- refresh restores transcript and draft state
- reset clears persisted local session state
- restored proposal state is clearly marked when stale

## Regression Guardrails

Because `/content-gen/chat` still depends on shared backlog chat code, verify:

- `/content-gen/backlog` still works
- existing backlog chat interactions on the backlog page do not break
- shared helpers did not change backlog CRUD behavior

## Likely Test Files

- `dashboard/tests/e2e/backlog-management.spec.ts`
- add a route-specific spec if the current file becomes too crowded

## Ship Checklist

- verify empty, loading, error, and partial-failure states
- verify keyboard submit behavior still works
- verify the route inside the content-gen shell on desktop and small screens
- verify no hidden automatic writes were introduced
- verify proposal review still reflects the actual backend contract

## Advice For The Smaller Coding Agent

- Prefer a targeted route-level spec over adding brittle assertions everywhere.
- If UI structure changes significantly, update selectors to be intentional rather than text-fragile.
- Keep the acceptance bar on operator trust and recoverability, not pixel perfection.
