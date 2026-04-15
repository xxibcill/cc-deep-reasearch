# Task P5-T2: Brief To Backlog Apply Flow

## Objective

Turn approved briefs into a deliberate backlog-generation workflow with explicit apply semantics.

## Scope

- Let operators generate backlog candidates from a selected brief revision.
- Show the resulting items as proposals or staging output before persistence.
- Add apply behavior that merges accepted ideas into the persistent backlog safely.
- Preserve trace links from backlog items back to the originating brief revision.

## Acceptance Criteria

- Operators can operationalize an approved brief without rerunning the entire pipeline blindly.
- Backlog persistence remains explicit and reviewable.
- Backlog items can explain which brief revision they came from.

## Advice For The Smaller Coding Agent

- Keep the handoff model explicit. “Generate backlog” and “persist backlog” should not be the same button unless the operator confirmed it.
- Preserve origin metadata compactly so later scoring and analytics can use it.
