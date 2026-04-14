# Task P1-T3: Batch Analysis And Enrichment

## Objective

Add the first batch AI behaviors that materially improve superuser throughput on backlog cleanup and preparation.

## Scope

- Detect exact and near-duplicate ideas.
- Cluster backlog items by theme, audience, and problem pattern.
- Identify gaps across category, audience, evidence, and freshness.
- Generate enrichment fields for sparse items, including:
  - `why_now`
  - `potential_hook`
  - `evidence`
  - `proof_gap_note`
  - `genericity_risk`

## Behavior Requirements

- AI should prefer suggesting merges or reframes over silently deleting records.
- Enrichment should target sparse or weak items, not overwrite already-strong operator-authored content by default.
- Dedupe output should include a recommendation reason and a preferred survivor item when relevant.

## Acceptance Criteria

- The system can identify duplicate and weak backlog items in a single triage run.
- Sparse items can be upgraded into production-ready backlog entries through structured proposals.
- Gap analysis produces actionable recommendations that the superuser can review and apply.

## Advice For The Smaller Coding Agent

- Start with heuristic pre-processing and let the LLM refine the editorial recommendation.
- Do not make duplicate detection depend entirely on the model.
- Keep the first enrichment pass focused on fields that already exist in `BacklogItem`.
