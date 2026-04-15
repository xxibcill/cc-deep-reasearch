# Task P2-T2: Approved Brief Execution Gates

## Objective

Make downstream execution intentionally aware of whether a brief is draft, edited, or approved.

## Scope

- Define which flows can proceed from an unapproved brief and which should require approval.
- Add policy points for backlog generation, scoring, and deeper execution stages.
- Surface clear operator-visible errors or warnings when a run starts from the wrong brief state.
- Decide how CLI and dashboard flows configure or bypass the gate.

## Acceptance Criteria

- The system can enforce approval requirements where the product needs them.
- Operators can tell when downstream work used a draft versus an approved brief.
- Gate behavior is explicit and configurable enough for rollout without hidden surprises.

## Advice For The Smaller Coding Agent

- Default to clarity over flexibility. A small number of clear policy modes is better than stage-by-stage ad hoc flags.
- Keep approval semantics visible in saved traces and run summaries.
