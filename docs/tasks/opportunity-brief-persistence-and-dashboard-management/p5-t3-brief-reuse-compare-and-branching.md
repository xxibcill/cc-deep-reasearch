# Task P5-T3: Brief Reuse, Compare, And Branching

## Objective

Support editorial iteration patterns where operators compare, clone, and branch briefs rather than overwriting a single artifact repeatedly.

## Scope

- Add compare views between revisions or sibling briefs.
- Support clone or branch actions for new themes, channels, or experiments.
- Preserve lineage between source brief and derived brief.
- Define when branching should create a new resource versus a new revision.

## Acceptance Criteria

- Operators can experiment without losing the original brief or muddying its history.
- Derived briefs remain traceable to their source.
- The product has a coherent answer to “revision versus new brief” decisions.

## Advice For The Smaller Coding Agent

- Keep branching semantics simple and operator-visible.
- Favor explicit lineage metadata over inferred relationships from similar text.
