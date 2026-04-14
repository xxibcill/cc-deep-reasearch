# Task P2-T1: Next-Action Recommendations

## Objective

Add AI guidance that tells the superuser what should happen next for each backlog item and why.

## Scope

- Introduce recommendation types such as:
  - produce next
  - reframe first
  - gather evidence
  - hold
  - archive
- Surface rationale tied to backlog fields, scoring metadata, and known proof gaps.
- Support both single-item and multi-item recommendation views.

## Behavior Requirements

- Recommendations must stay advisory until the operator applies a resulting change.
- The system should prefer explicit reasons over opaque scores.
- Recommendation output should highlight confidence and key blockers where possible.

## Acceptance Criteria

- A superuser can inspect next-action recommendations directly from backlog management.
- Recommendation explanations reference meaningful item context instead of generic AI prose.
- The output is structured enough to drive later apply flows and automation.

## Status

**Done** — Implemented in:
- `src/cc_deep_research/content_gen/agents/next_action.py` — NextActionAgent with heuristic fallback
- `src/cc_deep_research/content_gen/prompts/next_action.py` — prompt templates
- `src/cc_deep_research/content_gen/router.py` — POST /api/content-gen/backlog-ai/next-action endpoints
- `dashboard/src/components/content-gen/next-action-card.tsx` — recommendation card UI
- `dashboard/src/app/content-gen/backlog/[ideaId]/page.tsx` — embedded in backlog detail page
- `dashboard/src/types/content-gen.ts` + `dashboard/src/lib/content-gen-api.ts` — TypeScript types and API client

## Advice For The Smaller Coding Agent

- Reuse the existing scoring and selection metadata instead of inventing a parallel ranking model.
- Keep confidence signaling simple in the first pass.
- Avoid turning this into a second full scoring pipeline.
