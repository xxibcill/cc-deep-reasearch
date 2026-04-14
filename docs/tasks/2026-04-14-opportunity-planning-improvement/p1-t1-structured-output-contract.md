# Task P1-T1: Structured Output Contract

## Objective

Make the opportunity-planning stage produce a structured output format that is safer to parse and easier to evolve than the current exact-header text contract.

## Scope

- Define a structured output shape for `OpportunityBrief`.
- Support a safe rollout path from the legacy text contract.
- Keep parsing deterministic and failure modes explicit.

## Recommended Implementation

- Prefer JSON output with a tightly scoped schema.
- If migration risk is high, support dual-mode parsing during rollout:
  - structured output first
  - legacy text parsing as fallback
- Record which parse path succeeded in stage trace metadata.

## Acceptance Criteria

- Opportunity planning can parse structured output deterministically.
- Legacy prompt output can still be handled during migration if needed.
- Parse failures include useful diagnostics instead of only generic missing-field errors.

## Advice For The Smaller Coding Agent

- Keep the first structured schema narrow and directly mappable to `OpportunityBrief`.
- Do not expand field count during the same change unless downstream ownership is clear.
